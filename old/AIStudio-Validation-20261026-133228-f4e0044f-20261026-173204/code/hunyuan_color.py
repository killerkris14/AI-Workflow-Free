# ALIGNMENT_ABSOLUTE_IMPORT_FIX_V1
# AUTOMATIC_REFERENCE_ALIGNMENT_V1
# UNLIT_COLOR_PROOF_RENDERER_V1
"""Reference texture worker v2.1. Full-resolution image UVs, no palette conversion.
Invoked only by the matching native bridge: FOLDER prepare|preview|export.
"""
import bpy,bmesh,json,math,sys,hashlib,struct,traceback,zipfile,io,shutil
import numpy as np
from pathlib import Path
from collections import deque
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from xml.sax.saxutils import escape
DIRECTIONS={'front':((1,0,0),(0,0,1),(0,-1,0)),'back':((-1,0,0),(0,0,1),(0,1,0)),'right':((0,1,0),(0,0,1),(1,0,0)),'left':((0,-1,0),(0,0,1),(-1,0,0)),'top':((1,0,0),(0,1,0),(0,0,1)),'bottom':((1,0,0),(0,-1,0),(0,0,-1))}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for data in iter(lambda:f.read(1048576),b''):h.update(data)
 return h.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
 p=Path(path);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(p)
def job_file(job,name):
 p=job/name
 if p.is_symlink() or job.resolve() not in p.resolve().parents or not p.is_file():raise ValueError('Unsafe/missing job file: '+name)
 return p

def source_info(config):
 raw=Path(config['source_blend']);source=raw.resolve();job=source.parent.parent
 if raw.is_symlink() or source.parent.name!='final' or source.name!='model.blend' or not source.is_file():raise ValueError('Retained final/model.blend required')
 request=load(job_file(job,'request.json'));p=load(job_file(job,'hunyuan_progress.json'));frozen=load(job_file(job,'final/hunyuan_job.json'));checks=load(job_file(job,'final/checks.json'));fp=frozen.get('processing',{});route=fp.get('autoroute',{})
 if request.get('engine')!='hunyuan' or frozen.get('request',{}).get('engine')!='hunyuan' or fp.get('stage')!='export' or checks.get('ok') is not True or checks.get('phase')!='finished':raise ValueError('Successful approved Hunyuan export required')
 if p.get('candidate',1)!=fp.get('candidate',1) or p.get('transform')!=fp.get('transform') or p.get('autoroute')!=route or route.get('confirmed') is not True:raise ValueError('Current geometry/routing differs from the retained final export')
 source_sha=digest(source);approved=checks.get('preview_blend_sha256')
 if approved and approved!=source_sha:raise ValueError('Approved geometry hash changed')
 if not approved and config.get('confirm_bind_unhashed_source') is not True:raise ValueError('Explicit binding confirmation required for legacy unhashed final model')
 repair=checks.get('repair',{})
 if repair.get('applied') and (repair.get('passed_topology_checks') is not True or repair.get('exported_approved_preview') is not True or fp.get('solid_repair_approved') is not True):raise ValueError('Solid repair approval evidence missing')
 dims=checks.get('dimensions_mm');names=[o.get('name') for o in checks.get('objects',[])]
 if not isinstance(dims,list) or len(dims)!=3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in dims):raise ValueError('Invalid approved dimensions')
 if not names or len(set(names))!=len(names) or any(not isinstance(n,str) or not n for n in names):raise ValueError('Approved object names required')
 refs=[];seen=set()
 for panel in route.get('panels',[]):
  slot=panel.get('view')
  if slot not in set(DIRECTIONS)|{'main'} or slot in seen:raise ValueError('Invalid/duplicate prepared view')
  seen.add(slot);path=job_file(job,'autoroute_prepared/'+slot+'.png');hint=panel.get('reference_direction') if slot=='main' else slot
  refs.append({'slot':slot,'direction_hint':hint if hint in DIRECTIONS else None,'path':str(path),'sha256':digest(path)})
 if not refs:raise ValueError('No approved prepared references; raw-image fallback is prohibited')
 info={'job':str(job),'source':str(source),'source_sha256':source_sha,'dimensions_mm':dims,'object_names':names,'references':refs,'metadata_sha256':{n:digest(job_file(job,n)) for n in ['request.json','final/checks.json','final/hunyuan_job.json']}}
 info['fingerprint']=hashlib.sha256(canonical(info)).hexdigest();return info

def configuration_fingerprint(config):return hashlib.sha256(canonical({'source_blend':str(Path(config['source_blend']).resolve()),'settings':config.get('settings',{}),'reference_approval_fingerprint':config.get('reference_approval_fingerprint')})).hexdigest()
def geometry(items):
 h=hashlib.sha256();records=[]
 for obj in items:
  if any(m.show_viewport or m.show_render for m in obj.modifiers):raise ValueError('Active modifiers require separately validated extraction')
  obj.data.calc_loop_triangles();h.update(obj.name.encode())
  for v in obj.data.vertices:
   p=obj.matrix_world@v.co
   if not all(math.isfinite(x) for x in p):raise ValueError('Nonfinite geometry')
   h.update(struct.pack('<ddd',*p))
  for t in obj.data.loop_triangles:h.update(struct.pack('<III',*t.vertices))
  bm=bmesh.new()
  try:
   bm.from_mesh(obj.data);bad=sum(not e.is_manifold for e in bm.edges);orientation=sum(e.is_manifold and not e.is_contiguous for e in bm.edges);degenerate=sum(f.calc_area()<1e-10 for f in bm.faces);volume=abs(bm.calc_volume()*obj.matrix_world.to_3x3().determinant());r={'name':obj.name,'vertices':len(bm.verts),'faces':len(bm.faces),'non_manifold_edges':bad,'orientation_mismatch_edges':orientation,'degenerate_faces':degenerate,'volume_mm3':volume};records.append(r)
   if bad or orientation or degenerate or not math.isfinite(volume) or volume<1e-6:raise ValueError('Closed solid required: '+json.dumps(r))
  finally:bm.free()
 return h.hexdigest(),records

def pixels(path):
 image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='Non-Color';w,h=image.size
 if min(w,h)<2:raise ValueError('Empty/tiny reference')
 values=np.empty(w*h*4,np.float32);image.pixels.foreach_get(values);bpy.data.images.remove(image);return values.reshape(h,w,4)[::-1].copy()
def png(path,array):
 h,w=array.shape[:2];image=bpy.data.images.new('MaskReview',width=w,height=h,alpha=True);image.colorspace_settings.name='Non-Color';image.pixels.foreach_set(np.ascontiguousarray(array[::-1]).ravel());image.file_format='PNG';image.filepath_raw=str(path);image.save();bpy.data.images.remove(image)
def foreground(rgba):
 if np.any(rgba[:,:,3]<.06):mask=rgba[:,:,3]>=.06;method='existing-alpha'
 else:
  rgb=rgba[:,:,:3];edge=np.concatenate([rgb[0],rgb[-1],rgb[1:-1,0],rgb[1:-1,-1]]);bg=np.median(edge,axis=0)
  if np.mean(np.max(np.abs(edge-bg),axis=1)<=.04)<.9:raise ValueError('Ambiguous background: do not auto-approve a guessed mask')
  candidate=np.max(np.abs(rgb-bg),axis=2)<=.04;h,w=candidate.shape;seen=np.zeros((h,w),bool);q=deque()
  def seed(y,x):
   if candidate[y,x] and not seen[y,x]:seen[y,x]=True;q.append((y,x))
  for x in range(w):seed(0,x);seed(h-1,x)
  for y in range(1,h-1):seed(y,0);seed(y,w-1)
  while q:
   y,x=q.popleft()
   for yy,xx in [(y-1,x),(y+1,x),(y,x-1),(y,x+1)]:
    if 0<=yy<h and 0<=xx<w:seed(yy,xx)
  mask=~seen;method='boundary-connected-proposal'
 if np.count_nonzero(mask)<16:raise ValueError('Foreground mask is empty/tiny')
 return mask,method

def prepare(folder,config):
 info=source_info(config);assets={};views=[];masks={}
 for ref in info['references']:
  slot=ref['slot'];name='reference_'+slot+'.png';shutil.copy2(ref['path'],folder/name);rgba=pixels(folder/name);mask,method=foreground(rgba);masks[slot]=mask;overlay=rgba.copy();overlay[~mask,:3]=overlay[~mask,:3]*.35+np.array([1.,0.,.7])*.65;overlay[:,:,3]=1;matte=np.ones_like(rgba);matte[:,:,:3]=mask[:,:,None]
  for prefix,array in [('mask',matte),('overlay',overlay)]:png(folder/(prefix+'_'+slot+'.png'),array)
  for prefix in ['reference','mask','overlay']:file=prefix+'_'+slot+'.png';assets[file]=digest(folder/file)
  views.append({'slot':slot,'direction_hint':ref['direction_hint'],'width':rgba.shape[1],'height':rgba.shape[0],'mask_method':method,'warnings':['Inspect white/light markings and edges. Boundary-connected light subject areas can be excluded.']})
 np.savez_compressed(folder/'reference_masks.npz',**masks);assets['reference_masks.npz']=digest(folder/'reference_masks.npz');report={'ok':True,'protocol':2,'phase':'reference_masks_ready','source':info,'views':views,'artifacts':assets};report['reference_fingerprint']=hashlib.sha256(canonical(report)).hexdigest()
 if source_info(config)['fingerprint']!=info['fingerprint']:raise ValueError('Source changed during preparation')
 save(folder/'reference_review.json',report);save(folder/'checks.json',report)

def reference_check(folder,config):
 r=load(folder/'reference_review.json');body={k:v for k,v in r.items() if k!='reference_fingerprint'}
 if hashlib.sha256(canonical(body)).hexdigest()!=r.get('reference_fingerprint') or r.get('protocol')!=2 or r.get('phase')!='reference_masks_ready':raise ValueError('Reference review metadata changed')
 if source_info(config)['fingerprint']!=r['source']['fingerprint']:raise ValueError('Source/reference pixels changed')
 for name,value in r['artifacts'].items():
  if Path(name).name!=name or (folder/name).is_symlink() or digest(folder/name)!=value:raise ValueError('Reference/mask artifact changed')
 return r

def alignment(raw,hint):
 default={'scale':1.,'offset_x':0.,'offset_y':0.,'yaw':0.,'pitch':0.,'roll':0.,'flip':False}
 if not isinstance(raw,dict) or set(raw)-set(default)-{'direction'}:raise ValueError('Unknown view setting')
 s={**default,**raw};s['direction']=s.get('direction',hint)
 if s['direction'] not in DIRECTIONS:raise ValueError('Assign a model-facing direction for every source')
 if not isinstance(s['flip'],bool):raise ValueError('Mirror must be boolean')
 for key in ['scale','offset_x','offset_y','yaw','pitch','roll']:
  x=s[key];lo,hi=(.2,4) if key=='scale' else (-1,1) if key.startswith('offset') else (-180,180)
  if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi:raise ValueError('Invalid '+key)
 return s

def basis(s):
 r,u,t=[np.array(v,float) for v in DIRECTIONS[s['direction']]]
 def rotate(v,a,d):
  x=math.radians(d);return v*math.cos(x)+np.cross(a,v)*math.sin(x)+a*(a@v)*(1-math.cos(x))
 r,u,t=[rotate(v,np.array([0.,0.,1.]),s['yaw']) for v in [r,u,t]];r,u,t=[rotate(v,r,s['pitch']) for v in [r,u,t]];r,u,t=[rotate(v,t,s['roll']) for v in [r,u,t]];return r,u,t

def project(points,v):
 xy=np.stack([points@v['right']-v['world_center'][0],points@v['up']-v['world_center'][1]],axis=-1)
 if v['settings']['flip']:xy[:,0]*=-1
 return np.stack([v['center'][0]+xy[:,0]*v['scale'],v['center'][1]-xy[:,1]*v['scale']],axis=-1)

def transfer(items,folder,config,review):
 points=[];triangles=[];offset=0
 for obj in items:
  obj.data.calc_loop_triangles();points.extend(obj.matrix_world@v.co for v in obj.data.vertices);triangles.extend(tuple(offset+int(i) for i in t.vertices) for t in obj.data.loop_triangles);offset+=len(obj.data.vertices)
 coordinates=np.array([tuple(p) for p in points]);size=np.ptp(coordinates,axis=0)
 if any(abs(a-b)>max(.05,b*.002) for a,b in zip(size,review['source']['dimensions_mm'])):raise ValueError('Approved millimeter dimensions changed')
 tree=BVHTree.FromPolygons(points,triangles,all_triangles=True);epsilon=max(float(np.linalg.norm(size))*1e-6,1e-7);views=[];settings=config.get('settings',{}).get('views',{})
 if set(settings)-{r['slot'] for r in review['views']}:raise ValueError('Settings target unavailable view')
 with np.load(folder/'reference_masks.npz',allow_pickle=False) as data:masks={k:data[k].copy() for k in data.files}
 for record in review['views']:
  slot=record['slot'];s=alignment(settings.get(slot,{}),record['direction_hint']);right,up,toward=basis(s);mask=masks[slot];h,w=mask.shape;yy,xx=np.where(mask);x=coordinates@right;y=coordinates@up;extent=np.array([np.ptp(x),np.ptp(y)])
  if min(extent)<1e-10:raise ValueError('Degenerate projected extent')
  crop=np.array([xx.max()-xx.min()+1,yy.max()-yy.min()+1]);scale=float(np.min(crop*.98/extent))*s['scale'];center=np.array([(xx.max()+xx.min()+1)/2,(yy.max()+yy.min()+1)/2])+np.array([s['offset_x'],s['offset_y']])*crop
  image=bpy.data.images.load(str(folder/('reference_'+slot+'.png')),check_existing=False);image.colorspace_settings.name='sRGB';image.pack();material=bpy.data.materials.new('Reference_'+slot);material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear();texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.extension='EXTEND';shader=nodes.new('ShaderNodeBsdfPrincipled');shader.inputs['Metallic'].default_value=0;shader.inputs['Roughness'].default_value=.9;output=nodes.new('ShaderNodeOutputMaterial');material.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color']);material.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface']);material['reference_texture_slot']=slot
  views.append({'slot':slot,'right':right,'up':up,'toward':toward,'world_center':np.array([(x.min()+x.max())/2,(y.min()+y.max())/2]),'center':center,'scale':scale,'mask':mask,'w':w,'h':h,'settings':s,'material':material})
 neutral=bpy.data.materials.new('UNOBSERVED_NEUTRAL');neutral.diffuse_color=(.5,.5,.5,1);counts={v['slot']:0 for v in views};unknown=mapped=0
 for obj in items:
  obj.data.materials.clear()
  for v in views:obj.data.materials.append(v['material'])
  obj.data.materials.append(neutral);uv=obj.data.uv_layers.active or obj.data.uv_layers.new(name='ReferenceUV');normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
  for face in obj.data.polygons:
   vertices=np.array([tuple(obj.matrix_world@obj.data.vertices[i].co) for i in face.vertices]);center=vertices.mean(0);samples=np.vstack([center,center*.8+vertices*.2]);normal=np.array(tuple((normal_matrix@face.normal).normalized()));best=-1;chosen=None
   for index,v in enumerate(views):
    facing=float(normal@v['toward'])
    if facing<=.03:continue
    xy=project(samples,v)
    if np.any(xy<0) or np.any(xy[:,0]>=v['w']) or np.any(xy[:,1]>=v['h']):continue
    if not v['mask'][np.floor(xy[:,1]).astype(int),np.floor(xy[:,0]).astype(int)].all():continue
    corners=project(vertices,v)
    if np.any(corners<0) or np.any(corners[:,0]>v['w']) or np.any(corners[:,1]>v['h']):continue
    if any(tree.ray_cast(Vector(p+v['toward']*epsilon),Vector(v['toward']))[0] is not None for p in samples):continue
    score=facing*facing*v['scale']
    if score>best:best=score;chosen=(index,v,corners)
   if chosen is None:face.material_index=len(views);unknown+=1;continue
   index,v,xy=chosen;face.material_index=index;mapped+=1;counts[v['slot']]+=1
   for loop,p in zip(face.loop_indices,xy):uv.data[loop].uv=(float(p[0]/v['w']),float(1-p[1]/v['h']))
  obj.data.update()
 return {'mapped_faces':mapped,'fallback_faces':unknown,'reference_face_counts':counts,'palette_face_counts':[],'color_quantization':False,'source_resampling':False,'seam_blending':False}

def render(items,folder,config):
    """Flat unlit color proof. Temporary materials; export PBR materials remain intact."""
    scene=bpy.context.scene
    points=[obj.matrix_world@vertex.co for obj in items for vertex in obj.data.vertices]
    low=Vector([min(p[i] for p in points) for i in range(3)])
    high=Vector([max(p[i] for p in points) for i in range(3)])
    center=(low+high)/2
    radius=max((p-center).length for p in points)
    size=int(config.get('preview_size',512))
    if not 128<=size<=1024:raise ValueError('Preview size must be 128..1024')
    old_world=scene.world
    old_nodes=scene.use_nodes
    old_view={key:getattr(scene.view_settings,key) for key in ['view_transform','look','exposure','gamma']}
    old_display=scene.display_settings.display_device
    extras={key:getattr(scene.view_settings,key) for key in ['use_curve_mapping','use_white_balance'] if hasattr(scene.view_settings,key)}
    meshes={obj.data.as_pointer():obj.data for obj in items}
    originals={key:list(mesh.materials) for key,mesh in meshes.items()}
    indices={key:[p.material_index for p in mesh.polygons] for key,mesh in meshes.items()}
    temporary=[]
    cache={}
    def proof(material):
        key=material.as_pointer() if material else 0
        if key in cache:return cache[key]
        result=bpy.data.materials.new('TemporaryColorProof')
        temporary.append(result)
        result.use_nodes=True
        nodes=result.node_tree.nodes
        nodes.clear()
        emission=nodes.new('ShaderNodeEmission')
        emission.inputs['Strength'].default_value=1.0
        output=nodes.new('ShaderNodeOutputMaterial')
        result.node_tree.links.new(emission.outputs['Emission'],output.inputs['Surface'])
        source=None
        if material and material.use_nodes:
            source=next((n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image is not None),None)
        if source is not None:
            texture=nodes.new('ShaderNodeTexImage')
            texture.image=source.image
            texture.interpolation=source.interpolation
            texture.extension=source.extension
            result.node_tree.links.new(texture.outputs['Color'],emission.inputs['Color'])
        else:
            # Neutral unobserved area, approximately display sRGB 0.5.
            emission.inputs['Color'].default_value=(0.214041,0.214041,0.214041,1.0)
        cache[key]=result
        return result
    world=bpy.data.worlds.new('TemporaryColorProofWorld')
    world.use_nodes=True
    background=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND')
    background.inputs['Strength'].default_value=0.0
    scene.world=world
    try:
        for key,mesh in meshes.items():
            for index,material in enumerate(originals[key]):mesh.materials[index]=proof(material)
        scene.use_nodes=False
        scene.display_settings.display_device='sRGB'
        scene.view_settings.view_transform='Standard'
        scene.view_settings.look='None'
        scene.view_settings.exposure=0.0
        scene.view_settings.gamma=1.0
        for key in extras:setattr(scene.view_settings,key,False)
        for obj in list(scene.objects):
            if obj.type in {'CAMERA','LIGHT'}:bpy.data.objects.remove(obj,do_unlink=True)
        camera_data=bpy.data.cameras.new('ReferenceColorProofCamera')
        camera=bpy.data.objects.new('ReferenceColorProofCamera',camera_data)
        scene.collection.objects.link(camera)
        scene.camera=camera
        camera_data.type='ORTHO'
        camera_data.ortho_scale=max(radius*2.4,1)
        camera_data.clip_start=.001
        camera_data.clip_end=max(radius*20,10000)
        scene.render.engine='CYCLES'
        scene.cycles.device='CPU'
        scene.cycles.samples=8
        scene.cycles.use_denoising=False
        if hasattr(scene.cycles,'use_adaptive_sampling'):scene.cycles.use_adaptive_sampling=False
        if hasattr(scene.render.image_settings,'color_management'):scene.render.image_settings.color_management='FOLLOW_SCENE'
        scene.render.resolution_x=scene.render.resolution_y=size
        scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG'
        scene.render.image_settings.color_mode='RGBA'
        scene.render.image_settings.color_depth='8'
        scene.render.film_transparent=True
        for name,direction in [('preview.png',(-1.4,-1.8,1.25)),('preview_side.png',(0,-1,.05)),('preview_top.png',(0,0,1))]:
            camera.location=center+Vector(direction).normalized()*max(radius*4,10)
            camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(folder/name)
            bpy.ops.render.render(write_still=True)
    finally:
        for key,mesh in meshes.items():
            for index,material in enumerate(originals[key]):mesh.materials[index]=material
            if [p.material_index for p in mesh.polygons]!=indices[key]:
                for polygon,index in zip(mesh.polygons,indices[key]):polygon.material_index=index
        scene.world=old_world
        scene.use_nodes=old_nodes
        scene.display_settings.display_device=old_display
        for key,value in old_view.items():setattr(scene.view_settings,key,value)
        for key,value in extras.items():setattr(scene.view_settings,key,value)
        for material in temporary:
            if material.users==0:bpy.data.materials.remove(material)
        if world.users==0:bpy.data.worlds.remove(world)
    return list(high-low)

def glb(items,path):
 copies=[]
 try:
  bpy.ops.object.select_all(action='DESELECT')
  for obj in items:
   clone=obj.copy();clone.parent=None;clone.animation_data_clear();clone.matrix_world=Matrix.Diagonal((.001,.001,.001,1.))@obj.matrix_world;bpy.context.scene.collection.objects.link(clone);clone.select_set(True);copies.append(clone)
  options={'filepath':str(path),'export_format':'GLB','use_selection':True,'export_yup':True,'export_animations':False};props=bpy.ops.export_scene.gltf.get_rna_type().properties
  for key in ['export_apply','export_skins','export_morph','export_draco_mesh_compression_enable','export_use_gltfpack','export_cameras','export_lights']:
   if key in props:options[key]=False
  if 'FINISHED' not in bpy.ops.export_scene.gltf(**options):raise RuntimeError('GLB export failed')
 finally:
  for obj in copies:bpy.data.objects.remove(obj,do_unlink=True)

def write_master(items,folder,path):
 core='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';mat='http://schemas.microsoft.com/3dmanufacturing/material/2015/02';rels='http://schemas.openxmlformats.org/package/2006/relationships';slots=set()
 def slot_for(obj,triangle):
  face=obj.data.polygons[triangle.polygon_index];material=obj.data.materials[face.material_index];return material.get('reference_texture_slot')
 for obj in items:
  obj.data.calc_loop_triangles()
  for t in obj.data.loop_triangles:
   slot=slot_for(obj,t)
   if slot:slots.add(slot)
 groups={slot:10+2*i for i,slot in enumerate(sorted(slots))};counters={slot:0 for slot in slots}
 if not groups:raise ValueError('No textured faces')
 with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
  archive.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="png" ContentType="image/png"/></Types>');archive.writestr('_rels/.rels','<Relationships xmlns="'+rels+'"><Relationship Id="model" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="/3D/3dmodel.model"/></Relationships>');relationships=[]
  for slot in sorted(slots):
   name='reference_'+slot+'.png';archive.write(folder/name,'3D/Textures/'+name);relationships.append('<Relationship Id="'+slot+'" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dtexture" Target="/3D/Textures/'+name+'"/>')
  archive.writestr('3D/_rels/3dmodel.model.rels','<Relationships xmlns="'+rels+'">'+''.join(relationships)+'</Relationships>')
  with archive.open('3D/3dmodel.model','w') as binary:
   stream=io.TextIOWrapper(binary,encoding='utf-8',newline='');stream.write('<?xml version="1.0"?><model unit="millimeter" xml:lang="en-US" xmlns="'+core+'" xmlns:m="'+mat+'" requiredextensions="m"><metadata name="Title">Reference texture master - not filament mapped</metadata><resources><basematerials id="1"><base name="UNOBSERVED_NEUTRAL" displaycolor="#808080FF"/></basematerials>')
   for slot,tid in groups.items():
    stream.write('<m:texture2d id="%d" path="/3D/Textures/reference_%s.png" contenttype="image/png" tilestyleu="clamp" tilestylev="clamp"/><m:texture2dgroup id="%d" texid="%d">'%(tid,slot,tid+1,tid))
    for obj in items:
     uv=obj.data.uv_layers.active
     for t in obj.data.loop_triangles:
      if slot_for(obj,t)==slot:
       for loop in t.loops:stream.write('<m:tex2coord u="%.12g" v="%.12g"/>'%tuple(uv.data[loop].uv))
    stream.write('</m:texture2dgroup>')
   for number,obj in enumerate(items,1000):
    stream.write('<object id="%d" type="model" pid="1" pindex="0" name="%s"><mesh><vertices>'%(number,escape(obj.name,{'"':'&quot;'})))
    for v in obj.data.vertices:stream.write('<vertex x="%.12g" y="%.12g" z="%.12g"/>'%tuple(obj.matrix_world@v.co))
    stream.write('</vertices><triangles>')
    for t in obj.data.loop_triangles:
     slot=slot_for(obj,t);attributes=''
     if slot in groups:
      i=counters[slot];attributes=' pid="%d" p1="%d" p2="%d" p3="%d"'%(groups[slot]+1,i,i+1,i+2);counters[slot]+=3
     stream.write('<triangle v1="%d" v2="%d" v3="%d"%s/>'%(*t.vertices,attributes))
    stream.write('</triangles></mesh></object>')
   stream.write('</resources><build>')
   for i in range(1000,1000+len(items)):stream.write('<item objectid="%d"/>'%i)
   stream.write('</build></model>');stream.flush();stream.detach()
 with zipfile.ZipFile(path) as archive:
  if archive.testzip():raise ValueError('Corrupt master ZIP')
  for slot in slots:
   name='reference_'+slot+'.png'
   if archive.read('3D/Textures/'+name)!=(folder/name).read_bytes():raise ValueError('Source PNG bytes changed')

def preview(folder,config):
 ref=reference_check(folder,config)
 if config.get('reference_approval_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Approve exact masks/reference set first')
 bpy.ops.wm.open_mainfile(filepath=ref['source']['source'],load_ui=False,use_scripts=False);items=[o for o in bpy.context.scene.objects if o.type=='MESH']
 if {o.name for o in items}!=set(ref['source']['object_names']):raise ValueError('Loaded object set changed')
 before,records=geometry(items);stats=transfer(items,folder,config,ref)
 if not stats['mapped_faces'] or geometry(items)[0]!=before:raise ValueError('No texture coverage or geometry changed')
 dimensions=render(items,folder,config);glb(items,folder/'model-colored.glb')
 if geometry(items)[0]!=before:raise ValueError('Preview export changed geometry')
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'model-colored.blend'))
 if source_info(config)['fingerprint']!=ref['source']['fingerprint']:raise ValueError('Source changed while processing')
 artifacts=dict(ref['artifacts']);artifacts.update({n:digest(folder/n) for n in ['model-colored.blend','model-colored.glb','preview.png','preview_side.png','preview_top.png']});report={'ok':True,'protocol':2,'phase':'color_preview_ready','method':'reference_uv_textures', 'preview_render_method':'unlit_color_proof_v1','palette':[],'settings':config['settings'],'statistics':stats,'objects':records,'dimensions_mm':dimensions,'geometry_sha256':before,'source_blend_sha256':ref['source']['source_sha256'],'preview_blend_sha256':artifacts['model-colored.blend'],'reference_fingerprint':ref['reference_fingerprint'],'configuration_fingerprint':configuration_fingerprint(config),'artifacts':artifacts,'warnings':['Manual registration and all-view review are required.','Visibility is sampled per polygon; partial occlusion and seams can remain. No seam blending.','Unobserved areas remain neutral, not generated detail.','Unlit color-proof preview: Standard sRGB display, exposure 0, gamma 1; no scene-light washout. Source PNG bytes unchanged.','Texture master is not a verified Bambu/AMS filament-mapped project. No printability or articulation certification.']};report['preview_fingerprint']=hashlib.sha256(canonical(report)).hexdigest();save(folder/'checks.json',report)

def preview_check(folder,config):
 ref=reference_check(folder,config);r=load(folder/'checks.json');body={k:v for k,v in r.items() if k!='preview_fingerprint'}
 if r.get('phase')!='color_preview_ready' or r.get('ok') is not True or hashlib.sha256(canonical(body)).hexdigest()!=r.get('preview_fingerprint'):raise ValueError('Exact sealed preview required')
 if configuration_fingerprint(config)!=r['configuration_fingerprint'] or config.get('reference_approval_fingerprint')!=ref['reference_fingerprint']:raise ValueError('Settings/reference approval changed')
 for name,value in r['artifacts'].items():
  if Path(name).name!=name or (folder/name).is_symlink() or digest(folder/name)!=value:raise ValueError('Preview artifact changed')
 return r

def export(folder,config):
 r=preview_check(folder,config)
 if config.get('approved_preview_fingerprint')!=r['preview_fingerprint']:raise ValueError('Exact-preview approval required')
 if r['statistics']['fallback_faces'] and config.get('accept_uncovered') is not True:raise ValueError('Accept neutral unobserved regions explicitly')
 bpy.ops.wm.open_mainfile(filepath=str(folder/'model-colored.blend'),load_ui=False,use_scripts=False);items=[o for o in bpy.context.scene.objects if o.type=='MESH']
 if geometry(items)[0]!=r['geometry_sha256']:raise ValueError('Approved geometry changed')
 target=folder/'model-colored.3mf'
 if target.exists():raise ValueError('Existing export is never overwritten')
 try:write_master(items,folder,target);preview_check(folder,config)
 except FileExistsError:raise
 except BaseException:target.unlink(missing_ok=True);raise
 r.update(phase='color_export_finished',export_sha256=digest(target),export={'filament_mapped':False,'bambu_validated':False});save(folder/'checks.json',r)

def _load_reference_alignment_local():
 import importlib.util
 path = Path(__file__).resolve().with_name('reference_alignment.py')
 if path.is_symlink() or not path.is_file():
  raise RuntimeError('Automatic alignment helper is missing/unsafe: ' + str(path))
 if hashlib.sha256(path.read_bytes()).hexdigest() != 'daa2c7e58cd0dd44b836f9ae334b878cf78eb93d90f9d5946c475dc64521b457':
  raise RuntimeError('Automatic alignment helper changed; revalidate the update')
 spec = importlib.util.spec_from_file_location('studio_reference_alignment_local', str(path))
 if spec is None or spec.loader is None:
  raise RuntimeError('Cannot load alignment helper: ' + str(path))
 module = importlib.util.module_from_spec(spec)
 sys.modules[spec.name] = module
 spec.loader.exec_module(module)
 return module

def main():
 args=sys.argv[sys.argv.index('--')+1:];folder=Path(args[0]).resolve();mode=args[1]
 try:
  config=load(folder/'settings.json')
  if mode=='prepare':prepare(folder,config)
  elif mode=='align':
   _load_reference_alignment_local().run_alignment(folder, config, globals())
  elif mode=='preview':preview(folder,config)
  elif mode=='export':export(folder,config)
  else:raise ValueError('Unknown mode')
  print('REFERENCE_TEXTURE_WORKER_PASSED')
 except Exception:save(folder/'failure.json',{'ok':False,'phase':'reference_color_failed','error':traceback.format_exc()});raise
if __name__=='__main__':main()
