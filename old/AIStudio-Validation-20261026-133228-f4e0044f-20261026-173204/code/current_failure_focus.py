"""Current-stage-first failure reporting. Does not mix old mesh errors into color failures."""
import json,re,os,tempfile,time
from pathlib import Path

def _text(path,limit=18000):
 path=Path(path)
 if path.is_symlink() or not path.is_file():return ''
 try:
  with path.open('rb') as f:
   size=path.stat().st_size
   if size>limit*4:f.seek(max(0,size-limit*4))
   return f.read(limit*4).decode('utf-8-sig',errors='replace')[-limit:]
 except OSError as error:return '(Could not read '+path.name+': '+str(error)+')'
def _json(path):
 try:
  value=json.loads(_text(path,120000));return value if isinstance(value,dict) else {}
 except Exception:return {}
def _valid(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{16}',value) is not None

def focused_report(job,error_hint=''):
 job=Path(job);status=_json(job/'status.json');progress=_json(job/'hunyuan_progress.json');color=_json(job/'reference_color_state_v2.json');state=status.get('state');stage=str(progress.get('stage',''))
 if state not in {'FAILED','INTERRUPTED'}:return None
 header=['AI WORKFLOW - CURRENT FAILURE','Job: '+job.name,'State: '+str(state),'Current stage: '+(stage or '(not recorded)')];primary='';log='';log_name='';notes=[]
 if stage.startswith('color_'):
  version=progress.get('color_version');other=color.get('version');header+=['Color phase: '+str(color.get('phase')),'Current color version: '+str(version)]
  if _valid(version) and (not _valid(other) or other==version):
   folder=job/'color_versions'/version
   if not folder.is_symlink() and not (job/'color_versions').is_symlink():
    error_path=folder/'failure.json';log_path=folder/'color.log';failure=_json(error_path);fresh=True
    try:fresh=not log_path.is_file() or not error_path.is_file() or error_path.stat().st_mtime>=log_path.stat().st_mtime-5
    except OSError:pass
    if fresh:primary=str(failure.get('error',''))
    log=_text(log_path,2500);log_name=str(log_path);header.append('Current run folder: '+str(folder))
   notes.append('Older mesh-attempt failures are omitted from this current color report; their files remain in attempt/review history.')
  else:notes.append('Color-version metadata is missing/inconsistent; no older version was guessed.')
  if not primary:primary=str(color.get('error') or error_hint or status.get('error') or _text(job/'error.txt',4500))
 else:
  primary=str(error_hint or status.get('error') or _text(job/'error.txt',4500));candidate=progress.get('candidate',1)
  try:candidate=max(1,int(candidate))
  except (TypeError,ValueError):candidate=1
  attempt=job/('attempt_%02d'%candidate);header.append('Candidate: '+str(candidate));log_path=attempt/'blender.log';log_name=str(log_path);log=_text(log_path,2300)
  notes.append('This report prioritizes the current job error. Older generation_error.txt files are not treated as the current cause.')
 if not primary:primary='No current traceback was recorded. Inspect the current run log below; do not infer the cause from older attempts.'
 report='\n'.join(header)+'\n\nCURRENT ERROR / TRACEBACK:\n'+primary[-4300:]
 if log:report+='\n\nCURRENT RUN LOG (tail):\n'+log[-2100:]+'\nLog: '+log_name
 if notes:report+='\n\nREPORT NOTES:\n'+'\n'.join(notes)
 return report[:7950]+'\n[End current-failure report]' if len(report)>7990 else report

def save_current_report(job,text):
 path=Path(job)/'CURRENT_FAILURE_REPORT.txt';name=None
 try:
  fd,name=tempfile.mkstemp(prefix='.current-failure-',suffix='.tmp',dir=str(path.parent))
  with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
  deadline=time.monotonic()+.5
  while True:
   try:os.replace(name,path);name=None;return
   except OSError as error:
    if getattr(error,'winerror',None) not in {5,32,33} or time.monotonic()>=deadline:return
    time.sleep(.04)
 except OSError:return
 finally:
  if name:
   try:os.unlink(name)
   except OSError:pass
