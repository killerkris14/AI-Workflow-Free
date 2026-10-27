"""On-demand local services. Never terminates a process it did not launch."""
import atexit,contextlib,json,os,subprocess,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()
SERVICES={name:{'process':None,'active':0,'last_used':0.0,'starting':False,'error':''} for name in ('comfy','router')}
STARTED=False
STOPPING=False
SERVER=None
APP_CONTEXT={}
LAST_BROWSER=time.monotonic()

def settings():return json.loads((ROOT/'service_manager_settings.json').read_text(encoding='utf-8'))
def url_for(name):
    config=settings()
    if name=='comfy':return json.loads((ROOT/'hunyuan_settings.json').read_text(encoding='utf-8'))['comfy_url'].rstrip('/')+'/system_stats'
    return config.get('router_url','http://127.0.0.1:8080').rstrip('/')+'/health'

def ready(name):
    try:
        with urllib.request.urlopen(url_for(name),timeout=2) as response:return response.status==200
    except Exception:return False

def owned(name):
    p=SERVICES[name]['process'];return p is not None and p.poll() is None

def stop_owned(name):
    service=SERVICES[name];p=service['process']
    if p is None:return False
    if p.poll() is None:
        print('[Power manager] Stopping idle '+name+' (owned PID '+str(p.pid)+').',flush=True)
        if os.name=='nt':
            result=subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service['error']='Could not stop owned process tree: '+str(result.stdout)[-1000:];return False
        else:
            p.terminate()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
    service['process']=None;return True

def command_for(name):
    config=settings()
    if name=='router':
        launcher=config.get('router_launcher','')
        if not launcher or not Path(launcher).is_file():
            raise RuntimeError('Automatic Qwen startup is not configured. Set router_launcher in service_manager_settings.json to your working model-router BAT, or start it manually. Guest RPC is not remotely managed.')
        path=Path(launcher)
        if path.suffix.lower() in {'.bat','.cmd'}:return ['cmd.exe','/c',str(path)],path.parent
        return [str(path)],path.parent
    comfy=Path(json.loads((ROOT/'hunyuan_settings.json').read_text(encoding='utf-8'))['comfy_root'])
    options=[comfy.parent/'python_embeded'/'python.exe',comfy.parent/'python_embedded'/'python.exe',comfy/'.venv'/'Scripts'/'python.exe',comfy/'venv'/'Scripts'/'python.exe']
    python=next((p for p in options if p.is_file()),None)
    if python is None:raise RuntimeError('ComfyUI Python not found; check hunyuan_settings.json.')
    import urllib.parse
    port=urllib.parse.urlparse(json.loads((ROOT/'hunyuan_settings.json').read_text(encoding='utf-8'))['comfy_url']).port or 8188
    return [str(python),'-s',str(comfy/'main.py'),'--disable-auto-launch','--port',str(port)],comfy

def initialize():
    global STARTED
    with LOCK:
        if STARTED:return
        STARTED=True;threading.Thread(target=watchdog,name='AI service idle manager',daemon=True).start();atexit.register(shutdown)

def watchdog():
    while not STOPPING:
        time.sleep(5)
        try:
            timeout=max(15,int(settings().get('idle_seconds',120)))
            with LOCK:
                for name,service in SERVICES.items():
                    if owned(name) and not service['active'] and not service['starting'] and time.monotonic()-service['last_used']>=timeout:
                        stop_owned(name)
                portal_timeout=max(120,int(settings().get('portal_idle_seconds',600)))
                if SERVER is not None and time.monotonic()-LAST_BROWSER>=portal_timeout and not any(s['active'] or s['starting'] for s in SERVICES.values()):
                    allowed={'SUCCEEDED','FAILED','INTERRUPTED','WAITING_IMAGE_APPROVAL','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'}
                    statuses=[json.loads(p.read_text(encoding='utf-8')).get('state') for p in APP_CONTEXT['JOBS'].glob('*/status.json')]
                    if all(s in allowed for s in statuses):
                        print('[Power manager] No portal browser heartbeat; shutting down idle studio. Approvals remain saved.',flush=True)
                        for name in SERVICES:stop_owned(name)
                        threading.Thread(target=SERVER.shutdown,daemon=True).start();return
        except Exception as error:print('[Power manager] '+str(error),flush=True)

@contextlib.contextmanager
def service_lease(name):
    initialize();service=SERVICES[name]
    # A single workflow worker serializes engine use. LOCK also prevents idle-stop races.
    with LOCK:
        other='router' if name=='comfy' else 'comfy'
        if SERVICES[other]['active']:raise RuntimeError('The other AI engine is still processing. Wait for it before switching GPU services.')
        if owned(other):stop_owned(other)
        if ready(other):
            raise RuntimeError('A manually started '+other+' service is still running. Close it once to let this manager control GPU usage. External processes are never killed.')
        service['active']+=1;service['last_used']=time.monotonic()
        try:
            if not ready(name):
                if not owned(name):
                    command,cwd=command_for(name)
                    print('[Power manager] Starting '+name+' on demand.',flush=True)
                    service['process']=subprocess.Popen(command,cwd=str(cwd),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
                service['starting']=True;deadline=time.monotonic()+int(settings().get('startup_timeout_seconds',240))
                while not ready(name):
                    if service['process'].poll() is not None:raise RuntimeError(name+' exited during startup. Read its command window.')
                    if time.monotonic()>deadline:raise RuntimeError(name+' did not become ready. Check its command window; the job was not submitted.')
                    time.sleep(2)
            service['error']='';service['starting']=False
        except Exception as error:
            service['active']-=1;service['starting']=False;service['error']=str(error)
            if not service['active']:stop_owned(name)
            raise
    try:yield
    finally:
        with LOCK:service['active']=max(0,service['active']-1);service['last_used']=time.monotonic()


def comfy_lease():return service_lease('comfy')
def router_lease():return service_lease('router')

def snapshot():
    initialize()
    with LOCK:
        return {'idle_seconds':settings().get('idle_seconds',120),'services':{name:{'owned':owned(name),'active_jobs':s['active'],'error':s['error'],'running':ready(name)} for name,s in SERVICES.items()}}

def stop_idle_services():
    with LOCK:
        if any(s['active'] or s['starting'] for s in SERVICES.values()):raise RuntimeError('An engine is busy. Wait for processing to finish before stopping it.')
        for name in SERVICES:stop_owned(name)
        return {'ok':True,'note':'Stopped managed engines. Externally started programs were left untouched.'}

def shutdown():
    global STOPPING
    STOPPING=True
    with LOCK:
        for name in SERVICES:
            try:stop_owned(name)
            except Exception:pass


def install_portal_controls(namespace):
    APP_CONTEXT.update(namespace)
    initialize();previous=namespace['Handler']
    class PowerHandler(previous):
        def reply(self,code,content,kind='application/json'):
            if code==200 and kind.startswith('text/html'):
                script=(ROOT/'service_power_ui.js').read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',namespace['TOKEN'])
                content=(content.decode('utf-8') if isinstance(content,bytes) else content)+'<script>'+script+'</script>'
            return super().reply(code,content,kind)
        def do_GET(self):
            global SERVER,LAST_BROWSER
            SERVER=self.server
            route=self.path.split('?',1)[0]
            if route=='/services/heartbeat':
                if not self.authorized():return self.reply(403,{'error':'Invalid workflow key.'})
                LAST_BROWSER=time.monotonic();return self.reply(200,{'ok':True})
            if route!='/services/state':return super().do_GET()
            if not self.authorized():return self.reply(403,{'error':'Invalid workflow key.'})
            return self.reply(200,snapshot())
        def do_POST(self):
            if self.path not in {'/services/stop','/services/power-off'}:return super().do_POST()
            if not self.authorized():return self.reply(403,{'error':'Invalid workflow key.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 2<=length<=4096:raise ValueError('Invalid request size.')
                payload=json.loads(self.rfile.read(length))
                if payload.get('confirm') is not True:raise ValueError('Confirmation is required.')
                # Idle-engine stop is harmless to queued work, but portal shutdown must preserve it.
                if self.path=='/services/power-off':
                    with namespace['ARCHIVE_LOCK']:
                        allowed={'SUCCEEDED','FAILED','INTERRUPTED','WAITING_IMAGE_APPROVAL','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'}
                        for path in namespace['JOBS'].glob('*/status.json'):
                            if json.loads(path.read_text(encoding='utf-8')).get('state') not in allowed:raise ValueError('A job is queued or processing. Wait before powering off.')
                        data=stop_idle_services();self.reply(200,data)
                        threading.Thread(target=self.server.shutdown,daemon=True).start();return
                return self.reply(200,stop_idle_services())
            except Exception as error:return self.reply(400,{'error':str(error)})
    namespace['Handler']=PowerHandler
