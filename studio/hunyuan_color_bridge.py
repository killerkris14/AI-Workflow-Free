# BAMBU_FULL_COLOR_EXPORT_V1
# BAMBU_REGION_CLEANUP_V1
# ALIGNMENT_EVIDENCE_V1
# AUTO_ORIENTATION_SEARCH_V1
# POOR_FIT_VIEW_EXCLUSION_V1
# AUTOMATIC_COLOR_RUN_V1
# MASK_SHEET_CLEANUP_V1
# JOB_AREA_LAYOUT_V1
# AUTO_COLOR_AFTER_EXPORT_V1
# JOB_PROGRESS_BAR_V1
# GEOMETRY_CHECK_V1
# AI_PAINT_STAGE_V1
# STAGE_UNIFY_V1
# AI_PAINT_DEFAULTS_V1
# STUDIO_SHELL_V1
# ARCHIVE_RETENTION_V1
# AI_PAINT_RESULT_FIX_V1
# COLOUR_COUNT_TOGGLE_V1
"""Native reference texture bridge v2.1; uses the existing queue and cancellation worker."""
import ast,hashlib,json,math,re,shutil,subprocess,threading,time,uuid,urllib.parse,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WORKER_SHA256='43846871830b37b9585d7e22d935cc45c86835b0dc93dad493a37b35a37e66d0'
LOCK=threading.RLock();HELPERS=None
SLOTS={'main','front','back','left','right','top','bottom'};DIRECTIONS=SLOTS-{'main'}
ACTIONS={'color_cancel', 'color_preview', 'color_prepare', 'color_approve_masks', 'color_export', 'color_align', 'color_auto'}
ACTIVE={'previewing', 'preparing', 'exporting', 'aligning', 'cancelling'}
PHASE={'preparing': 'color_prepare', 'mask_review': 'color_mask_approval', 'mask_approved': 'color_mask_approved', 'previewing': 'color_preview', 'preview_review': 'color_approval', 'exporting': 'color_export', 'cancelling': 'color_cancelling', 'failed': 'color_failed', 'complete': 'finished', 'cancelled': 'finished', 'idle': 'finished', 'aligning': 'color_align'}
FILES={'alignment.json', 'reference_masks.npz', 'preview_top.png', 'failure.json', 'preview.png', 'model-colored.3mf', 'checks.json', 'model-colored.blend', 'reference_review.json', 'color.log', 'model-colored.glb', 'preview_side.png', 'model-bambu.3mf', 'bambu_report.txt', 'FAIL_REASON.txt', 'reference_masks_raw.npz'}
# AI_PAINT_STAGE_V1: AI paint outputs (model-bambu-aipaint.3mf, previews, report, result, progress log)
FILES|={'model-bambu-aipaint.3mf','aipaint_report.txt','aipaint_result.json','ai_paint.log','aipaint_front.png','aipaint_left.png','aipaint_right.png','aipaint_back.png','aipaint_texture.png'}
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

# BAMBU_FULL_COLOR_EXPORT_V1 (color update 0.002)
def bambu_template_filaments():
 import zipfile
 p=ROOT/'bambu_template.3mf'
 if p.is_symlink() or not p.is_file():raise ValueError('Bambu template missing: reinstall color update 0.002')
 with zipfile.ZipFile(p) as z:c=json.loads(z.read('Metadata/project_settings.config').decode('utf-8-sig')).get('filament_colour')
 if not isinstance(c,list) or not 1<=len(c)<=16:raise ValueError('Bambu template has no usable filament list')
 return len(c)

# AI_PAINT_STAGE_V1: optional module; the studio works unchanged without it (picture method only).
def ai_paint_stage():
 import importlib,sys as _s
 if str(ROOT) not in _s.path:_s.path.insert(0,str(ROOT))
 return importlib.import_module('ai_paint_stage')
# AI_PAINT_DEFAULTS_V1: unless "Custom AI paint settings" was ticked at upload, AI paint always uses these best settings
AI_PAINT_BEST={'enabled':True,'filaments':4,'colours':'studio'}
def ai_paint_custom(job):
 try:return load(job/'request.json').get('ai_paint_custom') is True
 except Exception:return False
def ai_paint_best(job):
 # COLOUR_COUNT_TOGGLE_V1 + CUSTOM_COLOUR_COUNT_V1: the upload form's 4 / 9 / custom 5-8 choice (request.json ai_paint_filaments); older jobs = 4
 try:n=load(job/'request.json').get('ai_paint_filaments')
 except Exception:n=None
 return dict(AI_PAINT_BEST,filaments=n if type(n) is int and 4<=n<=9 else AI_PAINT_BEST['filaments'],**({'props':True} if has_props(job) else {}),**({'nozzle':0.4} if nozzle_mm(job)==0.4 else {}))
# NOZZLE_OPTION_V1 (0.018): the upload form's 0.4 / 0.6 mm toggle (request.json nozzle_mm); older jobs = 0.6
def nozzle_mm(job):
 try:return 0.4 if load(job/'request.json').get('nozzle_mm')==0.4 else 0.6
 except Exception:return 0.6
# PROPS_TOGGLE_V1 (0.017): the upload form's "Has props included" toggle (request.json has_props); older jobs = no props
def has_props(job):
 try:return load(job/'request.json').get('has_props') is True
 except Exception:return False
def with_props(ap,job):
 if ap and has_props(job):ap['props']=True   # from the upload only, never from the export box
 elif ap:ap.pop('props',None)
 if ap and nozzle_mm(job)==0.4:ap['nozzle']=0.4   # NOZZLE_OPTION_V1: from the upload only
 elif ap:ap.pop('nozzle',None)
 return ap
# AUTO_REVIEW_V1 (0.018): the colour review is approved automatically when the automatic preview fits; same export as the
# one-click Export button with its defaults (all template filaments, unobserved -> main colour, specks 4 mm2, shading kept,
# neutral areas accepted, AI paint with the upload's settings). Switch off with "auto_approve_color": false in config.json.
AUTO_MIN_VIEW_IOU=0.70   # real jobs 2026-10-30: lowest view fit 0.81 (all approved by you); poor-fit exclusion in the worker is 0.30
def auto_color_reasons(job,r,cfg):
 if (cfg or {}).get('auto_approve_color',True) is False:return ['automatic approval is switched off (auto_approve_color in config.json)']
 try:adv=load(Path(job)/'request.json').get('advanced_review') is True   # ADVANCED_REVIEW_V1: upload toggle
 except Exception:adv=False
 if adv:return ['"Advanced mesh and paint" was ticked at upload, so you review the colours yourself']
 why=[]
 if ai_paint_custom(job):why.append('custom AI paint settings were chosen at upload')
 else:
  try:
   info=ai_paint_info();best=ai_paint_best(job)
   if not info['install'].get('installed'):why.append('AI paint is not installed')
   else:ai_paint_stage().options(best,ROOT)
  except Exception as e:why.append('AI paint settings not usable: '+str(e))
 ev=(r.get('alignment_evidence') or {}).get('views') or {};al={v.get('slot'):v for v in (r.get('alignment') or {}).get('views') or []}
 if not ev and not al:why.append('no alignment evidence in the preview')
 for slot in sorted(set(ev)|set(al)):
  iou=(ev.get(slot) or {}).get('iou',(al.get(slot) or {}).get('proposed_iou'))
  if iou is None or iou<AUTO_MIN_VIEW_IOU:why.append('the %s picture fits the model poorly (IoU %s, needs %.2f)'%(slot,'?' if iou is None else round(iou,2),AUTO_MIN_VIEW_IOU))
  if (al.get(slot) or {}).get('poor_fit'):why.append('the %s picture was marked as a poor fit'%slot)
 ex=(r.get('statistics') or {}).get('excluded_views') or {}
 for slot,reason in sorted(ex.items()):why.append('the %s picture was left out of the colours (%s)'%(slot,reason))
 try:bambu_template_filaments()
 except Exception as e:why.append('Bambu template problem: '+str(e))
 return why
def auto_export_config(job,config,r):
 ec=dict(config);ec['bambu']={'filaments':bambu_template_filaments(),'unobserved':'dominant','min_region_mm2':4.0,'shading':'keep'}
 ec['ai_paint']=ai_paint_stage().options(ai_paint_best(job),ROOT)
 ec.update(approved_preview_fingerprint=r['preview_fingerprint'],accept_uncovered=True,auto_review_color={'approved':True,'min_view_iou':AUTO_MIN_VIEW_IOU})
 return ec
def ai_paint_info():
 try:
  m=ai_paint_stage();return {'install':m.install_status(ROOT),'filaments':m.template_counts(ROOT),'colours':list(m.COLOURS)}
 except Exception as e:return {'install':{'installed':False,'problems':['AI paint module unavailable: '+str(e)]},'filaments':[],'colours':[]}
def ai_paint_cancelled(job):
 def check():
  import job_cancel
  try:st=load(job/'status.json')
  except Exception:st={}
  ctx=job_cancel.ACTIVE.get(job.name)
  return bool(st.get('cancelled') or st.get('cancel_requested') or (ctx and ctx.event.is_set()))
 return check

# STAGE_UNIFY_V1 (AI UI Unifi 0.015): ONE 12-stage list for every Hunyuan job, computed here from the files the workers write.
STAGES=['Queued','Image analysis & preparation','Checkpoint 1: approve images','Generating mesh','Mesh check & repair','Checkpoint 2: approve mesh','Mesh export','Colour: masks','Colour: alignment','Colour: texture preview','Colour: review & approve','Colour export + AI paint']
COLOR_STAGE={'color_prepare':8,'color_mask_approval':8,'color_mask_approved':9,'color_align':9,'color_preview':10,'color_approval':11,'color_export':12}
COLOR_PHASE={'preparing':8,'mask_review':8,'mask_approved':9,'aligning':9,'previewing':10,'preview_review':11,'exporting':12}
GEOMETRY_STAGE={'prepare':2,'route_analyze':2,'route_review':3,'image_approval':3,'generate':4,'reprocess':5,'model_approval':6,'joint_design':6,'export':7}
def color_reached(job,s):
 # last colour stage a stopped/failed colour run had reached, from the files it left (never guessed beyond them)
 try:folder=folder_for(job,s['version'])
 except Exception:return 8
 try:cfg=load(folder/'settings.json') if (folder/'settings.json').is_file() else {}
 except Exception:cfg={}
 if cfg.get('approved_preview_fingerprint'):return 12
 if (folder/'checks.json').is_file():return 11
 if cfg.get('reference_approval_fingerprint'):return 9
 return 8
def stage_info(job):
 st=load(job/'status.json');state=st.get('state') or '';engine=st.get('engine') or ''
 if (job/'request.json').is_file():engine=load(job/'request.json').get('engine',engine)
 if engine!='hunyuan':return {'engine':engine or 'procedural'}
 p=load(job/'hunyuan_progress.json') if (job/'hunyuan_progress.json').is_file() else {};ps=str(p.get('stage') or '')
 s=None
 if p.get('color_protocol')==2 and (job/'reference_color_state_v2.json').is_file():
  try:s=current(job)
  except Exception:s=None
 phase=(s or {}).get('phase') if s and s.get('version')==p.get('color_version') else None
 kind='running';index=1
 if ps in COLOR_STAGE:index=COLOR_STAGE[ps]
 elif phase in COLOR_PHASE:index=COLOR_PHASE[phase]
 elif phase=='complete':index=12;kind='done'
 elif phase in {'failed','cancelled','cancelling','color_failed'} or ps in {'color_failed','color_cancelling'}:index=color_reached(job,s);kind='stopped'
 elif state=='QUEUED' and ps=='prepare' and not p.get('autoroute'):index=1
 elif ps=='generate':index=5 if state=='RUNNING_BLENDER' else 4
 elif ps in GEOMETRY_STAGE:index=GEOMETRY_STAGE[ps]
 elif ps=='finished' or state=='SUCCEEDED':index=7;kind='done'
 if state in {'FAILED','INTERRUPTED'} or st.get('cancelled'):kind='stopped'
 elif state.startswith('WAITING_') and kind!='done':kind='waiting'
 elif state=='QUEUED' and kind!='done':kind='queued'
 elif state=='SUCCEEDED' and kind=='running' and not st.get('cancel_requested'):kind='waiting'
 task=console_tail(job)
 frac=(task.get('progress') or {}).get('percent') if kind=='running' and task.get('running') else None
 done=index if kind=='done' else index-1
 overall=100.0*(done+((frac or 0)/100.0 if kind=='running' else 0))/len(STAGES)
 return {'engine':'hunyuan','stages':STAGES,'count':len(STAGES),'index':index,'title':STAGES[index-1],'kind':kind,'state':state,'stage':ps,'color_phase':phase,
         'overall_percent':round(overall,1),'note':st.get('note') or '','error':st.get('error') or '','task':task}

# JOB_AREA_LAYOUT_V1: last lines of the job's most recently written task log, for the live log box.
def console_tail(job,count=5):
 import time
 newest=None
 for pattern in ('*.log','attempt_*/*.log','color_versions/*/*.log'):
  for p in job.glob(pattern):
   if p.is_symlink() or not p.is_file():continue
   t=p.stat().st_mtime
   if newest is None or t>newest[0]:newest=(t,p)
 # While a job is running, the AI services (ComfyUI, model router) work for it: include their logs.
 idle={'SUCCEEDED','FAILED','INTERRUPTED','WAITING_IMAGE_APPROVAL','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'}
 try:running=load(job/'status.json').get('state') not in idle
 except Exception:running=False
 service=None
 if running:
  for name,label in (('comfy','ComfyUI'),('router','Model router (llama)')):
   p=ROOT/'logs'/('service-'+name+'.log')
   if p.is_file() and not p.is_symlink() and (newest is None or p.stat().st_mtime>newest[0]):newest=(p.stat().st_mtime,p);service=label
 if newest is None:return {'file':None,'modified':None,'lines':[]}
 with newest[1].open('rb') as f:
  f.seek(0,2);size=f.tell();f.seek(max(0,size-16384));data=f.read()
 all_rows=[r for r in data.decode('utf-8','replace').replace('\r\n','\n').replace('\r','\n').split('\n') if r.strip()];rows=all_rows[-count:]
 # JOB_PROGRESS_BAR_V1: the newest 'NN%' or 'k/N' counter in the active log (ComfyUI/tqdm and similar tools print these).
 progress=None
 for row in reversed(all_rows[-60:]):
  m=re.search(r'(\d{1,3})%\|',row) or re.search(r'(?<![\d.])(\d{1,4})/(\d{1,4})(?![\d.])',row)
  if m:
   value=float(m.group(1)) if m.re.pattern.endswith('\\|') else 100*int(m.group(1))/max(int(m.group(2)),1)
   if 0<=value<=100:progress={'percent':round(value,1),'line':row[-160:]};break
 return {'running':running,'progress':progress,'file':(service+' \u00b7 logs/'+newest[1].name) if service else newest[1].relative_to(job).as_posix(),'modified':time.strftime('%H:%M:%S',time.localtime(newest[0])),'lines':[r[-400:] for r in rows]}

def folder_for(job,version):
 if not isinstance(version,str) or not re.fullmatch('[a-f0-9]{16}',version):raise ValueError('Invalid color version')
 parent=job/'color_versions';folder=parent/version
 if parent.is_symlink() or folder.is_symlink() or folder.resolve().parent!=parent.resolve() or job.resolve() not in folder.resolve().parents:raise ValueError('Unsafe color directory')
 return folder

def asset(folder,name):
 if not isinstance(name,str) or Path(name).name!=name or (name not in FILES and not re.fullmatch(r'(reference|mask|overlay|fit)_(main|front|back|left|right|top|bottom)\.png',name)):raise ValueError('Unknown asset')
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
  if not isinstance(v,dict) or set(v)-set(defaults)-{'direction','color_use'}:raise ValueError('Unknown alignment setting')
  v={**defaults,**v};v['direction']=v.get('direction',hint);use=v.pop('color_use','auto')
  if use not in {'auto','on','off'}:raise ValueError('Invalid color use for '+slot)
  if use!='auto':v['color_use']=use
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
     b=(r.get('export') or {}).get('bambu') if s['phase']=='complete' and not d.get('source_changed') else None
     if b and (folder/'model-bambu.3mf').is_file() and (folder/'bambu_report.txt').is_file() and b.get('sha256')==digest(asset(folder,'model-bambu.3mf')) and b.get('report_sha256')==digest(asset(folder,'bambu_report.txt')):d['bambu']=b
     try:d['bambu_template_filaments']=bambu_template_filaments()
     except Exception as e:d['bambu_template_problem']=str(e)
     # AI_PAINT_STAGE_V1
     d['ai_paint_options']=ai_paint_info();d['ai_paint_custom']=ai_paint_custom(job);d['ai_paint_best']=ai_paint_best(job)
     if s['phase']=='complete' and not d.get('source_changed'):
      # AI_PAINT_RESULT_FIX_V1: the export stores the AI paint outcome in status.json 'checks' (state(...,checks=...)), not in
      # final/checks.json, so the old read never found it and the page offered the picture-method file. Read status.json first;
      # if that record is gone, the hash-verified aipaint_result.json of this colour version decides.
      sc=d['status'].get('checks') if isinstance(d['status'].get('checks'),dict) else {}
      a=next((c['ai_paint'] for c in (sc,checks) if isinstance(c.get('ai_paint'),dict) and c['ai_paint'].get('version')==s['version']),None)
      if a is None and (folder/'aipaint_result.json').is_file():a={'ok':True,'version':s['version']}
      if a:
       d['ai_paint']={k:a.get(k) for k in ('ok','error','stage','fail_reason','cancelled','options')}
       if a.get('ok'):
        try:v_=ai_paint_stage().verified_result(folder)
        except Exception as e:v_=None;d['ai_paint']['problem']=str(e)
        if v_:d['ai_paint'].update(v_)
        else:d['ai_paint'].update(ok=False,error='AI paint files changed or missing since they were made - export again')
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
   if choice in {'color_prepare','color_auto'}:
    p=load(job/'hunyuan_progress.json');st=load(job/'status.json');resume=s['phase']=='cancelled' and p.get('color_protocol')==2 and p.get('color_version')==s.get('version') and p.get('stage')=='finished' and st.get('cancelled')
    if (st.get('state')!='SUCCEEDED' and not str(p.get('stage','')).startswith('color_') and not resume) or (s['phase']=='idle' and str(p.get('stage','')).startswith('color_')):raise ValueError('Export current mesh, or close the legacy color review first')
    cfg=baseconfig(job,payload.get('confirm_bind_unhashed_source') is True);helpers()['source_info'](cfg);cfg['settings']=normalize(payload.get('settings',{'views':{}}),v,False);s=persist(job,s,auto_color=choice=='color_auto');return enqueue(job,s,'prepare',cfg)
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
   if normalize(payload.get('settings'),v)!=normalize(cfg['settings'],v):raise ValueError('Settings changed: rebuild preview')
   b=payload.get('bambu') if isinstance(payload.get('bambu'),dict) else {};count=b.get('filaments');policy=b.get('unobserved','dominant');limit=bambu_template_filaments()
   if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=limit:raise ValueError('Choose 1-%d Bambu filament colors (template limit)'%limit)
   if policy not in {'dominant','gray'} or (policy=='gray' and count<2):raise ValueError('Choose how unobserved areas are printed (gray needs 2+ colors)')
   region=b.get('min_region_mm2',0)
   if isinstance(region,bool) or not isinstance(region,(int,float)) or not math.isfinite(region) or not 0<=region<=50:raise ValueError('Minimum color region must be 0-50 mm2')
   shading=b.get('shading','keep')
   if shading not in {'keep','reduce'}:raise ValueError('Choose whether to keep or reduce drawn shading')
   cfg['bambu']={'filaments':count,'unobserved':policy,'min_region_mm2':float(region),'shading':shading}
   # AI_PAINT_STAGE_V1: optional extra Bambu file painted by the AI (validated here, before anything is queued)
   if ai_paint_custom(job):ap=with_props(ai_paint_stage().options(payload.get('ai_paint'),ROOT) if payload.get('ai_paint') is not None else None,job)
   else:
    info=ai_paint_info();best=ai_paint_best(job);ap=ai_paint_stage().options(best,ROOT) if info['install'].get('installed') and best['filaments'] in info['filaments'] else None
   if ap:cfg['ai_paint']=ap
   else:cfg.pop('ai_paint',None)
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
   # AI_PAINT_STAGE_V1: picture-method export verified first; then the AI paint file (minutes; LOCK is not held meanwhile)
   ai=None
   if task.mode=='export':
    econfig=load(folder/'settings.json')
    if econfig.get('ai_paint'):
     preview_check(folder,econfig,True)
     with LOCK:
      s=sync_cancel(job,current(job))
      if not matches(s,task):return
      state(job,'RUNNING_BLENDER',note='Picture-method Bambu file done. AI paint running (about 10-15 minutes; progress bar below).')
     m=ai_paint_stage();ai={'version':task.version,'options':econfig['ai_paint']}
     try:
      res=m.run(ROOT,folder,econfig['ai_paint'],cfg['blender_exe'],ai_paint_cancelled(job),versions={'blender':cfg.get('blender_exe'),'studio_python':__import__('sys').version.split()[0]})
      ai.update(ok=True,file='model-bambu-aipaint.3mf',sha256=res['files']['model-bambu-aipaint.3mf'],result_sha256=res['result_sha256'])
     except m.Cancelled as e:ai.update(ok=False,cancelled=True,error=str(e))
     except Exception as e:
      ai.update(ok=False,error=(str(e).strip().splitlines() or [type(e).__name__])[0][:600],stage='AI paint',fail_reason=str(folder/'ai_paint_work'/'FAIL_REASON.txt'),traceback=traceback.format_exc()[-3000:])
   with LOCK:
    s=sync_cancel(job,current(job))
    if not matches(s,task):return
    config=load(folder/'settings.json')
    if task.mode=='prepare':r=reference_check(folder,config);s=persist(job,s,'mask_review',task_nonce=None,reference_fingerprint=r['reference_fingerprint']);note='Inspect all source/mask/overlay images before approving.'
    elif task.mode in {'preview','align'}:r=preview_check(folder,config);s=persist(job,s,'preview_review',task_nonce=None,preview_fingerprint=r['preview_fingerprint'],settings=config['settings']);note='Texture preview ready. Compare all views and neutral unobserved regions.'
    else:
     r=preview_check(folder,config,True)
     if config.get('approved_preview_fingerprint')!=s.get('preview_fingerprint') or r.get('preview_fingerprint')!=s.get('preview_fingerprint'):raise ValueError('Export approval changed')
     s=persist(job,s,'complete',task_nonce=None);note='Exported texture master and Bambu full-color project (model-bambu.3mf). Open it in Bambu Studio and confirm the painted colors before printing.'
    checks=load(job/'final/checks.json');checks['color_workflow']=r;error=''
    # AI_PAINT_STAGE_V1: the AI paint outcome is reported, never hidden; a failure leaves the picture-method file usable
    if task.mode=='export':
     checks['ai_paint']=ai
     if ai and ai.get('ok'):note='Exported your Bambu full-color 3MF (AI paint). Open it in Bambu Studio and check the colours before printing.'
     elif ai:error='AI paint FAILED: '+str(ai.get('error'))+' - see '+str(ai.get('fail_reason') or 'ai_paint_work')+'. The picture-method file model-bambu.3mf is still valid.'
    state(job,'SUCCEEDED' if task.mode=='export' else 'WAITING_MODEL_APPROVAL',checks=checks,error=error,note=note)
    # AUTOMATIC_COLOR_RUN_V1: one click runs masks -> approval -> auto-align -> preview, then stops for final review.
    if s.get('auto_color') and task.mode=='prepare':
     config['reference_approval_fingerprint']=r['reference_fingerprint'];config['masks_auto_approved']=True;save(folder/'settings.json',config);s=persist(job,s,'mask_approved',reference_approved=True)
     config['settings']=normalize(config.get('settings',{'views':{}}),views(job),False);config.pop('approved_preview_fingerprint',None);config.pop('accept_uncovered',None);enqueue(job,s,'align',config,s['version'])
    elif s.get('auto_color') and task.mode in {'align','preview'}:   # AUTO_REVIEW_V1
     why=auto_color_reasons(job,r,cfg);ec=None
     if not why:
      try:ec=auto_export_config(job,config,r)
      except Exception as e:why=['the automatic export could not be prepared: '+str(e)]
     s=persist(job,s,auto_color=False)
     if why:state(job,'WAITING_MODEL_APPROVAL',checks=checks,error='',note='Texture preview ready. Automatic approval stopped for your review: '+'; '.join(why)+'.')
     else:enqueue(job,s,'export',ec);state(job,'QUEUED',error='',note='Colour review passed automatically (every picture fits the model). Exporting the Bambu file with AI paint.')
    elif s.get('auto_color'):persist(job,s,auto_color=False)
  except Exception:
   detail=traceback.format_exc()
   try:(folder/'FAIL_REASON.txt').write_text('AI MODELING STUDIO - COLOR STAGE FAILURE\nColor update: 0.002\nJob: %s\nColor version: %s\nStage: %s\nWorker: %s (sha256 %s)\nBlender: %s\nInputs: %s (settings.json, reference_*.png, reference_masks.npz)\nLog: %s\n\nERROR / TRACEBACK:\n%s\n\nNEXT DIAGNOSTIC STEP:\n%s\n'%(job.name,task.version,task.mode,ROOT/'hunyuan_color.py',WORKER_SHA256,cfg.get('blender_exe'),folder,folder/'color.log',detail,'Bambu export: check bambu_template.3mf and the filament count, then send this file and color.log.' if task.mode=='export' else 'Send this file and color.log from the folder above. Earlier stage outputs are retained unchanged.'),encoding='utf-8')
   except Exception as report_error:print('FAIL_REASON.txt could not be written: '+str(report_error),flush=True)
   with LOCK:
    s=sync_cancel(job,current(job))
    if matches(s,task):persist(job,s,'failed',task_nonce=None,error=detail[-3000:],auto_color=False)
   raise
 def process(job):
  p=load(Path(job)/'hunyuan_progress.json')
  if p.get('color_protocol')==2 and str(p.get('stage','')).startswith('color_'):return
  result=previous_process(job)
  # AUTO_COLOR_AFTER_EXPORT_V1: once a geometry export succeeds, start Automatic color by itself (same checks as the button).
  try:
   if load(Path(job)/'status.json').get('state')=='SUCCEEDED' and context['config']().get('auto_color_after_export',True):schedule_auto_color(Path(job))
  except Exception:pass
  return result
 def schedule_auto_color(job):
  def run():
   for _ in range(240):
    time.sleep(.5)
    with LOCK:
     if not idle(job):continue
     try:
      s=sync_cancel(job,current(job));p=load(job/'hunyuan_progress.json');st=load(job/'status.json')
      if s['phase']!='idle' or st.get('state')!='SUCCEEDED' or str(p.get('stage','')).startswith('color_') or load(job/'request.json').get('engine')!='hunyuan':return
      if not context['config']().get('allow_generated_code_execution'):return
      v=views(job);cfg=baseconfig(job,False);helpers()['source_info'](cfg);cfg['settings']=normalize({'views':{}},v,False)
      s=persist(job,s,auto_color=True);enqueue(job,s,'prepare',cfg)
     except Exception as error:
      (job/'color_autostart.txt').write_text('Automatic color did not start: '+str(error)+'\nUse the Automatic color button.\n',encoding='utf-8')
     return
  threading.Thread(target=run,daemon=True,name='auto-color-'+job.name).start()
 def install(main):
  previous_install(main);old=main['Handler'];previous_dispatch=main['process']
  # ARCHIVE_RETENTION_V1: archived jobs are deleted after the time in archive_retention.json (default 24 h), logged in logs/
  try:
   import archive_retention;archive_retention.start(main)
  except Exception as e:print('Archive auto-delete did not start: '+str(e),flush=True)
  def dispatch(job):
   if isinstance(job,ColorTask):return run_task(job)
   return previous_dispatch(job)
  main['process']=dispatch
  class ColorHandler(old):
   def reply(self,code,content,kind='application/json'):
    if code==200 and kind.startswith('text/html'):
     script=(ROOT/'hunyuan_color_ui.js').read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',main['TOKEN']);content=(content.decode('utf-8') if isinstance(content,bytes) else content)+'<script>'+script+'</script>'
     layout=ROOT/'job_layout_ui.js'
     if layout.is_file():content+='<script>'+layout.read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',main['TOKEN'])+'</script>'
     shell=ROOT/'studio_shell_ui.js'   # STUDIO_SHELL_V1: header, page tabs, Prompt Builder, .3mf Repair (runs last)
     if shell.is_file():content+='<script>'+shell.read_text(encoding='utf-8')+'</script>'
    return super().reply(code,content,kind)
   def do_GET(self):
    url=urllib.parse.urlsplit(self.path)
    if not url.path.startswith('/hunyuan-color/'):return super().do_GET()
    if not self.authorized():return self.reply(403,{'error':'Invalid workflow key'})
    try:
     parts=url.path.strip('/').split('/')
     with main['ARCHIVE_LOCK'],LOCK:
      # GEOMETRY_CHECK_V1: evidence for checkpoint 2 (tries, reasons, fixes, fit pictures of the shown try).
      if len(parts)==3 and parts[1]=='geometry':
       job=main['get_job'](parts[2]);p=load(job/'hunyuan_progress.json');n=int(p.get('candidate',1));check=job/('attempt_%02d'%n)/'geometry_check'/'geometry_check.json'
       return self.reply(200,{'tries':p.get('geometry_tries',[]),'shown_candidate':n,'check':load(check) if check.is_file() else None})
      if len(parts)==5 and parts[1]=='geometry':
       job=main['get_job'](parts[2]);name=parts[4]
       if not re.fullmatch(r'\d{1,3}',parts[3]) or not re.fullmatch(r'fit_(front|back|left|right|top|main)\.png',name):raise ValueError('Unknown geometry evidence')
       folder=job/('attempt_%02d'%int(parts[3]))/'geometry_check';path=folder/name
       if path.is_symlink() or not path.is_file() or path.resolve().parent!=folder.resolve():raise ValueError('Evidence unavailable')
       return self.reply(200,path.read_bytes(),'image/png')
      if len(parts)==2 and parts[1]=='version':
       v=load(ROOT/'color_update_version.json') if (ROOT/'color_update_version.json').is_file() else {}
       return self.reply(200,{'version':v.get('version'),'build':v.get('build'),'installed':v.get('installed')})
      if len(parts)==3 and parts[1]=='detail':return self.reply(200,details(main['get_job'](parts[2])))
      if len(parts)==3 and parts[1]=='console':return self.reply(200,console_tail(main['get_job'](parts[2])))
      if len(parts)==3 and parts[1]=='stage':return self.reply(200,stage_info(main['get_job'](parts[2])))
      if len(parts)==4 and parts[1]=='prepared':
       job=main['get_job'](parts[2]);name=parts[3]
       if not re.fullmatch(r'(front|back|left|right|top|main)\.png',name):raise ValueError('Unknown prepared view')
       path=job/'autoroute_prepared'/name
       if path.is_symlink() or not path.is_file() or path.resolve().parent!=(job/'autoroute_prepared').resolve():raise ValueError('Prepared view unavailable')
       return self.reply(200,path.read_bytes(),'image/png')
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
