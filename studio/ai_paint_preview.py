# AI_PAINT_STAGE_V1 (studio 0.010 build 2026-10-28-5) - step "preview" (runs inside the studio's Blender, read-only)
# Renders the WRITTEN Bambu 3MF (the filament colours that will print) from 4 sides, plus the raw AI texture from the front.
# args: -- <studio folder> <prep dir> <work dir>     env PAINT_TURN=1 when the front check turned the model 180 degrees
import sys, os, json, re, zipfile, math
from pathlib import Path
import numpy as np, bpy
from mathutils import Vector
args = sys.argv[sys.argv.index('--') + 1:]
studio, prep, out = [Path(a) for a in args[:3]]
sys.path.insert(0, str(studio)); import bambu_color_export as B
d = np.load(prep / 'mesh.npz'); V, T = d['V'], d['T']
info = json.loads((prep / 'prep.json').read_text(encoding='utf-8'))
fwd = np.array(info['toward']); up = np.array(info['up']); rt = np.array(info['right'])
if os.environ.get('PAINT_TURN') == '1': fwd, rt = -fwd, -rt   # FRONT_TURN_V1: the model's real front is opposite the approved alignment
def prog(p, t): print('PROGRESS %d %s' % (p, t), flush=True)
def render(colors, path, elev, az):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new('m'); me.from_pydata(V.tolist(), [], T.tolist()); me.update()
    lin = np.where(colors <= 0.04045, colors / 12.92, ((colors + 0.055) / 1.055) ** 2.4)
    at = me.color_attributes.new('c', 'FLOAT_COLOR', 'CORNER'); at.data.foreach_set('color', np.repeat(np.c_[lin, np.ones(len(lin))], 3, 0).ravel())
    ob = bpy.data.objects.new('m', me); sc = bpy.context.scene; sc.collection.objects.link(ob)
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'VERTEX'
    sc.view_settings.view_transform = 'Standard'; sc.render.resolution_x = 640; sc.render.resolution_y = 640
    sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.32, 0.32, 0.34)
    lo, hi = V.min(0), V.max(0); ctr = Vector(((lo + hi) / 2).tolist()); rad = float(np.linalg.norm(hi - lo)) / 2
    e, a = math.radians(elev), math.radians(az)
    dv = Vector((fwd * math.cos(e) * math.cos(a) + rt * math.cos(e) * math.sin(a) + up * math.sin(e)).tolist()).normalized()
    cam = bpy.data.cameras.new('c'); cam.lens = 50; cam.clip_end = 1e5; co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
    co.location = ctr + dv * rad / math.tan(math.atan(18 / 50)) * 1.05
    q = (-dv).to_track_quat('-Z', 'Y'); co.rotation_euler = q.to_euler()
    if (q @ Vector((0, 1, 0))).dot(Vector(up.tolist())) < 0: co.rotation_euler.rotate_axis('Z', math.pi)   # keep the model's up as screen up
    sc.render.filepath = str(path); bpy.ops.render.render(write_still=True)
fj = json.loads((out / 'filaments.json').read_text(encoding='utf-8'))
f = [x for x in fj['files'] if 'file' in x][0]
z = zipfile.ZipFile(f['file']); xml = z.read([n for n in z.namelist() if n.endswith('.model') and 'Objects' in n][0]).decode()
st = np.array([B.decode_paint(t) if t else 1 for t in re.findall(r'<triangle v1="\d+" v2="\d+" v3="\d+"(?: paint_color="([^"]*)")?', xml)])
pal = json.loads(z.read('Metadata/project_settings.config'))['filament_colour']
if len(st) != len(T): raise RuntimeError('3MF triangle count differs from the prepared mesh')
prgb = np.array([[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] for c in pal])
done = []
angles = [('front', 15, 0), ('left', 25, -40), ('right', 25, 40), ('back', 25, 180)]
for i, (nm, el, az) in enumerate(angles):
    prog(10 + 20 * i, 'preview picture %d/5 (%s, printed filament colours)' % (i + 1, nm))
    p = out / ('aipaint_%s.png' % nm); render(prgb[np.clip(st - 1, 0, len(prgb) - 1)], p, el, az); done.append(p.name)
prog(90, 'preview picture 5/5 (raw AI texture, front)')
p = out / 'aipaint_texture.png'; render(np.load(out / 'tri_rgb.npy').astype(np.float64), p, 15, 0); done.append(p.name)
(out / 'previews.json').write_text(json.dumps(done), encoding='utf-8')
prog(100, 'preview pictures written')
print('PREVIEW_PASSED', len(done), flush=True)
