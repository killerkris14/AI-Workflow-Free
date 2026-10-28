"""PRE_GEOMETRY_SHEET_CLEANUP_V1 (AI Modeling Studio 0.005): remove reference-sheet extras (labels, ground lines,
rulers) from the prepared views BEFORE 3D generation, so the generator never models them. Runs in ComfyUI's Python
(numpy + PIL). The untouched prepared views are kept in autoroute_prepared_raw/."""
import hashlib, importlib.util, json, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image
spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
helper = Path(spec['helper'])
if hashlib.sha256(helper.read_bytes()).hexdigest() != '68bff08d52e2233354df29743ee96d457bceeb310c5f5e55b4f883fd79803b61':
    raise SystemExit('mask_cleanup.py changed; revalidate the update')
s = importlib.util.spec_from_file_location('studio_mask_cleanup_prepared', str(helper)); MC = importlib.util.module_from_spec(s); s.loader.exec_module(MC)
folder = Path(spec['folder']); raw = Path(spec['raw_folder']); raw.mkdir(exist_ok=True); report = {}
for view in spec['views']:
    path = folder / (view + '.png'); shutil.copy2(path, raw / (view + '.png'))
    with Image.open(path) as im:
        rgba = np.array(im.convert('RGBA'))
    mask = rgba[..., 3] >= 16                       # same foreground rule as the color stage (alpha >= 0.06)
    cleaned, result = MC.clean_mask(mask); removed = mask & ~cleaned
    if removed.any():
        rgba[removed] = [255, 255, 255, 0]          # transparent white, like the rest of the background
        Image.fromarray(rgba, 'RGBA').save(path, format='PNG')
    report[view] = result
    print(view, 'removed %.2f%%' % result['removed_percent'], result.get('skipped_reason', ''), flush=True)
(folder / 'sheet_cleanup.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
print('SHEET_CLEANUP_PASSED', flush=True)
