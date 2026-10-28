"""Silhouette-based automatic reference alignment v1 + AUTO_ORIENTATION_SEARCH_V1 (0.005).
Uses a temporary decimated proxy for scoring only; full-resolution images and approved
source geometry are untouched. Orthographic projection; no semantic landmark solver.
"""
import bpy,numpy as np,math,json,time,hashlib
from pathlib import Path

def raster(vertices,triangles,w,h):
 image=np.zeros((h,w),bool)
 for indices in triangles:
  p=vertices[indices];x0=max(0,int(np.floor(p[:,0].min())));x1=min(w-1,int(np.ceil(p[:,0].max())));y0=max(0,int(np.floor(p[:,1].min())));y1=min(h-1,int(np.ceil(p[:,1].max())))
  if x0>x1 or y0>y1:continue
  a,b,c=p;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-9:continue
  yy,xx=np.mgrid[y0:y1+1,x0:x1+1];xx=xx+.5;yy=yy+.5;u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den;v=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den
  image[y0:y1+1,x0:x1+1]|=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
 return image

def view_parameters(coords,mask,settings,W):
 right,up,toward=W['basis'](settings);yy,xx=np.where(mask);x=coords@right;y=coords@up;extent=np.array([np.ptp(x),np.ptp(y)])
 if min(extent)<1e-10:raise ValueError('Degenerate camera extent')
 crop=np.array([xx.max()-xx.min()+1,yy.max()-yy.min()+1]);center=np.array([(xx.max()+xx.min()+1)/2,(yy.max()+yy.min()+1)/2])+np.array([settings['offset_x'],settings['offset_y']])*crop
 return {'right':right,'up':up,'toward':toward,'world_center':np.array([(x.min()+x.max())/2,(y.min()+y.max())/2]),'center':center,'scale':float(np.min(crop*.98/extent))*settings['scale'],'settings':settings}

def score_pose(full,proxy,triangles,mask,settings,W,resolution=112):
 h,w=mask.shape;ratio=min(resolution/w,resolution/h);rw=max(8,int(round(w*ratio)));rh=max(8,int(round(h*ratio)));target=mask[np.minimum((np.arange(rh)+.5)*h/rh,h-1).astype(int)[:,None],np.minimum((np.arange(rw)+.5)*w/rw,w-1).astype(int)[None,:]]
 params=view_parameters(full,mask,settings,W);xy=W['project'](proxy,params)*np.array([rw/w,rh/h]);rendered=raster(xy,triangles,rw,rh);union=np.count_nonzero(rendered|target)
 return float(np.count_nonzero(rendered&target)/union) if union else 0.

def proxy_mesh(items,budget=2400):
 full=[];vertices=[];triangles=[];offset=0;total=sum(max(len(o.data.polygons),1) for o in items);scene=bpy.context.scene
 for obj in items:
  full.extend(tuple(obj.matrix_world@v.co) for v in obj.data.vertices);clone=obj.copy();clone.data=obj.data.copy();clone.parent=None;clone.matrix_world=obj.matrix_world;scene.collection.objects.link(clone);data=clone.data
  try:
   clone.modifiers.clear();quota=max(80,int(budget*max(len(obj.data.polygons),1)/max(total,1)))
   if len(data.polygons)>quota:
    mod=clone.modifiers.new('AlignmentProxyOnly','DECIMATE');mod.ratio=max(.001,min(1.,quota/len(data.polygons)))
   bpy.context.view_layer.update();evaluated=clone.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
   try:
    mesh.calc_loop_triangles();vertices.extend(tuple(evaluated.matrix_world@v.co) for v in mesh.vertices);triangles.extend(tuple(offset+int(i) for i in t.vertices) for t in mesh.loop_triangles);offset+=len(mesh.vertices)
   finally:evaluated.to_mesh_clear()
  finally:
   bpy.data.objects.remove(clone,do_unlink=True)
   if data.users==0:bpy.data.meshes.remove(data)
 return np.asarray(full,float),np.asarray(vertices,float),np.asarray(triangles,int)

def wrapped(angle):return (float(angle)+180)%360-180

# AUTO_ORIENTATION_SEARCH_V1 (color update 0.005)
OPPOSITE={'front':'back','back':'front','left':'right','right':'left','top':'bottom','bottom':'top'}
QUARTER_TURNS=[0.,90.,180.,-90.]
SWAP_MARGIN=.05
YAW_MARGIN=.02
SIDE_VIEWS={'left','right'}
ROTATABLE_VIEWS={'top','bottom'}

def optimize_views(full,proxy,triangles,masks,records,initial,W,deadline_seconds=540):
 began=time.monotonic();deadline=began+deadline_seconds;cache={};evaluations=0
 def evaluate(slot,s):
  nonlocal evaluations
  if time.monotonic()>deadline:raise TimeoutError('Automatic alignment reached its bounded search deadline; no geometry/export was changed')
  key=(slot,tuple((k,s[k]) for k in sorted(s)))
  if key not in cache:cache[key]=score_pose(full,proxy,triangles,masks[slot],s,W);evaluations+=1
  return cache[key]
 def with_direction(base,direction,extra_roll=0.):
  raw={k:v for k,v in base.items() if k!='direction'};raw['roll']=wrapped(raw.get('roll',0.)+extra_roll);raw['direction']=direction
  return W['alignment'](raw,direction)
 def rotations(slot,base,direction):
  # Image rotation in quarter turns (sheet layout), never a mirror image.
  # Only top/bottom pictures can be drawn turned on a sheet; front/back/side drawings are always upright.
  turns=QUARTER_TURNS if direction in ROTATABLE_VIEWS else [0.]
  table=[(evaluate(slot,s),q,s) for q in turns for s in [with_direction(base,direction,q)]]
  return max(table,key=lambda value:value[0]),[{'direction':direction,'image_rotation_deg':q,'iou':round(v,4)} for v,q,_ in table]
 labelled={};initial_settings={}
 for record in records:
  slot=record['slot'];raw=initial.get(slot,{})
  direction=raw.get('direction') if raw.get('direction') in W['DIRECTIONS'] else record.get('direction_hint') if record.get('direction_hint') in W['DIRECTIONS'] else None
  if direction is None:
   options=[(evaluate(slot,s),d) for d in W['DIRECTIONS'] for s in [W['alignment']({**raw,'direction':d},d)]];direction=max(options)[1]
  labelled[slot]=direction;initial_settings[slot]=W['alignment']({**raw,'direction':direction},direction)
 # One common model yaw for all views preserves the supplied multi-view relationship.
 groups=[]
 for yaw in [0.,90.,-90.,180.]:
  per={}
  for slot,s0 in initial_settings.items():
   base={**s0,'yaw':wrapped(s0['yaw']+yaw)};best,table=rotations(slot,base,labelled[slot])
   # 'Side view' sheets rarely say which side: side labels must not decide the model turn.
   vote=max(best[0],rotations(slot,base,OPPOSITE[labelled[slot]])[0][0]) if labelled[slot] in SIDE_VIEWS else best[0]
   per[slot]=(best,table,base,vote)
  groups.append((float(np.mean([per[k][3] for k in per])),yaw,per))
 groups.sort(key=lambda value:value[0],reverse=True);global_gap=groups[0][0]-groups[1][0]
 # Equivalent fits (e.g. symmetric front/back) keep the model as generated.
 unturned=[g for g in groups if g[1]==0.][0]
 _,global_yaw,chosen=unturned if groups[0][0]-unturned[0]<YAW_MARGIN else groups[0];results={};details=[]
 for record in records:
  slot=record['slot'];(label_score,label_rotation,label_pose),label_table,base,_=chosen[slot]
  alternative=OPPOSITE[labelled[slot]];(alt_score,alt_rotation,alt_pose),alt_table=rotations(slot,base,alternative)
  swapped=alt_score>=label_score+SWAP_MARGIN
  s=dict(alt_pose if swapped else label_pose);best=evaluate(slot,s);initial_score=evaluate(slot,initial_settings[slot]);print('AUTO_ALIGN_VIEW '+slot,flush=True)
  for steps in [(15.,10.,.10,.05),(7.5,5.,.05,.025),(3.75,2.5,.025,.0125)]:
   angle,roll,scale,offset=steps
   for key,step in [('yaw',angle),('pitch',angle),('roll',roll),('scale',scale),('offset_x',offset),('offset_y',offset)]:
    for sign in [-1,1]:
     candidate=dict(s);candidate[key]=wrapped(s[key]+sign*step) if key in {'yaw','pitch','roll'} else s[key]+sign*step
     if key=='scale' and not .2<=candidate[key]<=4:continue
     if key.startswith('offset') and not -1<=candidate[key]<=1:continue
     value=evaluate(slot,candidate)
     if value>best+1e-6:s=candidate;best=value
  # Never replace a better existing per-view silhouette fit.
  kept_existing=False
  if initial_score>best:s=initial_settings[slot];best=initial_score;kept_existing=True
  rotation=0. if kept_existing else (alt_rotation if swapped else label_rotation)
  results[slot]=s;details.append({'slot':slot,'initial_iou':initial_score,'proposed_iou':best,'direction':s['direction'],'labelled_direction':labelled[slot],
   'direction_changed':s['direction']!=labelled[slot],'image_rotation_deg':rotation,'kept_existing':kept_existing,'direction_score_gap':round(abs(alt_score-label_score),4),
   'direction_ambiguous':abs(alt_score-label_score)<SWAP_MARGIN,'candidates':label_table+alt_table,'poor_fit':best<.60})
 return results,{'method':'orthographic silhouette IoU search with automatic direction (labelled vs opposite) and quarter-turn image rotation, then fine refinement','version':'auto_orientation_v2_upright',
  'swap_margin_iou':SWAP_MARGIN,'mirroring_used':False,'review_required':True,'semantic_landmarks_checked':False,'full_resolution_RGB_changed':False,'proxy_faces':len(triangles),'global_yaw_proposal':global_yaw,'yaw_tie_margin_iou':YAW_MARGIN,'global_score_gap':global_gap,'orientation_ambiguous':global_gap<.02,'views':details,'evaluations':evaluations,'elapsed_seconds':time.monotonic()-began,
  'warnings':['Silhouette agreement is not proof that interior markings/eyes are aligned.','A view label is only overridden when the opposite direction fits clearly better (IoU margin %.2f); close calls keep your label and are marked ambiguous.'%SWAP_MARGIN,'Perspective differences, pose changes and source/model shape mismatch can prevent a good fit.']}

def run_alignment(folder,config,W):
 folder=Path(folder);ref=W['reference_check'](folder,config)
 if config.get('reference_approval_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Approve exact foreground masks before automatic alignment')
 bpy.ops.wm.open_mainfile(filepath=ref['source']['source'],load_ui=False,use_scripts=False);items=[o for o in bpy.context.scene.objects if o.type=='MESH'];before,_=W['geometry'](items)
 if {o.name for o in items}!=set(ref['source']['object_names']):raise ValueError('Approved object set changed')
 full,proxy,triangles=proxy_mesh(items)
 if W['geometry'](items)[0]!=before:raise ValueError('Alignment proxy changed approved geometry')
 with np.load(folder/'reference_masks.npz',allow_pickle=False) as data:masks={key:data[key].copy() for key in data.files}
 proposed,report=optimize_views(full,proxy,triangles,masks,ref['views'],config.get('settings',{}).get('views',{}),W)
 if W['geometry'](items)[0]!=before:raise ValueError('Alignment changed source geometry')
 config['settings']={'views':proposed};W['save'](folder/'settings.json',config);report.update(reference_fingerprint=ref['reference_fingerprint'],source_geometry_sha256=before);W['save'](folder/'alignment.json',report)
 W['preview'](folder,config);result=W['load'](folder/'checks.json');result['alignment']=report;result['artifacts']['alignment.json']=W['digest'](folder/'alignment.json');result['warnings']+=report['warnings'];result.pop('preview_fingerprint',None);result['preview_fingerprint']=hashlib.sha256(W['canonical'](result)).hexdigest();W['save'](folder/'checks.json',result)
