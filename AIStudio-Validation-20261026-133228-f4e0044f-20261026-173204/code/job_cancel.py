"""Per-job cancellation: cooperative Python, owned Blender processes, targeted Comfy prompts."""
import ast,contextlib,http.client,json,os,secrets,socket,subprocess,sys,threading,time,traceback,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock();LOCAL=threading.local();ACTIVE={};INSTALLED=False
class JobCancelled(BaseException):pass

def read(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except Exception:return {}
def comfy_http(route,body=None,timeout=8):
 settings=read(ROOT/'hunyuan_settings.json');url=settings.get('comfy_url','http://127.0.0.1:8188').rstrip('/')+route
 request=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=timeout) as response:
  data=response.read();return json.loads(data) if data else {}
def client_matches(item,job_id):
 return isinstance(item,(list,tuple)) and len(item)>3 and isinstance(item[3],dict) and item[3].get('client_id')=='portal-'+job_id

_TARGETED=None
def targeted_interrupt_supported():
 global _TARGETED
 if _TARGETED is None:
  _TARGETED=False
  try:
   root=Path(read(ROOT/'hunyuan_settings.json')['comfy_root'])
   if (root/'ComfyUI'/'server.py').is_file():root=root/'ComfyUI'
   tree=ast.parse((root/'server.py').read_text(encoding='utf-8-sig'))
   for fn in ast.walk(tree):
    if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)) and fn.name=='post_interrupt':_TARGETED=any(isinstance(n,ast.Constant) and n.value=='prompt_id' for n in ast.walk(fn))
  except Exception:pass
 return _TARGETED

def stop_comfy(ctx):
 """Never clear a shared queue or call untargeted interrupt."""
 ids=set()
 for path in ctx.job.glob('attempt_*/comfy_*.json'):
  value=read(path).get('prompt_id')
  if value:ids.add(str(value))
 queue=comfy_http('/queue');running=queue.get('queue_running',[]);pending=queue.get('queue_pending',[])
 ids.update(str(item[1]) for item in running+pending if client_matches(item,ctx.job.name))
 owned_pending=[str(item[1]) for item in pending if len(item)>1 and str(item[1]) in ids]
 owned_running=[str(item[1]) for item in running if len(item)>1 and str(item[1]) in ids]
 if owned_pending:comfy_http('/queue',{'delete':owned_pending})
 targeted=targeted_interrupt_supported()
 if targeted:
  for prompt in owned_running:comfy_http('/interrupt',{'prompt_id':prompt})
 return owned_running

class Context:
 def __init__(self,job):self.job=Path(job);self.event=threading.Event();self.connections=[];self.children=[]
 def close_connections(self):
  for connection in list(self.connections):
   sock=getattr(connection,'sock',None)
   if sock is not None:
    try:sock.shutdown(socket.SHUT_RDWR)
    except Exception:pass
    try:sock.close()
    except Exception:pass
 def kill_blender(self):
  for process in list(self.children):
   if process.poll() is not None:continue
   try:
    if os.name=='nt':_ORIGINAL_POPEN(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000).wait(timeout=20)
    else:process.kill()
   except Exception:
    try:process.kill()
    except Exception:pass
 def trace(self,frame,event,arg):
  filename=frame.f_code.co_filename
  if not str(filename).startswith(str(ROOT)) or Path(filename).name in {'job_cancel.py','ai_service_manager.py'}:return None
  if event=='line' and self.event.is_set():raise JobCancelled()
  return self.trace

_ORIGINAL_POPEN=subprocess.Popen

def install(namespace):
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 base_status=namespace['status'];previous_handler=namespace['Handler']
 def guarded_status(job,state,**extra):
  with LOCK:
   ctx=ACTIVE.get(Path(job).name)
   if ctx and ctx.event.is_set() and getattr(LOCAL,'ctx',None) is ctx:raise JobCancelled()
   if state!='INTERRUPTED':extra.setdefault('cancelled',False)
   return base_status(job,state,**extra)
 namespace['status']=guarded_status
 import hunyuan_bridge
 hunyuan_bridge.CONTEXT['status']=guarded_status
 # No global termination of Python, llama.cpp, ComfyUI or unrelated Blender sessions.
 class ManagedPopen(_ORIGINAL_POPEN):
  def __init__(self,args,*a,**kw):
   super().__init__(args,*a,**kw)
   ctx=getattr(LOCAL,'ctx',None)
   executable=args[0] if isinstance(args,(list,tuple)) and args else ''
   configured=read(ROOT/'config.json').get('blender_exe','')
   if ctx and executable and (Path(str(executable)).name.lower() in {'blender','blender.exe'} or (configured and os.path.normcase(str(executable))==os.path.normcase(configured))):
    ctx.children.append(self)
    def watch():
     while self.poll() is None:
      if ctx.event.wait(.2):ctx.kill_blender();return
    threading.Thread(target=watch,daemon=True).start()
 subprocess.Popen=ManagedPopen
 original_connect=http.client.HTTPConnection.connect
 def connect(connection):
  original_connect(connection)
  ctx=getattr(LOCAL,'ctx',None)
  frame=sys._getframe(1);in_service_manager=False
  while frame:
   if Path(frame.f_code.co_filename).name=='ai_service_manager.py':in_service_manager=True;break
   frame=frame.f_back
  if ctx and not in_service_manager:
   ctx.connections.append(connection)
   if ctx.event.is_set():ctx.close_connections()
 http.client.HTTPConnection.connect=connect

 def worker():
  while True:
   job=namespace['TASKS'].get();ctx=None
   try:
    with LOCK:
     if not job.is_dir():continue
     current=read(job/'status.json')
     if current.get('cancelled') and current.get('state')=='INTERRUPTED':continue
     ctx=Context(job);ACTIVE[job.name]=ctx
    LOCAL.ctx=ctx;sys.settrace(ctx.trace)
    try:namespace['process'](job)
    except JobCancelled:pass
    except Exception:
     if not ctx.event.is_set():
      sys.settrace(None);error=traceback.format_exc();(job/'error.txt').write_text(error,encoding='utf-8');base_status(job,'FAILED',error=error[-16000:]);namespace['write_job_failure'](job,error)
    finally:
     sys.settrace(None);LOCAL.ctx=None
     if ctx.event.is_set():
      ctx.close_connections();ctx.kill_blender();warning=''
      # Let late Comfy submission acknowledgments settle, then remove/interrupt only this job's IDs.
      for attempt in range(3):
       try:running=stop_comfy(ctx)
       except Exception as error:warning='Comfy cleanup could not be confirmed: '+str(error);running=[]
       time.sleep(.5)
      # Do not advance another studio job while a cancelled Comfy prompt is still known to be running.
      while running:
       base_status(job,read(job/'status.json').get('state','GENERATING_MESH'),cancel_requested=True,note='Cancellation requested; waiting for this Comfy prompt to stop safely. Use studio Force power off if the engine is stuck.')
       try:time.sleep(2);running=stop_comfy(ctx)
       except Exception as error:warning='Comfy cleanup could not be confirmed: '+str(error);break
      with LOCK:base_status(job,'INTERRUPTED',cancelled=True,cancel_requested=False,error='',note='Cancelled by user. Existing files retained; no later stages will run.'+(' '+warning if warning else ''))
   finally:
    sys.settrace(None);LOCAL.ctx=None
    with LOCK:
     if ctx:ACTIVE.pop(job.name,None)
    namespace['TASKS'].task_done()
 namespace['worker']=worker
 for path in namespace['JOBS'].glob('*/status.json'):
  if read(path).get('cancel_requested'):base_status(path.parent,'INTERRUPTED',cancelled=True,cancel_requested=False,error='',note='Cancellation request retained across controller restart.')

 def cancel_job(payload):
  if payload.get('confirm') is not True:raise ValueError('Confirmation required.')
  job=namespace['get_job'](payload.get('id',''))
  with namespace['ARCHIVE_LOCK'],LOCK:
   current=read(job/'status.json');state=current.get('state')
   if state in {'SUCCEEDED','FAILED','INTERRUPTED'}:raise ValueError('This job has already stopped. Refresh the page.')
   ctx=ACTIVE.get(job.name)
   (job/'cancel_requested.json').write_text(json.dumps({'requested_at':time.time(),'previous_state':state}),encoding='utf-8')
   if ctx:
    ctx.event.set();base_status(job,state,cancel_requested=True,note='Cancel requested. Stopping this job; partial files are retained.')
    def interrupt():
     ctx.close_connections();ctx.kill_blender()
     try:stop_comfy(ctx)
     except Exception:pass
    threading.Thread(target=interrupt,daemon=True).start()
    return {'id':job.name,'cancel_requested':True}
   base_status(job,'INTERRUPTED',cancelled=True,cancel_requested=False,error='',note='Cancelled by user before the next processing step. Existing files retained.')
   return {'id':job.name,'state':'INTERRUPTED','cancelled':True}
 class CancelHandler(previous_handler):
  def reply(self,code,content,kind='application/json'):
   if code==200 and kind.startswith('text/html'):
    script=(ROOT/'job_cancel_ui.js').read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',namespace['TOKEN']);content=(content.decode('utf-8') if isinstance(content,bytes) else content)+'<script>'+script+'</script>'
   return super().reply(code,content,kind)
  def do_POST(self):
   if self.path!='/jobs/cancel':return super().do_POST()
   if not self.authorized():return self.reply(403,{'error':'Invalid workflow key.'})
   try:
    size=int(self.headers.get('Content-Length','0'))
    if not 2<=size<=4096:raise ValueError('Invalid cancellation request size.')
    return self.reply(202,cancel_job(json.loads(self.rfile.read(size))))
   except Exception as error:return self.reply(409,{'error':str(error)})
 namespace['Handler']=CancelHandler
