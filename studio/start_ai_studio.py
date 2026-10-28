"""One-button portal launcher. AI engines start only when the portal's worker needs them."""
import subprocess,sys,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8765'
try:
    try:
        with urllib.request.urlopen(URL+'/',timeout=3) as response:running=response.status==200
    except Exception:running=False
    if running:
        webbrowser.open(URL+'/');print('Studio already running. Opened existing portal.');sys.exit(0)
    print('Starting AI Modeling Studio. ComfyUI and Qwen stay off until needed.',flush=True)
    print('Use the portal Power menu to stop engines or power off. Keep this window open.',flush=True)
    sys.exit(subprocess.call([sys.executable,str(ROOT/'app.py')],cwd=str(ROOT)))
except KeyboardInterrupt:
    print('Shutdown requested. Use Power off studio for a clean shutdown if an engine is still running.')
except Exception as error:
    print('STARTUP FAILED: '+str(error));sys.exit(1)
