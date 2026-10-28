# Color update self-test (0.010). Run: blender --background --factory-startup --python selftest_color_update.py -- <studio folder>
# Uses synthetic data in a temporary folder only; never touches jobs, settings or models.
import sys, tempfile, shutil, zipfile, importlib.util, traceback
from pathlib import Path
try:
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    root = Path(args[0]).resolve()
    import bpy, numpy as np
    spec = importlib.util.spec_from_file_location('selftest_hunyuan_color', str(root / 'hunyuan_color.py'))
    hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)
    work = Path(tempfile.mkdtemp(prefix='aistudio-selftest-'))
    folder = work / 'SELFTEST-JOB' / 'color_versions' / '0000000000000000'; folder.mkdir(parents=True)
    try:
        W = 64
        front = np.zeros((W, W, 4), np.float32); front[:, :32] = [1, 0, 0, 1]; front[:, 32:] = [0, 0, 1, 1]
        left = np.zeros((W, W, 4), np.float32); left[:] = [0, 1, 0, 1]
        hc.png(folder / 'reference_front.png', front); hc.png(folder / 'reference_left.png', left)
        mf = np.ones((W, W), bool); mf[:, 56:] = False            # approved mask excludes a background band
        np.savez_compressed(folder / 'reference_masks.npz', front=mf, left=np.ones((W, W), bool))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        verts = [(0, 0, 0), (10, 0, 0), (0, 10, 0), (20, 0, 0), (30, 0, 0), (20, 10, 0), (40, 0, 0), (50, 0, 0), (40, 10, 0),
                 (60, 0, 0), (70, 0, 0), (60, 10, 0), (80, 0, 5), (90, 0, 5), (80, 10, 5)]
        faces = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9, 10, 11), (12, 13, 14)]
        me = bpy.data.meshes.new('SelfTest'); me.from_pydata(verts, [], faces); me.update()
        obj = bpy.data.objects.new('SelfTest', me); bpy.context.scene.collection.objects.link(obj)
        for slot in ('front', 'left'):
            m = bpy.data.materials.new('Reference_' + slot); m['reference_texture_slot'] = slot; me.materials.append(m)
        me.materials.append(bpy.data.materials.new('UNOBSERVED_NEUTRAL'))
        uv = me.uv_layers.new(name='ReferenceUV')
        # face: material, uv centre  (v = 1 - row/H)
        plan = [(0, (0.25, 0.5)), (0, (0.70, 0.5)), (0, (0.95, 0.5)), (2, (0.5, 0.5)), (1, (0.5, 0.5))]
        for poly, (mat, (u, v)) in zip(me.polygons, plan):
            poly.material_index = mat
            for k, li in enumerate(poly.loop_indices):
                uv.data[li].uv = (u + (0.02 if k == 1 else 0), v + (0.02 if k == 2 else 0))
        fp = lambda: (tuple(tuple(round(c, 6) for c in v.co) for v in me.vertices), tuple(tuple(p.vertices) for p in me.polygons))
        before = fp()
        out = folder / 'model-bambu.3mf'; rep = folder / 'bambu_report.txt'
        r = hc.bambu_export([obj], folder, {'bambu': {'filaments': 4, 'unobserved': 'gray', 'min_region_mm2': 4.0}}, out, rep)
        assert r['statistics']['region_cleanup']['triangles_reassigned'] == 0, 'isolated test triangles must keep their colours'
        assert fp() == before, 'geometry changed'
        pal = {f['filament']: f['colour'] for f in r['filaments']}
        import xml.etree.ElementTree as ET
        B = sys.modules['studio_bambu_color_export_local']
        with zipfile.ZipFile(out) as z:
            states = [B.decode_paint(t.get('paint_color')) for t in ET.fromstring(z.read('3D/Objects/object_1.model')).iter() if t.tag.endswith('triangle')]
        got = [pal[s] for s in states]
        expected = ['#FF0000', '#0000FF', '#808080', '#808080', '#00FF00']
        assert got == expected, 'per-triangle colours %s != %s' % (got, expected)
        assert r['statistics']['unobserved_triangles'] == 2, r['statistics']
        assert rep.read_text(encoding='utf-8').startswith('AI Modeling Studio - Bambu full-color export report')
        try:
            hc.bambu_export([obj], folder, {'bambu': {'filaments': 4, 'unobserved': 'gray'}}, out, rep); raise AssertionError('overwrote export')
        except FileExistsError:
            pass
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print('Blender', bpy.app.version_string, 'per-triangle colours', got)
    # ---- 0.004: alignment fit evidence through the real transfer() projection ----
    import bmesh
    work2 = Path(tempfile.mkdtemp(prefix='aistudio-selftest-fit-'))
    try:
        f2 = work2 / 'FIT-JOB' / 'color_versions' / '0000000000000001'; f2.mkdir(parents=True)
        S = 128; yy, xx = np.mgrid[0:S, 0:S]
        disk = (xx + .5 - 64) ** 2 + (yy + .5 - 64) ** 2 < 40 ** 2
        square = (abs(xx + .5 - 64) < 40) & (abs(yy + .5 - 64) < 40)
        for slot, mk in (('front', disk), ('left', square)):
            img = np.zeros((S, S, 4), np.float32); img[mk] = [.2, .3, .8, 1]; hc.png(f2 / ('reference_' + slot + '.png'), img)
        np.savez_compressed(f2 / 'reference_masks.npz', front=disk, left=square)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        me2 = bpy.data.meshes.new('FitSphere'); bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=20.0); bm.to_mesh(me2); bm.free()
        ob2 = bpy.data.objects.new('FitSphere', me2); bpy.context.scene.collection.objects.link(ob2)
        co = np.array([tuple(v.co) for v in me2.vertices]); dims = [float(x) for x in np.ptp(co, axis=0)]
        review = {'views': [{'slot': 'front', 'direction_hint': 'front'}, {'slot': 'left', 'direction_hint': 'left'}], 'source': {'dimensions_mm': dims}}
        stats = hc.transfer([ob2], f2, {'settings': {'views': {}}}, review)
        ev = hc.alignment_evidence([ob2], f2)
        fr, lf = ev['views']['front'], ev['views']['left']
        assert fr['iou'] > 0.9, 'sphere vs disk fit %s' % fr
        assert 0.70 < lf['iou'] < 0.85, 'sphere vs square fit %s' % lf
        assert (f2 / 'fit_front.png').is_file() and (f2 / 'fit_left.png').is_file(), 'fit images missing'
        cov = ev['coverage']; assert 0 < cov['coloured_area_percent'] < 100 and abs(cov['coloured_area_percent'] + cov['unobserved_area_percent'] + cov.get('symmetry_inferred_percent', 0) - 100) < 0.05, cov
        import json as _json; _json.dumps(ev, allow_nan=False)
        print('fit evidence: front IoU', fr['iou'], 'left IoU', lf['iou'], 'coverage', cov['coloured_area_percent'], '% mapped faces', stats['mapped_faces'])
        # ---- poor-fit views are left out of color automatically; 'on' overrides; all excluded fails clearly ----
        bar = (abs(xx + .5 - 64) < 60) & (abs(yy + .5 - 64) < 4)
        img = np.zeros((S, S, 4), np.float32); img[bar] = [1, 1, 0, 1]; hc.png(f2 / 'reference_top.png', img)
        np.savez_compressed(f2 / 'reference_masks.npz', front=disk, left=square, top=bar)
        review3 = {'views': review['views'] + [{'slot': 'top', 'direction_hint': 'top'}], 'source': review['source']}
        def run3(views):
            for o in list(bpy.data.materials): bpy.data.materials.remove(o)
            return hc.transfer([ob2], f2, {'settings': {'views': views}}, review3)
        st3 = run3({})
        assert set(st3['excluded_views']) == {'top'} and st3['reference_face_counts']['top'] == 0, 'poor top view not excluded: %s' % st3['excluded_views']
        assert st3['view_fit_iou']['top'] < hc.POOR_FIT_IOU <= st3['view_fit_iou']['left'], st3['view_fit_iou']
        st4 = run3({'top': {'direction': 'top', 'color_use': 'on'}, 'left': {'direction': 'left', 'color_use': 'off'}})
        assert set(st4['excluded_views']) == {'left'} and st4['reference_face_counts']['top'] > 0, 'overrides ignored: %s' % st4
        try:
            run3({k: {'direction': d, 'color_use': 'off'} for k, d in (('front', 'front'), ('left', 'left'), ('top', 'top'))}); raise AssertionError('all-excluded did not fail')
        except ValueError as e:
            assert 'No reference view fits' in str(e)
        print('poor-fit exclusion: top IoU', st3['view_fit_iou']['top'], 'excluded; overrides honoured; all-excluded fails clearly')
    finally:
        shutil.rmtree(work2, ignore_errors=True)
    # ---- 0.005: automatic direction + picture-rotation search through the studio's pinned loader ----
    RA = hc._load_reference_alignment_local(); EV = hc._load_alignment_evidence_local(); W = vars(hc)
    def box(c, sz):
        c = np.array(c, float); sz = np.array(sz, float) / 2
        v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * sz + c
        return v, np.array([(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),(2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)])
    parts = [box((0, 0, 20), (16, 40, 14)), box((0, -26, 30), (10, 12, 10)), box((0, 34, 14), (4, 30, 4)), box((16, -4, 26), (18, 8, 2)),
             box((-5, -10, 6), (4, 4, 12)), box((5, -10, 6), (4, 4, 12)), box((0, 14, 6), (8, 4, 12))]
    PV = np.vstack([v for v, _ in parts]); PF = np.vstack([f + 8 * i for i, (_, f) in enumerate(parts)])
    def draw(direction, roll=0.0, size=300):
        st = W['alignment']({'direction': direction, 'roll': roll}, direction); r, u, _ = W['basis'](st)
        xy = np.stack([PV @ r, -(PV @ u)], 1); xy -= (xy.min(0) + xy.max(0)) / 2
        return EV.rasterize(xy * (.6 * size / np.ptp(xy, axis=0).max()) + size / 2, PF, size, size)
    masks = {'front': draw('front'), 'side': draw('right'), 'back': draw('back'), 'top': draw('top', roll=90)}
    records = [{'slot': 'front', 'direction_hint': 'front'}, {'slot': 'side', 'direction_hint': 'left'}, {'slot': 'back', 'direction_hint': 'back'}, {'slot': 'top', 'direction_hint': 'top'}]
    res, rep = RA.optimize_views(PV, PV, PF, masks, records, {}, W, deadline_seconds=300)
    dv = {v['slot']: v for v in rep['views']}
    assert dv['side']['direction'] == 'right' and dv['side']['direction_changed'], 'side direction not corrected: %s' % dv['side']
    assert dv['top']['image_rotation_deg'] == 90.0, 'top rotation not found: %s' % dv['top']
    assert dv['front']['direction'] == 'front' and dv['back']['direction'] == 'back', 'reliable labels changed'
    assert all(v['proposed_iou'] > .85 for v in dv.values()) and not any(x['flip'] for x in res.values()), 'auto-orientation fit too poor or mirrored'
    print('auto-orientation: side left -> right, top rotated 90, IoU', [round(dv[k]['proposed_iou'], 3) for k in ('front', 'side', 'back', 'top')])
    # ---- sheet cleanup: ground line through the feet, ruler box, labels removed; subject and a close ornament kept ----
    MC = hc._load_mask_cleanup_local(); H = 512; m = np.zeros((H, H), bool)
    m[100:300, 150:350] = True; m[300:360, 170:200] = True; m[300:360, 300:330] = True        # body + two legs (feet at row 359)
    m[360:363, 40:480] = True                                                                 # ground line under the feet
    m[348:363, 400:470] = True; m[350:360, 403:467] = False                                   # ruler box outline standing on the line
    for x0 in range(180, 300, 12): m[380:392, x0:x0 + 8] = True                              # label letters below the line
    m[60:72, 230:260] = True                                                                  # label above the subject
    m[302:308, 250:256] = True                                                                # ornament hanging 2 px below the body
    cleaned, rep = MC.clean_mask(m)
    assert cleaned[100:300, 150:350].all() and cleaned[300:358, 170:200].all() and cleaned[300:358, 300:330].all(), 'subject damaged'
    assert cleaned[302:308, 250:256].all(), 'close ornament removed'
    assert not cleaned[360:363, 40:150].any() and not cleaned[348:363, 400:470].any(), 'ground line / ruler kept'
    assert not cleaned[380:392].any() and not cleaned[60:72].any(), 'labels kept'
    assert rep['applied'] and not (cleaned & ~m).any(), rep
    print('sheet cleanup: removed %.2f%% (line, ruler, labels); subject and close ornament kept' % rep['removed_percent'])
    # ---- 0.006: symmetry colour fill through transfer(), fit evidence and the Bambu export ----
    import bmesh
    def sym_check(c, m):
        assert c, m
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bm = bmesh.new()
    def box(c, s):
        r = bmesh.ops.create_cube(bm, size=1.0); bmesh.ops.scale(bm, vec=s, verts=r['verts']); bmesh.ops.translate(bm, vec=c, verts=r['verts'])
    box((0, 0, 20), (16, 40, 14)); box((14, -4, 26), (12, 8, 2)); box((-14, -4, 26), (12, 8, 2))   # body + symmetric wings
    box((-9.5, 12, 14), (3, 6, 6))                                                                  # bump on the LEFT (-X) side only
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    me = bpy.data.meshes.new('Sym'); bm.to_mesh(me); bm.free(); obj = bpy.data.objects.new('Sym', me); bpy.context.scene.collection.objects.link(obj)
    work = Path(tempfile.mkdtemp()); folder = work / 'JOB' / 'color_versions' / '0000000000000002'; folder.mkdir(parents=True)
    try:
        S = 128
        front = np.zeros((S, S, 4), np.float32); front[:] = [0.1, 0.2, 0.9, 1]
        side = np.zeros((S, S, 4), np.float32); g = np.linspace(0, 1, S)
        side[..., 0] = g[None, :]; side[..., 1] = 1 - g[None, :]; side[..., 2] = 0.2; side[..., 3] = 1   # colour encodes picture x (model Y)
        hc.png(folder / 'reference_front.png', front); hc.png(folder / 'reference_side.png', side)
        np.savez_compressed(folder / 'reference_masks.npz', front=np.ones((S, S), bool), side=np.ones((S, S), bool))
        co = np.array([tuple(v.co) for v in me.vertices]); dims = [float(x) for x in np.ptp(co, axis=0)]
        review = {'views': [{'slot': 'front', 'direction_hint': 'front'}, {'slot': 'side', 'direction_hint': 'right'}], 'source': {'dimensions_mm': dims}}
        st = hc.transfer([obj], folder, {'settings': {'views': {'front': {'direction': 'front', 'color_use': 'on'}, 'side': {'direction': 'right', 'color_use': 'on'}}}}, review)
        sym = st['symmetry_fill']; print('symmetry:', sym, '| mapped', st['mapped_faces'], 'unobserved', st['fallback_faces'])
        sym_check(sym['applied'] and sym['filled_faces'] > 0, 'unseen flank filled')
        n = 2; mats = [p.material_index for p in me.polygons]; cent = np.array([tuple(p.center) for p in me.polygons]); nor = np.array([tuple(p.normal) for p in me.polygons])
        left_flank = (nor[:, 0] < -0.9) & (np.abs(cent[:, 1] - (-0)) < 19) & (cent[:, 0] < -7.9) & (cent[:, 0] > -8.1)   # body's -X wall
        sym_check(np.mean([m == n + 1 + 1 for m in np.array(mats)[left_flank]]) > 0.8, 'left wall coloured from the side view as symmetry')
        bump = (cent[:, 0] < -8.2) & (cent[:, 1] > 8.5) & (cent[:, 1] < 15.5) & (cent[:, 2] > 10.5) & (cent[:, 2] < 17.5) & (nor[:, 0] < -0.9)
        sym_check(bump.any() and all(m == n for m in np.array(mats)[bump]), 'asymmetric bump stays unobserved (no mirror partner)')
        # colours: a filled left-wall face must match its right-wall partner (sampled exactly like the Bambu export)
        ev = hc.alignment_evidence([obj], folder); cov = ev['coverage']; print('coverage:', cov)
        sym_check(cov['symmetry_inferred_percent'] > 0 and abs(cov['coloured_area_percent'] + cov['symmetry_inferred_percent'] + cov['unobserved_area_percent'] - 100) < 0.1, 'evidence reports symmetry separately')
        B = hc._load_bambu_export_local(); out = folder / 'model-bambu.3mf'; rep = folder / 'bambu_report.txt'
        r = hc.bambu_export([obj], folder, {'bambu': {'filaments': 4, 'unobserved': 'gray', 'min_region_mm2': 0}}, out, rep)
        split = r['statistics']['final_surface_split']; print('final split:', split)
        sym_check(split['inferred_by_symmetry_percent'] > 0 and split['reference_colour_percent'] > 0, 'Bambu report separates symmetry from reference colour')
        sym_check('inferred by left-right symmetry' in rep.read_text(encoding='utf-8'), 'report text states it')
        # colour agreement: per filled face, compare with its mirror partner's sampled colour
        me.calc_loop_triangles(); uvl = me.uv_layers.active.data
        imgs = {'front': hc.pixels(folder / 'reference_front.png'), 'side': hc.pixels(folder / 'reference_side.png')}
        def colour(poly):
            sl = me.materials[poly.material_index].get('reference_texture_slot'); uv = np.mean([tuple(uvl[l].uv) for l in poly.loop_indices], 0)
            im = imgs[sl]; h, w = im.shape[:2]; return im[min(h - 1, int((1 - uv[1]) * h)), min(w - 1, int(uv[0] * w)), :3]
        pairs = 0; bad = 0
        for i in np.where(left_flank)[0]:
            if mats[i] != n + 2: continue
            target = cent[i] * np.array([-1, 1, 1]); j = int(np.argmin(np.linalg.norm(cent - target, axis=1)))
            if mats[j] == 1: pairs += 1; bad += int(np.abs(colour(me.polygons[i]) - colour(me.polygons[j])).max() > 0.05)
        print('mirror colour pairs', pairs, 'mismatches', bad); sym_check(pairs > 10 and bad == 0, 'filled colours equal their mirror partners')
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('symmetry fill: mirror colours verified; asymmetric part left unobserved')
    # ---- 0.007: per-region view acceptance (misplaced drawing parts do not paint the model) ----
    E = hc._load_alignment_evidence_local()
    def lf_check(c, m):
        assert c, m
    def build(wing_y):
        bm = bmesh.new()
        def box(c, s):
            r = bmesh.ops.create_cube(bm, size=1.0); bmesh.ops.scale(bm, vec=s, verts=r['verts']); bmesh.ops.translate(bm, vec=c, verts=r['verts'])
        box((0, 0, 20), (16, 40, 14)); box((14, wing_y, 26), (12, 8, 2)); box((-14, wing_y, 26), (12, 8, 2))
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=4, use_grid_fill=True); return bm
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bm = build(-4.0); me = bpy.data.meshes.new('M'); bm.to_mesh(me); bm.free(); obj = bpy.data.objects.new('M', me); bpy.context.scene.collection.objects.link(obj)
    ref = build(-9.0); V = np.array([tuple(v.co) for v in ref.verts]); ref.verts.ensure_lookup_table(); ref.faces.ensure_lookup_table()
    F = np.array([[v.index for v in f.verts] for f in ref.faces]); ref.free(); T = np.vstack([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    S = 200; st = hc.alignment({'direction': 'top'}, 'top'); r, u, _ = hc.basis(st)
    xy = np.stack([V @ r, -(V @ u)], 1); lo = xy.min(0); hi = xy.max(0); xy = (xy - (lo + hi) / 2) * (0.8 * S / (hi - lo).max()) + S / 2
    mask = E.rasterize(xy, T, S, S)
    work = Path(tempfile.mkdtemp()); folder = work / 'JOB' / 'color_versions' / '0000000000000003'; folder.mkdir(parents=True)
    try:
        img = np.zeros((S, S, 4), np.float32); img[mask] = [0.2, 0.4, 0.9, 1]; hc.png(folder / 'reference_top.png', img)
        np.savez_compressed(folder / 'reference_masks.npz', top=mask)
        co = np.array([tuple(v.co) for v in me.vertices]); dims = [float(x) for x in np.ptp(co, axis=0)]
        review = {'views': [{'slot': 'top', 'direction_hint': 'top'}], 'source': {'dimensions_mm': dims}}
        hc.LOCAL_FIT_MIN = 0.0                                                       # old behaviour: no local check
        old = hc.transfer([obj], folder, {'settings': {'views': {}}}, review); mats_old = np.array([p.material_index for p in me.polygons])
        for o in list(bpy.data.materials): bpy.data.materials.remove(o)
        hc.LOCAL_FIT_MIN = 0.80
        stt = hc.transfer([obj], folder, {'settings': {'views': {}}}, review)
        print('fit IoU', stt['view_fit_iou'], '| local', stt['local_fit'], '| mapped', stt['mapped_faces'])
        lf_check(0.30 <= stt['view_fit_iou']['top'] < 0.90 and not stt['excluded_views'], 'imperfect view kept (old rule would drop it below 0.55 or take all of it)')
        mats = np.array([p.material_index for p in me.polygons]); cent = np.array([tuple(p.center) for p in me.polygons]); nor = np.array([tuple(p.normal) for p in me.polygons])
        up = nor[:, 2] > 0.9
        body_top = up & (np.abs(cent[:, 0]) < 7) & (np.abs(cent[:, 1]) < 17) & (cent[:, 2] > 26.5)
        wing_top = up & (np.abs(cent[:, 0]) > 9) & (cent[:, 2] > 26.5)
        print('OLD rule: wing tops coloured %.0f%% (from misplaced drawing) | NEW: body tops %.0f%%, wing tops %.0f%%' % (100 * np.mean(mats_old[wing_top] == 0), 100 * np.mean(mats[body_top] == 0), 100 * np.mean(mats[wing_top] == 0)))
        lf_check(np.mean(mats_old[wing_top] == 0) > 0.2, 'test reproduces the problem: old rule paints wings from the misplaced drawing')
        lf_check(np.mean(mats[body_top] == 0) > 0.9, 'well-fitting body region takes colour from the view')
        lf_check(np.mean(mats[wing_top] == 0) < 0.5 * np.mean(mats_old[wing_top] == 0), 'local check removes most misplaced wing colour')
        lf_check(stt['local_fit']['rejected_faces_per_view']['top'] > 0, 'rejections reported')
        for o in list(bpy.data.materials): bpy.data.materials.remove(o)
        on = hc.transfer([obj], folder, {'settings': {'views': {'top': {'direction': 'top', 'color_use': 'on'}}}}, review)
        mats2 = np.array([p.material_index for p in me.polygons]); lf_check(abs(np.mean(mats2[wing_top] == 0) - np.mean(mats_old[wing_top] == 0)) < 1e-9 and on['local_fit']['rejected_faces_per_view']['top'] == 0, '"always use" overrides the local check (same as the old rule)')
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('local fit: misplaced wing colour %.0f%% -> %.0f%%, body kept' % (100 * np.mean(mats_old[wing_top] == 0), 100 * np.mean(mats[wing_top] == 0)))
    # ---- 0.009: geometry check catches a doubled tail using every view (top included) ----
    E = hc._load_alignment_evidence_local(); W = vars(hc)
    def gc_check(c, m):
        assert c, m
    def boxes(extra):
        parts = [((0, 0, 20), (16, 40, 14)), ((0, -26, 30), (10, 12, 10)), ((0, 34, 14), (4, 30, 4)), ((16, -4, 26), (18, 8, 2)), ((-16, -4, 26), (18, 8, 2)),
                 ((-5, -10, 6), (4, 4, 12)), ((5, -10, 6), (4, 4, 12)), ((0, 14, 6), (8, 4, 12))]
        if extra == 'moved': parts[2] = ((14, 22, 14), (24, 4, 4))  # 0.010: ONE tail, bent sideways (drawn straight back)
        elif extra: parts.append(((15, 30, 8), (18, 5, 5)))       # the doubled tail: sticks out sideways near the real tail
        return parts
    def mesh_arrays(parts):
        V = []; F = []
        for c, s in parts:
            v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * np.array(s) / 2 + np.array(c)
            f = np.array([(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),(2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)]) + len(V) * 8
            V.append(v); F.append(f)
        return np.vstack(V), np.vstack(F)
    def save_blend(path, parts):
        bpy.ops.wm.read_factory_settings(use_empty=True); V, F = mesh_arrays(parts)
        me = bpy.data.meshes.new('M'); me.from_pydata([tuple(p) for p in V], [], [tuple(int(i) for i in f) for f in F]); me.update()
        bpy.context.scene.collection.objects.link(bpy.data.objects.new('M', me)); bpy.ops.wm.save_as_mainfile(filepath=str(path))
    work = Path(tempfile.mkdtemp())
    try:
        prepared = work / 'autoroute_prepared'; prepared.mkdir()
        V, F = mesh_arrays(boxes(False)); S = 300
        for slot, direction, roll in (('front', 'front', 0), ('left', 'right', 0), ('back', 'back', 0), ('top', 'top', 90)):
            s = hc.alignment({'direction': direction, 'roll': roll}, direction); r, u, _ = hc.basis(s)
            xy = np.stack([V @ r, -(V @ u)], 1); xy -= (xy.min(0) + xy.max(0)) / 2; xy = xy * (.6 * S / np.ptp(xy, axis=0).max()) + S / 2
            m = E.rasterize(xy, F, S, S); img = np.zeros((S, S, 4), np.float32); img[m] = [.2, .5, .2, 1]; hc.png(prepared / (slot + '.png'), img)
        views = [{'slot': 'front', 'direction_hint': 'front'}, {'slot': 'left', 'direction_hint': 'left'}, {'slot': 'back', 'direction_hint': 'back'}, {'slot': 'top', 'direction_hint': 'top'}]
        results = {}
        for name, extra in (('single tail', False), ('doubled tail', True), ('moved tail', 'moved')):
            folder = work / name.replace(' ', '_'); folder.mkdir(); save_blend(folder / 'model.blend', boxes(extra))
            hc.save(folder / 'spec.json', {'blend': str(folder / 'model.blend'), 'prepared': str(prepared), 'views': views, 'deadline_seconds': 300})
            r = hc.geometry_check(folder); results[name] = r
            print(name, '| passed', r['passed'], '| score', r['score'], '| reasons', r['reasons'], '|', {k: (v['iou'], v['far_extra_percent'], v['far_missing_percent']) for k, v in r['views'].items()})
        gc_check(results['single tail']['passed'], 'matching mesh passes')
        bad = results['doubled tail']; gc_check(not bad['passed'] and any(x['code'] == 'extra_geometry' for x in bad['reasons']), 'doubled tail fails as extra geometry')
        gc_check(any(x['code'] == 'extra_geometry' and x['view'] == 'top' for x in bad['reasons']), 'the TOP view catches it')
        gc_check(bad['score'] < results['single tail']['score'], 'doubled tail scores lower (best-of-N picks the clean one)')
        gc_check((work / 'doubled_tail' / 'fit_top.png').is_file(), 'evidence images written')
        moved = results['moved tail']; gc_check(not moved['passed'], 'moved tail fails')
        gc_check([x['code'] for x in moved['reasons'] if x['view'] == 'top'] == ['misplaced_part'], '0.010: from the TOP, a moved tail is labelled misplaced part (extra AND missing), not extra geometry')
        gc_check(not any(x['code'] == 'misplaced_part' for x in bad['reasons']), '0.010: doubled tail is still labelled extra geometry in every view')
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('geometry check: doubled tail caught (top view far-extra %.1f%%), clean mesh passes' % [x['value'] for x in results['doubled tail']['reasons'] if x['view'] == 'top'][0])
    print('COLOR_UPDATE_SELFTEST_PASSED', flush=True)
except Exception:
    traceback.print_exc(); print('COLOR_UPDATE_SELFTEST_FAILED', flush=True); sys.exit(1)
