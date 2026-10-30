# AI_PAINT_RESULT_FIX_V1 installer test (0.016 build 2026-10-29-3), studio launcher Python. Read-only on the jobs:
# every finished colour version that has a hash-verified AI paint result must now be offered as THE Bambu file.
#   python test_aipaint_result_016c.py <studio folder>
import sys, json, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
try:
    import hunyuan_color_bridge as HB, ai_paint_stage as A
    src = (root / 'hunyuan_color_bridge.py').read_text(encoding='utf-8'); ui = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8')
    check("sc=d['status'].get('checks')" in src, 'colour page reads the AI paint result where the export stores it (status.json)')
    check("'-picture-method-backup.3mf'" in ui, 'a picture-method backup download can no longer have the same file name as the AI paint file')
    n = {'process': lambda j: None, 'answer': lambda p: None, 'install': lambda m: None,
         'CONTEXT': {'config': lambda: {}, 'TASKS': None, 'get_job': lambda i: root / 'Jobs' / i}, 'state': lambda *a, **k: None, 'save': lambda p, v: None}
    HB.extend(n)
    cl = {c.cell_contents.__name__: c.cell_contents for c in n['answer'].__closure__ if callable(getattr(c, 'cell_contents', None)) and hasattr(c.cell_contents, '__name__')}
    tested = 0
    for job in sorted((root / 'Jobs').glob('*')):
        st = job / 'reference_color_state_v2.json'
        if not st.is_file(): continue
        try:
            s = json.loads(st.read_text(encoding='utf-8'))
            if s.get('phase') != 'complete' or not s.get('version'): continue
            folder = job / 'color_versions' / s['version']
            if A.verified_result(folder) is None: continue
            d = cl['details'](job)
        except Exception as e:
            check(False, '%s: details failed: %s' % (job.name, e)); continue
        if d.get('source_changed'): continue
        a = d.get('ai_paint') or {}; tested += 1
        check(a.get('ok') is True and 'model-bambu-aipaint.3mf' in (a.get('files') or {}),
              '%s: AI paint file offered (%s filaments, palette %s)' % (job.name, (a.get('filaments') or {}).get('filaments'), (a.get('filaments') or {}).get('palette')))
    print('  note %d finished AI paint job(s) checked on this PC' % tested, flush=True)
    print('AIPAINT_RESULT_016C_TEST_PASSED' if ok else 'AIPAINT_RESULT_016C_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('AIPAINT_RESULT_016C_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
