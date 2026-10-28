# BAMBU_FULL_COLOR_EXPORT_V1  (AI Modeling Studio color update 0.002)
# BAMBU_REGION_CLEANUP_V1     (AI Modeling Studio color update 0.003)
# REFERENCE_COLOUR_PRESERVING_CLEANUP_V1 + VISIBILITY_GAP_FILL_V1 (0.005)
"""Bambu Studio full-color project export.

Pure numpy/stdlib (no bpy) so it can be unit-tested outside Blender.
Pipeline: per-triangle colors sampled from approved reference pixels (via the
texture-master UVs) -> area-weighted k-means in CIELAB to the filament count ->
per-triangle Bambu paint states written into a copy of a Bambu-saved template
project -> the written file is reopened and verified.

Nothing here invents colour detail: triangles with no reliable reference pixels
are counted as UNOBSERVED and handled by an explicit, reported policy.
"""
import io, json, math, re, uuid, zipfile, hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

VERSION = '0.006'
MAX_REGION_MM2 = 50.0
GAP_FILL_MM = 1.5
MAX_FILAMENTS = 16
POLICIES = ('dominant', 'gray')


# ---------- Bambu / PrusaSlicer TriangleSelector paint encoding ----------
def paint_code(state):
    """Whole (unsplit) triangle painted with filament `state` (1-based)."""
    if not isinstance(state, (int, np.integer)) or not 1 <= state <= MAX_FILAMENTS:
        raise ValueError('Invalid filament state %r' % (state,))
    state = int(state)
    if state < 3:
        nibbles = [state << 2]                      # split=00, state in bits 2-3
    else:
        nibbles = [0b1100]                          # split=00, state marker 11
        n = state - 3
        while n >= 15:
            nibbles.append(15); n -= 15
        nibbles.append(n)
    return ''.join('%X' % v for v in reversed(nibbles))


def decode_paint(code):
    """Inverse of paint_code for unsplit triangles; raises on anything else."""
    if not re.fullmatch('[0-9A-F]+', code or ''):
        raise ValueError('Bad paint code %r' % (code,))
    nibbles = [int(c, 16) for c in reversed(code)]
    first = nibbles[0]
    if first & 0b11:
        raise ValueError('Split triangle not expected: %r' % code)
    state = first >> 2
    if state < 3:
        if len(nibbles) != 1:
            raise ValueError('Trailing data in %r' % code)
        return state
    n = 3; rest = nibbles[1:]
    while rest and rest[0] == 15:
        n += 15; rest = rest[1:]
    if len(rest) != 1:
        raise ValueError('Malformed extended state %r' % code)
    return n + rest[0]


# ---------- colour ----------
def srgb_to_lab(rgb):
    rgb = np.clip(np.asarray(rgb, float), 0, 1)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def lab_to_srgb(lab):
    lab = np.atleast_2d(np.asarray(lab, float)); fy = (lab[:, 0] + 16) / 116; fx = fy + lab[:, 1] / 500; fz = fy - lab[:, 2] / 200
    f = np.stack([fx, fy, fz], 1); d = 6 / 29
    xyz = np.where(f > d, f ** 3, 3 * d * d * (f - 4 / 29)) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314], [-0.9692660, 1.8760108, 0.0415560], [0.0556434, -0.2040259, 1.0572252]])
    lin = np.clip(xyz @ m.T, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


def hex_color(rgb):
    r, g, b = (int(round(float(np.clip(c, 0, 1)) * 255)) for c in rgb)
    return '#%02X%02X%02X' % (r, g, b)


def sample_triangle_colors(uv, slot, images, alpha_min=0.5):
    """uv: (T,3,2) texture coords; slot: (T,) image index or -1 (unobserved);
    images: list of float arrays (H,W,4) in [0,1], row 0 = TOP of the image.
    Samples centroid + three inner points per triangle; ignores background pixels.
    Returns rgb (T,3) and observed (T,) bool."""
    uv = np.asarray(uv, float); slot = np.asarray(slot, int); T = len(slot)
    rgb = np.zeros((T, 3)); observed = np.zeros(T, bool)
    c = uv.mean(1)
    pts = np.stack([c, (c + uv[:, 0]) / 2, (c + uv[:, 1]) / 2, (c + uv[:, 2]) / 2], 1)  # (T,4,2)
    for k, img in enumerate(images):
        sel = np.where(slot == k)[0]
        if not len(sel):
            continue
        h, w = img.shape[:2]
        p = pts[sel]
        x = np.clip(np.floor(p[..., 0] * w).astype(int), 0, w - 1)
        y = np.clip(np.floor((1 - p[..., 1]) * h).astype(int), 0, h - 1)
        px = img[y, x]                                    # (n,4,4)
        good = px[..., 3] >= alpha_min
        cnt = good.sum(1)
        tot = (px[..., :3] * good[..., None]).sum(1)
        ok = cnt > 0
        rgb[sel[ok]] = tot[ok] / cnt[ok, None]
        observed[sel[ok]] = True
    return rgb, observed


def triangle_areas(vertices, triangles):
    v = np.asarray(vertices, float)[np.asarray(triangles, int)]
    return 0.5 * np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)


def kmeans_lab(lab, weight, k, iterations=30, seed=0):
    rng = np.random.default_rng(seed)
    n = len(lab); k = max(1, min(k, n))
    w = weight / weight.sum()
    centers = [lab[rng.choice(n, p=w)]]
    for _ in range(1, k):                              # weighted k-means++
        d = np.min(((lab[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), 1) * w
        if d.sum() <= 0:
            break
        centers.append(lab[rng.choice(n, p=d / d.sum())])
    centers = np.array(centers)
    for _ in range(iterations):
        lbl = np.argmin(((lab[:, None, :] - centers[None]) ** 2).sum(-1), 1)
        new = np.array([np.average(lab[lbl == j], 0, weight[lbl == j]) if np.any(lbl == j) else centers[j] for j in range(len(centers))])
        if np.allclose(new, centers):
            break
        centers = new
    lbl = np.argmin(((lab[:, None, :] - centers[None]) ** 2).sum(-1), 1)
    return centers, lbl


def reduce_shading(rgb, observed, area, strength=0.7, min_chroma=15.0, families=6, min_lightness=22.0):
    """SHADING_REDUCTION_V1 (optional, changes colours): drawn light and shadow inside one coloured family (all oranges,
    all purples...) is pulled toward that family's typical lightness so a shaded orange prints orange, not dark brown.
    Near-neutral colours (black/gray/white) are left untouched: there the difference may be real paint."""
    out = np.asarray(rgb, float).copy(); sel = np.where(np.asarray(observed, bool))[0]
    if not len(sel) or strength <= 0:
        return out, 0
    lab = srgb_to_lab(out[sel]); chroma = np.hypot(lab[:, 1], lab[:, 2])
    coloured = (chroma >= min_chroma) & (lab[:, 0] >= min_lightness)   # very dark colours (black scales with a warm tint) are paint, not shading
    if coloured.sum() < families:
        return out, 0
    idx = np.where(coloured)[0]; w = np.maximum(np.asarray(area, float)[sel][idx], 1e-12)
    hue = np.arctan2(lab[idx, 2], lab[idx, 1])          # shading changes lightness/saturation, not hue: group by hue only
    centers, lbl = kmeans_lab(np.column_stack([np.zeros(len(idx)), 50 * np.cos(hue), 50 * np.sin(hue)]), w, families)
    # Families closer than 25 degrees in hue are one colour (k-means must not split one orange into sub-families).
    angle = np.degrees(np.arctan2(centers[:, 2], centers[:, 1])) % 360; order = np.argsort(angle); group = np.zeros(len(centers), int); g = 0
    for a, b in zip(order[:-1], order[1:]):
        g += (angle[b] - angle[a]) > 25; group[b] = g
    if len(order) > 1 and (angle[order[0]] + 360 - angle[order[-1]]) <= 25:
        group[group == group[order[-1]]] = group[order[0]]
    lbl = group[lbl]
    for j in np.unique(lbl):
        m = lbl == j
        if not m.any():
            continue
        order = np.argsort(lab[idx[m], 0]); cum = np.cumsum(w[m][order]); median = lab[idx[m], 0][order][np.searchsorted(cum, cum[-1] / 2)]
        lab[idx[m], 0] += strength * (median - lab[idx[m], 0])
    out[sel[idx]] = lab_to_srgb(lab[idx])               # only the coloured pixels are rewritten; neutrals stay bit-exact
    return out, int(coloured.sum())


def distinct_palette(lab, weight, k, candidates=16, min_share=0.004):
    """PRINT_AWARE_PALETTE_V1: choose k filament colours that are as different from each other as possible,
    weighted by surface share (farthest-point selection over 16 candidate colours). Each chosen filament keeps its
    candidate's own colour (vivid colours stay vivid instead of being averaged with neighbouring shades)."""
    centers, lbl = kmeans_lab(lab, weight, max(candidates, k))
    share = np.array([weight[lbl == j].sum() for j in range(len(centers))]) / weight.sum()
    usable = np.where(share >= min_share)[0]
    if len(usable) < k:
        usable = np.argsort(-share)[:max(k, len(usable))]
    chosen = [int(usable[np.argmax(share[usable])])]
    while len(chosen) < min(k, len(usable)):
        rest = [j for j in usable if j not in chosen]
        dist = np.array([min(np.linalg.norm(centers[j] - centers[c]) for c in chosen) for j in rest])
        chosen.append(int(rest[int(np.argmax(dist * share[rest] ** 0.2))]))
    return centers[chosen]


def quantize(rgb, observed, area, n_filaments, policy, palette_mode='distinct'):
    """Returns 1-based filament per triangle, palette hex list (filament order) and stats."""
    if policy not in POLICIES:
        raise ValueError('Unknown unobserved policy')
    if not 1 <= n_filaments <= MAX_FILAMENTS:
        raise ValueError('Filament count must be 1-%d' % MAX_FILAMENTS)
    T = len(rgb); obs = np.where(observed)[0]
    if not len(obs):
        raise ValueError('No triangle has reliable reference colour; nothing to export')
    k_obs = n_filaments - 1 if policy == 'gray' else n_filaments
    if k_obs < 1:
        raise ValueError('The gray policy needs at least 2 filaments')
    lab = srgb_to_lab(rgb[obs]); wt = np.maximum(area[obs], 1e-12)
    if palette_mode == 'distinct':
        centers = distinct_palette(lab, wt, k_obs)
        lbl = np.argmin(((lab[:, None, :] - centers[None]) ** 2).sum(-1), 1)
    else:
        centers, lbl = kmeans_lab(lab, wt, k_obs)
    # filament order: most surface area first (filament 1 = object default)
    cluster_area = np.array([wt[lbl == j].sum() for j in range(len(centers))])
    order = np.argsort(-cluster_area); rank = np.empty_like(order); rank[order] = np.arange(len(order))
    palette_rgb = [lab_to_srgb(centers[j])[0] if palette_mode == 'distinct' else np.average(rgb[obs][lbl == j], 0, wt[lbl == j]) for j in order]
    filament = np.zeros(T, int); filament[obs] = rank[lbl] + 1
    unobs = np.where(~observed)[0]
    if policy == 'gray':
        palette_rgb.append(np.array([0.5, 0.5, 0.5])); filament[unobs] = len(palette_rgb)
    else:
        filament[unobs] = 1
    de = np.linalg.norm(lab - centers[lbl], axis=1)
    stats = {
        'triangles': int(T), 'observed_triangles': int(len(obs)), 'unobserved_triangles': int(len(unobs)),
        'unobserved_area_percent': round(100 * float(area[unobs].sum() / max(area.sum(), 1e-12)), 2),
        'unobserved_policy': policy,
        'quantization_deltaE76_mean': round(float(np.average(de, weights=wt)), 2),
        'quantization_deltaE76_p95': round(float(np.percentile(de, 95)), 2),
    }
    return filament, [hex_color(c) for c in palette_rgb], stats


# ---------- region cleanup (speckle removal) ----------
def triangle_adjacency(triangles):
    """Pairs of triangles sharing an edge (works on non-manifold edges by chaining)."""
    tri = np.asarray(triangles, np.int64); T = len(tri)
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]); e.sort(1)
    owner = np.tile(np.arange(T), 3)
    key = e[:, 0] * (int(tri.max()) + 1) + e[:, 1]
    order = np.argsort(key, kind='stable'); key = key[order]; owner = owner[order]
    same = key[1:] == key[:-1]
    a, b = owner[:-1][same], owner[1:][same]
    keep = a != b
    return np.stack([a[keep], b[keep]], 1)


def _components(n, pairs, labels):
    """Connected components of triangles with equal label (union-find)."""
    parent = np.arange(n)
    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root
    for a, b in pairs[labels[pairs[:, 0]] == labels[pairs[:, 1]]].tolist():
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = np.fromiter((find(i) for i in range(n)), np.int64, n)
    return np.unique(roots, return_inverse=True)[1]


def clean_regions(filament, triangles, area, min_region_mm2, max_passes=12, observed=None):
    """Reassign every same-filament region smaller than min_region_mm2 to the neighbouring
    filament it shares the most boundary with. Isolated small parts (no neighbours) are kept.
    Returns the new filament array and statistics. 0 disables cleanup."""
    filament = np.asarray(filament, np.int64).copy(); area = np.asarray(area, float); T = len(filament)
    # REFERENCE_COLOUR_PRESERVING_CLEANUP_V1: reference-coloured patches never take a colour from triangles
    # without reference pixels (unobserved/gray); small unobserved holes may take the surrounding colour (reported as inferred).
    observed = np.ones(T, bool) if observed is None else np.asarray(observed, bool)
    if not 0 <= float(min_region_mm2) <= MAX_REGION_MM2:
        raise ValueError('Minimum region size must be 0-%g mm2' % MAX_REGION_MM2)
    pairs = triangle_adjacency(triangles)
    def count_regions(lbl):
        comp = _components(T, pairs, lbl); ra = np.bincount(comp, area)
        return int(comp.max() + 1), int(np.sum(ra < min_region_mm2)) if min_region_mm2 > 0 else 0
    before_regions, before_small = count_regions(filament)
    original = filament.copy(); passes = 0
    if min_region_mm2 > 0:
        nf = int(filament.max()) + 1
        for passes in range(1, max_passes + 1):
            comp = _components(T, pairs, filament); C = int(comp.max() + 1)
            region_area = np.bincount(comp, area, C); small = region_area < min_region_mm2
            if not small.any():
                break
            ca, cb = comp[pairs[:, 0]], comp[pairs[:, 1]]; diff = ca != cb
            region_observed = np.bincount(comp, observed.astype(float), C) > 0
            # boundary votes: (small region, neighbour filament) weighted by edge count; prefer large neighbours
            src = np.concatenate([ca[diff], cb[diff]]); dst = np.concatenate([cb[diff], ca[diff]])
            dst_tri = np.concatenate([pairs[:, 1][diff], pairs[:, 0][diff]])
            sel = small[src] & ~(region_observed[src] & ~observed[dst_tri]); src, dst = src[sel], dst[sel]
            if not len(src):
                break
            weight = np.where(small[dst], 1.0, 1000.0)
            votes = np.zeros((C, nf))
            region_filament = np.zeros(C, np.int64); region_filament[comp] = filament
            np.add.at(votes, (src, region_filament[dst]), weight)
            target = votes.argmax(1); has = votes.max(1) > 0
            change = small & has & (target != region_filament)
            if not change.any():
                break
            moved = change[comp]; filament[moved] = target[comp[moved]]
    after_regions, after_small = count_regions(filament)
    changed = filament != original
    filled = changed & ~observed
    return filament, {'min_region_mm2': float(min_region_mm2), 'regions_before': before_regions, 'regions_after': after_regions,
                      'small_regions_before': before_small, 'small_regions_after': after_small, 'passes': passes,
                      'triangles_reassigned': int(changed.sum()),
                      'area_reassigned_percent': round(100 * float(area[changed].sum() / max(area.sum(), 1e-12)), 2),
                      'unobserved_filled_from_neighbours': int(filled.sum()),
                      'unobserved_filled_area_percent': round(100 * float(area[filled].sum() / max(area.sum(), 1e-12)), 2)}


def fill_gaps(filament, observed, triangles, vertices, max_mm=GAP_FILL_MM):
    """VISIBILITY_GAP_FILL_V1: unobserved triangles within max_mm (in adjacency rings) of reference colour take the
    most common colour of their already-coloured neighbours, ring by ring. Large unseen areas stay unobserved.
    Returns (filament, filled_mask). Filled triangles are inference and must be reported as such."""
    filament = np.asarray(filament, np.int64).copy(); observed = np.asarray(observed, bool)
    if max_mm <= 0 or observed.all() or not observed.any():
        return filament, np.zeros(len(filament), bool)
    tri = np.asarray(triangles, np.int64); v = np.asarray(vertices, float)
    edge = float(np.mean(np.linalg.norm(v[tri[:, 1]] - v[tri[:, 0]], axis=1)))
    rings = int(min(20, max(1, round(max_mm / max(edge, 1e-6)))))
    pairs = triangle_adjacency(tri); known = observed.copy(); nf = int(filament.max()) + 1
    for _ in range(rings):
        a, b = pairs[:, 0], pairs[:, 1]
        src = np.concatenate([a, b]); dst = np.concatenate([b, a])
        sel = ~known[dst] & known[src]
        if not sel.any():
            break
        votes = np.zeros((len(filament), nf)); np.add.at(votes, (dst[sel], filament[src[sel]]), 1.0)
        grow = np.where(votes.max(1) > 0)[0]; grow = grow[~known[grow]]
        filament[grow] = votes[grow].argmax(1); known[grow] = True
    return filament, known & ~observed


# ---------- Bambu project writer ----------
TEMPLATE_PARTS = ('[Content_Types].xml', '3D/3dmodel.model', '3D/_rels/3dmodel.model.rels',
                  '3D/Objects/object_1.model', 'Metadata/project_settings.config', 'Metadata/model_settings.config')


def read_template(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        missing = [n for n in TEMPLATE_PARTS if n not in names]
        if missing:
            raise ValueError('Bambu template is missing ' + ', '.join(missing) + '. Save a single-object project from Bambu Studio as the template.')
        data = {n: z.read(n) for n in z.namelist()}
    settings = json.loads(data['Metadata/project_settings.config'].decode('utf-8-sig'))
    colours = settings.get('filament_colour')
    if not isinstance(colours, list) or not colours:
        raise ValueError('Template project_settings has no filament_colour list')
    model = data['3D/3dmodel.model'].decode('utf-8')
    app = re.search(r'name="Application">([^<]*)<', model)
    item = re.search(r'<item [^>]*transform="([^"]+)"', model)
    if not item:
        raise ValueError('Template has no build item transform')
    t = [float(x) for x in item.group(1).split()]
    return {'data': data, 'settings': settings, 'filaments': len(colours), 'application': app.group(1) if app else '',
            'bed_xy': (t[9], t[10]), 'model_header': model[:model.index('<resources>')]}


def _xml_attr(text):
    return text.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def write_bambu_project(template_path, out_path, vertices, triangles, filament, palette, name='Model'):
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError('Existing Bambu export is never overwritten: ' + str(out_path))
    tpl = read_template(template_path)
    if len(palette) > tpl['filaments']:
        raise ValueError('Palette has %d colours but the Bambu template has only %d filaments' % (len(palette), tpl['filaments']))
    v = np.asarray(vertices, float); tri = np.asarray(triangles, int); fil = np.asarray(filament, int)
    if tri.ndim != 2 or tri.shape[1] != 3 or len(fil) != len(tri) or tri.min() < 0 or tri.max() >= len(v):
        raise ValueError('Invalid mesh arrays')
    if fil.min() < 1 or fil.max() > len(palette):
        raise ValueError('Filament index outside palette')
    lo, hi = v.min(0), v.max(0); centre = (lo + hi) / 2; local = v - centre; half_h = float((hi - lo)[2] / 2)
    codes = {s: paint_code(s) for s in range(1, len(palette) + 1)}

    obj = io.StringIO()
    obj.write('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
              'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
              ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
              '  <object id="1" p:UUID="%s" type="model">\n   <mesh>\n    <vertices>\n' % uuid.uuid4())
    obj.write(''.join('     <vertex x="%.5f" y="%.5f" z="%.5f"/>\n' % tuple(p) for p in local))
    obj.write('    </vertices>\n    <triangles>\n')
    obj.write(''.join('     <triangle v1="%d" v2="%d" v3="%d" paint_color="%s"/>\n' % (a, b, c, codes[int(f)]) for (a, b, c), f in zip(tri, fil)))
    obj.write('    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n')

    bx, by = tpl['bed_xy']
    model = (tpl['model_header'] +
             '<resources>\n  <object id="2" p:UUID="%s" type="model">\n   <components>\n'
             '    <component p:path="/3D/Objects/object_1.model" objectid="1" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
             '   </components>\n  </object>\n </resources>\n <build p:UUID="%s">\n'
             '  <item objectid="2" p:UUID="%s" transform="1 0 0 0 1 0 0 0 1 %.5f %.5f %.5f" printable="1"/>\n </build>\n</model>\n'
             % (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), bx, by, half_h))
    model = re.sub(r'(<metadata name="Title">)[^<]*(</metadata>)', lambda m: m.group(1) + _xml_attr(name) + m.group(2), model)

    T = len(tri); nm = _xml_attr(name)
    settings_xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <object id="2">\n'
                    '    <metadata key="name" value="%s"/>\n    <metadata key="extruder" value="1"/>\n    <metadata face_count="%d"/>\n'
                    '    <part id="1" subtype="normal_part" uuid="%s">\n      <metadata key="name" value="%s"/>\n'
                    '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                    '      <mesh_stat face_count="%d" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
                    '    </part>\n  </object>\n  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value=""/>\n'
                    '    <metadata key="locked" value="false"/>\n    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
                    '    <model_instance>\n      <metadata key="object_id" value="2"/>\n      <metadata key="instance_id" value="0"/>\n'
                    '      <metadata key="identify_id" value="1"/>\n    </model_instance>\n  </plate>\n  <assemble>\n'
                    '   <assemble_item object_id="2" instance_id="0" transform="1 0 0 0 1 0 0 0 1 0 0 %.5f" offset="0 0 0" />\n'
                    '  </assemble>\n</config>\n' % (nm, T, uuid.uuid4(), nm, T, half_h))

    settings = json.loads(json.dumps(tpl['settings']))
    for key in ('filament_colour', 'filament_multi_colour'):
        if isinstance(settings.get(key), list) and len(settings[key]) == tpl['filaments']:
            for i, c in enumerate(palette):
                settings[key][i] = c

    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    replaced = {'3D/3dmodel.model': model, '3D/Objects/object_1.model': obj.getvalue(), 'Metadata/model_settings.config': settings_xml,
                'Metadata/project_settings.config': json.dumps(settings, indent=4), '_rels/.rels': rels}
    skip_prefix = ('Metadata/plate_', 'Metadata/top_', 'Metadata/pick_', 'Metadata/plate_no_light_')  # template thumbnails would show the template object
    tmp = out_path.with_name(out_path.name + '.partial')
    tmp.unlink(missing_ok=True)
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in tpl['data'].items():
            if n in replaced or n.startswith(skip_prefix) or n.endswith('.gcode') or n.endswith('.md5'):
                continue
            z.writestr(n, b)
        for n, text in replaced.items():
            z.writestr(n, text.encode('utf-8'))
    tmp.replace(out_path)
    return {'template_application': tpl['application'], 'template_filaments': tpl['filaments'], 'bed_xy': [bx, by]}


def verify_bambu_project(path, expect_vertices, expect_triangles, n_colours, palette):
    """Reopen the written file and check what Bambu Studio will read."""
    counts = [0] * (n_colours + 1)
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise ValueError('Corrupt Bambu 3MF')
        for n in TEMPLATE_PARTS:
            z.getinfo(n)
        settings = json.loads(z.read('Metadata/project_settings.config'))
        if settings['filament_colour'][:len(palette)] != list(palette):
            raise ValueError('filament_colour does not hold the palette')
        model = z.read('3D/3dmodel.model').decode('utf-8')
        if '/3D/Objects/object_1.model' not in model:
            raise ValueError('Build does not reference object_1.model')
        ET.fromstring(z.read('Metadata/model_settings.config'))
        nv = nt = 0
        with z.open('3D/Objects/object_1.model') as f:
            for _, el in ET.iterparse(f):
                tag = el.tag.rsplit('}', 1)[-1]
                if tag == 'vertex':
                    nv += 1
                elif tag == 'triangle':
                    nt += 1
                    ids = [int(el.get(k)) for k in ('v1', 'v2', 'v3')]
                    if min(ids) < 0 or max(ids) >= expect_vertices:
                        raise ValueError('Triangle references a missing vertex')
                    s = decode_paint(el.get('paint_color'))
                    if not 1 <= s <= n_colours:
                        raise ValueError('Paint state outside palette')
                    counts[s] += 1
                el.clear()
    if nv != expect_vertices or nt != expect_triangles:
        raise ValueError('Vertex/triangle count changed in written file (%d/%d vs %d/%d)' % (nv, nt, expect_vertices, expect_triangles))
    return counts[1:]


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def export_full_color(template_path, out_path, report_path, vertices, triangles, uv, slot, slot_names, images, n_filaments, policy, name, min_region_mm2=0.0, inferred=None, shading='keep'):
    """Complete stage: quantize, write, reopen/verify, and write a plain-text report.
    Raises on any failure; never returns a partial success."""
    area = triangle_areas(vertices, triangles)
    rgb, observed = sample_triangle_colors(uv, slot, images)
    if shading not in ('keep', 'reduce'):
        raise ValueError('Unknown shading option')
    rgb, shading_changed = reduce_shading(rgb, observed, triangle_areas(vertices, triangles)) if shading == 'reduce' else (rgb, 0)
    # SYMMETRY_COLOUR_FILL_V1: faces coloured from their mirror partner carry real pixels but are INFERRED, not reference colour.
    symmetric = (np.asarray(inferred, bool) if inferred is not None else np.zeros(len(observed), bool)) & observed
    tpl_filaments = read_template(template_path)['filaments']
    if n_filaments > tpl_filaments:
        raise ValueError('Requested %d filaments but the Bambu template has %d. Save a template with more filaments.' % (n_filaments, tpl_filaments))
    filament, palette, stats = quantize(rgb, observed, area, n_filaments, policy)
    stats['palette_method'] = 'print-aware: filament colours chosen to be distinct (farthest-point over 16 candidates)'
    stats['shading'] = {'option': shading, 'triangles_changed': shading_changed}
    filament, gap_filled = fill_gaps(filament, observed, triangles, vertices)
    stats['gap_fill'] = {'max_mm': GAP_FILL_MM, 'triangles': int(gap_filled.sum()), 'area_percent': round(100 * float(area[gap_filled].sum() / max(area.sum(), 1e-12)), 2)}
    filament, cleanup = clean_regions(filament, triangles, area, float(min_region_mm2), observed=observed | gap_filled)
    stats['region_cleanup'] = cleanup
    info = write_bambu_project(template_path, out_path, vertices, triangles, filament, palette, name)
    try:
        counts = verify_bambu_project(out_path, len(vertices), len(triangles), len(palette), palette)
    except Exception:
        Path(out_path).unlink(missing_ok=True)
        raise
    total = max(area.sum(), 1e-12)
    final_unobserved = ~observed & (filament == len(palette)) if policy == 'gray' else ~observed & (filament == 1)
    stats['final_surface_split'] = {'reference_colour_percent': round(100 * float(area[observed & ~symmetric].sum() / total), 2),
                                    'inferred_by_symmetry_percent': round(100 * float(area[symmetric].sum() / total), 2),
                                    'inferred_from_neighbours_percent': round(100 * float(area[~observed & ~final_unobserved].sum() / total), 2),
                                    'no_reference_percent': round(100 * float(area[final_unobserved].sum() / total), 2)}
    rows = [{'filament': i + 1, 'colour': c, 'triangles': counts[i], 'area_percent': round(100 * float(area[filament == i + 1].sum() / total), 2)} for i, c in enumerate(palette)]
    per_view = {n: int(np.sum((slot == k) & observed)) for k, n in enumerate(slot_names)}
    report = {'version': VERSION, 'ok': True, 'file': Path(out_path).name, 'sha256': file_sha256(out_path), 'filaments': rows,
              'statistics': stats, 'observed_triangles_per_view': per_view, 'template': info,
              'verified': 'reopened: archive, vertex/triangle counts, every paint_color decoded, palette in project settings',
              'bambu_studio_verified': False,
              'limitations': ['One filament per triangle; colour detail smaller than a triangle is averaged.',
                              'Region cleanup trades colour details smaller than the chosen size for fewer colour changes.',
                              'Palette is limited to the requested filament count; nearby shades merge (see deltaE).',
                              'Unobserved triangles use the policy shown; they are NOT reference colour.',
                              'Map filaments to your real AMS spools in Bambu Studio; colours here are the measured palette.',
                              'Must be opened in Bambu Studio to confirm the painted colours before printing.']}
    lines = ['AI Modeling Studio - Bambu full-color export report (v%s)' % VERSION, 'File: %s' % report['file'], 'SHA256: %s' % report['sha256'], '',
             'Filaments (filament 1 is the object default):']
    lines += ['  %2d  %s  %7d triangles  %6.2f%% of surface' % (r['filament'], r['colour'], r['triangles'], r['area_percent']) for r in rows]
    lines += ['', 'Unobserved triangles (no reliable reference pixels): %d (%.2f%% of surface) -> %s' % (
        stats['unobserved_triangles'], stats['unobserved_area_percent'],
        'filament 1 (dominant colour; NOT reference colour)' if policy == 'dominant' else 'dedicated neutral gray filament %d' % len(palette)),
              'Colour error from quantization (CIE76 deltaE): mean %.2f, 95th percentile %.2f' % (stats['quantization_deltaE76_mean'], stats['quantization_deltaE76_p95']),
              ('Region cleanup: regions smaller than %g mm2 merged into their largest neighbour: %d -> %d colour regions, %d triangles (%.2f%% of surface) reassigned; %d small regions remain (isolated parts or no neighbour).' % (stats['region_cleanup']['min_region_mm2'], stats['region_cleanup']['regions_before'], stats['region_cleanup']['regions_after'], stats['region_cleanup']['triangles_reassigned'], stats['region_cleanup']['area_reassigned_percent'], stats['region_cleanup']['small_regions_after']) if min_region_mm2 > 0 else 'Region cleanup: OFF (every triangle keeps its own colour; expect speckle).'),
              'Visibility gaps filled from neighbouring reference colour (within %.1f mm): %.2f%% of surface (inferred, not reference pixels).' % (GAP_FILL_MM, stats['gap_fill']['area_percent']),
              'Final surface: %.2f%% reference colour, %.2f%% inferred by left-right symmetry (mirror side), %.2f%% inferred from neighbouring colours (gaps and small holes), %.2f%% with no reference colour (%s).' % (stats['final_surface_split']['reference_colour_percent'], stats['final_surface_split']['inferred_by_symmetry_percent'], stats['final_surface_split']['inferred_from_neighbours_percent'], stats['final_surface_split']['no_reference_percent'], 'gray filament' if policy == 'gray' else 'main colour'),
              ('Drawn shading reduced inside coloured families (%d triangles changed): colours are NOT exact reference pixels there.' % shading_changed if shading == 'reduce' else 'Drawn shading kept as in the reference.'),
              'Palette: ' + stats['palette_method'] + '.',
              'Observed triangles per reference view: ' + ', '.join('%s %d' % kv for kv in per_view.items()),
              'Template: %s, %d filaments' % (info['template_application'], info['template_filaments']), '',
              'Checked by the studio: ' + report['verified'], 'NOT yet checked: opening in Bambu Studio. Do that before printing.', '', 'Limitations:']
    lines += ['  - ' + s for s in report['limitations']]
    Path(report_path).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report
