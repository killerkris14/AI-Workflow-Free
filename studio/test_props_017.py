# PROPS_TOGGLE_V1 installer test (0.017). Launcher Python; temporary folders only.
#   python test_props_017.py <studio folder> <texture_paint python>
import sys, os, json, base64, tempfile, shutil, queue, subprocess, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); tp_py = sys.argv[2]; sys.path.insert(0, str(root)); ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\0' * 64).decode()
try:
    import hunyuan_bridge as HY, hunyuan_color_bridge as HB, ai_paint_stage as A
    tmp = Path(tempfile.mkdtemp(prefix='props017-'))
    try:
        HY.CONTEXT.update(config=lambda: {'allow_generated_code_execution': True}, JOBS=tmp, TASKS=queue.Queue(), status=lambda job, name, **kw: None)
        base = {'image_base64': PNG, 'length_mm': 120, 'quality': 'standard', 'authorize_processing': True, 'ai_paint_filaments': 9}
        jp = tmp / HY.admit(dict(base, has_props=True))['id']; jn = tmp / HY.admit(dict(base))['id']; jx = tmp / HY.admit(dict(base, has_props='yes'))['id']
        r = lambda j: json.loads((j / 'request.json').read_text())
        check(r(jp)['has_props'] is True and r(jn)['has_props'] is False and r(jx)['has_props'] is False, 'upload: ticked -> has_props true; not ticked / anything else -> false')
        old = tmp / 'old'; old.mkdir(); (old / 'request.json').write_text(json.dumps({'engine': 'hunyuan'}))
        check(HB.ai_paint_best(jp).get('props') is True and 'props' not in HB.ai_paint_best(jn) and 'props' not in HB.ai_paint_best(old), 'colour export: props only for jobs uploaded with the box ticked (older jobs unchanged)')
        if A.install_status(root)['installed']:
            check(A.options(HB.ai_paint_best(jp), root) == {'enabled': True, 'filaments': 9, 'colours': 'studio', 'props': True}, 'AI paint stage accepts props')
            check(A.options(HB.ai_paint_best(jn), root) == {'enabled': True, 'filaments': 9, 'colours': 'studio'}, 'no props -> options exactly as in 0.016')
            try: A.options({'enabled': True, 'props': 'yes'}, root); check(False, 'non-true/false props refused')
            except ValueError: check(True, 'non-true/false props refused')
        check(HB.with_props({'enabled': True, 'filaments': 4, 'colours': 'auto', 'props': True}, jn) == {'enabled': True, 'filaments': 4, 'colours': 'auto'}, 'custom export box cannot switch props on; only the upload toggle does')
        # filament step in the texture_paint Python: tiny blue accent at 4 filaments, without and with props.
        # The synthetic model is built by the texture_paint Python too (the launcher Python has no numpy).
        maker = tmp / 'make_model.py'
        maker.write_text("""import sys
from pathlib import Path
import numpy as np
from PIL import Image
tmp = Path(sys.argv[1]); n = 60; xs, ys = np.meshgrid(np.arange(n + 1), np.arange(n + 1)); V = np.c_[xs.ravel(), ys.ravel(), np.zeros(xs.size)].astype(float); T = []; col = []
GREY, WHITE, MID, DARK, BLUE = (150, 152, 158), (213, 210, 208), (98, 100, 106), (69, 69, 74), (91, 161, 212)
for y in range(n):
    for x in range(n):
        a = y * (n + 1) + x; c = GREY if x < 27 else WHITE if x < 42 else MID if x < 51 else DARK
        if 28 <= x < 31 and 10 <= y < 13: c = BLUE
        T += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]; col += [c, c]
prep = tmp / 'prep'; prep.mkdir(); np.savez_compressed(prep / 'mesh.npz', V=V, T=np.array(T), Vh=V)
img = np.zeros((240, 240, 4), np.uint8); img[..., 3] = 255
img[:, :108, :3] = GREY; img[:, 108:168, :3] = WHITE; img[:, 168:204, :3] = MID; img[:, 204:, :3] = DARK; img[40:52, 112:124, :3] = BLUE; img[100:104, 20:120, :3] = (20, 20, 22)
Image.fromarray(img).save(prep / 'ref_front.png')
for flag in ('0', '1'):
    w = tmp / ('w' + flag); w.mkdir(); np.save(w / 'tri_rgb.npy', np.array(col, np.float32) / 255)
print('MODEL_MADE')
""", encoding='utf-8')
        mk = subprocess.run([tp_py, '-I', str(maker), str(tmp)], capture_output=True, text=True, timeout=300)
        check(mk.returncode == 0 and 'MODEL_MADE' in mk.stdout, 'synthetic test model made in the AI paint Python' + ('' if mk.returncode == 0 else ': ' + mk.stderr[-300:]))
        prep = tmp / 'prep'; res = {}
        for flag in ('0', '1'):
            w = tmp / ('w' + flag)
            p = subprocess.run([tp_py, str(root / 'ai_paint_filaments.py'), str(root), str(prep), str(w), '4', 'studio'], capture_output=True, text=True, timeout=600, env=dict(os.environ, AIPAINT_PROPS=flag))
            res[flag] = json.loads((w / 'filaments.json').read_text(encoding='utf-8')) if (w / 'filaments.json').is_file() else {'error': p.stderr[-400:]}
        check(res['0'].get('accents_to_outline') and res['0'].get('props') is False, 'no props: tiny accent still moved to the outline colour (0.016 behaviour kept): %s' % res['0'].get('accents_to_outline'))
        check(res['1'].get('ok') and res['1'].get('accents_to_outline') == [] and res['1'].get('props') is True, 'props: nothing moved to the outline colour; palette %s' % (res['1'].get('files') or [{}])[0].get('palette'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = (root / 'ai_paint_stage.py').read_text(encoding='utf-8'); portal = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    check("AIPAINT_PROPS='1' if opts.get('props') else '0'" in src and "'Props: %s'" in src, 'AI paint passes props to the filament step and writes it in the report')
    check('hunyuan-has-props-box' in portal and 'has_props:prBox.checked' in portal and 'apBtns[1].click()' in portal, 'upload form: "Has props included" box, sent with the upload, picks 9 colours')
    print('PROPS_017_TEST_PASSED' if ok else 'PROPS_017_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('PROPS_017_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
