# COLOUR_ADVICE_V1 installer test (0.017 build 2026-10-30-3), launcher Python, read-only.
# The advice runs in the browser (JavaScript); this checks that the installed upload form carries it, wired to image uploads only.
# Calibration (Chromium, 2026-10-30): fox 4, mammoth 4, 6-colour dragon 6, Christmas dragon 7, shaded 2026-10-27 sheet 9 (capped).
import sys, re, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
try:
    js = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    check('COLOUR_ADVICE_V1' in js and 'function advAnalyse(img)' in js and 'function advShow(box,r)' in js, 'upload form has the colour advice')
    check('const ADV_MERGE=14,ADV_MIN_SHARE=1.0,ADV_SIZE=400;' in js, 'calibrated settings: merge 14 deltaE, colours from 1 %, picture scaled to 400 px')
    check("image.addEventListener('change'" in js and "/^image\\//.test(f.type)" in js, 'runs when an image is chosen; videos are skipped')
    check('Math.max(4,Math.min(9,needed))' in js and 'cuToggle.click();apSet(r.recommended)' in js, 'recommendation 4-9 pre-selects 4 / 9 / Custom 5-8')
    check('hunyuan-colour-custom-toggle' in js and 'has_props:prBox.checked' in js and 'ai_paint_filaments:apCount' in js, 'Custom button, props box and the upload request unchanged')
    check(js.count('function advAnalyse(') == 1 and js.count('COLOUR_ADVICE_V1') == 2, 'advice added once (no duplicate on re-install)')
    print('COLOUR_ADVICE_017C_TEST_PASSED' if ok else 'COLOUR_ADVICE_017C_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('COLOUR_ADVICE_017C_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
