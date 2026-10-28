"""VIEW_MIRROR_CHECK_V1 (AI Modeling Studio 0.010): before 3D generation, check that opposite views of one sheet agree.

An orthographic BACK silhouette is the left-right mirror image of the FRONT silhouette (same for RIGHT vs LEFT).
AI reference sheets sometimes draw the back view as a mirror image (e.g. the tail curls to the viewer's right in
BOTH front and back). Then no single 3D shape can match both pictures.

Test: compare the front mask with the back mask as drawn and with the back mask flipped left-right.
  consistent pair  -> the flipped back matches the front better
  mirrored back    -> the back AS DRAWN matches the front better (by a clear margin)
A nearly symmetric subject gives no evidence either way ("cannot tell"); nothing is changed then.

When the back looks mirrored (mode auto_flip, the default), the prepared back view is flipped left-right so 3D
shape, geometry check and color all use the corrected picture. The untouched picture is kept next to it as
<view>.as_drawn.png and in autoroute_prepared_raw/. Every number and the decision go to view_consistency.json.
Runs in ComfyUI's Python (numpy + PIL). Pure functions are importable for tests.
"""
import hashlib, json, shutil, sys
from pathlib import Path
import numpy as np

VERSION = '0.010'
SIZE = 256                 # masks are compared at this height
SHIFT_SHARE = 0.12         # horizontal search range (share of height) when lining the two masks up
MIN_ASYMMETRY = 0.04       # front must differ from its own mirror image by at least this (1 - IoU) to judge
MIN_MARGIN = 0.02          # as-drawn must beat mirrored by this IoU ...
MIN_MARGIN_SHARE = 0.25    # ... and by this share of the subject's own asymmetry
PAIRS = (('front', 'back'), ('left', 'right'))   # the SECOND view of a pair is the one flipped
MODES = ('auto_flip', 'warn', 'off')


def normalise(mask, size=SIZE):
    """Crop to the subject and scale to a fixed height (aspect kept). Returns a bool array size x width."""
    from PIL import Image
    ys, xs = np.nonzero(mask)
    if len(ys) < 50:
        raise ValueError('view has almost no foreground')
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape; width = max(1, int(round(w * size / h)))
    im = Image.fromarray(crop.astype(np.uint8) * 255).resize((width, size), Image.BILINEAR)
    return np.array(im) >= 128


def best_iou(a, b, shift_share=SHIFT_SHARE):
    """Highest IoU of b against a over horizontal shifts (both already the same height)."""
    h = a.shape[0]; s = int(h * shift_share); width = max(a.shape[1], b.shape[1]) + 2 * s + 2
    ca = np.zeros((h, width), bool); xa = (width - a.shape[1]) // 2; ca[:, xa:xa + a.shape[1]] = a
    best = 0.0; area_a = int(a.sum())
    for dx in range(-s, s + 1, 2):
        xb = (width - b.shape[1]) // 2 + dx
        if xb < 0 or xb + b.shape[1] > width:
            continue
        cb = np.zeros((h, width), bool); cb[:, xb:xb + b.shape[1]] = b
        inter = int((ca & cb).sum()); union = area_a + int(b.sum()) - inter
        best = max(best, inter / union if union else 0.0)
    return best


def compare(first_mask, second_mask):
    """Pure decision. Returns numbers + verdict: consistent | mirrored | uncertain | cannot_tell."""
    f = normalise(first_mask); b = normalise(second_mask)
    as_drawn = best_iou(f, b); mirrored = best_iou(f, b[:, ::-1]); self_sym = best_iou(f, f[:, ::-1])
    asym = 1.0 - self_sym; margin = as_drawn - mirrored
    if asym < MIN_ASYMMETRY:
        verdict = 'cannot_tell'
    elif margin >= MIN_MARGIN and margin >= MIN_MARGIN_SHARE * asym:
        verdict = 'mirrored'
    elif margin <= -MIN_MARGIN:
        verdict = 'consistent'
    else:
        verdict = 'uncertain'
    return {'iou_as_drawn': round(as_drawn, 4), 'iou_flipped': round(mirrored, 4), 'first_view_asymmetry': round(asym, 4),
            'margin': round(margin, 4), 'verdict': verdict,
            'thresholds': {'min_asymmetry': MIN_ASYMMETRY, 'min_margin': MIN_MARGIN, 'min_margin_share_of_asymmetry': MIN_MARGIN_SHARE}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rgba(path):
    from PIL import Image
    with Image.open(path) as im:
        return np.array(im.convert('RGBA'))


def evidence_image(first, second, flipped, out):
    """front | back as drawn | back flipped, each on white, outlines of the front mask drawn on the others."""
    from PIL import Image
    tiles = []
    for rgba in (first, second, flipped):
        im = Image.fromarray(rgba, 'RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
        bg = bg.convert('RGB'); bg.thumbnail((360, 360)); tiles.append(bg)
    sheet = Image.new('RGB', (sum(t.width for t in tiles) + 20, max(t.height for t in tiles)), (255, 255, 255)); x = 0
    for t in tiles:
        sheet.paste(t, (x, 0)); x += t.width + 10
    sheet.save(out, format='PNG')


def run(folder, views, mode='auto_flip'):
    folder = Path(folder); mode = mode if mode in MODES else 'auto_flip'
    report_path = folder / 'view_consistency.json'
    previous = json.loads(report_path.read_text(encoding='utf-8')) if report_path.is_file() else {}
    report = {'version': VERSION, 'mode': mode, 'pairs': []}
    if mode == 'off':
        report['note'] = 'Mirror check switched off in autoroute_settings.json (mirror_check).'
        report_path.write_text(json.dumps(report, indent=1), encoding='utf-8'); return report
    for first, second in PAIRS:
        if first not in views or second not in views:
            continue
        p1 = folder / (first + '.png'); p2 = folder / (second + '.png'); kept = folder / (second + '.as_drawn.png')
        old = next((x for x in previous.get('pairs', []) if x.get('second') == second), None)
        # Idempotent: the prepared picture is already our flipped output -> judge the kept original again, do not re-flip.
        already = bool(old and old.get('action') == 'flipped' and kept.is_file() and sha(p2) == old.get('flipped_sha256'))
        source = kept if already else p2
        a = load_rgba(p1); b = load_rgba(source)
        entry = {'first': first, 'second': second, 'second_as_drawn_sha256': sha(source)}
        try:
            entry.update(compare(a[..., 3] >= 16, b[..., 3] >= 16))
        except ValueError as error:
            entry.update({'verdict': 'cannot_tell', 'error': str(error)})
        flipped = np.ascontiguousarray(b[:, ::-1])
        if entry['verdict'] == 'mirrored' and mode == 'auto_flip':
            from PIL import Image
            if not already:
                shutil.copy2(p2, kept)                                   # untouched picture kept beside it
                Image.fromarray(flipped, 'RGBA').save(p2, format='PNG')
            entry.update({'action': 'flipped', 'kept_original': kept.name, 'flipped_sha256': sha(p2),
                          'message': 'The %s picture looked MIRRORED compared with the %s (as drawn it matched %.2f, flipped %.2f). '
                                     'It was flipped left-right for 3D shape, geometry check and color; the original is kept as %s.'
                                     % (second, first, entry['iou_as_drawn'], entry['iou_flipped'], kept.name)})
        else:
            if already:                                                  # verdict changed (e.g. thresholds): restore original
                shutil.copy2(kept, p2)
            entry['action'] = 'none'
            entry['message'] = {
                'mirrored': 'The %s picture looks MIRRORED compared with the %s (as drawn %.2f vs flipped %.2f). Not changed (mirror_check = warn). One shape cannot match both pictures.',
                'consistent': 'The %s and %s pictures agree (flipped %.2f beats as drawn %.2f).',
                'uncertain': 'The %s and %s pictures could not be confirmed as consistent (as drawn %.2f, flipped %.2f). Check that the tail/limbs are on opposite sides in front and back.',
                'cannot_tell': 'The %s/%s mirror check is not decisive (subject nearly symmetric or empty view).'}[entry['verdict']]
            entry['message'] = entry['message'] % ((second, first, entry['iou_as_drawn'], entry['iou_flipped']) if entry['verdict'] == 'mirrored'
                                                   else (first, second, entry['iou_flipped'], entry['iou_as_drawn']) if entry['verdict'] == 'consistent'
                                                   else (first, second, entry.get('iou_as_drawn', 0), entry.get('iou_flipped', 0)) if entry['verdict'] == 'uncertain'
                                                   else (first, second))
        try:
            evidence_image(a, b, flipped, folder / ('view_consistency_%s_%s.png' % (first, second)))
        except Exception as error:                                       # evidence only; the decision is already made
            entry['evidence_error'] = str(error)
        report['pairs'].append(entry)
    report_path.write_text(json.dumps(report, indent=1), encoding='utf-8')
    return report


def summary(report):
    pairs = report.get('pairs') or []
    if report.get('mode') == 'off':
        return 'Mirror check off.'
    if not pairs:
        return 'Mirror check: no front/back or left/right pair to compare.'
    return ' '.join(p['message'] for p in pairs)


if __name__ == '__main__':
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    result = run(spec['folder'], spec['views'], spec.get('mode', 'auto_flip'))
    for p in result.get('pairs', []):
        print(p['first'], p['second'], p['verdict'], p.get('action'), p.get('iou_as_drawn'), p.get('iou_flipped'), flush=True)
    print('VIEW_CONSISTENCY_PASSED', flush=True)
