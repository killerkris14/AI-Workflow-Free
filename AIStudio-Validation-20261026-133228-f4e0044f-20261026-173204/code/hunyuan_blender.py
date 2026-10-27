# OPT-IN SOLID REPAIR v1
# GLB SEAM WELD FIX v1
"""Trusted import/preview/export path for Hunyuan meshes. No AI-generated Python is executed."""
import bpy,bmesh,addon_utils,json,math,sys,traceback,zipfile
from pathlib import Path
from mathutils import Vector,Matrix
args=sys.argv[sys.argv.index('--')+1:];attempt=Path(args[0]).resolve();cfg=json.loads(Path(args[1]).read_text(encoding='utf-8-sig'))
report={'ok':False,'phase':'import','warnings':[],'engine':'hunyuan','articulated':False}
def write(): (attempt/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def meshes():return [o for o in bpy.context.scene.objects if o.type=='MESH']
def bounds():
    bpy.context.view_layer.update();p=[o.matrix_world@v.co for o in meshes() for v in o.data.vertices]
    if not p:raise RuntimeError('Imported GLB contains no mesh vertices.')
    lo=Vector([min(v[i] for v in p) for i in range(3)]);hi=Vector([max(v[i] for v in p) for i in range(3)])
    return lo,hi,hi-lo

def repair_integrity(obj):
    bm=bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return {'name':obj.name,'vertices':len(bm.verts),'faces':len(bm.faces),
                'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
                'boundary_edges':sum(e.is_boundary for e in bm.edges),
                'wire_edges':sum(e.is_wire for e in bm.edges),
                'overconnected_edges':sum(len(e.link_faces)>2 for e in bm.edges),
                'orientation_mismatch_edges':sum(e.is_manifold and not e.is_contiguous for e in bm.edges),
                'degenerate_faces':sum(f.calc_area()<=1e-10 for f in bm.faces),
                'volume_mm3':abs(bm.calc_volume()) if bm.faces else 0.0}
    finally:bm.free()

def repair_problematic(items):
    return not items or any(not item['vertices'] or not item['faces'] or item['non_manifold_edges'] or item.get('orientation_mismatch_edges',0) or item.get('degenerate_faces',0) or not math.isfinite(item['volume_mm3']) or item['volume_mm3']<1e-6 for item in items)

def apply_solid_repair(objects,settings):
    voxel=float(settings.get('repair_voxel_mm',0))
    if not math.isfinite(voxel) or not .05<=voxel<=2:raise ValueError('Repair voxel size must be 0.05 to 2.0 mm.')
    lo,hi,size=bounds();before_size=list(size)
    estimates=[]
    for obj in objects:
        coords=[v.co for v in obj.data.vertices]
        if not coords:raise RuntimeError('Empty object before solid repair: '+obj.name)
        extents=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)]
        estimates.append(math.prod(math.ceil(max(0,d)/voxel)+6 for d in extents))
    estimate=sum(estimates)
    report['repair']={'applied':False,'method':'voxel_remesh','voxel_mm':voxel,'estimated_bounding_grid_cells':estimate,'before_dimensions_mm':before_size,'before': [repair_integrity(obj) for obj in objects], 'passed_topology_checks':False}
    report['phase']='solid_repair';write()
    if estimate>20000000:raise RuntimeError('Repair grid estimate is too large (%s cells). Increase voxel size, then repair again. This guard is not a RAM guarantee.'%estimate)
    for obj in objects:
        bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
        modifier=obj.modifiers.new(name='PortalSolidRepair',type='REMESH');modifier.mode='VOXEL';modifier.voxel_size=voxel
        modifier.adaptivity=0.0;modifier.use_remove_disconnected=False
        result=bpy.ops.object.modifier_apply(modifier=modifier.name)
        if 'FINISHED' not in result:raise RuntimeError('Voxel remesh failed for '+obj.name)
        bm=bmesh.new()
        try:
            bm.from_mesh(obj.data)
            if not bm.verts or not bm.faces:raise RuntimeError('Repair produced an empty surface. Return to the original preview or try another voxel size.')
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);obj.data.update()
        finally:bm.free()
    lo,hi,size=bounds();length=float(settings.get('length_mm',120))
    if size.x<=1e-9:raise RuntimeError('Repaired mesh has no usable X extent.')
    factor=length/size.x;center=(lo+hi)/2
    transform=Matrix.Translation(Vector((-center.x*factor,-center.y*factor,-lo.z*factor)))@Matrix.Diagonal((factor,factor,factor,1))
    for obj in objects:obj.data.transform(transform)
    report['repair'].update(applied=True,length_rescale_factor=factor,after_dimensions_mm=list(bounds()[2]))
    report['warnings'].append('Opt-in solid repair changed topology; small gaps or thin features may close or disappear. Surface texture/UV data may change. Review all views; no articulation was added.')

def file_sha256(path):
    import hashlib
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()

try:
    settings=json.loads((attempt/'mesh_processing.json').read_text(encoding='utf-8'))
    report['processing_settings']={k:v for k,v in settings.items() if k!='export_final'}
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    if '--self-test' in args:
        bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.scale=(2,1,1)
        bpy.ops.export_scene.gltf(filepath=str(attempt/'source.glb'),export_format='GLB')
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    if settings.get('export_final') and settings.get('repair_voxel_mm'):
        previous=json.loads((attempt/'checks.json').read_text(encoding='utf-8'))
        expected={k:v for k,v in settings.items() if k!='export_final'}
        if not previous.get('ok') or previous.get('phase')!='preview_ready' or not previous.get('repair',{}).get('passed_topology_checks'):
            raise RuntimeError('A repaired preview must pass review before export.')
        if previous.get('processing_settings')!=expected:
            raise RuntimeError('Processing settings changed since the repaired preview. Run repair/preview again before export.')
        approved=attempt/'model.blend'
        if not approved.is_file() or file_sha256(approved)!=previous.get('preview_blend_sha256'):
            raise RuntimeError('The approved preview file is missing or changed. Run repair/preview again.')
        bpy.ops.wm.open_mainfile(filepath=str(approved),load_ui=False,use_scripts=False)
        scene=bpy.context.scene;objects=meshes()
        if not objects:raise RuntimeError('Approved preview contains no meshes.')
        report=previous;report['ok']=False;report['phase']='approved_preview_loaded'
        report['repair']['exported_approved_preview']=True
        integrity=[repair_integrity(obj) for obj in objects]
        lo,hi,size=bounds();report.update(dimensions_mm=list(size),mesh_objects=len(objects),objects=integrity)
    else:
        import_options = {'filepath': str(attempt / 'source.glb')}
        if 'merge_vertices' in {p.identifier for p in bpy.ops.import_scene.gltf.get_rna_type().properties}:
            import_options['merge_vertices'] = True
        bpy.ops.import_scene.gltf(**import_options)
        scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
        objects=meshes()
        if not objects:raise RuntimeError('GLB import produced no mesh objects.')
        # Bake complete world transforms, including parent transforms, before changing orientation.
        graph=bpy.context.evaluated_depsgraph_get();baked=[]
        for obj in objects:
            ev=obj.evaluated_get(graph);mesh=bpy.data.meshes.new_from_object(ev,depsgraph=graph);mesh.transform(ev.matrix_world)
            baked.append((obj,mesh))
        for obj,mesh in baked:obj.parent=None;obj.constraints.clear();obj.modifiers.clear();obj.data=mesh;obj.matrix_world=Matrix.Identity(4)
        rot=Matrix.Identity(4)
        for axis in ('x','y','z'):rot=Matrix.Rotation(math.radians(float(settings.get('rotate_'+axis,0))),4,axis.upper())@rot
        for obj in objects:obj.data.transform(rot)
        lo,hi,size=bounds()
        # Align the longer horizontal extent with the portal's X length convention.
        if size.y>size.x:
            turn=Matrix.Rotation(math.pi/2,4,'Z')
            for obj in objects:obj.data.transform(turn)
        lo,hi,size=bounds();length=float(settings.get('length_mm',120))
        if size.x<=1e-9 or not math.isfinite(length) or not 1<=length<=1000:raise ValueError('Invalid mesh extent or requested length.')
        scale=length/size.x;center=(lo+hi)/2
        transform=Matrix.Translation(Vector((-center.x*scale,-center.y*scale,-lo.z*scale)))@Matrix.Diagonal((scale,scale,scale,1))
        for obj in objects:obj.data.transform(transform)
        report['phase']='mesh_cleanup';write()
        for obj in objects:
            bm=bmesh.new()
            try:
                bm.from_mesh(obj.data)
                # Positions are now normalized in millimeters. This joins GLB seam duplicates,
                # not a visible smoothing/remeshing operation or a general hole repair.
                before_weld = len(bm.verts)
                bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
                welded = before_weld - len(bm.verts)
                report.setdefault('seam_weld', []).append({'name': obj.name, 'vertices_merged': welded, 'tolerance_mm': 0.00001})
                if settings.get('remove_tiny'):
                    # Explicit opt-in: vertex-count heuristic can remove legitimate small details.
                    unseen=set(bm.verts);components=[]
                    while unseen:
                        start=unseen.pop();component={start};todo=[start]
                        while todo:
                            for edge in todo.pop().link_edges:
                                for vertex in edge.verts:
                                    if vertex in unseen:unseen.remove(vertex);component.add(vertex);todo.append(vertex)
                        components.append(component)
                    limit=max(8,round(len(bm.verts)*.0005))
                    small=[v for component in components if len(component)<limit for v in component]
                    if small:bmesh.ops.delete(bm,geom=small,context='VERTS');report['warnings'].append(obj.name+': removed %s vertices in tiny disconnected fragments.'%len(small))
                if settings.get('flatten'):
                    zmin=min(v.co.z for v in bm.verts);zmax=max(v.co.z for v in bm.verts);cut=zmin+min(1.0,(zmax-zmin)*.03)
                    result=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=(0,0,cut),plane_no=(0,0,1),clear_inner=True)
                    edges=[e for e in result['geom_cut'] if isinstance(e,bmesh.types.BMEdge)]
                    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
                if bm.faces:bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
                bm.to_mesh(obj.data);obj.data.update()
            finally:bm.free()
        if settings.get('repair_voxel_mm'):
            apply_solid_repair(objects,settings)
        lo,hi,size=bounds()
        for obj in objects:obj.data.transform(Matrix.Translation((0,0,-lo.z)))
        integrity=[]
        for obj in objects:
            bm=bmesh.new()
            try:
                bm.from_mesh(obj.data)
                opened=sum(not e.is_manifold for e in bm.edges);volume=abs(bm.calc_volume()) if bm.faces else 0
                integrity.append({'name':obj.name,'vertices':len(bm.verts),'faces':len(bm.faces),'non_manifold_edges':opened,'volume_mm3':volume})
                if opened:report['warnings'].append('%s: %s non-manifold/boundary edges; inspect before printing.'%(obj.name,opened))
                if volume<1e-6:report['warnings'].append(obj.name+': effectively zero enclosed volume.')
            finally:bm.free()
        integrity=[repair_integrity(obj) for obj in objects]
        if report.get('repair',{}).get('applied'):
            report['repair']['after']=integrity
            report['repair']['passed_topology_checks']=not repair_problematic(integrity)
            if repair_problematic(integrity):report['warnings'].append('Solid repair still fails the limited topology checks. Export remains blocked; inspect and try a different repair resolution.')
        lo,hi,size=bounds();report.update(dimensions_mm=list(size),mesh_objects=len(objects),objects=integrity)
        report['warnings'].append('Single-image shape is inferred. No automatic articulation, local wall-thickness, collision, color-region or slicer certification.')
    if settings.get('export_final'):
        problematic=repair_problematic(integrity)
        if problematic and (settings.get('repair_voxel_mm') or not settings.get('allow_mesh_warnings')):raise RuntimeError('Mesh still fails topology/volume checks. Repair needs a valid new preview before solid export. Details: ' + json.dumps(integrity) + '. Return to preview or explicitly accept warnings; validation has not been bypassed.')
        report['mesh_warnings_explicitly_accepted']=bool(problematic)
        report['phase']='export';write();module=cfg['addon_module'];addon_utils.enable(module,default_set=False,persistent=False)
        if not addon_utils.check(module)[1]:raise RuntimeError('Could not enable installed 3MF exporter '+module)
        operator=bpy.ops.export_mesh.threemf;rna=operator.get_rna_type();valid={p.identifier:p for p in rna.properties};options=dict(cfg.get('export_settings',{}))
        for key,value in options.items():
            if key not in valid:raise RuntimeError('Unknown 3MF setting '+key)
            if valid[key].type=='ENUM' and value not in {i.identifier for i in valid[key].enum_items}:raise ValueError('Invalid 3MF enum '+key)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.hide_set(False);obj.hide_render=False;obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];options['filepath']=str(attempt/'model.3mf')
        if 'check_existing' in valid:options['check_existing']=False
        if 'thumbnail_mode' in valid and 'thumbnail_mode' not in options:
            for item in valid['thumbnail_mode'].enum_items:
                if item.identifier.upper() in {'NONE','OFF','DISABLED'}:options['thumbnail_mode']=item.identifier;break
        if 'FINISHED' not in operator(**options):raise RuntimeError('3MF export did not finish.')
        with zipfile.ZipFile(attempt/'model.3mf') as archive:
            if archive.testzip() or not any(n.endswith('.model') for n in archive.namelist()):raise RuntimeError('Invalid 3MF output archive.')
        bpy.ops.export_scene.gltf(filepath=str(attempt/'model.glb'),export_format='GLB',use_selection=True)
    report['phase']='render';write()
    center=(lo+hi)/2;radius=max((o.matrix_world@v.co-center).length for o in objects for v in o.data.vertices)
    camera_data=bpy.data.cameras.new('PortalCamera');camera=bpy.data.objects.new('PortalCamera',camera_data);scene.collection.objects.link(camera);scene.camera=camera
    camera_data.type='ORTHO';camera_data.ortho_scale=max(radius*2.35,1);camera_data.clip_start=.01;camera_data.clip_end=max(radius*20,10000)
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.background_type='WORLD'
    if scene.world is None:scene.world=bpy.data.worlds.new('PortalWorld')
    scene.world.color=(.12,.12,.12);scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    for name,direction in [('preview.png',(-1.4,-1.8,1.25)),('preview_side.png',(0,-1,.05)),('preview_top.png',(0,0,1))]:
        camera.location=center+Vector(direction).normalized()*max(radius*4,10);camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(attempt/name);bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(attempt/'model.blend'))
    if settings.get('repair_voxel_mm'):report['preview_blend_sha256']=file_sha256(attempt/'model.blend')
    report.update(ok=True,phase='finished' if settings.get('export_final') else 'preview_ready');write();print('HUNYUAN_PORTAL_MESH_PROCESSING_PASSED')
except Exception:
    report['error']=traceback.format_exc();write();raise
