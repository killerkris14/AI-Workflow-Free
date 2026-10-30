# AI Modeling Studio 0.011 self-test: SELF_HIT_OCCLUSION_FIX_V1 + HIDDEN_AREA_FILL_V1.
# Run: blender --background --factory-startup --python test_color_coverage_011.py -- <studio folder>
# Synthetic data in a temporary folder only; never touches jobs, settings or models.
import sys, tempfile, shutil, importlib.util, traceback, math
from pathlib import Path
failures = []
def check(cond, msg):
    print(('  ok    ' if cond else '  FAIL  ') + msg, flush=True)
    if not cond: failures.append(msg)
try:
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    root = Path(args[0]).resolve()
    import bpy, bmesh, numpy as np
    spec = importlib.util.spec_from_file_location('t011_hunyuan_color', str(root / 'hunyuan_color.py'))
    hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)
    B = hc._load_bambu_export_local()
    print('AI Modeling Studio 0.011 color coverage self-test  (folder: %s)' % root, flush=True)

    def grid(name, x0, x1, z0, z1, y, n, jitter, seed):
        bm = bmesh.new(); rng = np.random.default_rng(seed)
        xs = np.linspace(x0, x1, n + 1); zs = np.linspace(z0, z1, n + 1); vid = {}
        for i, x in enumerate(xs):
            for k, z in enumerate(zs):
                vid[i, k] = bm.verts.new((x, y + (rng.uniform(-jitter, jitter) if jitter else 0.0), z))
        for i in range(n):
            for k in range(n):
                bm.faces.new((vid[i, k], vid[i + 1, k], vid[i + 1, k + 1], vid[i, k + 1]))
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        for p in me.polygons:   # all quads must face the front camera (-Y)
            if p.normal.y > 0: p.flip()
        me.update(); ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob

    def job(work, mask_right_half=False):
        folder = work / 'JOB' / 'color_versions' / '0000000000000011'; folder.mkdir(parents=True)
        S = 200; img = np.zeros((S, S, 4), np.float32); img[:] = [0.85, 0.1, 0.1, 1]; img[:, S // 2:] = [0.1, 0.6, 0.15, 1]
        hc.png(folder / 'reference_front.png', img)
        mask = np.ones((S, S), bool)
        if mask_right_half: mask[3:S // 2, :] = False   # hide the UPPER half (not mirrored by left-right symmetry); a thin top edge keeps the mask's extent (projection scale) unchanged
        np.savez_compressed(folder / 'reference_masks.npz', front=mask); return folder

    def run(objs, folder):
        co = np.vstack([np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices]) for o in objs])
        review = {'views': [{'slot': 'front', 'direction_hint': 'front'}], 'source': {'dimensions_mm': [float(x) for x in np.ptp(co, axis=0)]}}
        return hc.transfer(objs, folder, {'settings': {'views': {'front': {'direction': 'front', 'color_use': 'on'}}}}, review)

    new_blocked = hc.blocked
    def old_blocked(tree, p, toward, epsilon, owner, own, max_skips=16):   # 0.010 rule: ANY hit, including the face itself
        from mathutils import Vector
        return tree.ray_cast(Vector(p + toward * epsilon), Vector(toward))[0] is not None

    print('[1] non-planar quads facing the camera, nothing in front (the real-job bug)')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    work = Path(tempfile.mkdtemp(prefix='aistudio-t011-'))
    try:
        ob = grid('Bumpy', -20, 20, 0, 40, 0.0, 40, 0.35, 1); folder = job(work)
        n = len(ob.data.polygons)
        hc.blocked = old_blocked; st_old = run([ob], folder)
        hc.blocked = new_blocked; st_new = run([ob], folder)
        print('      faces %d | 0.010 rule mapped %d | 0.011 mapped %d' % (n, st_old['mapped_faces'], st_new['mapped_faces']))
        check(st_old['mapped_faces'] < 0.9 * n, 'test reproduces the bug: the 0.010 rule loses visible faces to self-hits')
        check(st_new['mapped_faces'] == n, '0.011: every visible face gets reference colour')
    finally:
        hc.blocked = new_blocked; shutil.rmtree(work, ignore_errors=True)

    print('[2] a real occluder still hides what is behind it')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    work = Path(tempfile.mkdtemp(prefix='aistudio-t011-'))
    try:
        back = grid('Back', -20, 20, 0, 40, 0.0, 40, 0.35, 2); plate = grid('Plate', -20, 0, 0, 40, -8.0, 10, 0.0, 3)
        folder = job(work); st = run([back, plate], folder)
        mats = np.array([p.material_index for p in back.data.polygons]); cx = np.array([p.center.x for p in back.data.polygons])
        hidden = cx < -1.0; visible = cx > 1.0
        check(np.all(mats[hidden] != 0), 'faces behind the plate get NO colour from the front view')
        check(np.all(mats[visible] == 0), 'faces beside the plate get front-view colour')
        pm = np.array([p.material_index for p in plate.data.polygons]); check(np.all(pm == 0), 'the plate itself is coloured')
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print('[3] hidden-area fill distance (pure function)')
    # strip of 60 triangles 1 mm wide: first 6 observed (filament 2), rest hidden (policy colour 1); separate island hidden
    V = []; T = []
    for i in range(31):
        V += [(i, 0, 0), (i, 1, 0)]
    for i in range(30):
        a, b, c, d = 2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1; T += [(a, b, c), (a, c, d)]
    base = len(V); V += [(100, 0, 0), (101, 0, 0), (100, 1, 0)]; T += [(base, base + 1, base + 2)]
    V = np.array(V, float); T = np.array(T); obs = np.zeros(len(T), bool); obs[:6] = True; fil = np.ones(len(T), int); fil[:6] = 2
    res = {}
    for mm in B.FILL_CHOICES:
        f2, filled = B.fill_gaps(fil, obs, T, V, mm); res[mm] = (f2, filled)
    near = res[1.5][1].sum(); all_ = res[math.inf][1]
    print('      filled triangles: 1.5mm %d, 5mm %d, 15mm %d, all %d (of %d hidden, 1 isolated)' % (near, res[5.0][1].sum(), res[15.0][1].sum(), all_.sum(), (~obs).sum()))
    check(near < res[5.0][1].sum() < res[15.0][1].sum() <= all_.sum(), 'larger distance fills more')
    check(all_[:60].all() == False and all_[6:60].all() and not all_[60], '"all" fills every connected hidden triangle, never the isolated one')
    check(np.all(res[math.inf][0][6:60] == 2), 'filled triangles take the nearest reference colour')
    try:
        B.fill_gaps  # noqa
        hc.fill_distance('7'); check(False, 'unknown fill setting is rejected')
    except ValueError:
        check(True, 'unknown fill setting is rejected')

    print('[4] full export through bambu_export(): report accounting with fill')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    work = Path(tempfile.mkdtemp(prefix='aistudio-t011-'))
    try:
        ob = grid('Half', -20, 20, 0, 40, 0.0, 40, 0.35, 4); folder = job(work, mask_right_half=True); st = run([ob], folder)
        check(0 < st['fallback_faces'] < len(ob.data.polygons), 'upper half is hidden (mask), lower half coloured')
        reports = {}
        for fill in ('1.5', 'all'):
            out = folder / ('m-%s.3mf' % fill); rep = folder / ('r-%s.txt' % fill)
            r = hc.bambu_export([ob], folder, {'bambu': {'filaments': 2, 'unobserved': 'dominant', 'min_region_mm2': 0.0, 'shading': 'keep', 'fill_unseen': fill}}, out, rep)
            reports[fill] = (r['statistics']['final_surface_split'], rep.read_text(encoding='utf-8'))
            print('      fill %-3s ->' % fill, reports[fill][0])
        s15, sall = reports['1.5'][0], reports['all'][0]
        check(s15['no_reference_percent'] > 30, 'small-gap fill leaves the hidden half unpainted (as before)')
        check(sall['no_reference_percent'] == 0 and sall['inferred_from_neighbours_percent'] > 30, '"all": hidden half filled and reported as INFERRED, not reference colour')
        check(abs(sum(sall.values()) - 100) < 0.1, 'surface split adds up to 100%')
        check('Hidden areas filled from the nearest reference colour (all hidden areas' in reports['all'][1], 'report text states the fill')
        check(sall['reference_colour_percent'] == s15['reference_colour_percent'], 'fill never changes the reference-colour share')
    finally:
        shutil.rmtree(work, ignore_errors=True)
except Exception:
    traceback.print_exc(); failures.append('exception')
if failures:
    print('COLOR_COVERAGE_011_SELFTEST_FAILED: %d check(s): %s' % (len(failures), '; '.join(failures))); sys.exit(1)
print('COLOR_COVERAGE_011_SELFTEST_PASSED')
