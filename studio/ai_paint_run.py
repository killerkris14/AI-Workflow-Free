# AI texture paint TEST - step "paint" (runs in the separate texture_paint Python, never in ComfyUI's Python)
# args: <hunyuan code dir> <models dir> <prep dir> <output dir>
# Uses the Hunyuan3D-2 texture model (delight + multiview paint, turbo) to paint a texture FOR this mesh from the approved
# front picture, then samples that texture per triangle (triangle order = the studio's own order) -> tri_rgb.npy.
import sys, os, json, time, traceback
from pathlib import Path
code, models, prep, out = [Path(a) for a in sys.argv[1:5]]
out.mkdir(parents=True, exist_ok=True)
info = {'ok': False, 'stage': 'start'}
def save(): (out / 'paint.json').write_text(json.dumps(info, indent=1, default=str), encoding='utf-8')
def prog(pct, text):   # PROGRESS_LINES_V1: read by the .bat to drive its progress bar
    print('PROGRESS %d %s' % (pct, text), flush=True)
try:
    import numpy as np, torch, trimesh
    from PIL import Image
    info.update(torch=torch.__version__, cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    if not torch.cuda.is_available(): raise RuntimeError('CUDA is not available in the texture_paint Python (torch %s)' % torch.__version__)
    free, total = torch.cuda.mem_get_info(); info['vram_free_start_MiB'] = free // 2**20; info['vram_total_MiB'] = total // 2**20
    sys.path.insert(0, str(code))
    import custom_rasterizer, custom_rasterizer_kernel as _K
    # CPU_RASTER_FALLBACK_V1: the prebuilt rasterizer's GPU code is compiled ONLY for sm_89 (RTX 40xx). On any other card
    # (RTX 3080 = sm_86 -> "no kernel image is available") use the CPU rasterizer that is compiled into the same file
    # (same algorithm; ~1 s per 2048 px view on this mesh). The AI models still run on the graphics card.
    cap = torch.cuda.get_device_capability(0); info['gpu_capability'] = '%d.%d' % cap
    if cap != (8, 9) or os.environ.get('PAINT_RASTER') == 'cpu':
        def _rasterize(pos, tri, resolution, clamp_depth=torch.zeros(0), use_depth_prior=0):
            dev = pos.device
            f, b = _K.rasterize_image(pos[0].detach().float().cpu().contiguous(), tri.detach().to(torch.int32).cpu().contiguous(),
                                      clamp_depth.detach().float().cpu().contiguous(), resolution[1], resolution[0], 1e-6, use_depth_prior)
            return f.to(dev), b.to(dev)
        custom_rasterizer.rasterize = _rasterize; info['rasterizer'] = 'cpu (prebuilt GPU code is sm_89 only)'
    else:
        info['rasterizer'] = 'gpu'
    from hy3dgen.texgen import pipelines as PL
    from hy3dgen.texgen.utils.uv_warp_utils import mesh_uv_wrap
    d = np.load(prep / 'mesh.npz'); Vh, T = d['Vh'], d['T']
    # FRONT_TURN_V1: the approved FRONT alignment can point at the model's back (old jobs). The .bat re-runs with PAINT_TURN=1,
    # which turns the mesh 180 degrees about its up axis (a rotation, not a mirror) so the front picture lands on the face.
    info['turned_180'] = os.environ.get('PAINT_TURN') == '1'
    if info['turned_180']: Vh = Vh * np.array([-1.0, 1.0, -1.0])
    mesh = trimesh.Trimesh(vertices=Vh, faces=T, process=False)          # process=False keeps triangle order
    if len(mesh.faces) != len(T): raise RuntimeError('triangle count changed while loading the mesh')
    image = Image.open(prep / 'front_rgba.png').convert('RGBA')
    info['stage'] = 'load models'; save(); t0 = time.time(); prog(2, 'loading the AI paint models')
    root = models / 'Hunyuan3D-2'
    cfg = PL.Hunyuan3DTexGenConfig(str(root / 'hunyuan3d-delight-v2-0'), str(root / 'hunyuan3d-paint-v2-0-turbo'), 'hunyuan3d-paint-v2-0-turbo')
    cfg.device = 'cpu'                                                    # load on the CPU first: 10 GB card, ~7 GB free
    pipe = PL.Hunyuan3DPaintPipeline(cfg)
    mode = os.environ.get('PAINT_OFFLOAD', 'model')
    for m in pipe.models.values():
        if mode == 'sequential': m.pipeline.enable_sequential_cpu_offload(device='cuda')
        else: m.pipeline.enable_model_cpu_offload(device='cuda')
        m.device = 'cuda'
    info['offload'] = mode; info['load_seconds'] = round(time.time() - t0, 1)
    info['stage'] = 'uv unwrap'; save(); t0 = time.time(); prog(10, 'laying out the texture (UV unwrap, a few minutes, no output)')
    mesh = mesh_uv_wrap(mesh)
    if len(mesh.faces) != len(T): raise RuntimeError('UV unwrap changed the triangle count')
    info['uv_seconds'] = round(time.time() - t0, 1)
    # pipeline __call__ re-runs mesh_uv_wrap; give it the already unwrapped mesh and skip the second unwrap
    PL.mesh_uv_wrap = lambda m: m
    # SAVE_PAINT_VIEWS_V1: keep the AI's intermediate pictures (de-lit front picture + the 6 generated views) so the
    # baking step can be re-run and compared without repeating the AI paint (same seed -> same views).
    from hy3dgen.texgen.utils.multiview_utils import Multiview_Diffusion_Net as _MV
    from hy3dgen.texgen.utils.dehighlight_utils import Light_Shadow_Remover as _LR
    vdir = out / 'views'; vdir.mkdir(exist_ok=True)
    _mv_call, _lr_call = _MV.__call__, _LR.__call__
    def _mv_wrap(self, *a, **k):
        res = _mv_call(self, *a, **k)
        for i, im in enumerate(res): im.save(vdir / ('view_%d_elev%d_azim%d.png' % (i, cfg.candidate_camera_elevs[i], cfg.candidate_camera_azims[i])))
        return res
    def _lr_wrap(self, *a, **k):
        res = _lr_call(self, *a, **k); res.save(vdir / 'front_delit.png'); return res
    _MV.__call__, _LR.__call__ = _mv_wrap, _lr_wrap
    # count diffusion steps (de-light 50, multiview 30) and wrap bake / gap fill, to report progress
    def _count(sched, lo, hi, n, label):
        st0 = sched.step; c = [0]
        def step(*a, **k):
            c[0] += 1; prog(lo + (hi - lo) * min(c[0], n) // n, '%s step %d/%d' % (label, min(c[0], n), n)); return st0(*a, **k)
        sched.step = step
    _count(pipe.models['delight_model'].pipeline.scheduler, 25, 35, 50, 'AI de-light')
    _count(pipe.models['multiview_model'].pipeline.scheduler, 36, 70, 10 if cfg.pipe_name == 'hunyuanpaint-turbo' else 30, 'AI paint views')
    _bake, _inp = PL.Hunyuan3DPaintPipeline.bake_from_multiview, PL.Hunyuan3DPaintPipeline.texture_inpaint
    def _bake_w(self, *a, **k): prog(71, 'baking the 6 views onto the model'); return _bake(self, *a, **k)
    def _inp_w(self, *a, **k): prog(78, 'filling texture gaps (several minutes, no output)'); r = _inp(self, *a, **k); prog(94, 'saving the texture'); return r
    PL.Hunyuan3DPaintPipeline.bake_from_multiview, PL.Hunyuan3DPaintPipeline.texture_inpaint = _bake_w, _inp_w
    info['views_saved_to'] = str(vdir); info['view_cameras'] = {'elev': cfg.candidate_camera_elevs, 'azim': cfg.candidate_camera_azims, 'weight': cfg.candidate_view_weights}
    info['stage'] = 'paint'; save(); t0 = time.time(); torch.cuda.reset_peak_memory_stats(); prog(24, 'AI paint starting')
    textured = pipe(mesh, image=image)
    info['paint_seconds'] = round(time.time() - t0, 1); info['vram_peak_allocated_MiB'] = torch.cuda.max_memory_allocated() // 2**20
    info['stage'] = 'save'; save()
    # FRONT_CHECK_V1: the AI's azim-0 view should look like the front picture. If its azim-180 view matches clearly better,
    # the approved front alignment points at the model's back -> the .bat repaints with PAINT_TURN=1.
    def _small(pth):
        a = np.asarray(Image.open(pth).convert('RGB').resize((128, 128)), float) / 255; return a
    def _diff(a, b):
        fa = np.abs(a - a[2, 2]).sum(-1) > 0.08; fb = np.abs(b - b[2, 2]).sum(-1) > 0.08; m = fa & fb
        return float(np.mean(np.abs(a[m] - b[m]))) if m.sum() > 50 else 1.0
    ref = _small(vdir / 'front_delit.png')
    d0 = _diff(ref, _small(vdir / 'view_0_elev0_azim0.png')); d180 = _diff(ref, _small(vdir / 'view_2_elev0_azim180.png'))
    info['front_check'] = {'diff_front_view': round(d0, 4), 'diff_back_view': round(d180, 4), 'front_points_at_back': bool(d180 < d0 - 0.015)}
    save(); prog(96, 'sampling the texture per triangle')
    textured.export(out / 'ai_textured.glb')
    tex = textured.visual.material.image if hasattr(textured.visual.material, 'image') and textured.visual.material.image is not None else textured.visual.image
    tex = tex.convert('RGB'); tex.save(out / 'ai_texture.png')
    uv = np.asarray(textured.visual.uv, float); F = np.asarray(textured.faces)
    if len(F) != len(T): raise RuntimeError('painted mesh triangle count differs from the studio mesh')
    # sample each triangle at 4 points (centre + 3 inner points); trimesh's uv_to_color uses the same uv convention as the GLB
    bary = np.array([[1/3, 1/3, 1/3], [2/3, 1/6, 1/6], [1/6, 2/3, 1/6], [1/6, 1/6, 2/3]])
    def sample(flipv):
        U = uv.copy()
        if flipv: U[:, 1] = 1 - U[:, 1]
        acc = np.zeros((len(F), 3))
        for b in bary:
            p = (U[F] * b[None, :, None]).sum(1)
            acc += trimesh.visual.color.uv_to_color(p, tex)[:, :3] / 255.0
        return acc / len(bary)
    # orientation self-check: the right texture orientation makes neighbouring triangles similar in colour
    edges = np.sort(np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), 1); tri = np.tile(np.arange(len(T)), 3)
    order = np.lexsort((edges[:, 1], edges[:, 0])); e = edges[order]; same = np.all(e[1:] == e[:-1], 1)
    pa, pb = tri[order][:-1][same], tri[order][1:][same]
    scores = {}
    cols = {}
    for fv in (False, True):
        c = sample(fv); cols[fv] = c; scores['flip_v' if fv else 'as_is'] = float(np.abs(c[pa] - c[pb]).sum(1).mean())
    best = min((False, True), key=lambda fv: scores['flip_v' if fv else 'as_is'])
    info['uv_orientation_neighbour_difference'] = scores; info['uv_orientation_used'] = 'flip_v' if best else 'as_is'
    if scores['flip_v' if best else 'as_is'] > 0.6 * max(scores.values()):
        info['uv_orientation_warning'] = 'the two orientations are not clearly different - check the preview pictures'
    np.save(out / 'tri_rgb.npy', cols[best].astype(np.float32))
    info['ok'] = True; info['stage'] = 'done'; save(); prog(100, 'AI paint finished')
    print('PAINT_PASSED', json.dumps({k: info.get(k) for k in ('paint_seconds', 'vram_peak_allocated_MiB', 'offload', 'rasterizer', 'uv_orientation_used')}))
except Exception as e:
    oom = type(e).__name__ == 'OutOfMemoryError' or 'out of memory' in str(e).lower()
    info['error'] = ('out of graphics memory: ' if oom else '') + type(e).__name__ + ': ' + (str(e).strip().splitlines() or [''])[0][:400]
    info['traceback'] = traceback.format_exc(); save(); traceback.print_exc(); sys.exit(3 if oom else 1)
