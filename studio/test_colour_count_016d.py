# COLOUR_COUNT_TOGGLE_V1 installer test (0.016 build 2026-10-29-4), launcher Python, temporary folders only.
#   python test_colour_count_016d.py <studio folder>
import sys, json, base64, tempfile, shutil, queue, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\0' * 64).decode()
try:
    import hunyuan_bridge as HY, hunyuan_color_bridge as HB, ai_paint_stage as A
    tmp = Path(tempfile.mkdtemp(prefix='colourcount-'))
    try:
        HY.CONTEXT.update(config=lambda: {'allow_generated_code_execution': True}, JOBS=tmp, TASKS=queue.Queue(), status=lambda job, name, **kw: None)
        base = {'image_base64': PNG, 'length_mm': 120, 'quality': 'standard', 'authorize_processing': True}
        j4 = tmp / HY.admit(dict(base, ai_paint_filaments=4))['id']; j9 = tmp / HY.admit(dict(base, ai_paint_filaments=9))['id']
        jx = tmp / HY.admit(dict(base, ai_paint_filaments=10))['id']; jn = tmp / HY.admit(dict(base))['id']
        jc = {n: tmp / HY.admit(dict(base, ai_paint_filaments=n))['id'] for n in (5, 6, 7, 8)}; jb = [tmp / HY.admit(dict(base, ai_paint_filaments=v))['id'] for v in (3, '7', True, 7.0)]
        r = lambda j: json.loads((j / 'request.json').read_text())
        check(r(j4)['ai_paint_filaments'] == 4 and r(j9)['ai_paint_filaments'] == 9, 'upload: 4 colours -> 4, 9 colours -> 9 stored in request.json')
        check(all(r(j)['ai_paint_filaments'] == n for n, j in jc.items()), 'custom: 5, 6, 7, 8 colours stored as chosen (CUSTOM_COLOUR_COUNT_V1)')
        check(r(jx)['ai_paint_filaments'] == 4 and r(jn)['ai_paint_filaments'] == 4 and all(r(j)['ai_paint_filaments'] == 4 for j in jb), 'anything else (10, 3, text, true, 7.0 or nothing) -> 4 colours default')
        check(all(HB.ai_paint_best(j)['filaments'] == n for n, j in jc.items()), 'colour export uses the custom amount')
        if A.install_status(root)['installed']:
            check(all(A.options(HB.ai_paint_best(j), root)['filaments'] == n for n, j in jc.items()), 'AI paint stage accepts 5-8 (Bambu templates present for %s)' % A.template_counts(root))
        old = tmp / 'old'; old.mkdir(); (old / 'request.json').write_text(json.dumps({'engine': 'hunyuan'}))
        check(HB.ai_paint_best(j9)['filaments'] == 9 and HB.ai_paint_best(j4)['filaments'] == 4 and HB.ai_paint_best(old)['filaments'] == 4, 'colour export uses the uploaded choice; older jobs use 4')
        if A.install_status(root)['installed']:
            check(A.options(HB.ai_paint_best(j9), root) == {'enabled': True, 'filaments': 9, 'colours': 'studio'}, '9-colour master accepted by the AI paint stage (bambu_template_9.3mf present)')
        else:
            check(False, 'AI paint runtime not installed')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    portal = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8'); colour = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8')
    check('hunyuan-colour-count' in portal and 'Click here if you want more than 4' not in portal, 'upload form shows the 4 / 9 colour toggle instead of the old checkbox')
    check('hunyuan-colour-custom-toggle' in portal and 'for(const n of [5,6,7,8])' in portal, 'upload form has the Custom button with 5 / 6 / 7 / 8')
    check('The 4 / 9 colour choice is made on the upload form.' in colour, 'colour export box names the choice')
    print('COLOUR_COUNT_016D_TEST_PASSED' if ok else 'COLOUR_COUNT_016D_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('COLOUR_COUNT_016D_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
