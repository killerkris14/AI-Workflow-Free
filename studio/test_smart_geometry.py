# Blender self-test for the v3 smart geometry helpers. Run:
# blender --background --python-exit-code 1 --python test_smart_geometry.py
import sys
from pathlib import Path
import bpy
import bmesh
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smart_geometry as g
from quality_support import plan_to_script

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
orange = g.make_material('Orange', (1.0, 0.45, 0.05, 1))
g.make_ellipsoid('Body', center=(20, 0, 12), size=(60, 26, 20), material=orange)
g.make_box('Base', center=(20, 0, 2), size=(30, 10, 4), material=orange)
g.make_cylinder_between('Leg', start=(0, -8, 0), end=(0, -8, 12), radius=3.5, material=orange)
g.make_tapered_between('Tail', start=(48, 0, 12), end=(90, 0, 10), radius_start=6, radius_end=1.5, material=orange)
g.make_wing('Wing_Left', side='left', root_x=15, root_y=-10, z_bottom=14, span_mm=28, chord_mm=24, material=(0.45, 0.15, 0.7, 1))
g.make_solid_profile('Fin', [(0, 0, 5), (10, 0, 5), (5, 8, 5)], 2, orange, z_bottom=20)  # 3D points: auto-corrected
assert any('3rd value' in w for w in g.WARNINGS), 'expected 3D outline warning'
g.ground_assembly()
g.fit_assembly(target_length_mm=120, max_width_mm=65, max_height_mm=35)
g.flatten_underside(1.5)
g.assert_assembly_bounds(target_length_mm=120, max_width_mm=65, max_height_mm=35)
lo, hi, size = g.assembly_bounds()
assert abs(size[0] - 120) < 1.5 and size[1] <= 65.5 and size[2] <= 35.5 and abs(lo[2]) < 0.01, (lo, hi, size)
for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    open_edges = [e for e in bm.edges if not e.is_manifold]
    vol = bm.calc_volume()
    bm.free()
    assert not open_edges, obj.name + ' is not closed'
    assert abs(vol) > 1, obj.name + ' has no volume'
script = plan_to_script({'target_length_mm': 120, 'max_width_mm': 65, 'max_height_mm': 35, 'parts': [
    {'name': 'Body', 'shape': 'ellipsoid', 'center_mm': [0, 0, 10], 'size_mm': [60, 20, 16], 'color': 'orange'},
    {'name': 'Wing_Left', 'shape': 'wing', 'center_mm': [0, -15, 12], 'size_mm': [20, 20, 3], 'color': 'purple'}]})
compile(script, 'plan_script', 'exec')
print('SMART_GEOMETRY_SELF_TEST_PASSED')
