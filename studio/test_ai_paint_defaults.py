# AI_PAINT_DEFAULTS_V1 installer test (update 0.016). Studio launcher Python, temporary folders only.
#   python test_ai_paint_defaults.py <studio folder>
import sys, json, base64, tempfile, shutil, traceback, queue
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
ok = True
def check(cond, text):
    global ok
    print(('  ok   ' if cond else '  FAIL ') + text, flush=True); ok = ok and bool(cond)
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\0' * 64).decode()
try:
    import hunyuan_bridge as HY, hunyuan_color_bridge as HB, ai_paint_stage as A
    tmp = Path(tempfile.mkdtemp(prefix='aipaint-defaults-'))
    try:
        # 1 upload: the checkbox value is stored in request.json (unticked -> False)
        statuses = {}
        HY.CONTEXT.update(config=lambda: {'allow_generated_code_execution': True}, JOBS=tmp, TASKS=queue.Queue(),
                          status=lambda job, name, **kw: statuses.__setitem__(Path(job).name, name))
        base = {'image_base64': PNG, 'length_mm': 120, 'quality': 'high', 'authorize_processing': True}
        j0 = tmp / HY.admit(dict(base))['id']; j1 = tmp / HY.admit(dict(base, ai_paint_custom=True))['id']
        r0 = json.loads((j0 / 'request.json').read_text()); r1 = json.loads((j1 / 'request.json').read_text())
        check(r0.get('ai_paint_custom') is False, 'upload without the box ticked -> request.json ai_paint_custom = false')
        check(r1.get('ai_paint_custom') is True, 'upload with "Custom AI paint settings" ticked -> request.json ai_paint_custom = true')
        rr = tmp / 'old'; rr.mkdir(); (rr / 'request.json').write_text(json.dumps({'engine': 'hunyuan'}))
        check(HB.ai_paint_custom(j0) is False and HB.ai_paint_custom(j1) is True and HB.ai_paint_custom(rr) is False, 'colour stage reads the choice; jobs from before this update use the best defaults')
        # 2 the best settings are valid for the installed AI paint stage and templates
        st = A.install_status(root)
        if st['installed']:
            check(A.options(dict(HB.AI_PAINT_BEST), root) == {'enabled': True, 'filaments': 4, 'colours': 'studio'}, 'best settings accepted by the AI paint stage: 4 filaments, studio colours')
        else:
            check(False, 'AI paint runtime not installed: ' + '; '.join(st['problems']))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # 3 the export step enforces the defaults for non-custom jobs (code path in answer())
    src = (root / 'hunyuan_color_bridge.py').read_text(encoding='utf-8')
    check("if ai_paint_custom(job):ap=" in src and "best=ai_paint_best(job);ap=ai_paint_stage().options(best,ROOT)" in src, 'colour export uses the best settings (4 or 9 colours from the upload form) unless the job was uploaded as custom')
    ui = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8'); portal = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    check('AI_PAINT_DEFAULTS_V1' in ui and '!data.ai_paint_custom' in ui, 'colour export box: no AI paint choices unless the job is custom')
    check('hunyuan-colour-count' in portal and 'ai_paint_filaments:apCount' in portal, 'upload form has the 4 / 9 colour toggle and sends it (COLOUR_COUNT_TOGGLE_V1)')
    print('AI_PAINT_DEFAULTS_TEST_PASSED' if ok else 'AI_PAINT_DEFAULTS_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('AI_PAINT_DEFAULTS_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
