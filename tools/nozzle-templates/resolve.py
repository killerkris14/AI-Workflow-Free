# Resolves Bambu Studio system presets (inherits + include) from profiles.json (made by tools/Collect-Nozzle-Profiles-2.bat).
import json
from pathlib import Path
P=json.load(open(Path(__file__).with_name('profiles.json'),encoding='utf-8'))
def res(kind,name):
    j=P[kind+'/'+name]; out={}
    if j.get('inherits'): out.update(res(kind,j['inherits']))
    for inc in j.get('include',[]) if kind!='machine' else []:
        out.update(res(kind,inc))
    for k,v in j.items():
        if k in ('include','inherits','type','name','from','instantiation','setting_id','description'): continue
        out[k]=v
    return out
