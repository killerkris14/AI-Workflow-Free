# WHITE_TIP_CROP_FIX_V1 test, run in ComfyUI's Python (numpy + PIL):  python test_fd_016.py <studio folder> <video sheet png>
import sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, sys.argv[1]); import figure_detection as F
ok = True
def check(c, t):
    global ok
    print(('ok   ' if c else 'FAIL ') + t); ok = ok and bool(c)
# a grey figure whose white tail tip (RGB 232) touches the white sheet background: the tip must stay inside the box
a = np.full((600, 600, 3), 255, np.uint8); a[200:520, 220:380] = (130, 132, 140); a[60:200, 280:320] = (130, 132, 140); a[10:60, 285:315] = (232, 232, 230)
p = Path(tempfile.mkdtemp()) / 'tip.png'; Image.fromarray(a).save(p)
_, figs = F.detect(str(p)); y0 = min(f['bbox'][1] for f in figs)
check(y0 <= 10 / 600 + 0.02, 'white tip kept in the crop (box top %.3f, tip starts at %.3f; rule: %s)' % (y0, 10 / 600, F.BACKGROUND_RULE.get('reason')))
# checkerboard 'transparency' background still uses the old rule
c = ((np.indices((400, 400)) // 20).sum(0) % 2); b = np.repeat(np.where(c[..., None], 255, 204), 3, 2).astype(np.uint8); b[120:280, 140:260] = (180, 60, 60)
q = p.with_name('cb.png'); Image.fromarray(b).save(q); _, figs = F.detect(str(q))
check(len(figs) == 1 and 'old rule' in F.BACKGROUND_RULE.get('reason', ''), 'checkerboard background: one figure, old rule')
_, figs = F.detect(sys.argv[2])
views = sorted(f['view'] for f in figs)
check(len(figs) == 4 and views == ['back', 'front', 'left', 'right'], 'video sheet: 4 views found %s' % views)
print('FD_016_PASSED' if ok else 'FD_016_FAILED'); sys.exit(0 if ok else 1)
