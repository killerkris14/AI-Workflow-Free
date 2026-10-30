# COLOUR_TEXT_CLEANUP_V1 installer test (0.016 build 2026-10-29-4), studio launcher Python.
import sys, json
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
import ai_paint_stage as A
v = json.loads((root / 'color_update_version.json').read_text(encoding='utf-8-sig'))
check((A.VERSION, A.BUILD) == (str(v['version']), str(v['build'])), 'AI paint report shows the installed version: %s build %s' % (A.VERSION, A.BUILD))
src = (root / 'ai_paint_stage.py').read_text(encoding='utf-8')
check('still available' not in src, 'AI paint report no longer mentions the picture-method file as available')
ui = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8')
check('Texture-master 3MF is NOT verified' not in ui, 'stale texture-master warning removed')
check("&&!data.ai_paint)body.append" in ui, '"exported before color update 0.002" notice only for jobs without AI paint')
check("complete:'Bambu full-color 3MF exported'" in ui and "details.open=s.phase!=='complete'" in ui, 'finished colour stage: clear title, alignment details folded')
print('CLEANUP_016D_TEST_PASSED' if ok else 'CLEANUP_016D_TEST_FAILED', flush=True)
sys.exit(0 if ok else 1)
