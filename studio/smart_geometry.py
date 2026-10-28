# SMART GEOMETRY v3 - trusted helpers injected into generated Blender scripts.
# Units: 1 Blender unit = 1 mm. X = length (head -X, tail +X), Y = width, Z = height.
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

WARNINGS = []


def _warn(text):
    if text not in WARNINGS:
        WARNINGS.append(text)


def _num(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(what + ' must be a number, got ' + repr(value)) from None
    if not math.isfinite(number):
        raise ValueError(what + ' must be finite, got ' + repr(value))
    return number


def _vec(value, count, what, example):
    try:
        items = [float(v) for v in value]
    except (TypeError, ValueError):
        raise ValueError(what + ' must be a list of ' + str(count) + ' numbers, e.g. ' + example + '. Got ' + repr(value)) from None
    if len(items) != count or not all(math.isfinite(v) for v in items):
        raise ValueError(what + ' must have exactly ' + str(count) + ' finite numbers, e.g. ' + example + '. Got ' + repr(value))
    return items


def _take(kwargs, names, default=None):
    for name in names:
        if name in kwargs:
            return kwargs.pop(name)
    return default


def _no_extra(kwargs, signature):
    if kwargs:
        raise TypeError('Unknown argument(s) ' + ', '.join(sorted(kwargs)) + '. Correct signature: ' + signature)


def make_material(name, color, roughness=0.65):
    """Solid-color material with an explicit shader graph."""
    rgba = tuple(float(v) for v in color)
    if len(rgba) == 3:
        rgba = rgba + (1.0,)
    if len(rgba) != 4 or not all(math.isfinite(v) for v in rgba):
        raise ValueError('make_material requires three or four finite color values.')
    material = bpy.data.materials.new(name=str(name))
    material.diffuse_color = rgba
    if material.node_tree is None:
        material.use_nodes = True
    tree = material.node_tree
    if tree is None:
        raise RuntimeError('Could not initialize material node tree: ' + str(name))
    tree.nodes.clear()
    shader = tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    output = tree.nodes.new(type='ShaderNodeOutputMaterial')
    shader.inputs['Base Color'].default_value = rgba
    shader.inputs['Roughness'].default_value = float(roughness)
    tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    return material


def _material(material, name):
    if material is None or isinstance(material, bpy.types.Material):
        return material
    if isinstance(material, (tuple, list)) and len(material) in (3, 4):
        _warn(name + ': a color tuple was passed as material; converted with make_material.')
        return make_material(name + '_Color', material)
    raise ValueError(name + ': material must be a value returned by make_material(name, rgba).')


def _finish(name, bm, material):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(str(name))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(str(name), mesh)
    bpy.context.scene.collection.objects.link(obj)
    material = _material(material, str(name))
    if material is not None:
        mesh.materials.append(material)
    if obj.name != str(name):
        _warn('Object name "' + str(name) + '" already existed; Blender renamed it to "' + obj.name + '". Use unique names.')
    return obj


def make_ellipsoid(name, center=None, size=None, material=None, segments=32, rings=16, **kw):
    """make_ellipsoid(name, center_xyz, size_xyz, material). size = full X/Y/Z extents in mm."""
    center = center if center is not None else _take(kw, ('center_mm', 'location', 'position'))
    size = size if size is not None else _take(kw, ('size_mm', 'dimensions', 'dims', 'scale'))
    material = material if material is not None else _take(kw, ('mat', 'color'))
    _no_extra(kw, 'make_ellipsoid(name, center_xyz, size_xyz, material)')
    c = _vec(center, 3, name + ' center', '(0, 0, 10)')
    s = [max(abs(v), 0.5) for v in _vec(size, 3, name + ' size', '(40, 20, 16)')]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=int(segments), v_segments=int(rings), radius=0.5)
    for v in bm.verts:
        v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
    obj = _finish(name, bm, material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def make_box(name, center=None, size=None, material=None, **kw):
    """make_box(name, center_xyz, size_xyz, material)."""
    center = center if center is not None else _take(kw, ('center_mm', 'location', 'position'))
    size = size if size is not None else _take(kw, ('size_mm', 'dimensions', 'dims', 'scale'))
    material = material if material is not None else _take(kw, ('mat', 'color'))
    _no_extra(kw, 'make_box(name, center_xyz, size_xyz, material)')
    c = _vec(center, 3, name + ' center', '(0, 0, 5)')
    s = [max(abs(v), 0.4) for v in _vec(size, 3, name + ' size', '(20, 10, 10)')]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
    return _finish(name, bm, material)


def _between(name, start, end, r1, r2, material, segments):
    a = Vector(_vec(start, 3, name + ' start', '(0, 0, 10)'))
    b = Vector(_vec(end, 3, name + ' end', '(40, 0, 10)'))
    axis = b - a
    if axis.length < 0.2:
        raise ValueError(name + ': start and end points are the same. Give two different (x, y, z) points.')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=int(segments),
                          radius1=r1, radius2=r2, depth=axis.length)
    rot = Vector((0, 0, 1)).rotation_difference(axis.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=bm.verts[:])
    return _finish(name, bm, material)


def make_cylinder_between(name, start=None, end=None, radius=None, material=None, segments=24, **kw):
    """make_cylinder_between(name, start_xyz, end_xyz, radius_mm, material)."""
    start = start if start is not None else _take(kw, ('start_mm', 'p1', 'point1', 'a'))
    end = end if end is not None else _take(kw, ('end_mm', 'p2', 'point2', 'b'))
    radius = radius if radius is not None else _take(kw, ('radius_mm', 'r'))
    diameter = _take(kw, ('diameter', 'diameter_mm'))
    material = material if material is not None else _take(kw, ('mat', 'color'))
    _no_extra(kw, 'make_cylinder_between(name, start_xyz, end_xyz, radius_mm, material)')
    if radius is None and diameter is not None:
        radius = _num(diameter, name + ' diameter') / 2
    r = max(abs(_num(radius, name + ' radius')), 0.6)
    return _between(name, start, end, r, r, material, segments)


def make_tapered_between(name, start=None, end=None, radius_start=None, radius_end=None, material=None, segments=24, **kw):
    """make_tapered_between(name, start_xyz, end_xyz, radius_start_mm, radius_end_mm, material). Thick end at start."""
    start = start if start is not None else _take(kw, ('start_mm', 'p1', 'point1'))
    end = end if end is not None else _take(kw, ('end_mm', 'p2', 'point2'))
    radius_start = radius_start if radius_start is not None else _take(kw, ('start_radius', 'radius1', 'r1', 'base_radius', 'radius'))
    radius_end = radius_end if radius_end is not None else _take(kw, ('end_radius', 'radius2', 'r2', 'tip_radius'))
    material = material if material is not None else _take(kw, ('mat', 'color'))
    _no_extra(kw, 'make_tapered_between(name, start_xyz, end_xyz, radius_start_mm, radius_end_mm, material)')
    r1 = max(abs(_num(radius_start, name + ' radius_start')), 0.6)
    r2 = abs(_num(radius_end if radius_end is not None else r1 * 0.35, name + ' radius_end'))
    if r2 < 0.6:
        _warn(name + ': tip radius raised to 0.6 mm (blunt, printable tip).')
        r2 = 0.6
    return _between(name, start, end, r1, r2, material, segments)


def _clean_outline(name, points):
    clean = []
    for p in points:
        if not clean or (Vector(p) - Vector(clean[-1])).length > 1e-4:
            clean.append(p)
    if len(clean) > 2 and (Vector(clean[0]) - Vector(clean[-1])).length <= 1e-4:
        clean.pop()
    if len(clean) < 3:
        raise ValueError(name + ': outline needs at least 3 different (x, y) points.')
    area = 0.0
    for i, (x1, y1) in enumerate(clean):
        x2, y2 = clean[(i + 1) % len(clean)]
        area += x1 * y2 - x2 * y1
    area /= 2
    if abs(area) < 1.0:
        raise ValueError(name + ': outline encloses almost no area (points are in a line). '
                         'The outline is a top-down (x, y) shape, e.g. a wing: [(0, -8), (15, -8), (30, -40), (5, -30)].')
    if area < 0:
        clean.reverse()
    return clean


def make_solid_profile(name, outline_xy=None, thickness_mm=None, material=None, z_bottom=None, **kw):
    """make_solid_profile(name, outline_xy=[(x, y), ...], thickness_mm, material, z_bottom=0).
    A flat top-down outline extruded upward in +Z by thickness_mm, starting at z_bottom."""
    outline_xy = outline_xy if outline_xy is not None else _take(kw, ('points', 'outline', 'profile', 'vertices', 'points_xy'))
    thickness_mm = thickness_mm if thickness_mm is not None else _take(kw, ('thickness', 'depth', 'height', 'extrude'))
    material = material if material is not None else _take(kw, ('mat', 'color'))
    z_bottom = z_bottom if z_bottom is not None else _take(kw, ('z', 'z_offset', 'z_min', 'base_z', 'z_mm', 'elevation'))
    _no_extra(kw, 'make_solid_profile(name, outline_xy, thickness_mm, material, z_bottom=0)')
    if outline_xy is None:
        raise ValueError(name + ': outline_xy is required, e.g. [(0, -8), (15, -8), (30, -40)].')
    raw = list(outline_xy)
    points, zs = [], []
    for p in raw:
        values = list(p) if isinstance(p, (list, tuple, Vector)) else None
        if not values or len(values) not in (2, 3):
            raise ValueError(name + ': each outline point must be (x, y). Got ' + repr(p))
        points.append(tuple(_num(v, name + ' outline value') for v in values[:2]))
        if len(values) == 3:
            zs.append(_num(values[2], name + ' outline z'))
    if zs:
        if z_bottom is None:
            z_bottom = min(zs)
        _warn(name + ': outline points had a 3rd value (z). Used (x, y) only and z_bottom=' + format(float(z_bottom), 'g') +
              '. Next time pass outline_xy=[(x, y), ...] and z_bottom=<height>.')
    z0 = _num(z_bottom if z_bottom is not None else 0.0, name + ' z_bottom')
    t = abs(_num(thickness_mm if thickness_mm is not None else 2.4, name + ' thickness_mm'))
    if t < 0.8:
        _warn(name + ': thickness raised to 0.8 mm minimum.')
        t = 0.8
    pts = _clean_outline(name, points)
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z0 + t)) for x, y in pts]
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    return _finish(name, bm, material)


def make_wing(name, side=None, root_x=0.0, root_y=0.0, z_bottom=0.0, span_mm=30.0, chord_mm=30.0,
              thickness_mm=2.4, sweep_mm=None, material=None, scallops=3, **kw):
    """make_wing(name, side='left'|'right', root_x, root_y, z_bottom, span_mm, chord_mm, thickness_mm, sweep_mm, material).
    Flat, thick, swept-back dragon wing with a scalloped trailing edge. left = -Y, right = +Y. Tip sweeps toward +X (tail)."""
    material = material if material is not None else _take(kw, ('mat', 'color'))
    span_mm = _take(kw, ('span', 'length', 'length_mm'), span_mm)
    chord_mm = _take(kw, ('chord', 'width', 'width_mm'), chord_mm)
    thickness_mm = _take(kw, ('thickness',), thickness_mm)
    _no_extra(kw, 'make_wing(name, side, root_x, root_y, z_bottom, span_mm, chord_mm, thickness_mm, sweep_mm, material)')
    side = str(side or ('left' if 'left' in str(name).lower() else 'right')).lower()
    s = -1.0 if side.startswith('l') or side in ('-y', 'neg', 'negative') else 1.0
    span = max(abs(_num(span_mm, name + ' span_mm')), 4.0)
    chord = max(abs(_num(chord_mm, name + ' chord_mm')), 4.0)
    rx, ry = _num(root_x, name + ' root_x'), _num(root_y, name + ' root_y')
    sweep = chord * 0.85 if sweep_mm is None else _num(sweep_mm, name + ' sweep_mm')
    front = (rx - chord / 2, ry)
    tip = (rx - chord / 2 + sweep, ry + s * span)
    rear = (rx + chord / 2, ry + s * span * 0.12)
    pts = [front, ((front[0] + tip[0]) / 2 - chord * 0.08, ry + s * span * 0.55), tip]
    count = max(int(scallops), 1)
    for i in range(1, count * 2):
        t = i / (count * 2)
        x = tip[0] + (rear[0] - tip[0]) * t
        y = tip[1] + (rear[1] - tip[1]) * t
        if i % 2:
            x -= chord * 0.16
            y -= s * span * 0.06
        pts.append((x, y))
    pts += [rear, (rx + chord / 2, ry)]
    return make_solid_profile(name, pts, thickness_mm, material, z_bottom=z_bottom)


def _meshes(objects=None):
    objs = list(objects) if objects is not None else list(bpy.context.scene.objects)
    return [o for o in objs if o.type == 'MESH']


def assembly_bounds(objects=None):
    """Returns (min_xyz, max_xyz, size_xyz) of all mesh objects in world space, in mm."""
    bpy.context.view_layer.update()
    pts = []
    for obj in _meshes(objects):
        mw = obj.matrix_world
        pts.extend(mw @ v.co for v in obj.data.vertices)
    if not pts:
        raise RuntimeError('No mesh objects exist yet; create parts before measuring the assembly.')
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi, hi - lo


def _apply_world(obj, matrix):
    obj.data.transform(matrix @ obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    obj.data.update()


def ground_assembly(objects=None, z=0.0):
    """Moves ALL mesh objects together so the lowest point sits on Z=0. Relative positions are kept."""
    lo, hi, size = assembly_bounds(objects)
    shift = Matrix.Translation((0, 0, float(z) - lo.z))
    for obj in _meshes(objects):
        _apply_world(obj, shift)
    return assembly_bounds(objects)


def fit_assembly(target_length_mm=None,max_width_mm=None,max_height_mm=None,objects=None):
    """Uniform scale only. Never squeeze axes to conceal a bad design."""
    lo,hi,size=assembly_bounds(objects)
    scale=float(target_length_mm)/max(size.x,1e-6) if target_length_mm else 1.0
    if not math.isfinite(scale) or scale<=0:raise ValueError('Target length must be positive.')
    if max_width_mm and size.y*scale>float(max_width_mm)+.1:
        raise ValueError('Uniform width %.2f exceeds %.2f mm. Redesign span/pose: no Y squeeze.'%(size.y*scale,max_width_mm))
    if max_height_mm and size.z*scale>float(max_height_mm)+.1:
        raise ValueError('Uniform height %.2f exceeds %.2f mm. Redesign pose: no Z squeeze.'%(size.z*scale,max_height_mm))
    pivot=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    matrix=Matrix.Translation(pivot)@Matrix.Diagonal((scale,scale,scale,1))@Matrix.Translation(-pivot)
    for obj in _meshes(objects):_apply_world(obj,matrix)
    if abs(scale-1)>.02:_warn('Uniform reference-preserving scale x%.3f'%scale)
    return assembly_bounds(objects)


def flatten_underside(depth_mm=1.5, objects=None):
    """Cuts everything below (lowest Z + depth_mm), caps the cut, then re-grounds: a genuinely flat underside at Z=0."""
    lo, hi, size = assembly_bounds(objects)
    depth = min(max(float(depth_mm), 0.2), size.z * 0.3)
    cut = lo.z + depth
    for obj in _meshes(objects):
        _apply_world(obj, Matrix.Identity(4))
        zs = [v.co.z for v in obj.data.vertices]
        if min(zs) >= cut - 1e-6:
            continue
        if max(zs) <= cut + 0.3:
            continue
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        result = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                        plane_co=(0, 0, cut), plane_no=(0, 0, 1), clear_inner=True)
        cut_edges = [e for e in result['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if cut_edges:
            bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
    return ground_assembly(objects)


def assert_assembly_bounds(target_length_mm=None, max_width_mm=None, max_height_mm=None, tolerance_fraction=0.03, objects=None):
    """Raises with measured values if the assembly misses the targets. Does not resize anything."""
    lo, hi, size = assembly_bounds(objects)
    problems = []
    if target_length_mm:
        tol = max(0.5, float(target_length_mm) * float(tolerance_fraction))
        if abs(size.x - float(target_length_mm)) > tol:
            problems.append('length X is %.1f mm, target %.1f mm' % (size.x, float(target_length_mm)))
    if max_width_mm and size.y > float(max_width_mm) + 0.1:
        problems.append('width Y is %.1f mm, max %.1f mm' % (size.y, float(max_width_mm)))
    if max_height_mm and size.z > float(max_height_mm) + 0.1:
        problems.append('height Z is %.1f mm, max %.1f mm' % (size.z, float(max_height_mm)))
    if abs(lo.z) > 0.15:
        problems.append('lowest Z is %.2f mm, must be 0 (call ground_assembly())' % lo.z)
    if problems:
        raise AssertionError('Assembly bounds failed: ' + '; '.join(problems) +
                             '. Tip: call fit_assembly(target_length_mm, max_width_mm, max_height_mm) then ground_assembly().')
    return lo, hi, size


HELPERS = {f.__name__: f for f in (make_material, make_ellipsoid, make_box, make_cylinder_between, make_tapered_between,
                                   make_solid_profile, make_wing, assembly_bounds, ground_assembly, fit_assembly,
                                   flatten_underside, assert_assembly_bounds)}
