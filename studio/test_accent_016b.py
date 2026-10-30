# ACCENT_TO_OUTLINE_V1 installer test (0.016 build 2026-10-29-2). Runs the INSTALLED ai_paint_filaments.py in the texture_paint
# Python on a synthetic model (temp folder only) and, if present, on a copy of the real fox job's AI paint data.
#   python test_accent_016b.py <studio folder> <texture_paint python>
import sys, json, shutil, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
root = Path(sys.argv[1]).resolve(); tp_py = sys.argv[2]
ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
GREY, WHITE, MID, DARK, BLUE = (150, 152, 158), (213, 210, 208), (98, 100, 106), (69, 69, 74), (91, 161, 212)
def run(prep, work, k):
    r = subprocess.run([tp_py, str(root / 'ai_paint_filaments.py'), str(root), str(prep), str(work), str(k), 'studio'], capture_output=True, text=True, timeout=600)
    d = json.loads((work / 'filaments.json').read_text(encoding='utf-8'))
    return r.returncode, d
tmp = Path(tempfile.mkdtemp(prefix='accent016b-'))
try:
    # synthetic flat model: 60 x 60 squares (7200 triangles, 1 mm each); grey 45 %, white 25 %, mid grey 15 %, dark 15 %, blue eyes 0.25 %
    n = 60; xs, ys = np.meshgrid(np.arange(n + 1), np.arange(n + 1)); V = np.c_[xs.ravel(), ys.ravel(), np.zeros(xs.size)].astype(float)
    T = []; col = []
    for y in range(n):
        for x in range(n):
            a = y * (n + 1) + x; c = GREY if x < 27 else WHITE if x < 42 else MID if x < 51 else DARK
            if 28 <= x < 31 and 10 <= y < 13: c = BLUE
            T += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]; col += [c, c]
    prep = tmp / 'prep'; prep.mkdir(); work = tmp / 'w'; work.mkdir()
    np.savez_compressed(prep / 'mesh.npz', V=V, T=np.array(T), Vh=V)
    np.save(work / 'tri_rgb.npy', np.array(col, np.float32) / 255)
    img = np.zeros((240, 240, 4), np.uint8); img[..., 3] = 255
    img[:, :108, :3] = GREY; img[:, 108:168, :3] = WHITE; img[:, 168:204, :3] = MID; img[:, 204:, :3] = DARK; img[40:52, 112:124, :3] = BLUE; img[100:104, 20:120, :3] = (20, 20, 22)
    Image.fromarray(img).save(prep / 'ref_front.png')
    hexes = lambda d: [p.upper() for p in d['files'][0]['palette']]
    def blueish(h): r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16); return b - r > 60
    rc, d4 = run(prep, work, 4)
    check(rc == 0 and len(hexes(d4)) == 4, '4 filaments: 3MF written: %s' % hexes(d4))
    check(not any(blueish(h) for h in hexes(d4)) and d4.get('accents_to_outline'), '4 filaments: the tiny blue accent is not a filament (moved to the outline colour): %s' % d4.get('accents_to_outline'))
    sh = d4['files'][0]['share_percent']
    check(sh[-1] >= 15.0, '4 filaments: the blue areas print in the darkest (outline) filament (outline share %.1f %%)' % sh[-1])
    w5 = tmp / 'w5'; w5.mkdir(); shutil.copy(work / 'tri_rgb.npy', w5)
    rc, d5 = run(prep, w5, 5)
    check(rc == 0 and len(hexes(d5)) == 5 and any(blueish(h) for h in hexes(d5)), '5 filaments: the accent colour is kept: %s' % hexes(d5))
    # the real fox job (read-only copy), if it is still on this PC
    fox = root / 'Jobs' / '20261029-100218-508c5672' / 'color_versions' / '99bda0c7755343c5' / 'ai_paint_work'
    if (fox / 'tri_rgb.npy').is_file() and (fox / 'prep' / 'mesh.npz').is_file():
        wf = tmp / 'fox'; wf.mkdir(); shutil.copy(fox / 'tri_rgb.npy', wf)
        rc, df = run(fox / 'prep', wf, 4)
        check(rc == 0 and not any(blueish(h) for h in hexes(df)), 'real fox (4 filaments): palette %s, shares %s, accents to outline %s' % (hexes(df), df['files'][0]['share_percent'], df.get('accents_to_outline')))
    else:
        print('  note fox job 20261029-100218-508c5672 not found - real-data check skipped', flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print('ACCENT_016B_TEST_PASSED' if ok else 'ACCENT_016B_TEST_FAILED', flush=True)
sys.exit(0 if ok else 1)
