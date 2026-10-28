# RUNNER v3 - trusted Blender runner: smart geometry helpers, checks, 3MF export, previews.
import bpy
import addon_utils
import sys
import json
import math
import traceback
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from mathutils import Vector

# QUALITY PIPELINE PATCH v1
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality_support import quality_geometry_gate, quality_extra_previews
import smart_geometry
make_material = smart_geometry.make_material

args = sys.argv[sys.argv.index('--') + 1:]
job = Path(args[0]).resolve()
config = json.loads(Path(args[1]).read_text(encoding='utf-8'))
report = {'ok': False, 'phase': 'startup', 'warnings': []}

def write_report():
    (job / 'checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

def enable_exporter():
    module = config['addon_module']
    addon_utils.enable(module, default_set=False, persistent=False)
    if not addon_utils.check(module)[1]:
        raise RuntimeError('Could not enable installed 3MF extension: ' + module)
    return bpy.ops.export_mesh.threemf.get_rna_type()

try:
    report['phase'] = 'exporter_configuration'
    write_report()
    rna = enable_exporter()
    if '--inspect' in args:
        props = {}
        for p in rna.properties:
            if p.identifier == 'rna_type':
                continue
            item = {'type': p.type, 'description': p.description}
            try:
                item['default'] = p.default
            except Exception:
                pass
            if p.type == 'ENUM':
                item['choices'] = [{'id': i.identifier, 'name': i.name} for i in p.enum_items]
            props[p.identifier] = item
        (job / 'exporter_properties.json').write_text(json.dumps(props, indent=2), encoding='utf-8')
        print('EXPORTER_INSPECTION_OK')
    else:
        report['phase'] = 'modeling'
        write_report()
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = 0.001
        source = job / 'model.py'
        namespace = {'__name__': '__main__', '__file__': str(source), 'math': math, 'Vector': Vector}
        from image_fidelity import register_helpers
        register_helpers()
        namespace.update(smart_geometry.HELPERS)
        smart_geometry.WARNINGS.clear()
        if config.get('enable_legacy_dragon_workflow', False):
            from mega_geometry import build_stylized_dragon
            namespace['build_stylized_dragon'] = build_stylized_dragon
        try:
            exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), namespace)
        finally:
            report['helper_warnings'] = list(smart_geometry.WARNINGS)
        if isinstance(namespace.get('mega_build_report'), dict):
            report['mega_build'] = namespace['mega_build_report']
        from quality_support import color_map
        request_text = json.loads((job.parent / 'request.json').read_text(encoding='utf-8')).get('instructions', '')
        explicit_colors = color_map(request_text)
        import re
        color_materials = {}
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                continue
            words = [w.rstrip('s') for w in re.findall(r'[a-z]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', obj.name).lower())]
            if any(w in {'pupil', 'outline', 'highlight'} for w in words):
                continue
            rgba = next((explicit_colors[w] for w in words if w in explicit_colors), None)
            if rgba is not None:
                key = tuple(rgba)
                if key not in color_materials:
                    color_materials[key] = make_material('RequestedColor_' + str(len(color_materials)), rgba)
                obj.data.materials.clear()
                obj.data.materials.append(color_materials[key])
                for polygon in obj.data.polygons:
                    polygon.material_index = 0
        scene = bpy.context.scene
        if scene.unit_settings.system != 'METRIC' or abs(scene.unit_settings.scale_length - .001) > 1e-9:
            raise RuntimeError('Model script changed required millimeter unit settings.')

        report['phase'] = 'geometry_validation'
        write_report()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        meshes = [o for o in scene.objects if o.type == 'MESH']
        if not meshes:
            raise RuntimeError('No mesh objects created.')
        points = []
        stats = []
        for obj in meshes:
            # Mesh-integrity guard v1: reject invalid data before evaluated drawing.
            for polygon in obj.data.polygons:
                if len(polygon.vertices) < 3:
                    raise RuntimeError('Invalid polygon in ' + obj.name + ': fewer than three vertices. Use actual closed mesh geometry, not two-vertex faces.')
            if obj.data.validate(verbose=True):
                raise RuntimeError('Invalid mesh data was found in ' + obj.name + ' and Blender corrected/removed it. Rejecting this attempt; regenerate valid solid geometry.')
            if obj.data.validate_material_indices():
                raise RuntimeError('Invalid face material indices in ' + obj.name + '. Assign only existing material slots.')
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                # Evaluated-integrity guard v1: includes modifier output.
                for polygon in mesh.polygons:
                    if len(polygon.vertices) < 3:
                        raise RuntimeError('Invalid evaluated face in ' + obj.name)
                if mesh.validate(verbose=True):
                    raise RuntimeError('Invalid evaluated mesh in ' + obj.name + '. Regenerate valid solid geometry.')
                if mesh.validate_material_indices():
                    raise RuntimeError('Invalid evaluated material indices in ' + obj.name)
                if not mesh.vertices or not mesh.polygons:
                    raise RuntimeError('Empty or faceless mesh: ' + obj.name)
                vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
                if not all(math.isfinite(c) for v in vertices for c in v):
                    raise RuntimeError('Nonfinite coordinates in ' + obj.name)
                points.extend(vertices)
                stats.append({'name': obj.name, 'vertices': len(mesh.vertices), 'faces': len(mesh.polygons),
                              'materials': [m.name if m else None for m in obj.data.materials]})
            finally:
                evaluated.to_mesh_clear()
        low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        size = high - low
        if any(v <= 1e-6 for v in size):
            raise RuntimeError('Model must have nonzero extent along all three axes.')
        report.update({'mesh_objects': len(meshes), 'objects': stats, 'dimensions_mm': list(size),
                       'scene_unit_scale': scene.unit_settings.scale_length})
        quality_geometry_gate(meshes, points, job, report)
        from image_fidelity import attachment_gate
        attachment_gate(meshes, job, report)
        report['warnings'].append('Execution/export checks are NOT proof of manifold geometry, printability, fit, articulation, or visual similarity.')
        if any(s['materials'] == [] for s in stats):
            report['warnings'].append('Some objects have no assigned materials.')

        report['phase'] = 'export_configuration'
        write_report()
        options = dict(config.get('export_settings', {}))
        valid = {p.identifier: p for p in rna.properties}
        for key, value in options.items():
            if key not in valid:
                raise RuntimeError('Unknown 3MF export setting: ' + key)
            prop = valid[key]
            if prop.type == 'ENUM' and value not in {i.identifier for i in prop.enum_items}:
                raise RuntimeError('Invalid export enum for ' + key + ': ' + str(value))
        options['filepath'] = str(job / 'model.3mf')
        if 'check_existing' in valid:
            options['check_existing'] = False
        if 'thumbnail_mode' in valid and 'thumbnail_mode' not in options:
            prop = valid['thumbnail_mode']
            if prop.type == 'ENUM':
                for item in prop.enum_items:
                    if item.identifier.upper() in {'NONE', 'OFF', 'DISABLED'}:
                        options['thumbnail_mode'] = item.identifier
                        break
        bpy.ops.object.select_all(action='DESELECT')
        for obj in meshes:
            obj.hide_set(False)
            obj.hide_render = False
            obj.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        report['export_settings_used'] = options
        report['phase'] = 'export'
        write_report()
        result = bpy.ops.export_mesh.threemf(**options)
        if 'FINISHED' not in result:
            raise RuntimeError('Exporter did not return FINISHED: ' + repr(result))
        output = job / 'model.3mf'
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError('Exporter produced no 3MF file.')
        report['phase'] = 'archive_validation'
        write_report()
        with zipfile.ZipFile(output) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError('Corrupt 3MF archive member: ' + bad)
            names = archive.namelist()
            if '[Content_Types].xml' not in names:
                raise RuntimeError('Missing 3MF content types.')
            models = [n for n in names if n.lower().endswith('.model')]
            if not models:
                raise RuntimeError('No model XML in 3MF archive.')
            mesh_count = 0
            for name in models:
                root = ET.fromstring(archive.read(name))
                mesh_count += sum(1 for e in root.iter() if e.tag.rsplit('}', 1)[-1] == 'mesh')
            if mesh_count < 1:
                raise RuntimeError('No mesh data in 3MF model XML.')
        report['archive_mesh_count'] = mesh_count

        from image_fidelity import reference_file
        original_image = bpy.data.images.load(str(reference_file(job.parent)), check_existing=False)
        try:
            width, height = original_image.size
            factor = min(1.0, 768.0 / max(width, height))
            if factor < 1:
                original_image.scale(max(1, round(width * factor)), max(1, round(height * factor)))
            original_image.filepath_raw = str(job / 'reference_small.png')
            original_image.file_format = 'PNG'
            original_image.save()
        finally:
            bpy.data.images.remove(original_image)
        report['phase'] = 'preview_setup'
        write_report()
        center = (low + high) / 2
        radius = max((p - center).length for p in points)
        camera_data = bpy.data.cameras.new('WorkflowPreviewCamera')
        camera = bpy.data.objects.new('WorkflowPreviewCamera', camera_data)
        scene.collection.objects.link(camera)
        camera.location = center + Vector((-1.4, -1.8, 1.25)).normalized() * max(radius * 4, 10)
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera_data.type = 'ORTHO'
        camera_data.ortho_scale = max(radius * 2.35, 1)
        camera_data.clip_start = .01
        camera_data.clip_end = max(radius * 20, 10000)
        scene.camera = camera
        # Preview engine patch: assign directly rather than enumerate RNA.
        try:
            scene.render.engine = 'BLENDER_WORKBENCH'
        except (TypeError, ValueError) as engine_error:
            raise RuntimeError('Could not select BLENDER_WORKBENCH. Blender reported: ' + str(engine_error)) from engine_error
        shading = scene.display.shading
        shading.light = 'STUDIO'
        shading.color_type = 'MATERIAL'
        shading.background_type = 'WORLD'
        if scene.world is None:
            scene.world = bpy.data.worlds.new('WorkflowWorld')
        scene.world.color = (.12, .12, .12)
        scene.render.resolution_x = int(config.get('preview_size', 900))
        scene.render.resolution_y = int(config.get('preview_size', 900))
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'
        scene.render.film_transparent = False
        scene.render.filepath = str(job / 'preview.png')
        report['phase'] = 'save_blend'
        write_report()
        bpy.ops.wm.save_as_mainfile(filepath=str(job / 'model.blend'))
        report['phase'] = 'render'
        write_report()
        bpy.ops.render.render(write_still=True)
        quality_extra_previews(scene, camera, center, radius, job)
        report['phase'] = 'output_validation'
        write_report()
        for name in ['model.blend', 'model.3mf', 'preview.png']:
            f = job / name
            if not f.exists() or f.stat().st_size == 0:
                raise RuntimeError('Missing or empty deliverable: ' + name)
        if (job / 'preview.png').read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise RuntimeError('Preview is not a PNG.')
        report.update({'ok': True, 'phase': 'finished'})
        write_report()
        print('WORKFLOW_BUILD_EXPORTED_AND_RENDERED')
except Exception:
    report['error'] = traceback.format_exc()
    write_report()
    raise
