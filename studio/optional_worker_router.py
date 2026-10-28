"""Optional worker router: choose RPC or local-only at each router startup.
Does not edit models.ini. Does not hot-switch active model requests.
"""
import json,os,re,socket,subprocess,sys,tempfile,threading,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MARKER='; AI Studio optional-worker runtime preset - generated\n'

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def setting(line):
 value=line.strip()
 if not value or value.startswith(('#',';','[')):return None
 m=re.match(r'^\s*([A-Za-z_\-][\w\-]*)\s*=\s*(.*?)\s*$',line)
 if not m:return None
 return m.group(1).lstrip('-').lower().replace('_','-'),m.group(2).split('#',1)[0].split(';',1)[0].strip().strip('"\'')
def endpoint(value):
 value=value.strip()
 if value.startswith('['):
  m=re.fullmatch(r'\[([^\]]+)\]:(\d+)',value)
  if not m:raise ValueError('Invalid bracketed worker endpoint')
  host,port=m.groups()
 else:
  host,sep,port=value.rpartition(':')
  if not sep or not host or ':' in host:raise ValueError('Use worker-IP:port or [IPv6]:port')
 if not re.fullmatch(r'[A-Za-z0-9_.:%\-]+',host) or not str(port).isdigit() or not 1<=int(port)<=65535:raise ValueError('Invalid worker host/port')
 return host,int(port)
def rpc_endpoints(text):
 result=[]
 for line in text.splitlines():
  item=setting(line)
  if item and item[0]=='rpc':
   for value in item[1].split(','):
    value=value.strip()
    if value:
     endpoint(value)
     if value not in result:result.append(value)
 if len(result)>4:raise ValueError('More than four RPC endpoints are not supported by this bounded detector')
 return result

def local_preset(text):
 lines=[]
 for line in text.splitlines(keepends=True):
  item=setting(line)
  if not item:lines.append(line);continue
  key,value=item
  if key in {'rpc','tensor-split','main-gpu'}:continue
  if key in {'device','devices','dev'} and re.search(r'RPC',value,re.I):
   kept=[part.strip() for part in value.split(',') if part.strip() and not re.search(r'RPC',part,re.I)]
   if kept:lines.append(key+' = '+','.join(kept)+('\r\n' if line.endswith('\r\n') else '\n'))
   continue
  lines.append(line)
 result=''.join(lines)
 if rpc_endpoints(result):raise ValueError('Local-only runtime preset still contains RPC')
 return result

def remote_preset(text,saved):
 if rpc_endpoints(text):return text
 endpoint(saved);lines=[];wildcard=False
 for line in text.splitlines(keepends=True):
  header=re.match(r'^\s*\[([^]]+)\]',line)
  if header:wildcard=header.group(1).strip()=='*'
  item=setting(line)
  if wildcard and item and item[0]=='rpc':continue
  lines.append(line)
 for i,line in enumerate(lines):
  if re.fullmatch(r'\s*\[\*\]\s*(?:[;#].*)?',line.strip()):lines.insert(i+1,'rpc = '+saved+'\n');return ''.join(lines)
 return '[*]\nrpc = '+saved+'\n'+text

def reachable(address,timeout=1.0):
 host,port=endpoint(address);done=threading.Event();result=[]
 def check():
  try:
   with socket.create_connection((host,port),timeout=timeout):result.append(True)
  except OSError:pass
  finally:done.set()
 threading.Thread(target=check,daemon=True).start();done.wait(timeout+.1);return bool(result)

def choose(text,saved,probe=reachable):
 remote=remote_preset(text,saved);addresses=rpc_endpoints(remote);available=True
 for address in addresses:
  try:
   ok=probe(address)
   if not ok:time.sleep(.2);ok=probe(address)
  except Exception:ok=False
  if not ok:available=False;break
 return ('RPC + local',remote,addresses) if available else ('SINGLE-PC',local_preset(text),addresses)

def child_environment(mode,environ=None):
 env=dict(os.environ if environ is None else environ)
 # Preset is the sole RPC selector; inherited RPC must not override a local decision.
 for name in list(env):
  key=name.upper()
  if key=='LLAMA_ARG_RPC' or (mode=='SINGLE-PC' and key in {'LLAMA_ARG_TENSOR_SPLIT','LLAMA_ARG_MAIN_GPU'}):env.pop(name,None)
  elif mode=='SINGLE-PC' and key in {'LLAMA_ARG_DEVICE','LLAMA_ARG_DEVICES'} and 'RPC' in env[name].upper():env.pop(name,None)
 return env

def main():
 config=load(ROOT/'optional_worker_router.json');source=ROOT/'models.ini';server=Path(config['server']);args=list(config['server_args'])
 if not source.is_file() or source.is_symlink() or not server.is_file():raise ValueError('Configured models.ini or llama-server.exe is missing')
 saved=config['saved_endpoint'];settings=ROOT/'studio_settings.json'
 if settings.is_file():
  s=load(settings);host=s.get('worker_ip');port=s.get('worker_rpc_port',50052)
  if host:
   host=str(host);saved=('['+host+']' if ':' in host and not host.startswith('[') else host)+':'+str(port)
 text=source.read_text(encoding='utf-8-sig');mode,preset,addresses=choose(text,saved)
 print('[Optional worker] '+(', '.join(addresses))+' -> '+mode,flush=True)
 if mode=='SINGLE-PC':print('[Optional worker] Worker not reachable. Continuing locally; existing context/GPU-layer settings retained.',flush=True)
 else:print('[Optional worker] TCP port reachable; RPC protocol/build compatibility is not certified by this check.',flush=True)
 if '--check-only' in sys.argv:return 0
 runtime=ROOT/('models.auto-worker-runtime-'+uuid.uuid4().hex+'.ini')
 try:
  with runtime.open('x',encoding='utf-8',newline='') as f:f.write(MARKER);f.write(preset)
  index=args.index('--models-preset')+1;args[index]=str(runtime)
  logs=ROOT/'logs';logs.mkdir(exist_ok=True);(logs/'optional-worker-last-mode.json').write_text(json.dumps({'mode':mode,'endpoints':addresses,'time':time.time(),'runtime_preset':str(runtime)},indent=2),encoding='utf-8')
  # Keep the original server args/cwd; child inherits the existing Studio Job Object.
  child=subprocess.Popen([str(server),*args],cwd=config['cwd'],env=child_environment(mode))
  try:return child.wait()
  except BaseException:
   if child.poll() is None:child.terminate();child.wait(timeout=20)
   raise
 finally:runtime.unlink(missing_ok=True)
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as error:print('[Optional worker] STOPPED: '+str(error),flush=True);sys.exit(1)
