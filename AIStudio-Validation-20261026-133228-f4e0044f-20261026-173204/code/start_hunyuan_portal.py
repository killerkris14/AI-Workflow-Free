import json,subprocess,sys,time,urllib.request,urllib.parse,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
settings=json.loads((ROOT/'hunyuan_settings.json').read_text(encoding='utf-8'))

def online(url):
    try:
        with urllib.request.urlopen(url,timeout=3) as response:return response.status==200
    except Exception:return False

try:
    url=settings['comfy_url'].rstrip('/')
    if not online(url+'/system_stats'):
        comfy=Path(settings['comfy_root']);candidates=[comfy.parent/'python_embeded'/'python.exe',comfy.parent/'python_embedded'/'python.exe',comfy/'.venv'/'Scripts'/'python.exe',comfy/'venv'/'Scripts'/'python.exe']
        python=next((p for p in candidates if p.is_file()),None)
        if python is None:raise RuntimeError('Cannot identify ComfyUI Python. Start ComfyUI using your normal launcher, then rerun this launcher.')
        port=urllib.parse.urlparse(url).port or 8188
        subprocess.Popen([str(python),'-s',str(comfy/'main.py'),'--disable-auto-launch','--port',str(port)],cwd=str(comfy),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
        print('Waiting for ComfyUI to start...',flush=True)
        deadline=time.monotonic()+180
        while not online(url+'/system_stats'):
            if time.monotonic()>deadline:raise RuntimeError('ComfyUI did not become ready. Read its command window.')
            time.sleep(2)
    if online('http://127.0.0.1:8765/'):
        webbrowser.open('http://127.0.0.1:8765/')
    else:
        subprocess.Popen([sys.executable,str(ROOT/'app.py')],cwd=str(ROOT),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
    print('Services started. Use your existing portal at http://127.0.0.1:8765')
    print('Leave the Qwen model router stopped for Hunyuan GPU-memory headroom.')
except Exception as error:
    print('STARTUP ERROR: '+str(error));sys.exit(1)
