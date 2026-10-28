# ALIGNMENT_EVIDENCE_V1  (AI Modeling Studio color update 0.004)
"""Reference-versus-mesh fit evidence for the color preview stage.

The mesh silhouette is rasterized with the SAME 2D projection that color transfer uses,
so the overlay shows exactly where reference pixels land on the model. Pure numpy.
Image arrays are float RGBA in [0,1] with row 0 at the TOP of the image.
"""
import numpy as np

VERSION = '0.004'
BOTH = np.array([0.10, 0.70, 0.25])        # reference and mesh agree
REF_ONLY = np.array([0.90, 0.15, 0.15])    # reference has subject, mesh missing
MESH_ONLY = np.array([0.20, 0.35, 0.95])   # mesh where the reference has background
LEGEND = 'green = reference and mesh agree; red = reference only (mesh missing); blue = mesh only (no reference)'


def triangle_areas(points, triangles):
    p = np.asarray(points, float)[np.asarray(triangles, int)]
    return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)


def rasterize(xy, triangles, w, h, chunk=20000, small=8):
    """Silhouette of 2D triangles (pixel coords: x right, y down; pixel (i,j) centre at j+.5,i+.5).
    Every triangle also marks the pixel holding its centroid so sub-pixel triangles are not lost."""
    xy = np.asarray(xy, float); tri = np.asarray(triangles, np.int64)
    mask = np.zeros((h, w), bool)
    if not len(tri):
        return mask
    P = xy[tri]                                                     # (T,3,2)
    c = P.mean(1); ci = np.floor(c).astype(np.int64)
    ok = (ci[:, 0] >= 0) & (ci[:, 0] < w) & (ci[:, 1] >= 0) & (ci[:, 1] < h)
    mask[ci[ok, 1], ci[ok, 0]] = True
    lo = np.floor(P.min(1) - 0.5).astype(np.int64) + 1             # first pixel whose centre can be inside
    hi = np.floor(P.max(1) - 0.5).astype(np.int64)
    lo = np.maximum(lo, 0); hi = np.minimum(hi, [w - 1, h - 1])
    span = hi - lo + 1
    live = (span[:, 0] > 0) & (span[:, 1] > 0)
    def fill(idx, k):
        oy, ox = np.mgrid[0:k, 0:k]; off = np.stack([ox.ravel(), oy.ravel()], 1)       # (k*k,2)
        for s in range(0, len(idx), chunk):
            ids = idx[s:s + chunk]; q = P[ids]
            pix = lo[ids][:, None, :] + off[None]                                       # (n,k*k,2)
            pc = pix + 0.5
            a, b, cc = q[:, 0][:, None], q[:, 1][:, None], q[:, 2][:, None]
            def edge(p0, p1):
                return (p1[..., 0] - p0[..., 0]) * (pc[..., 1] - p0[..., 1]) - (p1[..., 1] - p0[..., 1]) * (pc[..., 0] - p0[..., 0])
            e0, e1, e2 = edge(a, b), edge(b, cc), edge(cc, a)
            inside = ((e0 >= 0) & (e1 >= 0) & (e2 >= 0)) | ((e0 <= 0) & (e1 <= 0) & (e2 <= 0))
            inside &= (pix[..., 0] <= hi[ids][:, None, 0]) & (pix[..., 1] <= hi[ids][:, None, 1])
            mask[pix[..., 1][inside], pix[..., 0][inside]] = True
    small_ids = np.where(live & (span.max(1) <= small))[0]
    fill(small_ids, small)
    for i in np.where(live & (span.max(1) > small))[0]:                                 # few large triangles
        fill(np.array([i]), int(span[i].max()))
    return mask


def fit_metrics(reference, mesh):
    ref = np.asarray(reference, bool); m = np.asarray(mesh, bool)
    both = int((ref & m).sum()); r = int(ref.sum()); n = int(m.sum()); union = int((ref | m).sum())
    out = {'iou': round(both / union, 4) if union else 0.0,
           'reference_covered_percent': round(100 * both / r, 2) if r else 0.0,
           'mesh_outside_reference_percent': round(100 * (n - both) / n, 2) if n else 0.0,
           'reference_pixels': r, 'mesh_pixels': n}
    if r and n:
        ry, rx = np.where(ref); my, mx = np.where(m)
        rw, rh = np.ptp(rx) + 1, np.ptp(ry) + 1
        out['width_ratio_mesh_to_reference'] = round(float((np.ptp(mx) + 1) / rw), 3)
        out['height_ratio_mesh_to_reference'] = round(float((np.ptp(my) + 1) / rh), 3)
        out['centre_offset_x_percent_of_width'] = round(float(100 * (mx.mean() - rx.mean()) / rw), 2)
        out['centre_offset_y_percent_of_height'] = round(float(100 * (my.mean() - ry.mean()) / rh), 2)
    return out


def overlay(reference_rgba, reference_mask, mesh_mask, margin=0.06):
    """Colour-coded fit image cropped to the union of both silhouettes. Returns (rgba, [x0,y0,x1,y1])."""
    img = np.asarray(reference_rgba, np.float32); ref = np.asarray(reference_mask, bool); m = np.asarray(mesh_mask, bool)
    if img.shape[:2] != ref.shape or ref.shape != m.shape:
        raise ValueError('Reference, mask and silhouette sizes differ')
    gray = img[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    base = np.where(ref, 0.25 + 0.5 * gray, 0.93)[..., None].repeat(3, 2)
    out = base.copy()
    for sel, colour in ((ref & m, BOTH), (ref & ~m, REF_ONLY), (~ref & m, MESH_ONLY)):
        out[sel] = 0.45 * base[sel] + 0.55 * colour
    rgba = np.concatenate([out, np.ones(ref.shape + (1,), np.float32)], 2)
    ys, xs = np.where(ref | m)
    if not len(ys):
        return rgba, [0, 0, ref.shape[1], ref.shape[0]]
    pad = int(margin * max(np.ptp(xs), np.ptp(ys))) + 2
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + pad + 1, ref.shape[1]), min(int(ys.max()) + pad + 1, ref.shape[0])
    return rgba[y0:y1, x0:x1].copy(), [x0, y0, x1, y1]


def coverage(area, material_index, view_slots):
    area = np.asarray(area, float); mat = np.asarray(material_index, int); total = max(float(area.sum()), 1e-12)
    n = len(view_slots); coloured = mat < n
    return {'coloured_area_percent': round(100 * float(area[coloured].sum()) / total, 2),
            'unobserved_area_percent': round(100 * float(area[~coloured].sum()) / total, 2),
            'per_view_area_percent': {s: round(100 * float(area[mat == i].sum()) / total, 2) for i, s in enumerate(view_slots)}}
