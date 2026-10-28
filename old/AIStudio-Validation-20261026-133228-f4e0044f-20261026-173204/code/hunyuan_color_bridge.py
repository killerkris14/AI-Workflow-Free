"""Native reference texture bridge v2.1; uses the existing queue and cancellation worker."""
import ast,hashlib,json,math,re,shutil,subprocess,threading,uuid,urllib.parse,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WORKER_SHA256='883ca0784e0495ac89698617b269070de01e294d9da53db5852b50c73af4c7ee'
LOCK=threading.RLock();HELPERS=None
SLOTS={'main','front','back','left','right','top','bottom'};DIRECTIONS=SLOTS-{'main'}
ACTIONS={'color_cancel', 'color_preview', 'color_prepare', 'color_approve_masks', 'color_export', 'color_align'}
ACTIVE={'previewing', 'preparing', 'exporting', 'aligning', 'cancelling'}
PHASE={'preparing': 'color_prepare', 'mask_review': 'color_mask_approval', 'mask_approved': 'color_mask_approved', 'previewing': 'color_preview', 'preview_review': 'color_approval', 'exporting': 'color_export', 'cancelling': 'color_cancelling', 'failed': 'color_failed', 'complete': 'finished', 'cancelled': 'finished', 'idle': 'finished', 'aligning': 'color_align'}
FILES={'alignment.json', 'reference_masks.npz', 'preview_top.png', 'failure.json', 'preview.png', 'model-colored.3mf', 'checks.json', 'model-colored.blend', 'reference_review.json', 'color.log', 'model-colored.glb', 'preview_side.png'}
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
 p=Path(path);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(value,indent=2),encoding='utf-8');t.replace(p)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(path):return sha(Path(path).read_bytes())
def helpers():
 global HELPERS
 path=ROOT/'hunyuan_color.py'
 if digest(path)!=WORKER_SHA256:raise ValueError('Matching reference-texture worker missing/changed')
 if HELPERS is None:
  tree=ast.parse(path.read_text(encoding='utf-8-sig'));wanted={'canonical','digest','load','job_file','source_info','configuration_fingerprint'};nodes=[]
  for n in tree.body:
   if isinstance(n,ast.FunctionDef) and n.name in wanted:nodes.append(n)
   elif isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DIRECTIONS' for t in n.targets):ast.literal_eval(n.value);nodes.append(n)
  if {n.name for n in nodes if isinstance(n,ast.FunctionDef)}!=wanted:raise ValueError('Worker protocol helpers missing')
  scope={'Path':Path,'json':json,'hashlib':hashlib,'math':math};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path)+'[pure validators]','exec'),scope);HELPERS=scope
 return HELPERS

def folder_for(job,version):
 if not isinstance(version,str) or not re.fullmatch('[a-f0-9]{16}',version):raise ValueError('Invalid color version')
 parent=job/'color_versions';folder=parent/version
 if parent.is_symlink() or folder.is_symlink() or folder.resolve().parent!=parent.resolve() or job.resolve() not in folder.resolve().parents:raise ValueError('Unsafe color directory')
 return folder

def asset(folder,name):
 if not isinstance(name,str) or Path(name).name!=name or (name not in FILES and not re.fullmatch(r'(reference|mask|overlay)_(main|front|back|left|right|top|bottom)\.png',name)):raise ValueError('Unknown asset')
 p=folder/name
 if p.is_symlink() or not p.is_file() or p.resolve().parent!=folder.resolve():raise ValueError('Missing/unsafe asset')
 return p

def current(job):
 path=job/'reference_color_state_v2.json'
 if not path.is_file():return {'protocol':2,'job_id':job.name,'revision':0,'version':None,'phase':'idle','task_nonce':None,'reference_fingerprint':None,'reference_approved':False,'preview_fingerprint':None,'settings':{'views':{}},'error':''}
 if path.is_symlink():raise ValueError('Unsafe state file')
 s=load(path)
 if s.get('protocol')!=2 or s.get('job_id')!=job.name:raise ValueError('Wrong state context')
 return s

def normalize(raw,views,require_direction=True):
 if not isinstance(raw,dict) or set(raw)!={'views'} or not isinstance(raw['views'],dict) or set(raw['views'])-set(views):raise ValueError('Per-reference settings required')
 defaults={'scale':1.,'offset_x':0.,'offset_y':0.,'yaw':0.,'pitch':0.,'roll':0.,'flip':False};result={}
 for slot,hint in views.items():
  v=raw['views'].get(slot,{})
  if not isinstance(v,dict) or set(v)-set(defaults)-{'direction'}:raise ValueError('Unknown alignment setting')
  v={**defaults,**v};v['direction']=v.get('direction',hint)
  if v['direction'] not in DIRECTIONS and (require_direction or v['direction'] is not None):raise ValueError('Choose direction for '+slot)
  if not isinstance(v['flip'],bool):raise ValueError('Mirror must be boolean')
  for key in ['scale','offset_x','offset_y','yaw','pitch','roll']:
   x=v[key];lo,hi=(.2,4) if key=='scale' else (-1,1) if key.startswith('offset') else (-180,180)
   if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Invalid '+key)
   v[key]=float(x)
  result[slot]=v
 return {'views':result}

class ColorTask:
 def __init__(self,job,version,nonce,mode):self.job=Path(job);self.version=version;self.nonce=nonce;self.mode=mode
 def __fspath__(self):return str(self.job)
 def __getattr__(self,name):return getattr(self.job,name)
 def __truediv__(self,name):return self.job/name

def matches(s,task):return isinstance(task,ColorTask) and s.get('version')==task.version and s.get('task_nonce')==task.nonce and s.get('phase')=={'prepare':'preparing','preview':'previewing','export':'exporting','align':'aligning'}.get(task.mode)
def reference_check(folder,config):
 r=load(asset(folder,'reference_review.json'));body={k:v for k,v in r.items() if k!='reference_fingerprint'}
 if r.get('ok') is not True or r.get('phase')!='reference_masks_ready' or r.get('protocol')!=2 or sha(canonical(body))!=r.get('reference_fingerprint'):raise ValueError('Reference review metadata changed')
 if helpers()['source_info'](config)['fingerprint']!=r['source']['fingerprint']:raise ValueError('Model/reference source changed')
 if not r.get('artifacts'):raise ValueError('Reference assets missing')
 for name,value in r['artifacts'].items():
  if digest(asset(folder,name))!=value:raise ValueError('Reference/mask asset changed')
 return r

def preview_check(folder,config,exported=False):
 if load(asset(folder,'checks.json')).get('preview_render_method')!='unlit_color_proof_v1':raise ValueError('Old lighting preview: build a NEW unlit texture preview before export')
 ref=reference_check(folder,config);r=load(asset(folder,'checks.json'));body={k:v for k,v in r.items() if k not in {'preview_fingerprint','export','export_sha256'}}
 expected='color_export_finished' if exported else 'color_preview_ready'
 if r.get('phase')!=expected or r.get('ok') is not True or r.get('protocol')!=2:raise ValueError('Expected successful exact preview/export')
 body['phase']='color_preview_ready'
 if sha(canonical(body))!=r.get('preview_fingerprint') or helpers()['configuration_fingerprint'](config)!=r.get('configuration_fingerprint'):raise ValueError('Preview metadata/settings changed')
 if r.get('reference_fingerprint')!=ref['reference_fingerprint'] or config.get('reference_approval_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Reference approval changed')
 for name,value in r['artifacts'].items():
  if digest(asset(folder,name))!=value:raise ValueError('Preview artifact changed')
 if exported and digest(asset(folder,'model-colored.3mf'))!=r.get('export_sha256'):raise ValueError('Export changed')
 return r

def extend(n):
 previous_process=n['process'];previous_answer=n['answer'];previous_install=n['install'];context=n['CONTEXT'];state=n['state']
 def persist(job,s,phase=None,**values):
  s={**s,**values,'revision':s['revision']+1}
  if phase:s['phase']=phase
  save(job/'reference_color_state_v2.json',s);p=load(job/'hunyuan_progress.json');p.update(color_protocol=2,color_version=s['version'],stage=PHASE[s['phase']],color_settings=s['settings']);n['save'](job/'hunyuan_progress.json',p);return s
 def sync_cancel(job,s):
  import job_cancel
  p=load(job/'hunyuan_progress.json');owned=p.get('color_protocol')==2 and p.get('color_version')==s.get('version') and (p.get('stage')=='finished' or str(p.get('stage','')).startswith('color_'))
  if s['phase'] in {'idle','cancelled'} or (s['phase'] not in ACTIVE and not owned):return s
  st=load(job/'status.json');ctx=job_cancel.ACTIVE.get(job.name)
  if not(st.get('cancelled') or st.get('cancel_requested') or (ctx and ctx.event.is_set())):return s
  phase='cancelling' if ctx or st.get('cancel_requested') else 'cancelled'
  if s['phase']!=phase or s.get('task_nonce'):s=persist(job,s,phase,task_nonce=None,preview_fingerprint=None)
  return s
 def views(job):
  result={}
  for p in load(job/'hunyuan_progress.json').get('autoroute',{}).get('panels',[]):
   slot=p.get('view');hint=p.get('reference_direction') if slot=='main' else slot
   if slot not in SLOTS or slot in result:raise ValueError('Invalid/duplicate prepared view')
   result[slot]=hint if hint in DIRECTIONS else None
  return result
 def baseconfig(job,confirm=False):return {'source_blend':str(job/'final/model.blend'),'confirm_bind_unhashed_source':confirm,'settings':{'views':{}}}
 def details(job):
  with LOCK:
   req=load(job/'request.json')
   if req.get('engine')!='hunyuan':return {'engine':req.get('engine','procedural')}
   s=sync_cancel(job,current(job));base=job/'final/model.blend';checks=load(job/'final/checks.json') if (job/'final/checks.json').is_file() else {};v=views(job);d={'engine':'hunyuan','id':job.name,'state':s,'status':load(job/'status.json'),'progress':load(job/'hunyuan_progress.json'),'available_views':[{'slot':a,'direction_hint':b} for a,b in v.items()],'base_available':base.is_file(),'approved_geometry_available':False,'needs_unhashed_confirmation':not checks.get('preview_blend_sha256')}
   if base.is_file():
    try:helpers()['source_info'](baseconfig(job,True));d['approved_geometry_available']=True
    except Exception as e:d['source_problem']=str(e)
   if s['version']:
    folder=folder_for(job,s['version'])
    if (folder/'reference_review.json').is_file():d['reference_review']=load(asset(folder,'reference_review.json'));d['source_changed']=not base.is_file() or d['reference_review']['source']['source_sha256']!=digest(base)
    if (folder/'checks.json').is_file():
     r=load(asset(folder,'checks.json'));d['color_checks']=r
     if r.get('phase') in {'color_preview_ready','color_export_finished'}:d['preview_report']=r
     if s['phase']=='complete' and not d.get('source_changed') and r.get('export_sha256')==digest(asset(folder,'model-colored.3mf')):d['export_sha256']=r['export_sha256']
   return d
 def idle(job):
  import job_cancel
  st=load(job/'status.json');return job.name not in job_cancel.ACTIVE and not st.get('cancel_requested') and st.get('state') in {'SUCCEEDED','FAILED','INTERRUPTED','WAITING_MODEL_APPROVAL'}
 def check(s,payload):
  rev=payload.get('revision')
  if payload.get('id')!=s['job_id'] or isinstance(rev,bool) or not isinstance(rev,int) or rev!=s['revision'] or payload.get('version')!=s['version']:raise ValueError('Stale tab/version: refresh before submitting')
 def enqueue(job,s,mode,config,clone=None):
  version=s['version'] if mode=='export' else uuid.uuid4().hex[:16];folder=folder_for(job,version)
  if mode!='export':folder.mkdir(parents=True,exist_ok=False)
  if clone:
   old=folder_for(job,clone);r=reference_check(old,load(old/'settings.json'))
   for name,value in r['artifacts'].items():
    shutil.copy2(asset(old,name),folder/name)
    if digest(folder/name)!=value:raise ValueError('Reference changed during cloning')
   shutil.copy2(asset(old,'reference_review.json'),folder/'reference_review.json')
  save(folder/'settings.json',config);nonce=uuid.uuid4().hex;s=persist(job,s,{'prepare':'preparing','preview':'previewing','export':'exporting','align':'aligning'}[mode],version=version,task_nonce=nonce,settings=config['settings'],preview_fingerprint=s.get('preview_fingerprint') if mode=='export' else None,error='')
  if mode=='prepare':s=persist(job,s,reference_fingerprint=None,reference_approved=False)
  try:state(job,'QUEUED',cancel_requested=False,error='',note='Reference texture '+mode+' queued; original successful files retained.');context['TASKS'].put(ColorTask(job,version,nonce,mode))
  except Exception:persist(job,s,'failed',task_nonce=None,error='Queue admission failed');state(job,'FAILED',note='Reference admission failed');raise
  return details(job)
 def answer(payload):
  job=context['get_job'](payload.get('id',''));choice=payload.get('choice')
  if choice not in ACTIONS:
   if str(load(job/'hunyuan_progress.json').get('stage','')).startswith('color_'):raise ValueError('Finish/cancel color review before changing geometry')
   return previous_answer(payload)
  with LOCK:
   if load(job/'request.json').get('engine')!='hunyuan':raise ValueError('Not a Hunyuan job')
   s=sync_cancel(job,current(job));check(s,payload)
   if choice=='color_cancel':
    if s['phase'] in ACTIVE:raise ValueError('Use native Cancel job and wait for owned work to stop')
    s=persist(job,s,'cancelled',task_nonce=None,preview_fingerprint=None);state(job,'SUCCEEDED',checks=load(job/'final/checks.json'),error='',note='Color review closed; original successful export retained.');return details(job)
   if not context['config']().get('allow_generated_code_execution'):raise ValueError('Workflow processing disabled')
   if not idle(job) or s['phase'] in ACTIVE:raise ValueError('Wait for processing/cancellation to finish')
   v=views(job)
   if choice=='color_prepare':
    p=load(job/'hunyuan_progress.json');st=load(job/'status.json');resume=s['phase']=='cancelled' and p.get('color_protocol')==2 and p.get('color_version')==s.get('version') and p.get('stage')=='finished' and st.get('cancelled')
    if (st.get('state')!='SUCCEEDED' and not str(p.get('stage','')).startswith('color_') and not resume) or (s['phase']=='idle' and str(p.get('stage','')).startswith('color_')):raise ValueError('Export current mesh, or close the legacy color review first')
    cfg=baseconfig(job,payload.get('confirm_bind_unhashed_source') is True);helpers()['source_info'](cfg);cfg['settings']=normalize(payload.get('settings',{'views':{}}),v,False);return enqueue(job,s,'prepare',cfg)
   folder=folder_for(job,s['version']);cfg=load(folder/'settings.json')
   if choice=='color_approve_masks':
    ref=reference_check(folder,cfg)
    if s['phase']!='mask_review' or payload.get('confirm_masks') is not True or payload.get('reference_fingerprint')!=ref['reference_fingerprint'] or s.get('reference_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Approve this exact mask/reference set')
    cfg['reference_approval_fingerprint']=ref['reference_fingerprint'];save(folder/'settings.json',cfg);s=persist(job,s,'mask_approved',reference_approved=True);state(job,'WAITING_MODEL_APPROVAL',error='',note='References approved. Align views, then build texture preview.');return details(job)
   if choice in {'color_preview','color_align'}:
    if s['phase'] not in {'mask_approved','preview_review','failed'} or not s.get('reference_approved'):raise ValueError('Approve source masks first')
    ref=reference_check(folder,cfg)
    if cfg.get('reference_approval_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Reference approval changed')
    cfg['settings']=normalize(payload.get('settings'),v,choice!='color_align');cfg.pop('approved_preview_fingerprint',None);cfg.pop('accept_uncovered',None);return enqueue(job,s,'align' if choice=='color_align' else 'preview',cfg,s['version'])
   if s['phase']!='preview_review' or payload.get('confirm_preview') is not True:raise ValueError('Explicit exact-preview approval required')
   r=preview_check(folder,cfg)
   if payload.get('preview_fingerprint')!=r['preview_fingerprint'] or s.get('preview_fingerprint')!=r['preview_fingerprint']:raise ValueError('Preview changed')
   if normalize(payload.get('settings'),v)!=cfg['settings']:raise ValueError('Settings changed: rebuild preview')
   if r['statistics']['fallback_faces'] and payload.get('accept_uncovered') is not True:raise ValueError('Accept neutral unobserved areas explicitly')
   cfg.update(approved_preview_fingerprint=r['preview_fingerprint'],accept_uncovered=payload.get('accept_uncovered') is True);return enqueue(job,s,'export',cfg)
 def run_task(task):
  job=task.job
  with LOCK:
   s=sync_cancel(job,current(job))
   if not matches(s,task):return
   folder=folder_for(job,task.version);cfg=context['config']();helpers();state(job,'RUNNING_BLENDER',note='Reference textures: '+task.mode+'. Full-resolution image textures; no palette quantization.')
  try:
   command=[cfg['blender_exe'],'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(ROOT/'hunyuan_color.py'),'--',str(folder),task.mode]
   with (folder/'color.log').open('w',encoding='utf-8') as log:r=subprocess.run(command,cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,timeout=cfg.get('blender_timeout_seconds',900))
   if r.returncode:raise RuntimeError('Reference worker failed: '+(folder/'color.log').read_text(encoding='utf-8',errors='replace')[-9000:])
   with LOCK:
    s=sync_cancel(job,current(job))
    if not matches(s,task):return
    config=load(folder/'settings.json')
    if task.mode=='prepare':r=reference_check(folder,config);s=persist(job,s,'mask_review',task_nonce=None,reference_fingerprint=r['reference_fingerprint']);note='Inspect all source/mask/overlay images before approving.'
    elif task.mode in {'preview','align'}:r=preview_check(folder,config);s=persist(job,s,'preview_review',task_nonce=None,preview_fingerprint=r['preview_fingerprint']);note='Texture preview ready. Compare all views and neutral unobserved regions.'
    else:
     r=preview_check(folder,config,True)
     if config.get('approved_preview_fingerprint')!=s.get('preview_fingerprint') or r.get('preview_fingerprint')!=s.get('preview_fingerprint'):raise ValueError('Export approval changed')
     s=persist(job,s,'complete',task_nonce=None);note='Texture master exported separately. Bambu/AMS filament mapping is NOT validated.'
    checks=load(job/'final/checks.json');checks['color_workflow']=r;state(job,'SUCCEEDED' if task.mode=='export' else 'WAITING_MODEL_APPROVAL',checks=checks,error='',note=note)
  except Exception:
   with LOCK:
    s=sync_cancel(job,current(job))
    if matches(s,task):persist(job,s,'failed',task_nonce=None,error=traceback.format_exc()[-3000:])
   raise
 def process(job):
  p=load(Path(job)/'hunyuan_progress.json')
  if p.get('color_protocol')==2 and str(p.get('stage','')).startswith('color_'):return
  return previous_process(job)
 def install(main):
  previous_install(main);old=main['Handler'];previous_dispatch=main['process']
  def dispatch(job):
   if isinstance(job,ColorTask):return run_task(job)
   return previous_dispatch(job)
  main['process']=dispatch
  class ColorHandler(old):
   def reply(self,code,content,kind='application/json'):
    if code==200 and kind.startswith('text/html'):
     script=(ROOT/'hunyuan_color_ui.js').read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',main['TOKEN']);content=(content.decode('utf-8') if isinstance(content,bytes) else content)+'<script>'+script+'</script>'
    return super().reply(code,content,kind)
   def do_GET(self):
    url=urllib.parse.urlsplit(self.path)
    if not url.path.startswith('/hunyuan-color/'):return super().do_GET()
    if not self.authorized():return self.reply(403,{'error':'Invalid workflow key'})
    try:
     parts=url.path.strip('/').split('/')
     with main['ARCHIVE_LOCK'],LOCK:
      if len(parts)==3 and parts[1]=='detail':return self.reply(200,details(main['get_job'](parts[2])))
      if len(parts)==5 and parts[1]=='file':
       job=main['get_job'](parts[2]);folder=folder_for(job,parts[3]);name=parts[4];data=asset(folder,name).read_bytes();expected=urllib.parse.parse_qs(url.query).get('sha256',[''])[0]
       if not re.fullmatch('[a-f0-9]{64}',expected) or sha(data)!=expected:raise ValueError('Exact asset hash mismatch')
       return self.reply(200,data,'image/png' if name.endswith('.png') else 'application/octet-stream')
     return self.reply(404,{'error':'Unknown color route'})
    except Exception as e:return self.reply(409,{'error':str(e)})
   def do_POST(self):
    if self.path!='/hunyuan-color/answer':return super().do_POST()
    if not self.authorized():return self.reply(403,{'error':'Invalid workflow key'})
    try:
     size=int(self.headers.get('Content-Length','0'))
     if not 2<=size<=65536:raise ValueError('Invalid request size')
     p=json.loads(self.rfile.read(size))
     if not isinstance(p,dict):raise ValueError('Expected JSON object')
     with main['ARCHIVE_LOCK']:r=answer(p)
     return self.reply(202,r)
    except Exception as e:return self.reply(409,{'error':str(e)})
  main['Handler']=ColorHandler
 n.update(process=process,answer=answer,install=install)
