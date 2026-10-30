"""AUTO_VIEW_DETECTION_V1 (AI Modeling Studio 0.006) + WHITE_TIP_CROP_FIX_V1 (0.016): find the separate figures on a reference sheet and name each
view from its shape. Runs in ComfyUI's Python (numpy + PIL). No AI: background = light, colourless pixels connected to
the image border (works for white sheets and for checkerboard 'transparency' painted into the picture).

Usage: python figure_detection.py spec.json   spec = {"source": image, "out_dir": folder}
Writes out_dir/figures.json and out_dir/figure-<i>.png crops (for the per-crop front/back question)."""
import json, sys
from collections import deque
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

VERSION = '0.016'
WORK_SIDE = 640                 # detection resolution (longest side)
MIN_FIGURE_SHARE = 0.012        # figures smaller than this share of the sheet are labels/arrows/rulers
MAX_FIGURES = 5
SMALL_PIECE_SHARE = 0.0015       # letters / arrows / ruler ticks are smaller than this share of the sheet


def background_rule(rgb):
    """WHITE_TIP_CROP_FIX_V1 (0.016): white parts of the creature that touch the background (white tail tips, hat
    pompoms) were flood-filled as background by the old rule (min channel >= 200), so the crop cut them off. A plain
    sheet background is near pure white, so the threshold now follows the measured border brightness (at most 246).
    Checkerboard 'transparency' borders (two light greys) keep the old rule."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    lo = border.min(1); spread = border.max(1) - lo
    neutral = lo[(lo >= 200) & (spread <= 28)]
    if len(neutral) < 0.5 * len(lo):
        return 200, 28, 'old rule (border not light/neutral)'
    med = float(np.median(neutral))
    if np.mean((neutral < med - 8)) > 0.15:
        return 200, 28, 'old rule (checkerboard-like border)'
    thr = int(max(200, min(246, med - 8)))
    return thr, 10, 'near-white border %.0f -> threshold %d' % (med, thr)


BACKGROUND_RULE = {}


def background(rgb):
    """Light, colourless pixels connected to the border (4-connected flood fill)."""
    thr, spr, why = background_rule(rgb); BACKGROUND_RULE.update(threshold=thr, spread=spr, reason=why)
    lo = rgb.min(2); spread = rgb.max(2) - lo
    light = (lo >= thr) & (spread <= spr)
    h, w = light.shape; bg = np.zeros((h, w), bool); q = deque()
    def seed(y, x):
        if light[y, x] and not bg[y, x]:
            bg[y, x] = True; q.append((y, x))
    for x in range(w):
        seed(0, x); seed(h - 1, x)
    for y in range(h):
        seed(y, 0); seed(y, w - 1)
    while q:
        y, x = q.popleft()
        if y > 0: seed(y - 1, x)
        if y < h - 1: seed(y + 1, x)
        if x > 0: seed(y, x - 1)
        if x < w - 1: seed(y, x + 1)
    return bg


def dilate(m, steps):
    for _ in range(steps):
        g = m.copy(); g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]; m = g
    return m


def components(mask):
    h, w = mask.shape; lab = np.zeros((h, w), np.int32); n = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        n += 1; lab[y0, x0] = n; q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; q.append((yy, xx))
    return lab, n


def symmetry(m):
    """IoU of a tight silhouette with its left-right and top-bottom mirror images."""
    lr = (m & m[:, ::-1]).sum() / max((m | m[:, ::-1]).sum(), 1)
    tb = (m & m[::-1, :]).sum() / max((m | m[::-1, :]).sum(), 1)
    return float(lr), float(tb)


def thin_line_rows(fg, w):
    """Rows that are mostly a long thin horizontal stroke (ground lines / rulers) - they glue figures together."""
    out = np.zeros_like(fg)
    vert = np.zeros(fg.shape, np.int32)
    for x in range(fg.shape[1]):
        col = fg[:, x]; d = np.diff(np.concatenate([[0], col.astype(np.int8), [0]]))
        for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            vert[s:e, x] = e - s
    thin = fg & (vert <= max(2, round(0.004 * fg.shape[0])))
    for y in range(fg.shape[0]):
        row = thin[y]; d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            if e - s >= 0.08 * w:
                out[y, s:e] = True
    return out


def detect(path):
    with Image.open(path) as raw:
        full = ImageOps.exif_transpose(raw).convert('RGB')
    W, H = full.size; scale = WORK_SIDE / max(W, H)
    small = full.resize((max(1, round(W * scale)), max(1, round(H * scale))), Image.BILINEAR) if scale < 1 else full
    rgb = np.asarray(small).astype(np.int16); h, w = rgb.shape[:2]
    fg = ~background(rgb)
    fg &= ~thin_line_rows(fg, w)                                  # ground lines/rulers must not join figures
    # Labels (letters), arrows and ruler ticks are small separate pieces: drop them BEFORE growing figures,
    # otherwise a caption between two views bridges them into one figure.
    pieces, count = components(fg)
    if count:
        sizes = np.bincount(pieces.ravel())
        fg &= sizes[pieces] >= max(12, round(SMALL_PIECE_SHARE * h * w))
    # Group with a 1-pixel bridge only: neighbouring views on a sheet can nearly touch, so growing figures would merge them.
    lab, n = components(dilate(fg, 1))
    sizes = np.bincount((lab * fg).ravel(), minlength=n + 1); sizes[0] = 0
    big = [k for k in range(1, n + 1) if sizes[k] >= MIN_FIGURE_SHARE * h * w]
    regions = {k: (lab == k) & fg for k in big}
    # Medium pieces (detached horn tips, ornaments) join the nearest figure only when they are very close to it.
    reach = max(2, round(0.02 * max(h, w))); near = {k: dilate(regions[k], reach) for k in big}
    for k in range(1, n + 1):
        if k in regions or not sizes[k]:
            continue
        piece = (lab == k) & fg
        hits = [b for b in big if (piece & near[b]).any()]
        if len(hits) == 1:
            regions[hits[0]] |= piece
    figures = []
    for k, region in regions.items():
        share = region.sum() / (h * w)
        ys, xs = np.nonzero(region); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        tight = region[y0:y1, x0:x1]; lr, tb = symmetry(tight)
        figures.append({'bbox_px': [int(x0), int(y0), int(x1), int(y1)], 'share': round(float(share), 4), 'aspect': round((x1 - x0) / (y1 - y0), 3),
                        'symmetry_left_right': round(lr, 3), 'symmetry_top_bottom': round(tb, 3), 'centre_x': float((x0 + x1) / 2 / w), 'centre_y': float((y0 + y1) / 2 / h)})
    figures.sort(key=lambda f: -f['share']); figures = figures[:MAX_FIGURES]
    classify(figures)
    pad = 0.015
    for f in figures:
        x0, y0, x1, y1 = f.pop('bbox_px')
        f['bbox'] = [max(0.0, x0 / w - pad), max(0.0, y0 / h - pad), min(1.0, x1 / w + pad), min(1.0, y1 / h + pad)]
    return full, figures


def classify(figures):
    """Shape rules: front/back silhouettes mirror left-right; a top view (body horizontal) mirrors top-bottom;
    side views mirror neither. Front vs back is NOT decidable from a silhouette: marked for the per-crop question,
    with the sheet convention (front placed left of back) as fallback."""
    for f in figures:
        lr, tb = f['symmetry_left_right'], f['symmetry_top_bottom']
        if tb >= 0.70 and tb > lr + 0.10 and f['aspect'] >= 1.4:
            f['kind'] = 'top'                                    # spread wings mirror across the spine
        elif lr >= 0.75 or (lr >= 0.55 and f['aspect'] <= 1.35):
            f['kind'] = 'front_or_back'                          # mirror left-right; tails can lower it, but these views are not wide
        else:
            f['kind'] = 'side'
    tops = [f for f in figures if f['kind'] == 'top']
    for f in sorted(tops, key=lambda f: -f['symmetry_top_bottom'])[1:]:
        f['kind'] = 'side'                                       # only one top view
    fb = sorted([f for f in figures if f['kind'] == 'front_or_back'], key=lambda f: f['centre_x'])
    for i, f in enumerate(fb):
        f['view'] = ['front', 'back'][i] if i < 2 else 'side_extra'; f['front_back_source'] = 'sheet convention (front left of back)'
    sides = sorted([f for f in figures if f['kind'] == 'side'], key=lambda f: f['centre_x'])
    for i, f in enumerate(sides):
        f['view'] = ['left', 'right'][i] if i < 2 else 'side_extra'
    for f in tops:
        if f['kind'] == 'top':
            f['view'] = 'top'
    for f in figures:
        f.setdefault('view', 'side_extra')


if __name__ == '__main__':
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    out = Path(spec['out_dir']); out.mkdir(parents=True, exist_ok=True)
    full, figures = detect(spec['source'])
    W, H = full.size
    for i, f in enumerate(figures):
        x0, y0, x1, y1 = f['bbox']; crop = full.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
        crop.thumbnail((768, 768)); f['crop'] = 'figure-%d.png' % i; crop.save(out / f['crop'])
    (out / 'figures.json').write_text(json.dumps({'version': VERSION, 'image_size': [W, H], 'background_rule': BACKGROUND_RULE, 'figures': figures}, indent=1), encoding='utf-8')
    print('FIGURE_DETECTION_PASSED', json.dumps([(f['view'], [round(v, 3) for v in f['bbox']]) for f in figures]), flush=True)
