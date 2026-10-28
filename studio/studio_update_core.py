"""Signed stable-release checks and local publisher tooling. No third-party Python packages."""
import ast,base64,contextlib,datetime,hashlib,io,json,os,re,secrets,shutil,socket,stat,subprocess,sys,tempfile,time,urllib.parse,urllib.request,uuid,zipfile
from pathlib import Path,PurePosixPath
VERSION='1.0.0'
PRODUCT='AI-Modeling-Studio'
DATA=Path(os.environ.get('APPDATA') or Path.home()/'.config')/PRODUCT
PRIVATE=DATA/'publisher'/'release-key.dpapi'
PUBLIC=DATA/'publisher'/'release-public.xml'
PROTECTED={'config.json','hunyuan_settings.json','service_manager_settings.json','studio_settings.json','worker_settings.json','models.ini','start-model-router.bat','access-token.txt','update_settings.json','release_version.json'}
SKIP={'jobs','archived-jobs','archives','logs','__pycache__','.git','.venv','venv','models','input','output','temp','tmp','color_versions','review_versions','final','.studio_release','release-output','releases','updates','update-cache'}
EXTS={'.py','.pyw','.html','.js','.css','.json','.ico','.png','.svg','.bat','.ps1','.md'}
MAX_PACKAGE=256*1024*1024
MAX_EXPANDED=512*1024*1024
NOWIN=getattr(subprocess,'CREATE_NO_WINDOW',0)

def read(path,default=None):
 try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {} if default is None else default

def write(path,data):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');q.write_text(json.dumps(data,indent=2),encoding='utf-8');q.replace(p)

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for part in iter(lambda:f.read(1048576),b''):h.update(part)
 return h.hexdigest()

def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('utf-8')
def ver(value):
 if not re.fullmatch(r'\d+\.\d+\.\d+(?:\.\d+)?',str(value)):raise ValueError('Use a numeric version such as 1.0.1.')
 return tuple(int(x) for x in str(value).split('.'))+(0,)*(4-len(str(value).split('.')))

def ps(action,public='',data=b'',signature='',private=PRIVATE):
 if os.name!='nt':raise RuntimeError('Release signing requires Windows PowerShell/.NET on this computer.')
 script=r"""$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Security;
$r=New-Object System.Security.Cryptography.RSACryptoServiceProvider(3072);$r.PersistKeyInCsp=$false;
$a=$env:AISTUDIO_CRYPTO_ACTION;
if($a -eq 'generate'){
 $xml=$r.ToXmlString($true);$raw=[Text.Encoding]::UTF8.GetBytes($xml);
 $encrypted=[Security.Cryptography.ProtectedData]::Protect($raw,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser);
 [IO.File]::WriteAllBytes($env:AISTUDIO_PRIVATE_PATH,$encrypted);$r.ToXmlString($false)
}elseif($a -eq 'sign'){
 $raw=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($env:AISTUDIO_PRIVATE_PATH),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser);
 $r.FromXmlString([Text.Encoding]::UTF8.GetString($raw));
 [Convert]::ToBase64String($r.SignData([IO.File]::ReadAllBytes($env:AISTUDIO_DATA_PATH),'SHA256'))
}elseif($a -eq 'verify'){
 $r.FromXmlString([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:AISTUDIO_PUBLIC_B64)));
 if(-not $r.VerifyData([IO.File]::ReadAllBytes($env:AISTUDIO_DATA_PATH),'SHA256',[Convert]::FromBase64String($env:AISTUDIO_SIGNATURE))){throw 'Invalid release signature'};'VALID'
}else{throw 'Unknown crypto action'};$r.Dispose()
"""
 with tempfile.TemporaryDirectory(prefix='aistudio-crypto-') as t:
  f=Path(t)/'data.bin';f.write_bytes(data);private=Path(private);private.parent.mkdir(parents=True,exist_ok=True)
  env=dict(os.environ,AISTUDIO_CRYPTO_ACTION=action,AISTUDIO_DATA_PATH=str(f),AISTUDIO_PRIVATE_PATH=str(private),AISTUDIO_PUBLIC_B64=base64.b64encode(public.encode()).decode(),AISTUDIO_SIGNATURE=signature)
  r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],env=env,capture_output=True,text=True,creationflags=NOWIN,timeout=90)
  if r.returncode:raise RuntimeError('Windows signing/verification failed: '+(r.stderr or r.stdout)[-1600:])
  return r.stdout.strip()

def identity():
 if PRIVATE.exists() and PUBLIC.exists():return PUBLIC.read_text(encoding='utf-8')
 if PRIVATE.exists() or PUBLIC.exists():raise RuntimeError('Incomplete publisher identity. Do not delete or replace a deployed signing key; restore its matching key/public file.')
 public=ps('generate');PUBLIC.write_text(public,encoding='utf-8');return public

def settings_path(root):
 key=hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:20]
 return DATA/'update_profiles'/(key+'.json')
def settings(root):return read(settings_path(root),{'manifest_url':'','public_key':'','check_on_launch':True,'highest_sequence':0})
def set_settings(root,cfg):write(settings_path(root),cfg)

def validate_source(value):
 value=str(value).strip()
 if value.startswith('https://'):
  parsed=urllib.parse.urlparse(value)
  if not parsed.hostname or parsed.username or parsed.password:raise ValueError('Use an HTTPS manifest URL without embedded credentials.')
  return value
 path=Path(value).expanduser()
 if path.is_absolute():return str(path)
 raise ValueError('Use an HTTPS latest.json URL or an absolute local latest.json path for testing.')

def get_bytes(source,limit):
 if source.startswith('https://'):
  req=urllib.request.Request(source,headers={'User-Agent':'AIStudio-Updater/'+VERSION})
  with urllib.request.urlopen(req,timeout=30) as response:
   if urllib.parse.urlparse(response.geturl()).scheme!='https':raise RuntimeError('HTTPS downgrade refused.')
   length=response.headers.get('Content-Length')
   if length and int(length)>limit:raise ValueError('Download exceeds size limit.')
   data=response.read(limit+1)
 else:
  p=Path(source)
  if p.stat().st_size>limit:raise ValueError('File exceeds size limit.')
  data=p.read_bytes()
 if len(data)>limit:raise ValueError('Download exceeds size limit.')
 return data

def get_manifest(cfg):
 if not cfg.get('manifest_url') or not cfg.get('public_key'):raise RuntimeError('Updates are not configured. Set a manifest location and trusted public key in Release Tool.')
 source=validate_source(cfg['manifest_url']);raw=get_bytes(source,1024*1024);envelope=json.loads(raw)
 body=envelope.get('signed');signature=envelope.get('signature')
 if envelope.get('algorithm')!='rsa-pkcs1v15-sha256' or not isinstance(body,dict) or not isinstance(signature,str):raise ValueError('Unsupported or unsigned release metadata.')
 ps('verify',cfg['public_key'],canonical(body),signature)
 if body.get('product')!=PRODUCT:raise ValueError('Wrong update product.')
 ver(body.get('version'));ver(body.get('min_updater','1.0.0'))
 if ver(VERSION)<ver(body.get('min_updater','1.0.0')):raise RuntimeError('This updater is too old. Use the newer verified setup instead.')
 if int(body.get('sequence',0))<int(cfg.get('highest_sequence',0)):raise ValueError('Release rollback refused.')
 now=time.time()
 if float(body.get('expires',0))<now:raise ValueError('Release metadata has expired. Ask the publisher to renew it.')
 if float(body.get('published',0))>now+86400:raise ValueError('Release is dated in the future. Check the Windows clock.')
 if not 0<float(body.get('expires',0))-float(body.get('published',0))<=370*86400:raise ValueError('Invalid release expiration interval.')
 return body

def asset_source(manifest_source,name):
 if not re.fullmatch(r'[A-Za-z0-9_.-]+',str(name)):raise ValueError('Invalid release asset filename.')
 if manifest_source.startswith('https://'):return urllib.parse.urljoin(manifest_source,name)
 return str(Path(manifest_source).parent/name)

def download_asset(cfg,asset,dest):
 size=int(asset.get('size',-1))
 if not 0<size<=MAX_PACKAGE or not re.fullmatch(r'[a-f0-9]{64}',asset.get('sha256','')):raise ValueError('Invalid release download metadata.')
 data=get_bytes(asset_source(cfg['manifest_url'],asset['name']),size)
 if len(data)!=size or hashlib.sha256(data).hexdigest()!=asset['sha256']:raise ValueError('Download integrity check failed.')
 Path(dest).write_bytes(data)

def current_version(root):return read(Path(root)/'release_version.json',{'version':'0.0.0'})
def busy(root,role='main'):
 for port in ((50054,50052) if role=='worker' else (8764,8765,8188,8080)):
  with socket.socket() as s:
   try:s.bind(('127.0.0.1',port))
   except OSError:return True
 return False

class Gate:
 def __init__(self,root):self.path=Path(root)/'.studio_release'/'update.lock';self.handle=None
 def __enter__(self):
  self.path.parent.mkdir(parents=True,exist_ok=True);self.handle=self.path.open('a+b');self.handle.seek(0);self.handle.write(b'0');self.handle.flush();self.handle.seek(0)
  try:
   if os.name=='nt':
    import msvcrt;msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl;fcntl.flock(self.handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:self.handle.close();raise RuntimeError('Another studio launch, release build, or update is in progress.')
  return self
 def __exit__(self,*args):self.handle.close()

def safe_member(name):
 path=PurePosixPath(name)
 if not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts or any(x.endswith((' ','.')) for x in path.parts):raise ValueError('Unsafe ZIP path: '+name)
 if any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',x) for x in path.parts):raise ValueError('Reserved Windows ZIP path.')
 return path

def safe_archive(path):
 seen=set();total=0
 with zipfile.ZipFile(path) as z:
  if len(z.infolist())>10000:raise ValueError('Too many release files.')
  for item in z.infolist():
   p=safe_member(item.filename);key=item.filename.casefold()
   if key in seen:raise ValueError('Duplicate/case-colliding ZIP path.')
   seen.add(key);total+=item.file_size
   if total>MAX_EXPANDED or stat.S_ISLNK(item.external_attr>>16) or item.flag_bits&1:raise ValueError('Unsupported/oversized ZIP entry.')
   if p.parts[0]!='AI-Studio-Package':raise ValueError('Unexpected release ZIP root.')
  if z.testzip():raise ValueError('Release ZIP is corrupt.')

def destinations(root,archive,role):
 root=Path(root);cfg=read(root/'hunyuan_settings.json');studio_cfg=read(root/'studio_settings.json')
 comfy=Path(cfg.get('comfy_root') or str(Path(studio_cfg.get('comfy_dir',r'C:\ComfyUI_windows_portable'))/'ComfyUI'))
 result=[]
 with zipfile.ZipFile(archive) as z:
  for item in z.infolist():
   if item.is_dir():continue
   p=safe_member(item.filename);parts=p.parts
   if len(parts)<3:continue
   area=parts[1];rel=PurePosixPath(*parts[2:])
   if area=='studio' and role=='main':
    if rel.name.casefold() in PROTECTED:continue
    dest=root/Path(*rel.parts)
   elif area=='worker' and role=='worker':
    if rel.name not in {'worker_agent.pyw','studio_update_core.py','studio_update_ui.py','studio_update_launch.pyw'}:continue
    dest=root/rel.name
   elif area=='custom_nodes' and role=='main' and rel.parts[0]=='ai_workflow_portal':dest=comfy/'custom_nodes'/Path(*rel.parts)
   else:continue
   if any(x.casefold() in SKIP or x.casefold().startswith(('backup-','attempt_')) for x in rel.parts):raise ValueError('Protected data in update package.')
   if not (dest==root or root in dest.parents or (comfy/'custom_nodes') in dest.parents):raise ValueError('Invalid destination.')
   cursor=dest
   while cursor!=cursor.parent:
    if cursor.is_symlink() or (hasattr(cursor,'is_junction') and cursor.is_junction()):raise ValueError('Symlink/junction destination refused: '+str(cursor))
    cursor=cursor.parent
   result.append((item.filename,dest))
 return result

def install_package(root,archive,manifest,role='main'):
 root=Path(root);safe_archive(archive);targets=destinations(root,archive,role)
 if not targets:raise RuntimeError('No application files for this PC role in the release.')
 backup=root/('Backup-Update-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir();record=[];done=[]
 with tempfile.TemporaryDirectory(prefix='aistudio-stage-') as temp:
  stage=Path(temp)
  with zipfile.ZipFile(archive) as z:
   for i,(member,dest) in enumerate(targets):
    p=stage/str(i);p.write_bytes(z.read(member))
    if dest.suffix.lower() in {'.py','.pyw'}:ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(dest))
    record.append({'destination':str(dest),'backup':str(i),'existed':dest.exists(),'sha256':sha(p)})
  # Snapshot every target before changing any file. Preserve a recoverable journal.
  for item in record:
   dest=Path(item['destination'])
   if item['existed']:shutil.copy2(dest,backup/item['backup'])
  version_path=root/'release_version.json';previous_version=version_path.read_bytes() if version_path.exists() else None
  write(backup/'journal.json',{'state':'prepared','previous_version':base64.b64encode(previous_version).decode() if previous_version else None,'files':record})
  try:
   for i,item in enumerate(record):
    dest=Path(item['destination']);dest.parent.mkdir(parents=True,exist_ok=True);q=dest.with_name(dest.name+'.update-tmp');shutil.copy2(stage/str(i),q);q.replace(dest);done.append(item)
   for item in record:
    if sha(item['destination'])!=item['sha256']:raise RuntimeError('Installed-file verification failed.')
   write(version_path,{'version':manifest['version'],'sequence':manifest['sequence'],'installed':time.time()})
   write(backup/'journal.json',{'state':'complete','previous_version':base64.b64encode(previous_version).decode() if previous_version else None,'files':record})
  except BaseException:
   for item in reversed(done):
    dest=Path(item['destination'])
    if item['existed']:shutil.copy2(backup/item['backup'],dest)
    else:dest.unlink(missing_ok=True)
   if previous_version is None:version_path.unlink(missing_ok=True)
   else:version_path.write_bytes(previous_version)
   raise
 return backup

def check(root,role,log):
 cfg=settings(root)
 if not cfg.get('manifest_url') or not cfg.get('public_key'):raise RuntimeError('Updates not configured: open AI Studio Release Tool and configure the manifest location + trusted public key.')
 body=get_manifest(cfg);cfg['highest_sequence']=max(int(cfg.get('highest_sequence',0)),int(body['sequence']));set_settings(root,cfg)
 if ver(body['version'])<=ver(current_version(root).get('version','0.0.0')):log('Latest stable release already installed.');return False
 if busy(root,role):log('New release available; update deferred because a studio service is running.');return False
 log('Downloading and verifying '+body['version']+'...')
 with tempfile.TemporaryDirectory(prefix='aistudio-release-') as t:
  package=Path(t)/'update.zip';download_asset(cfg,body['package'],package)
  if busy(root,role):raise RuntimeError('A studio service started during download. Update deferred.')
  backup=install_package(root,package,body,role)
 log('Installed '+body['version']+'. Backup: '+str(backup));return True

def sanitize(value):
 if isinstance(value,dict):return {k:('' if any(x in k.casefold() for x in ('token','password','secret','api_key','worker_key','pairing','credential')) else sanitize(v)) for k,v in value.items()}
 if isinstance(value,list):return [sanitize(x) for x in value]
 return value

def snapshot_files(root):
 root=Path(root)
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root);parts=[s.casefold() for s in rel.parts]
  if any(s in SKIP or s.startswith(('backup-','attempt_','.')) for s in parts):continue
  if not p.is_file() or p.is_symlink() or p.stat().st_size>50*1024*1024:continue
  if p.name.casefold() in PROTECTED and p.name.casefold() not in {'config.json','hunyuan_settings.json','service_manager_settings.json'}:continue
  if p.suffix.lower() not in EXTS and p.name.lower() not in {'requirements.txt','license.txt'}:continue
  if p.name.lower().startswith(('install-','collect-','export-')):continue
  yield p,rel

def bundle(root,out,version,worker_code=None):
 root=Path(root);count=0;required={'app.py','ui.html','hunyuan_bridge.py','hunyuan_workflow_api.json'}
 files=list(snapshot_files(root));present={rel.as_posix() for _,rel in files}
 if not required.issubset(present):raise RuntimeError('Missing required project files: '+', '.join(sorted(required-present)))
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for p,rel in files:
   data=p.read_bytes()
   if p.name.casefold() in {'config.json','hunyuan_settings.json','service_manager_settings.json'}:data=json.dumps(sanitize(json.loads(data.decode('utf-8-sig'))),indent=2).encode()
   if p.suffix.lower() in {'.py','.pyw'}:ast.parse(data.decode('utf-8-sig'),filename=str(p))
   z.writestr('AI-Studio-Package/studio/'+rel.as_posix(),data);count+=1
  z.writestr('AI-Studio-Package/studio/release_version.json',json.dumps({'version':version}))
  if worker_code:
   z.writestr('AI-Studio-Package/worker/worker_agent.pyw',worker_code)
   for name in ('studio_update_core.py','studio_update_ui.py','studio_update_launch.pyw'):
    shared=root/name
    if shared.is_file():z.write(shared,'AI-Studio-Package/worker/'+name)
  hs=read(root/'hunyuan_settings.json');node=Path(hs.get('comfy_root',r'C:\ComfyUI_windows_portable\ComfyUI'))/'custom_nodes'/'ai_workflow_portal'
  if not node.is_dir():raise RuntimeError('The required ai_workflow_portal custom node folder is missing.')
  for p in sorted(node.rglob('*')):
   if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix.lower() in {'.py','.json','.md','.txt'}:
    z.write(p,'AI-Studio-Package/custom_nodes/ai_workflow_portal/'+p.relative_to(node).as_posix());count+=1
  z.writestr('AI-Studio-Package/package_info.json',json.dumps({'version':version,'created':time.time(),'file_count':count,'models_included':False}))
 if Path(out).stat().st_size>MAX_PACKAGE:raise RuntimeError('Application-only package exceeds 256 MiB; inspect source folders before publishing.')
 safe_archive(out);return count


def recover(root,role='main'):
 root=Path(root)
 for journal in sorted(root.glob('Backup-Update-*/journal.json')):
  data=read(journal)
  if data.get('state')!='prepared':continue
  if busy(root,role):raise RuntimeError('Interrupted update requires recovery. Close studio services first; do not launch a partial installation.')
  for item in reversed(data.get('files',[])):
   dest=Path(item['destination']);saved=journal.parent/item['backup']
   if item['existed']:
    if not saved.is_file():raise RuntimeError('Missing interrupted-update backup: '+str(saved))
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(saved,dest)
   else:dest.unlink(missing_ok=True)
  previous=data.get('previous_version')
  if previous:(root/'release_version.json').write_bytes(base64.b64decode(previous))
  else:(root/'release_version.json').unlink(missing_ok=True)
  data['state']='recovered';write(journal,data)

def rollback(root,role='main'):
 root=Path(root)
 if busy(root,role):raise RuntimeError('Close all studio services before rollback.')
 choices=[p for p in sorted(root.glob('Backup-Update-*/journal.json'),reverse=True) if read(p).get('state')=='complete']
 if not choices:raise RuntimeError('No completed update backup is available.')
 journal=choices[0];data=read(journal)
 # Refuse if files have been manually edited since this release.
 for item in data['files']:
  dest=Path(item['destination'])
  if not dest.is_file() or sha(dest)!=item['sha256']:raise RuntimeError('A release file was edited after installation; make a manual backup before rollback: '+str(dest))
 for item in reversed(data['files']):
  dest=Path(item['destination'])
  if item['existed']:shutil.copy2(journal.parent/item['backup'],dest)
  else:dest.unlink(missing_ok=True)
 if data.get('previous_version'):(root/'release_version.json').write_bytes(base64.b64decode(data['previous_version']))
 else:(root/'release_version.json').unlink(missing_ok=True)
 data['state']='rolled_back';write(journal,data)
 # Keep highest-seen metadata sequence; explicit local rollback does not lower trust protections.
 return journal.parent
