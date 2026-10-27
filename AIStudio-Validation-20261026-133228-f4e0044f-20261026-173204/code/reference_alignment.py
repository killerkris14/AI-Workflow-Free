"""Silhouette-based automatic reference alignment v1.
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

def optimize_views(full,proxy,triangles,masks,records,initial,W,deadline_seconds=540):
 began=time.monotonic();deadline=began+deadline_seconds;cache={};evaluations=0
 def evaluate(slot,s):
  nonlocal evaluations
  if time.monotonic()>deadline:raise TimeoutError('Automatic alignment reached its bounded search deadline; no geometry/export was changed')
  key=(slot,tuple((k,s[k]) for k in sorted(s)))
  if key not in cache:cache[key]=score_pose(full,proxy,triangles,masks[slot],s,W);evaluations+=1
  return cache[key]
 base={};alternatives={}
 for record in records:
  slot=record['slot'];raw=initial.get(slot,{})
  if raw.get('direction') in W['DIRECTIONS']:choices=[raw['direction']]
  elif record.get('direction_hint') in W['DIRECTIONS']:choices=[record['direction_hint']]
  else:choices=list(W['DIRECTIONS'])
  options=[]
  for direction in choices:
   s=W['alignment']({**raw,'direction':direction},direction);options.append((evaluate(slot,s),s))
  options.sort(key=lambda value:value[0],reverse=True);base[slot]=dict(options[0][1]);alternatives[slot]=options[0][0]-(options[1][0] if len(options)>1 else 0.)
 # One common yaw hypothesis preserves the supplied multi-view relationship.
 groups=[]
 for yaw in [0.,90.,-90.,180.]:
  proposal={slot:{**s,'yaw':wrapped(s['yaw']+yaw)} for slot,s in base.items()};scores={slot:evaluate(slot,s) for slot,s in proposal.items()};groups.append((float(np.mean(list(scores.values()))),yaw,proposal))
 groups.sort(key=lambda value:value[0],reverse=True);_,global_yaw,chosen=groups[0];global_gap=groups[0][0]-groups[1][0];results={};details=[]
 for record in records:
  slot=record['slot'];s=dict(chosen[slot]);best=evaluate(slot,s);initial_score=evaluate(slot,base[slot]);print('AUTO_ALIGN_VIEW '+slot,flush=True)
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
  if initial_score>best:s=base[slot];best=initial_score;kept_existing=True
  results[slot]=s;details.append({'slot':slot,'initial_iou':initial_score,'proposed_iou':best,'direction':s['direction'],'kept_existing':kept_existing,'direction_score_gap':alternatives[slot],'poor_fit':best<.60})
 return results,{'method':'orthographic silhouette IoU search','review_required':True,'semantic_landmarks_checked':False,'full_resolution_RGB_changed':False,'proxy_faces':len(triangles),'global_yaw_proposal':global_yaw,'global_score_gap':global_gap,'orientation_ambiguous':global_gap<.02,'views':details,'evaluations':evaluations,'elapsed_seconds':time.monotonic()-began,'warnings':['Silhouette agreement is not proof that interior markings/eyes are aligned.','Symmetric views can have ambiguous orientation; inspect every source direction.','Perspective differences, pose changes and source/model shape mismatch can prevent a good fit.']}

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
