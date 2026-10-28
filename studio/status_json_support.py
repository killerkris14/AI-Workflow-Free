"""Status JSON reliability support v1. No destructive/non-atomic write fallback."""
import json,os,tempfile,threading,time
from pathlib import Path
_LOCK=threading.RLock();_PATH_LOCKS={}
def _lock(path):
 key=os.path.normcase(os.path.abspath(os.fspath(path)))
 with _LOCK:return _PATH_LOCKS.setdefault(key,threading.RLock())
def _retry(operation,timeout=2.0):
 deadline=time.monotonic()+timeout;attempt=0
 while True:
  try:return operation()
  except OSError as error:
   transient=getattr(error,'winerror',None) in {5,32,33}
   if not transient or time.monotonic()>=deadline:
    if transient and hasattr(error,'add_note'):error.add_note('Status write remained blocked after bounded retries. Check read-only attributes, access permissions, or another process holding the target. Existing JSON was not deleted.')
    raise
   attempt+=1;time.sleep(min(.1,.01*(2**min(attempt,4)),max(0,deadline-time.monotonic())))
def _atomic_unlocked(path,payload):
 path=Path(path);data=json.dumps(payload,indent=2).encode('utf-8');fd=None;name=None
 try:
  fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=str(path.parent))
  with os.fdopen(fd,'wb') as f:
   fd=None;f.write(data);f.flush();os.fsync(f.fileno())
  _retry(lambda:os.replace(name,path));name=None
 finally:
  if fd is not None:
   try:os.close(fd)
   except OSError:pass
  if name is not None:
   try:os.unlink(name)
   except OSError:pass

def atomic_write_json(path,payload):
 with _lock(path):_atomic_unlocked(path,payload)
def update_json(path,changes):
 path=Path(path)
 with _lock(path):
  def read():
   try:return json.loads(path.read_text(encoding='utf-8'))
   except FileNotFoundError:return {}
  previous=_retry(read)
  if not isinstance(previous,dict) or not isinstance(changes,dict):raise ValueError('Status JSON and updates must be objects')
  _atomic_unlocked(path,{**previous,**changes})
