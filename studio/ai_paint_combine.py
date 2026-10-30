# MULTI_PICTURE_AI_PAINT_V1 (AI Modeling Studio 0.017) - step "combine pictures" (texture_paint Python: numpy + PIL; read-only inputs)
# args: <front work dir> <side work dir> <side prep dir> <out dir> <front turned 0|1> [<other-side work dir> <other-side prep dir>]
# Every triangle gets the colour of the AI paint run whose camera really sees it, weighted by how directly it faces that camera
# (visible x cos^2 - the setting the user picked from the mammoth tests; sharper blends measured worse).
#   symmetric shape (shape check passed and, if the job has a picture of the other side, the picture check passed):
#       front run + side run + the side run MIRRORED onto the other side  (user's option C)
#   otherwise: needs an AI paint run of the other side -> exit 10 without output; run again with that run's folders (option D)
# Unseen triangles (top, belly, hidden parts) keep the front run's colours. Writes <out>/tri_rgb.npy + <out>/combine.json.
import sys, json, time, traceback
from pathlib import Path
import numpy as np
fw, sw, sp, out = [Path(x) for x in sys.argv[1:5]]
front_turned = sys.argv[5] == '1'
ow, op = (Path(sys.argv[6]), Path(sys.argv[7])) if len(sys.argv) > 7 else (None, None)
out.mkdir(parents=True, exist_ok=True)
res = {'ok': False, 'version': 'MULTI_PICTURE_AI_PAINT_V1'}
SHAPE_PASS = 90.0      # % of the other side's visible surface that has a mirror partner on the pictured side
PICTURE_PASS = 0.80    # outline overlap (IoU) of the side picture and the MIRRORED opposite picture
COLOUR_PASS = 12.0     # mean colour difference (deltaE) between those two pictures inside the overlap
MATCH_MM, NORMAL_MIN = 1.5, 0.7
def prog(p, t): print('PROGRESS %d %s' % (p, t), flush=True)
def lab(c):
    c = np.clip(np.asarray(c, float), 0, 1); l = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]); xyz = l @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)
def de(a, b): return np.linalg.norm(lab(a) - lab(b), axis=-1)
class Grid:   # nearest neighbour inside a radius, numpy only (no scipy needed)
    def __init__(self, P, cell):
        self.P, self.cell = P, cell; k = np.floor(P / cell).astype(np.int64); self.lo = k.min(0) - 2; k -= self.lo
        self.dim = k.max(0) + 3; key = (k[:, 0] * self.dim[1] + k[:, 1]) * self.dim[2] + k[:, 2]
        self.order = np.argsort(key, kind='stable'); self.sk = key[self.order]
    def query(self, Q):
        k = np.floor(Q / self.cell).astype(np.int64) - self.lo; best = np.full(len(Q), np.inf); idx = np.full(len(Q), -1)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    kk = k + (dx, dy, dz); good = np.all((kk >= 0) & (kk < self.dim), 1)
                    key = (kk[:, 0] * self.dim[1] + kk[:, 1]) * self.dim[2] + kk[:, 2]
                    a = np.searchsorted(self.sk, key, 'left'); b = np.searchsorted(self.sk, key, 'right'); b[~good] = a[~good]
                    for step in range(int((b - a).max(initial=0))):
                        q = np.nonzero(a + step < b)[0]; j = self.order[a[q] + step]; d = np.linalg.norm(self.P[j] - Q[q], axis=1)
                        w = d < best[q]; best[q[w]] = d[w]; idx[q[w]] = j[w]
        return idx, best
def visible(C, N, d, cell=0.4, tol=1.0):
    """orthographic visibility from direction d (toward the camera): a triangle is seen if nothing lies in front of it."""
    d = d / np.linalg.norm(d); a = np.cross(d, [0, 0, 1.0])
    if np.linalg.norm(a) < 1e-6: a = np.cross(d, [1.0, 0, 0])
    a /= np.linalg.norm(a); b = np.cross(d, a)
    x = np.floor(C @ a / cell).astype(np.int64); y = np.floor(C @ b / cell).astype(np.int64); z = C @ d
    x -= x.min() - 1; y -= y.min() - 1; W, H = x.max() + 2, y.max() + 2
    zb = np.full((H, W), -np.inf); np.maximum.at(zb, (y, x), z)
    zm = zb.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1): zm = np.maximum(zm, np.roll(np.roll(zb, dy, 0), dx, 1))
    facing = N @ d
    return (z >= zm[y, x] - tol) & (facing > 0.05), np.clip(facing, 0, 1)
def blend(base, views):
    """views: list of (colour, weight). Weighted mean where any view saw the triangle, else the front run's colour."""
    num = np.zeros_like(base); den = np.zeros(len(base))
    for c, w in views: num += c * w[:, None]; den += w
    outc = base.copy(); s = den > 1e-6; outc[s] = num[s] / den[s, None]; return outc, s
def picture_check(prep_dir, side_slot, opp_slot):
    from PIL import Image
    def crop(slot, mirror):
        im = np.asarray(Image.open(prep_dir / ('ref_' + slot + '.png')).convert('RGBA'), float) / 255
        if mirror: im = im[:, ::-1]
        m = im[..., 3] > 0.5; ys, xs = np.nonzero(m); im = im[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        return np.asarray(Image.fromarray((im * 255).astype(np.uint8)).resize((160, 160), Image.BILINEAR), float) / 255
    a, b = crop(side_slot, False), crop(opp_slot, True); ma, mb = a[..., 3] > 0.5, b[..., 3] > 0.5
    iou = float((ma & mb).sum() / max((ma | mb).sum(), 1)); both = ma & mb
    col = float(de(a[..., :3][both], b[..., :3][both]).mean()) if both.any() else 99.0
    return {'outline_overlap_iou': round(iou, 3), 'colour_difference_deltaE': round(col, 2), 'passed': bool(iou >= PICTURE_PASS and col <= COLOUR_PASS)}
try:
    t0 = time.time(); prog(2, 'loading the mesh and the AI paint colours')
    fp = fw / 'prep'; m = np.load(fp / 'mesh.npz'); V, T = m['V'], m['T']
    ms = np.load(sp / 'mesh.npz')
    if not np.array_equal(ms['T'], T) or not np.allclose(ms['V'], V): raise RuntimeError('the side preparation has a different mesh / triangle order than the front run')
    cF = np.load(fw / 'tri_rgb_front.npy').astype(float); cS = np.load(sw / 'tri_rgb.npy').astype(float)
    if len(cF) != len(T) or len(cS) != len(T): raise RuntimeError('colour count does not match the triangle count')
    pf = json.loads((fp / 'prep.json').read_text(encoding='utf-8')); ps = json.loads((sp / 'prep.json').read_text(encoding='utf-8'))
    s_turn = bool(json.loads((sw / 'paint.json').read_text(encoding='utf-8')).get('turned_180'))
    dF = np.array(pf['toward']) * (-1 if front_turned else 1); dS = np.array(ps['toward']) * (-1 if s_turn else 1)
    P = V[T]; C = P.mean(1); N = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); area = np.linalg.norm(N, axis=1) / 2; N /= (2 * area[:, None] + 1e-12)
    tot = area.sum(); pct = lambda sel: round(float(area[sel].sum() / tot * 100), 2)
    prog(10, 'which parts each picture really sees (front)'); vF, fF = visible(C, N, dF)
    prog(20, 'which parts each picture really sees (side)'); vS, fS = visible(C, N, dS)
    prog(25, 'shape check: finding the mirror plane')
    # the model's left-right axis = the front picture's "right" direction (as in the colour stage's symmetry fill),
    # refined by a small search (+-2 degrees about up, +-3 mm offset) for the plane with the closest mirror partners
    r0 = np.array(pf['right'], float); r0 /= np.linalg.norm(r0)
    upv = np.array(pf['up'], float); upv /= np.linalg.norm(upv); grid = Grid(C, MATCH_MM)
    sub = np.arange(0, len(C), max(1, len(C) // 8000)); best = None
    def rot(v, deg):
        x = np.radians(deg); return v * np.cos(x) + np.cross(upv, v) * np.sin(x) + upv * np.dot(upv, v) * (1 - np.cos(x))
    def score(l, md, off):
        al = C[sub] @ l; Q = C[sub] - 2 * ((al - (md + off))[:, None]) * l; _, dist = grid.query(Q)
        return -float(np.mean(np.minimum(dist, MATCH_MM)))
    for ang in (-2, -1, 0, 1, 2):
        l = rot(r0, ang); full = C @ l; md = (full.min() + full.max()) / 2
        for off in np.arange(-3.0, 3.01, 0.5):
            sc = score(l, md, off)
            if best is None or sc > best[1] + 1e-9: best = (md + off, sc, ang, l, md)
    for off in np.arange(-0.4, 0.41, 0.1):
        sc = score(best[3], best[0], off)
        if sc > best[1] + 1e-9: best = (best[0] + off, sc, best[2], best[3], best[4])
    lat = best[3]; along = C @ lat; mid = (along.min() + along.max()) / 2
    dO = dS - 2 * np.dot(dS, lat) * lat     # mirror image of the side camera = the camera that sees the other side
    prog(35, 'which parts each picture really sees (other side)'); vO, fO = visible(C, N, dO)
    wF, wS, wO = vF * fF ** 2, vS * fS ** 2, vO * fO ** 2
    res['seen_percent'] = {'front_picture': pct(vF), 'side_picture': pct(vS), 'other_side': pct(vO), 'none': pct(~(vF | vS | vO))}
    res['cameras'] = {'front_toward': dF.round(4).tolist(), 'front_turned_180': front_turned, 'side_toward': dS.round(4).tolist(), 'side_turned_180': s_turn,
                      'side_slot': ps['slot'], 'side_direction': ps['approved_direction'], 'mirror_toward': dO.round(4).tolist()}
    prog(45, 'shape check: mirror partners')
    Q = C - 2 * ((along - best[0])[:, None]) * lat; NQ = N - 2 * (N @ lat)[:, None] * lat; idx, dist = grid.query(Q)
    ok = (idx >= 0) & (dist < MATCH_MM); ok[ok] &= np.einsum('ij,ij->i', NQ[ok], N[idx[ok]]) > NORMAL_MIN
    other = vO & (wO > 0)
    shape_pct = float(area[other & ok].sum() / max(area[other].sum(), 1e-9) * 100)
    res['shape_check'] = {'other_side_with_mirror_partner_percent': round(shape_pct, 1), 'pass_mark_percent': SHAPE_PASS, 'passed': bool(shape_pct >= SHAPE_PASS),
                          'mirror_plane_offset_from_box_middle_mm': round(best[0] - mid, 2), 'mirror_axis_turned_deg': best[2], 'match_distance_mm': MATCH_MM}
    opp_slot = None
    for k, v in ps['all_slots'].items():
        if k != ps['slot'] and np.dot(np.array(v['toward']), np.array(ps['all_slots'][ps['slot']]['toward'])) < -0.8: opp_slot = k
    if opp_slot and (fp / ('ref_' + opp_slot + '.png')).is_file() and (fp / ('ref_' + ps['slot'] + '.png')).is_file():
        res['picture_check'] = dict(picture_check(fp, ps['slot'], opp_slot), other_side_slot=opp_slot, pass_marks={'iou': PICTURE_PASS, 'deltaE': COLOUR_PASS})
    else:
        res['picture_check'] = {'available': False, 'passed': None, 'reason': 'no approved picture of the other side - only the shape is checked'}
    pc = res['picture_check'].get('passed')
    mirror_ok = res['shape_check']['passed'] and pc is not False
    res['other_side_slot'] = opp_slot
    res['reason'] = 'shape %.1f %% (pass %s %%), picture check %s' % (shape_pct, SHAPE_PASS, 'not available' if pc is None else ('passed' if pc else 'FAILED'))
    if mirror_ok:
        prog(60, 'combining: front + side + side mirrored onto the other side')
        cM = np.zeros_like(cF); wM = np.zeros(len(T)); j = idx.clip(0)
        use = ok & (wS[j] > 0); cM[use] = cS[j[use]]; wM[use] = wS[j[use]]
        final, seen = blend(cF, [(cF, wF), (cS, wS), (cM, wM)])
        res['method'] = 'mirror'; res['other_side_mirrored_percent'] = round(float(area[other & use].sum() / max(area[other].sum(), 1e-9) * 100), 1)
    elif ow is None:
        res['method'] = 'needs_other_run'; res['ok'] = True
        (out / 'combine.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
        print('COMBINE_NEEDS_OTHER_RUN', json.dumps({'reason': res['reason'], 'other_side_slot': opp_slot}), flush=True); sys.exit(10)
    else:
        cO = np.load(ow / 'tri_rgb.npy').astype(float); po = json.loads((op / 'prep.json').read_text(encoding='utf-8'))
        if len(cO) != len(T): raise RuntimeError('other-side colour count does not match the triangle count')
        o_turn = bool(json.loads((ow / 'paint.json').read_text(encoding='utf-8')).get('turned_180'))
        dO2 = np.array(po['toward']) * (-1 if o_turn else 1)
        if np.dot(dO2, dO) / np.linalg.norm(dO2) < 0.5: raise RuntimeError('the other-side run does not look at the other side (check its preparation)')
        prog(60, 'combining: front + side + other-side run'); vO2, fO2 = visible(C, N, dO2)
        final, seen = blend(cF, [(cF, wF), (cS, wS), (cO, vO2 * fO2 ** 2)])
        res['method'] = 'other_side_run'; res['other_side_run'] = {'slot': po['slot'], 'kind': 'approved picture' if po['mode'] == 'same' else 'side picture mirrored (no picture of that side)', 'turned_180': o_turn}
    res['changed_percent_vs_front_only'] = pct(np.abs(final - cF).sum(1) > 0.03)
    prog(85, 'comparing with your approved pictures')
    R = np.load(sp / 'ref_colours.npz'); rr, rok, rs, names = R['rgb'].astype(float), R['ok'], R['slot'], [str(x) for x in R['slots']]
    res['match_to_your_pictures_deltaE'] = {}
    for k, c in (('front_only', cF), ('combined', final)):
        row = {}
        for si, nm in enumerate(names):
            sel = rok & (rs == si)
            if sel.sum() > 100: row[nm] = round(float((de(c[sel], rr[sel]) * area[sel]).sum() / area[sel].sum()), 2)
        res['match_to_your_pictures_deltaE'][k] = row
    if not np.isfinite(final).all(): raise RuntimeError('combined colours contain invalid values')
    np.save(out / 'tri_rgb.npy', final.astype(np.float32))
    res['ok'] = True; res['seconds'] = round(time.time() - t0, 1)
    (out / 'combine.json').write_text(json.dumps(res, indent=1), encoding='utf-8'); prog(100, 'combined')
    print('COMBINE_PASSED', json.dumps({'method': res['method'], 'shape': res['shape_check']['other_side_with_mirror_partner_percent']}), flush=True)
except SystemExit:
    raise
except Exception:
    res['error'] = traceback.format_exc(); (out / 'combine.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8'); traceback.print_exc(); sys.exit(1)
