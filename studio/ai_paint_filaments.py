# AI_PAINT_STAGE_V1 (studio 0.010 build 2026-10-28-5) + ACCENT_TO_OUTLINE_V1 (0.016 build 2026-10-29-2) - step "filaments": AI-painted triangle colours -> ONE Bambu 3MF.
# Runs in the texture_paint Python. Uses the studio's own exporter (bambu_color_export.py) and the user's Bambu templates (read-only).
# args: <studio folder> <prep dir> <work dir> <filament count 4-9> <colours: studio|drawing|auto>
import sys, json, traceback
from pathlib import Path
studio, prep, out = [Path(a) for a in sys.argv[1:4]]
COUNT = int(sys.argv[4]); COLOURS = sys.argv[5]
# PROPS_TOGGLE_V1 (0.017): job uploaded with "Has props included" -> small prop colours (charms, bows) are NOT moved to the
# outline colour by ACCENT_TO_OUTLINE_V1; they compete for a filament like any other drawing colour.
import os
PROPS = os.environ.get('AIPAINT_PROPS') == '1'
# ACCENT_TO_OUTLINE_V1 (0.016 build 2026-10-29-2): with 4 or fewer filaments a tiny accent colour (e.g. blue eyes, <1 % of the
# surface) would take a whole filament. It is dropped from the palette, its areas print in the outline colour (the darkest,
# black-like filament) and the freed filament goes to the next most used drawing colour. 5+ filaments keep accents.
ACCENT_MAX_FILAMENTS = 4
ACCENT_MIN_SHARE = 0.01
TEMPLATES = {4: 'bambu_template_default.3mf', 5: 'bambu_template.3mf', 6: 'bambu_template_6.3mf', 7: 'bambu_template_7.3mf', 8: 'bambu_template_8.3mf', 9: 'bambu_template_9.3mf'}
# NOZZLE_OPTION_V1 (0.018): upload toggle 0.4 / 0.6 mm (both H2C nozzles). 0.4 -> the *_04 templates (H2C 0.4 nozzle, 0.20mm High Quality,
# Generic PLA 0.4 nozzle) and finer colour detail: speck merge 0.5 -> 0.25 mm2, thin/tiny dark areas -> outline below 1.0 mm wide / 5 mm2
# (0.6: 1.5 mm / 10 mm2). Unset or 0.6 = exactly the 0.017 behaviour.
NOZZLE = '0.4' if os.environ.get('AIPAINT_NOZZLE') == '0.4' else '0.6'
if NOZZLE == '0.4': TEMPLATES = {k: v[:-4] + '_04.3mf' for k, v in TEMPLATES.items()}
DETAIL = {'0.6': {'speck_mm2': 0.5, 'line_width_mm': 1.5, 'line_area_mm2': 10.0}, '0.4': {'speck_mm2': 0.25, 'line_width_mm': 1.0, 'line_area_mm2': 5.0}}[NOZZLE]
def prog(p, t): print('PROGRESS %d %s' % (p, t), flush=True)
res = {'ok': False, 'files': [], 'nozzle_mm': float(NOZZLE), 'detail': DETAIL}   # NOZZLE_OPTION_V1
try:
    import numpy as np
    sys.path.insert(0, str(studio)); import bambu_color_export as B
    res['exporter_version'] = getattr(B, 'VERSION', '?')
    d = np.load(prep / 'mesh.npz'); V, T = d['V'], d['T']; rgb = np.load(out / 'tri_rgb.npy').astype(np.float64)
    if len(rgb) != len(T): raise RuntimeError('colour count does not match triangle count')
    area = B.triangle_areas(V, T); obs = np.ones(len(T), bool)
    # ---- DRAWING_PALETTE_V1 (user's choice "D2"): filament colours come from the user's own approved pictures ----
    from PIL import Image
    def erode(m, n):
        o = m.copy()
        for a in range(1, n + 1): o &= np.roll(m, a, 0) & np.roll(m, -a, 0) & np.roll(m, a, 1) & np.roll(m, -a, 1)
        return o
    lines, flats = [], []
    for f in sorted(prep.glob('ref_*.png')):
        im = np.asarray(Image.open(f).convert('RGBA'), float) / 255; m = im[..., 3] > 0.5
        lab = B.srgb_to_lab(im[..., :3].reshape(-1, 3)).reshape(im.shape[0], im.shape[1], 3)
        ln = (lab[..., 0] < 32) & (np.hypot(lab[..., 1], lab[..., 2]) < 25) & m
        near = ln.copy()
        for a in (-2, -1, 1, 2): near |= np.roll(ln, a, 0) | np.roll(ln, a, 1)
        lines.append(lab[ln]); flats.append(lab[m & ~near & erode(m, 3)])
    if not lines or not sum(len(x) for x in flats): raise RuntimeError('no approved reference pictures found in the prepare folder')
    LINE_LAB = np.median(np.vstack(lines), 0); FL = np.vstack(flats)[::7]
    # STYLE_SWITCH_V1: drawing colours + black outlines (D2) only suit FLAT cartoon drawings. Shaded/detailed drawings have
    # many dark pixels and no few dominant colours -> use the automatic colours. Measured: cartoon dragon 12.7% dark / 68.5%
    # in its 12 most common colour bins; detailed dragon 44.7% / 22.0%.
    tot = dark = top = 0
    for f in sorted(prep.glob('ref_*.png')):
        im = np.asarray(Image.open(f).convert('RGBA'), float) / 255; m = im[..., 3] > 0.5
        lab = B.srgb_to_lab(im[..., :3][m]); tot += len(lab)
        dark += int(((lab[:, 0] < 32) & (np.hypot(lab[:, 1], lab[:, 2]) < 25)).sum())
        _, cnt = np.unique(np.round(lab / 6).astype(int), axis=0, return_counts=True); top += int(np.sort(cnt)[::-1][:12].sum())
    dark_pct, top_pct = 100.0 * dark / max(tot, 1), 100.0 * top / max(tot, 1)
    flat = dark_pct < 25 and top_pct >= 50
    res['style'] = {'dark_pixels_percent': round(dark_pct, 1), 'top12_colours_percent': round(top_pct, 1), 'flat_cartoon': flat,
                    'recommended': 'drawing' if flat else 'auto',
                    'reason': ('flat cartoon drawing -> filament colours from the drawing + black outlines' if flat else
                               'shaded/detailed drawing -> automatic colours (drawing colours would turn most of the model into outline colour)')}
    res['drawing_pictures'] = [f.name for f in sorted(prep.glob('ref_*.png'))]
    def drawing_palette(k, fl=None):
        fl = FL if fl is None else fl
        cand, lb = B.kmeans_lab(fl, np.ones(len(fl)), 16); cw = np.array([(lb == j).sum() for j in range(len(cand))], float)
        keep = cw > 0; cand, cw = cand[keep], cw[keep]; LW = np.array([0.45, 1, 1])
        while len(cand) > k - 1:          # shades of one hue (holly dark green) merge before different hues (brown antlers)
            dd = np.linalg.norm((cand[:, None] - cand[None]) * LW, axis=-1); np.fill_diagonal(dd, np.inf); x, y = np.unravel_index(np.argmin(dd), dd.shape)
            if cw[y] > cw[x]: x, y = y, x
            cw[x] += cw[y]; cand = np.delete(cand, y, 0); cw = np.delete(cw, y)
        return np.vstack([cand[np.argsort(-cw)], LINE_LAB[None]])   # last = outline colour
    pairs = B.triangle_adjacency(T); a_, b_ = pairs[:, 0], pairs[:, 1]; ta, tb = T[a_], T[b_]
    eq = (ta[:, :, None] == tb[:, None, :]).any(2); sh = np.stack([np.where(eq, ta, -1).max(1), np.where(eq, ta, 1 << 40).min(1)], 1)
    elen = np.linalg.norm(V[sh[:, 0]] - V[sh[:, 1]], axis=1); tlab = B.srgb_to_lab(rgb)
    def drawing_assign(k):
        flx = FL; accent = np.zeros(len(T), bool); dropped = []
        for _ in range(3):
            P = drawing_palette(k, flx); LINE = len(P)
            fil = np.argmin((((tlab[:, None, :] - P[None]) * np.array([0.5, 1, 1])) ** 2).sum(-1), 1) + 1   # AI paint is darker/duller: hue first
            if k > ACCENT_MAX_FILAMENTS or PROPS: break
            share = [float(area[fil == j + 1].sum() / area.sum()) for j in range(LINE - 1)]
            acc = [j for j, s_ in enumerate(share) if s_ < ACCENT_MIN_SHARE]
            if not acc: break
            for j in acc:
                accent |= fil == j + 1; dropped.append({'colour': B.hex_color(B.lab_to_srgb(P[j][None])[0]), 'share_percent': round(100 * share[j], 2)})
            near = np.argmin(np.linalg.norm(flx[:, None, :] - P[None, :LINE - 1], axis=-1), 1)
            keep_px = ~np.isin(near, acc)
            if keep_px.sum() < 50: break
            flx = flx[keep_px]
        fil = np.where(accent, LINE, fil)          # accents (eyes) print in the outline colour
        res['accents_to_outline'] = dropped; res['props'] = PROPS
        fil, _ = B.clean_regions(fil, T, area, DETAIL['speck_mm2'])
        # thin or tiny DARK regions are outlines, whatever colour they were matched to (D2: lines back to black, antlers stay brown)
        comp = B._components(len(T), pairs, fil); nc = comp.max() + 1; border = fil[a_] != fil[b_]
        carea = np.bincount(comp, weights=area, minlength=nc)
        per = np.bincount(comp[a_[border]], weights=elen[border], minlength=nc) + np.bincount(comp[b_[border]], weights=elen[border], minlength=nc)
        width = 2 * carea / np.maximum(per, 1e-9)
        cl = np.bincount(comp, weights=area * tlab[:, 0], minlength=nc) / np.maximum(carea, 1e-12)
        clab = np.zeros(nc, int); clab[comp] = fil
        to_line = (clab != LINE) & ((width < DETAIL['line_width_mm']) | (carea < DETAIL['line_area_mm2'])) & (cl < 40)
        moved = float(area[to_line[comp]].sum() / area.sum() * 100)
        fil = np.where(to_line[comp], LINE, fil)
        pal = [B.hex_color(B.lab_to_srgb(c[None])[0]) for c in P]
        de = float(np.average(np.linalg.norm(tlab - P[fil - 1], axis=1), weights=area))
        return fil, pal, {'quantization_deltaE76_mean': round(de, 2), 'thin_dark_regions_to_outline_area_percent': round(moved, 2), 'accents_to_outline': dropped}
    if COUNT not in TEMPLATES: raise ValueError('filament count must be 4-9')
    if COLOURS not in ('studio', 'drawing', 'auto'): raise ValueError('colours must be studio, drawing or auto')
    mode = res['style']['recommended'] if COLOURS == 'studio' else COLOURS
    t = studio / TEMPLATES[COUNT]
    if not t.is_file(): raise RuntimeError('Bambu template missing: ' + TEMPLATES[COUNT] + ' (save a Bambu Studio project with %d filaments there)' % COUNT)
    if B.read_template(t)['filaments'] != COUNT: raise RuntimeError(TEMPLATES[COUNT] + ' does not hold %d filaments - re-save it in Bambu Studio' % COUNT)
    prog(30, 'choosing %d filament colours (%s)' % (COUNT, mode))
    if mode == 'drawing':
        fil, pal, st = drawing_assign(COUNT)
    else:
        fil, pal, st = B.quantize(rgb, obs, area, COUNT, 'dominant', 'distinct'); fil, cst = B.clean_regions(fil, T, area, DETAIL['speck_mm2'])
    prog(70, 'writing the Bambu 3MF')
    p = out / 'AI-PAINT.3mf'
    if p.exists(): p.unlink()
    B.write_bambu_project(t, p, V, T, fil, pal, name='AIPaint')
    ver = B.verify_bambu_project(p, len(V), len(T), len(pal), pal)
    res['files'].append({'mode': mode, 'requested': COLOURS, 'filaments': COUNT, 'template': TEMPLATES[COUNT], 'file': str(p), 'palette': pal,
                         'deltaE_mean': st.get('quantization_deltaE76_mean'), 'thin_dark_to_outline_percent': st.get('thin_dark_regions_to_outline_area_percent'),
                         'verify': ver, 'share_percent': [round(100 * float(area[fil == j + 1].sum() / area.sum()), 1) for j in range(len(pal))]})
    prog(100, '3MF written and re-read')
    res['ok'] = any('file' in f for f in res['files'])
    if not res['ok']: raise RuntimeError('no 3MF written: ' + json.dumps(res['files']))
    print('FILAMENTS_PASSED', json.dumps([(f.get('mode'), f['filaments'], f.get('palette')) for f in res['files']]), flush=True)
except Exception:
    res['error'] = traceback.format_exc(); traceback.print_exc()
(out / 'filaments.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
sys.exit(0 if res['ok'] else 1)
