import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,bmesh
import smart_geometry as g
from image_fidelity import register_helpers,overlap_volume
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
helpers=register_helpers()
mat=g.make_material('TestOrange',(1,.45,.05,1))
a=g.make_ellipsoid('A',(0,0,10),(20,20,20),mat)
b=g.make_ellipsoid('B',(20,0,10),(20,20,20),mat)
bpy.context.view_layer.update()
assert overlap_volume(a,b)<.01,'Tangent ellipsoids must not pass volume overlap.'
b.location.x=-3;bpy.context.view_layer.update()
assert overlap_volume(a,b)>.01,'Intersecting ellipsoids must have positive volume.'
eye=helpers['make_surface_eye']('Eye_Left',a,(-.4,-1,.2),diameter=5,material=mat,embed_mm=.8)
assert overlap_volume(a,eye)>.01,'Surface eye must overlap its parent.'
tube=helpers['make_swept_tube']('CurvedHorn',[(0,0,22),(2,0,27),(4,0,30),(7,0,31)],[2.5,2,1,.5],mat)
bm=bmesh.new()
try:
 bm.from_mesh(tube.data)
 assert all(e.is_manifold for e in bm.edges),'Loft must be closed.'
 assert abs(bm.calc_volume())>.01,'Loft must have nonzero volume.'
finally:bm.free()
# Uniform fit must reject incompatible width, rather than squeeze it.
try:g.fit_assembly(target_length_mm=120,max_width_mm=1,max_height_mm=35)
except ValueError:pass
else:raise AssertionError('Uniform fit silently accepted an impossible width.')
print('REFERENCE_FIDELITY_SELF_TEST_PASSED')
