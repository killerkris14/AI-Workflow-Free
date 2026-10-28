# MASK_SHEET_CLEANUP_V1  (AI Modeling Studio color update 0.005)
"""Remove reference-sheet extras from a foreground mask: ground lines / scale-bar edges
at the subject's foot level, then small detached pieces (labels, ruler boxes, arrows)
that sit clearly away from the subject. Pure numpy (runs inside Blender, no SciPy).
Never applied when it would remove a large share of the mask."""
import numpy as np
from collections import deque

VERSION = '0.005'
MAX_REMOVED_FRACTION = 0.15


def components(mask):
    """8-connected labels (0 = background) and pixel counts per label."""
    h, w = mask.shape; lab = np.zeros((h, w), np.int32); sizes = [0]; n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        n += 1; lab[y0, x0] = n; q = deque([(y0, x0)]); c = 0
        while q:
            y, x = q.popleft(); c += 1
            for yy in (y - 1, y, y + 1):
                if 0 <= yy < h:
                    for xx in (x - 1, x, x + 1):
                        if 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n; q.append((yy, xx))
        sizes.append(c)
    return lab, np.array(sizes)


def _runs(mask, axis):
    """Length of the run each True pixel belongs to, along axis (0 = vertical, 1 = horizontal)."""
    m = mask if axis == 1 else mask.T
    out = np.zeros(m.shape, np.int32)
    for i, row in enumerate(m):
        if not row.any():
            continue
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        for s, e in zip(starts, ends):
            out[i, s:e] = e - s
    return out if axis == 1 else out.T


def _dilate(mask, steps):
    m = mask.copy()
    for _ in range(steps):
        g = m.copy()
        g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
        g[1:, 1:] |= m[:-1, :-1]; g[1:, :-1] |= m[:-1, 1:]; g[:-1, 1:] |= m[1:, :-1]; g[:-1, :-1] |= m[1:, 1:]
        m = g
    return m


def clean_mask(mask):
    """Returns (cleaned_mask, report). The input is not modified."""
    mask = np.asarray(mask, bool); h, w = mask.shape; total = int(mask.sum())
    thin = max(3, round(0.006 * h)); long_run = max(30, round(0.04 * w)); gap = max(6, round(0.008 * h))
    report = {'version': VERSION, 'applied': False, 'line_pixels_removed': 0, 'pieces_removed': [], 'removed_percent': 0.0,
              'parameters': {'line_max_thickness_px': thin, 'line_min_length_px': long_run, 'piece_gap_px': gap, 'piece_max_share_of_subject': 0.02}}
    if total == 0:
        return mask.copy(), report
    # 1) ground lines / ruler edges: long thin horizontal runs in the lowest quarter of the subject.
    #    The whole stretch of such a row is removed, including where the drawn line runs under the feet.
    vthick = _runs(mask, 0)
    candidate = mask & (vthick <= thin)
    seed = candidate & (_runs(candidate, 1) >= long_run)
    rows = np.where(mask.any(1))[0]; seed[:rows.min() + int(0.75 * (rows.max() - rows.min()))] = False
    line = np.zeros_like(mask)
    for y in np.where(seed.any(1))[0]:
        d = np.diff(np.concatenate([[0], mask[y].astype(np.int8), [0]]))
        for s0, e0 in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            if seed[y, s0:e0].any():
                line[y, s0:e0] = True
    cleaned = mask & ~line
    # 2) small pieces clearly away from the subject (labels, detached ruler boxes, arrows)
    lab2, sizes2 = components(cleaned); main2 = int(sizes2[1:].argmax()) + 1
    near = _dilate(lab2 == main2, gap); limit = 0.02 * sizes2[main2]
    for k in range(1, len(sizes2)):
        if k == main2 or sizes2[k] >= limit:
            continue
        piece = lab2 == k
        if (piece & near).any():
            continue                      # touching distance of the subject: keep (e.g. ornaments)
        ys, xs = np.nonzero(piece)
        report['pieces_removed'].append({'pixels': int(sizes2[k]), 'bbox_xyxy': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]})
        cleaned &= ~piece
    removed = total - int(cleaned.sum())
    report['line_pixels_removed'] = int(line.sum()); report['removed_percent'] = round(100 * removed / total, 3)
    if removed / total > MAX_REMOVED_FRACTION:
        report['skipped_reason'] = 'would remove %.1f%% of the mask (limit %d%%); kept the original mask' % (100 * removed / total, 100 * MAX_REMOVED_FRACTION)
        report['pieces_removed'] = []; report['line_pixels_removed'] = 0; report['removed_percent'] = 0.0
        return mask.copy(), report
    report['applied'] = removed > 0
    return cleaned, report
