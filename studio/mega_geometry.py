"""Reusable closed-mesh baseline. Pure geometry functions are testable without Blender."""
import math


def _sub(a,b):return tuple(a[i]-b[i] for i in range(3))
def _add(a,b):return tuple(a[i]+b[i] for i in range(3))
def _mul(a,s):return tuple(v*s for v in a)
def _dot(a,b):return sum(a[i]*b[i] for i in range(3))
def _cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _unit(a):
    size=math.sqrt(_dot(a,a))
    if size<1e-12:raise ValueError('Zero-length direction.')
    return _mul(a,1/size)


def ellipsoid_data(center,radii,floor=0.0,sides=32,rings=14):
    cx,cy,cz=center;rx,ry,rz=radii
    if min(radii)<=0:raise ValueError('Positive ellipsoid radii required.')
    z0=max(cz-rz,floor)
    if z0>=cz+rz:raise ValueError('Floor removes ellipsoid.')
    phi0=math.asin(max(-1,min(1,(z0-cz)/rz)))
    clipped=z0>cz-rz+1e-7
    vertices=[];faces=[];layers=[]
    if not clipped:
        vertices.append((cx,cy,cz-rz))
    start=0 if clipped else 1
    for j in range(start,rings):
        phi=phi0+(math.pi/2-phi0)*j/rings
        ring=[]
        for i in range(sides):
            angle=2*math.pi*i/sides
            ring.append(len(vertices))
            vertices.append((cx+rx*math.cos(phi)*math.cos(angle),cy+ry*math.cos(phi)*math.sin(angle),cz+rz*math.sin(phi)))
        layers.append(ring)
    if clipped:
        faces.append(tuple(reversed(layers[0])))
    else:
        for i in range(sides):faces.append((0,layers[0][(i+1)%sides],layers[0][i]))
    for lower,upper in zip(layers,layers[1:]):
        for i in range(sides):
            n=(i+1)%sides;faces.append((lower[i],lower[n],upper[n],upper[i]))
    top=len(vertices);vertices.append((cx,cy,cz+rz))
    for i in range(sides):faces.append((top,layers[-1][i],layers[-1][(i+1)%sides]))
    return vertices,faces


def tube_data(centers,radii,sides=24):
    if len(centers)<2 or len(centers)!=len(radii):raise ValueError('Invalid tube path.')
    vertices=[];faces=[];layers=[]
    for j,(center,radius) in enumerate(zip(centers,radii)):
        if radius<=0:raise ValueError('Tube tips must have positive radius.')
        tangent=_unit(_sub(centers[min(j+1,len(centers)-1)],centers[max(0,j-1)]))
        reference=(0,0,1) if abs(tangent[2])<.8 else (0,1,0)
        u=_unit(_cross(tangent,reference));v=_cross(tangent,u)
        layer=[]
        for i in range(sides):
            angle=2*math.pi*i/sides
            point=_add(center,_add(_mul(u,radius*math.cos(angle)),_mul(v,radius*math.sin(angle))))
            layer.append(len(vertices));vertices.append(point)
        layers.append(layer)
    faces.append(tuple(reversed(layers[0])))
    for a,b in zip(layers,layers[1:]):
        for i in range(sides):
            n=(i+1)%sides;faces.append((a[i],a[n],b[n],b[i]))
    faces.append(tuple(layers[-1]))
    return vertices,faces


def _triangulate_outline(points):
    def cross2(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
    order=list(range(len(points)))
    if area<0:order.reverse()
    triangles=[]
    def inside(p,a,b,c):return min(cross2(a,b,p),cross2(b,c,p),cross2(c,a,p))>=-1e-9
    while len(order)>3:
        for i,b in enumerate(order):
            a=order[i-1];c=order[(i+1)%len(order)]
            if cross2(points[a],points[b],points[c])<=1e-9:continue
            if any(inside(points[k],points[a],points[b],points[c]) for k in order if k not in (a,b,c)):continue
            triangles.append((a,b,c));order.pop(i);break
        else:raise ValueError('Wing outline is self-crossing or degenerate.')
    triangles.append(tuple(order))
    return triangles


def wing_data(side,thickness=2.8):
    # Root lies inside the body; broad scalloped membrane extends sideways.
    outline=[(-8,0),(-13,8),(-12,20),(-3,17),(2,23),(6,15),(15,18),(11,9),(16,3),(8,0)]
    polygon=[(x,side*(6+y)) for x,y in outline]
    area=sum(polygon[i][0]*polygon[(i+1)%len(polygon)][1]-polygon[(i+1)%len(polygon)][0]*polygon[i][1] for i in range(len(polygon)))
    if area<0:polygon.reverse()
    n=len(polygon);vertices=[]
    for upper in (False,True):
        for x,y in polygon:
            mid=12+.16*(abs(y)-6)
            vertices.append((x,y,mid+(thickness/2 if upper else -thickness/2)))
    triangles=_triangulate_outline(polygon)
    faces=[tuple(reversed(t)) for t in triangles]+[tuple(i+n for i in t) for t in triangles]
    for i in range(n):
        j=(i+1)%n;faces.append((i,j,n+j,n+i))
    return vertices,faces


def dragon_specs(length_mm=120.0):
    length_mm=float(length_mm)
    if not math.isfinite(length_mm) or not 80<=length_mm<=180:raise ValueError('Baseline supports 80..180mm length; use 120mm for the first test.')
    specs=[]
    def add(name,color,data,parent=None):
        verts,faces=data;specs.append({'name':name,'color':color,'vertices':verts,'faces':faces,'parent':parent})
    def egg(name,color,center,radii,parent=None):add(name,color,ellipsoid_data(center,radii),parent)
    egg('Body','Orange',(0,0,9),(24,10,10))
    egg('Head','Orange',(-29,0,12),(13,10,11),'Body')
    egg('Snout','Orange',(-42,0,9),(10,7,6),'Head')
    for label,side in [('Left',-1),('Right',1)]:
        egg('Eye_'+label,'Green',(-35,side*8.6,16),(2.1,2.1,2.1),'Head')
        add('Horn_'+label,'Purple',tube_data([(-28,side*5.8,20),(-26,side*6.4,25),(-23,side*7,29)],[2.9,2.0,1.3]),'Head')
        add('Wing_'+label,'Purple',wing_data(side),'Body')
        for location,x in [('Front',-14),('Rear',13)]:
            leg='Leg_'+location+'_'+label
            egg(leg,'Orange',(x,side*9,4),(6,4.2,6),'Body')
            egg('Foot_'+location+'_'+label,'Orange',(x-2,side*11,2),(6.5,4.8,3.2),leg)
    add('Tail','Orange',tube_data([(17,0,8),(28,0,7.5),(40,1,6),(51,2,4.5),(61,1,3),(68,0,2)],[7.5,6.0,4.6,3.2,2.0,1.3]),'Body')
    for i,x in enumerate((-10,-2,6,14),1):
        add('Back_Spike_'+str(i),'Purple',tube_data([(x,0,16),(x+1,0,21),(x+2,0,23)],[2.8,1.8,1.3]),'Body')
    all_points=[v for s in specs for v in s['vertices']]
    minimum=[min(v[i] for v in all_points) for i in range(3)]
    maximum=[max(v[i] for v in all_points) for i in range(3)]
    scale=length_mm/(maximum[0]-minimum[0])
    for spec in specs:
        spec['vertices']=[(x*scale,y*scale,(z-minimum[2])*scale) for x,y,z in spec['vertices']]
    return specs


def _material(name,rgba):
    import bpy
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=rgba
    if mat.node_tree is None:mat.use_nodes=True
    nodes=mat.node_tree.nodes;nodes.clear()
    shader=nodes.new('ShaderNodeBsdfPrincipled');output=nodes.new('ShaderNodeOutputMaterial')
    shader.inputs['Base Color'].default_value=rgba
    shader.inputs['Roughness'].default_value=.65
    mat.node_tree.links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    return mat


def build_stylized_dragon(length_mm=120.0):
    import bpy
    import bmesh
    from mathutils.bvhtree import BVHTree
    if any(o.type=='MESH' for o in bpy.context.scene.objects):
        raise RuntimeError('Dragon builder expects an empty mesh scene; do not mix it with generated placeholder objects.')
    specs=dragon_specs(length_mm)
    colors={'Orange':(1.0,.32,.06,1.0),'Purple':(.42,.07,.72,1.0),'Green':(.1,.85,.2,1.0)}
    materials={name:_material(name,rgba) for name,rgba in colors.items()}
    objects={};trees={};statistics=[]
    for spec in specs:
        mesh=bpy.data.meshes.new(spec['name']+'_Mesh')
        mesh.from_pydata(spec['vertices'],[],spec['faces']);mesh.update()
        if mesh.validate(verbose=True):raise RuntimeError('Builder generated invalid data: '+spec['name'])
        bm=bmesh.new()
        try:
            bm.from_mesh(mesh)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
            if any(not e.is_manifold for e in bm.edges):raise RuntimeError('Builder part is not closed: '+spec['name'])
            volume=abs(bm.calc_volume(signed=True))
            if volume<1e-8:raise RuntimeError('Builder part has zero volume: '+spec['name'])
            bm.to_mesh(mesh)
        finally:bm.free()
        mesh.update();obj=bpy.data.objects.new(spec['name'],mesh)
        bpy.context.scene.collection.objects.link(obj);obj.data.materials.append(materials[spec['color']])
        for polygon in mesh.polygons:polygon.use_smooth=spec['name'].startswith(('Head','Body','Snout','Eye','Leg','Foot','Tail'))
        objects[spec['name']]=obj
        mesh.calc_loop_triangles()
        triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
        trees[spec['name']]=BVHTree.FromPolygons([tuple(v.co) for v in mesh.vertices],triangles,all_triangles=True)
        statistics.append({'name':spec['name'],'closed':True,'volume_mm3':volume})
    contacts=[]
    for spec in specs:
        parent=spec['parent']
        if parent:
            # This is a surface-intersection test, not a weld/strength/slicer guarantee.
            overlap=trees[spec['name']].overlap(trees[parent])
            if not overlap:raise RuntimeError('Expected attachment has no intersecting surfaces: '+spec['name']+' -> '+parent)
            contacts.append({'part':spec['name'],'parent':parent,'surface_intersection':True})
    vertices=[v.co for obj in objects.values() for v in obj.data.vertices]
    low=[min(v[i] for v in vertices) for i in range(3)]
    high=[max(v[i] for v in vertices) for i in range(3)]
    dimensions=[high[i]-low[i] for i in range(3)]
    if abs(dimensions[0]-length_mm)>.01:raise RuntimeError('Baseline length normalization failed.')
    if abs(low[2])>1e-5:raise RuntimeError('Baseline grounding failed.')
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.001
    return {'builder':'MEGA_DRAGON_BASELINE_v1','dimensions_mm':dimensions,'lowest_z_mm':low[2],
            'parts':statistics,'attachment_surface_checks':contacts,
            'limitations':'Intersecting separate solids are not Boolean-unioned; no wall-thickness, self-intersection, slicer, articulation or printability certification.'}
