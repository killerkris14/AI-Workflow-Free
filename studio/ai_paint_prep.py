# AI texture paint TEST - step "prepare" (runs inside the studio's Blender, read-only on the job)
# args: -- <studio folder> <colour-version folder> <output folder>
# Writes: mesh.npz (V_world mm, T triangles in the studio's own order, V_hy = mesh turned so the approved FRONT picture
#         looks at it along -Z with +Y up, as the paint model expects), front_rgba.png (approved front picture + approved mask
#         as alpha, mirrored only if the approved alignment says "mirror"), prep.json (all transforms, for tracing).
import sys, json, hashlib, traceback
from pathlib import Path
import numpy as np
import bpy
args = sys.argv[sys.argv.index('--') + 1:]
studio, folder, out = Path(args[0]), Path(args[1]), Path(args[2])
out.mkdir(parents=True, exist_ok=True)
try:
    sys.path.insert(0, str(studio))
    import hunyuan_color as H                      # the INSTALLED studio module: same alignment/basis maths as the colour stage
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(folder / 'model-colored.blend'))
    items = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not items: raise RuntimeError('no mesh object in model-colored.blend')
    V = []; T = []; off = 0
    for o in items:
        me = o.data; me.calc_loop_triangles()
        n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co)
        M = np.array(o.matrix_world, dtype=np.float64); co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        tv = np.empty(len(me.loop_triangles) * 3, np.int64); me.loop_triangles.foreach_get('vertices', tv)
        V.append(co); T.append(tv.reshape(-1, 3) + off); off += n
    V = np.vstack(V); T = np.vstack(T)
    cfg = json.loads((folder / 'settings.json').read_text(encoding='utf-8-sig'))
    review = json.loads((folder / 'reference_review.json').read_text(encoding='utf-8-sig'))
    views = cfg.get('settings', {}).get('views', {})
    front = None
    for rec in review['views']:
        s = H.alignment(views.get(rec['slot'], {}), rec['direction_hint'])
        if s['direction'] == 'front': front = (rec['slot'], s); break
    if front is None: raise RuntimeError('this job has no picture assigned to the FRONT direction; the paint model needs the front picture')
    slot, s = front
    r, u, t = [np.asarray(x, float) for x in H.basis(s)]
    hand = float(np.dot(np.cross(r, u), t))
    if hand < 0.99: raise RuntimeError('front camera basis is not right-handed (%.3f)' % hand)
    Vh = np.stack([V @ r, V @ u, V @ t], 1)          # +Z = toward the front camera, +Y = picture up, +X = picture right
    img = H.pixels(folder / ('reference_' + slot + '.png'))
    with np.load(folder / 'reference_masks.npz', allow_pickle=False) as d: mask = d[slot].copy()
    if mask.shape != img.shape[:2]: raise RuntimeError('approved mask size does not match the front picture')
    rgba = img.copy(); rgba[..., 3] = mask.astype(np.float32)
    rgba[~mask, :3] = 1.0
    if s.get('flip'): rgba = rgba[:, ::-1].copy()     # approved alignment mirrors this picture -> mirror the copy, never the mesh
    H.png(out / 'front_rgba.png', rgba)
    # every approved picture + its approved mask as alpha (read-only copies) -> drawing palette for the filament step
    with np.load(folder / 'reference_masks.npz', allow_pickle=False) as dm: allmasks = {k: dm[k].copy() for k in dm.files}
    refs = []
    for rec in review['views']:
        sl = rec['slot']; pth = folder / ('reference_' + sl + '.png')
        if not pth.is_file() or sl not in allmasks: continue
        im2 = H.pixels(pth)
        if allmasks[sl].shape != im2.shape[:2]: continue
        im2[..., 3] = allmasks[sl].astype(np.float32); H.png(out / ('ref_' + sl + '.png'), im2); refs.append(sl)
    np.savez_compressed(out / 'mesh.npz', V=V, T=T, Vh=Vh)
    info = {'ok': True, 'front_slot': slot, 'alignment': s, 'right': r.tolist(), 'up': u.tolist(), 'toward': t.tolist(),
            'flip_applied_to_picture': bool(s.get('flip')), 'vertices': int(len(V)), 'triangles': int(len(T)),
            'size_mm': np.ptp(V, 0).round(3).tolist(), 'objects': [o.name for o in items],
            'inputs_sha256': {p: sha(folder / p) for p in ('model-colored.blend', 'settings.json', 'reference_review.json', 'reference_' + slot + '.png', 'reference_masks.npz')},
            'hunyuan_color_sha256': sha(studio / 'hunyuan_color.py'), 'mask_pixels': int(mask.sum()), 'reference_copies': refs}
    (out / 'prep.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    print('PAINT_PREP_PASSED', json.dumps({k: info[k] for k in ('front_slot', 'triangles', 'size_mm')}))
except Exception:
    (out / 'prep_error.txt').write_text(traceback.format_exc(), encoding='utf-8'); traceback.print_exc(); sys.exit(1)
