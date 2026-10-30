# MULTI_PICTURE_AI_PAINT_V1 (AI Modeling Studio 0.017) - step "prepare a side picture" (studio Blender, read-only on the job)
# args: -- <studio folder> <colour-version folder> <output folder> <slot> <mode: same|opposite>
#   same     : the paint model's front camera looks at the model from the slot's APPROVED direction, with the slot's picture
#   opposite : the camera looks from the mirror-image position on the OTHER side (reflected across the left-right plane)
#              and gets the slot's picture MIRRORED - a stand-in when the job has no picture of the opposite side (labelled as such in the report)
# Writes mesh.npz (V, T in the studio's triangle order, Vh = mesh in the paint model's frame), front_rgba.png (the picture the
# paint model is given), prep.json (all transforms) and ref_colours.npz (the colour stage's own per-triangle picture colours).
import sys, json, hashlib, traceback
from pathlib import Path
import numpy as np
import bpy
a = sys.argv[sys.argv.index('--') + 1:]
studio, folder, out, slot, mode = Path(a[0]), Path(a[1]), Path(a[2]), a[3], a[4]
out.mkdir(parents=True, exist_ok=True)
try:
    if mode not in ('same', 'opposite'): raise ValueError('mode must be same or opposite')
    sys.path.insert(0, str(studio))
    import hunyuan_color as H
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(folder / 'model-colored.blend'))
    items = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not items: raise RuntimeError('no mesh object in model-colored.blend')
    cfg = json.loads((folder / 'settings.json').read_text(encoding='utf-8-sig'))
    review = json.loads((folder / 'reference_review.json').read_text(encoding='utf-8-sig'))
    views = cfg.get('settings', {}).get('views', {})
    al = {}; bases = {}
    for rec in review['views']:
        s = H.alignment(views.get(rec['slot'], {}), rec['direction_hint']); al[rec['slot']] = s
        bases[rec['slot']] = [np.asarray(x, float) for x in H.basis(s)]
    if slot not in al: raise RuntimeError('slot %r is not an approved picture of this colour version (have %s)' % (slot, sorted(al)))
    s = al[slot]; r, u, t = bases[slot]
    if mode == 'opposite':
        # the camera that sees the MIRROR IMAGE of what this slot's camera sees: reflect it across the model's left-right
        # plane (plane normal = the approved FRONT picture's "right" direction, as in the colour stage's symmetry fill).
        # The mesh is never mirrored; the picture is (below). r is negated so the camera stays right-handed.
        fr = [k for k in al if al[k]['direction'] == 'front'] or [k for k in al if al[k]['direction'] == 'back']
        if not fr: raise RuntimeError('no front or back picture defines the left-right axis')
        lat = bases[fr[0]][0] / np.linalg.norm(bases[fr[0]][0]); R = lambda v: v - 2 * np.dot(v, lat) * lat
        r, u, t = -R(r), R(u), R(t)
    hand = float(np.dot(np.cross(r, u), t))
    if hand < 0.99: raise RuntimeError('camera basis is not right-handed (%.3f)' % hand)
    V = []; T = []; S = []; UV = []; INF = []; off = 0
    with np.load(folder / 'reference_masks.npz', allow_pickle=False) as d: masks = {k: d[k].copy() for k in d.files}
    names = sorted(masks)
    for o in items:
        me = o.data; me.calc_loop_triangles()
        n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co)
        M = np.array(o.matrix_world, dtype=np.float64); co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        nt = len(me.loop_triangles); tv = np.empty(nt * 3, np.int64); me.loop_triangles.foreach_get('vertices', tv)
        V.append(co); T.append(tv.reshape(-1, 3) + off); off += n
        tl = np.empty(nt * 3, np.int64); me.loop_triangles.foreach_get('loops', tl); tm = np.empty(nt, np.int64); me.loop_triangles.foreach_get('material_index', tm)
        uv = np.zeros(len(me.loops) * 2)
        if me.uv_layers.active: me.uv_layers.active.data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)[tl.reshape(-1, 3)].mean(1)
        sl = [(m.get('reference_texture_slot') if m else None) for m in me.materials]; inf = [bool(m and m.get('inferred')) for m in me.materials]
        S.append(np.array([names.index(sl[i]) if sl[i] in names else -1 for i in tm], np.int64)); INF.append(np.array([inf[i] for i in tm], bool)); UV.append(uv)
    V = np.vstack(V); T = np.vstack(T); S = np.concatenate(S); UV = np.vstack(UV); INF = np.concatenate(INF)
    Vh = np.stack([V @ r, V @ u, V @ t], 1)
    img = H.pixels(folder / ('reference_' + slot + '.png')); mask = masks[slot]
    if mask.shape != img.shape[:2]: raise RuntimeError('approved mask size does not match the picture')
    rgba = img.copy(); rgba[..., 3] = mask.astype(np.float32); rgba[~mask, :3] = 1.0
    flip = bool(s.get('flip')) != (mode == 'opposite')        # approved mirror setting, plus the stand-in mirror for "opposite"
    if flip: rgba = rgba[:, ::-1].copy()
    H.png(out / 'front_rgba.png', rgba)
    # the colour stage's per-triangle picture colours (where a picture really saw the triangle; inferred faces excluded)
    rgb = np.zeros((len(S), 3), np.float32); ok = np.zeros(len(S), bool)
    for k, nm in enumerate(names):
        sel = S == k
        if not sel.any(): continue
        im = H.pixels(folder / ('reference_' + nm + '.png')); m = masks[nm]; h, w = m.shape
        x = np.clip((UV[sel, 0] * (w - 1)).round().astype(int), 0, w - 1); y = np.clip(((1 - UV[sel, 1]) * (h - 1)).round().astype(int), 0, h - 1)
        rgb[sel] = im[y, x, :3]; ok[sel] = m[y, x] & ~INF[sel]
    np.savez_compressed(out / 'ref_colours.npz', slot=S, rgb=rgb, ok=ok, inferred=INF, slots=np.array(names))
    np.savez_compressed(out / 'mesh.npz', V=V, T=T, Vh=Vh)
    info = {'ok': True, 'slot': slot, 'mode': mode, 'approved_direction': s['direction'], 'alignment': s,
            'right': r.tolist(), 'up': u.tolist(), 'toward': t.tolist(), 'picture_mirrored': flip,
            'all_slots': {k: {'direction': al[k]['direction'], 'toward': bases[k][2].tolist(), 'right': bases[k][0].tolist(), 'up': bases[k][1].tolist(), 'flip': bool(al[k].get('flip'))} for k in al},
            'vertices': int(len(V)), 'triangles': int(len(T)), 'size_mm': np.ptp(V, 0).round(3).tolist(),
            'inputs_sha256': {p: sha(folder / p) for p in ('model-colored.blend', 'settings.json', 'reference_review.json', 'reference_' + slot + '.png', 'reference_masks.npz')},
            'hunyuan_color_sha256': sha(studio / 'hunyuan_color.py'), 'mask_pixels': int(mask.sum()),
            'reference_triangles': {nm: int((S == k).sum()) for k, nm in enumerate(names)}, 'reference_observed': int(ok.sum())}
    (out / 'prep.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    print('SIDE_PREP_PASSED', json.dumps({k: info[k] for k in ('slot', 'mode', 'approved_direction', 'picture_mirrored', 'triangles')}))
except Exception:
    (out / 'prep_error.txt').write_text(traceback.format_exc(), encoding='utf-8'); traceback.print_exc(); sys.exit(1)
