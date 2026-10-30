# AI texture paint TEST - step "models": download the Hunyuan3D-2 delight + paint (turbo) models at a FIXED revision,
# then check every large file against the SHA-256 that Hugging Face publishes for it. Resumes if interrupted.
# args: <models dir> <revision>
import sys, os, json, hashlib, time
from pathlib import Path
dest, rev = Path(sys.argv[1]), sys.argv[2]
from huggingface_hub import snapshot_download, HfApi
REPO = 'tencent/Hunyuan3D-2'
ALLOW = ['hunyuan3d-delight-v2-0/*', 'hunyuan3d-paint-v2-0-turbo/*']
IGNORE = ['hunyuan3d-paint-v2-0-turbo/unet/diffusion_pytorch_model.safetensors']   # code loads the .bin; skip 3.7 GB duplicate
local = dest / 'Hunyuan3D-2'
t0 = time.time()
snapshot_download(repo_id=REPO, revision=rev, local_dir=str(local), allow_patterns=ALLOW, ignore_patterns=IGNORE, max_workers=4)
api = HfApi(); expected = {}
for sub in ('hunyuan3d-delight-v2-0', 'hunyuan3d-paint-v2-0-turbo'):
    for f in api.list_repo_tree(REPO, path_in_repo=sub, revision=rev, recursive=True, expand=True):
        if getattr(f, 'lfs', None) and f.path not in IGNORE:
            expected[f.path] = (f.lfs.sha256 if hasattr(f.lfs, 'sha256') else f.lfs['sha256'], f.size)
bad = []; checked = []
for path, (sha, size) in sorted(expected.items()):
    p = local / path
    if not p.is_file(): bad.append(path + ' missing'); continue
    if p.stat().st_size != size: bad.append('%s size %d expected %d' % (path, p.stat().st_size, size)); continue
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b''): h.update(chunk)
    if h.hexdigest() != sha: bad.append(path + ' sha256 mismatch')
    checked.append({'path': path, 'bytes': size, 'sha256': sha})
total = sum(c['bytes'] for c in checked)
(dest / 'models_manifest.json').write_text(json.dumps({'repo': REPO, 'revision': rev, 'files': checked, 'problems': bad, 'total_GB': round(total / 1e9, 2), 'seconds': round(time.time() - t0)}, indent=1), encoding='utf-8')
if bad: print('MODELS_FAILED', bad); sys.exit(1)
print('MODELS_PASSED %d large files, %.2f GB verified' % (len(checked), total / 1e9))
