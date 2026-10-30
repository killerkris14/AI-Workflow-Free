# PROMPT_BUILDER_SYNC_V1 installer test (0.017), launcher Python, read-only.
#   python test_prompt_builder_017.py <studio folder>
import sys, re, json, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); ok = True
ART = 'd8affbd9df5c7ce3828d98818859e9150ac6b470e4f4978d2d49702ecbf8ddf3'
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
try:
    js = (root / 'studio_shell_ui.js').read_text(encoding='utf-8')
    check('PROMPT_BUILDER_SYNC_V1' in js and ART in js, 'Prompt Builder page is the synced chat build (source sha256 %s...)' % ART[:12])
    fn = js[js.index('function buildPromptBuilder('):js.index('// ---------- .3mf Repair')]
    html = json.loads(re.search(r"root\.innerHTML=(\".*?\");\n", fn, re.S).group(1))
    ids = re.findall(r'\bid="([^"]+)"', html)
    check(ids and all(i.startswith('pb-') for i in ids), 'all %d page element ids are prefixed pb- (no clash with the Image to 3D page)' % len(ids))
    presets = re.findall(r'^\s+\["[^"]+", "(four|sit|belly|two|bird|many|snake|swim|tentacle|blob|custom)", ', fn, re.M)
    check(len(presets) == 210, 'presets: %d (expected 210)' % len(presets))
    hol = re.findall(r'^\s+(\w+): \["[^"]+", "', fn, re.M)
    check(len(hol) == 20, 'holiday themes with small / medium / large props: %d (expected 20)' % len(hol))
    for need in ('pb-presetSearch', 'pb-holiday', 'pb-propSize', 'value="grid5"', 'value="thick"', 'value="voxel"', 'pb-copy'):
        check(need in html, 'control present: ' + need)
    check("document.getElementById('pb-' + id)" in fn and fn.count('document.getElementById(') == 1, 'the builder only reads its own pb- elements')
    check('tick \\"Has props included\\"' in fn, 'holiday sheets remind you to tick "Has props included" when uploading')
    check("'Prompt Builder'" in js and "'Old Blender'" in js and 'buildRepair(' in js, 'tabs and the .3mf Repair page unchanged')
    print('PROMPT_BUILDER_017_TEST_PASSED' if ok else 'PROMPT_BUILDER_017_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('PROMPT_BUILDER_017_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
