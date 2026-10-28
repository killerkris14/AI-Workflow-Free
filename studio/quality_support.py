# QUALITY SUPPORT v3 - plan validation/repair, plan-built starter script, geometry gate, previews, visual review.
import base64
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'pair of': 2}
COUNTABLE = {'leg': 'leg', 'legs': 'leg', 'wing': 'wing', 'wings': 'wing', 'eye': 'eye', 'eyes': 'eye',
             'horn': 'horn', 'horns': 'horn', 'ear': 'ear', 'ears': 'ear', 'arm': 'arm', 'arms': 'arm'}


def settings():
    defaults = {'length_tolerance_fraction': 0.03, 'bed_tolerance_mm': 0.15, 'require_closed_parts': True,
                'review_preview_size': 512}
    try:
        defaults.update(json.loads((ROOT / 'quality_settings.json').read_text(encoding='utf-8')))
    except (OSError, ValueError):
        pass
    return defaults


def json_object(text):
    decoder = json.JSONDecoder()
    text = re.sub(r',\s*([}\]])', r'\1', text.strip())
    for match in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    raise ValueError('Did not return a usable JSON object.')


def _mm(pattern, text):
    found = [(m.start(), float(m.group(1))) for m in re.finditer(pattern, text, re.I)]
    return max(found)[1] if found else None


def explicit_length(text):
    return _mm(r'(?:overall\s+)?(?:head-to-tail\s+)?length[^0-9\n]{0,40}?(\d+(?:\.\d+)?)\s*mm', text) or \
        _mm(r'(\d+(?:\.\d+)?)\s*mm\s*(?:long\b|overall\s*length)', text)


def explicit_width(text):
    return _mm(r'(?:max(?:imum)?\s+)?(?:overall\s+)?width[^0-9\n]{0,40}?(\d+(?:\.\d+)?)\s*mm', text) or \
        _mm(r'(\d+(?:\.\d+)?)\s*mm\s*wide', text)


def explicit_height(text):
    return _mm(r'(?:max(?:imum)?\s+)?(?:overall\s+)?height[^0-9\n]{0,40}?(\d+(?:\.\d+)?)\s*mm', text) or \
        _mm(r'(\d+(?:\.\d+)?)\s*mm\s*(?:tall|high)\b', text)


def requested_counts(text):
    counts = {}
    pattern = r'(?<![\d.])\b(one|two|three|four|five|six|pair of|[1-8])[ \t]+(?:[a-z,-]+[ \t]+){0,3}?(legs|wings|eyes|horns|ears|arms|leg|wing|eye|horn|ear|arm)\b(?![ \t]*(?:membrane|thickness|root|tip))'
    for m in re.finditer(pattern, text, re.I):
        n = WORDS.get(m.group(1).lower()) or (int(m.group(1)) if m.group(1).isdigit() else 0)
        stem = COUNTABLE[m.group(2).lower()]
        if 0 < n <= 8:
            counts[stem] = max(counts.get(stem, 0), n)
    return counts


def required_names(text):
    m = re.search(r'required (?:exact )?object names\s*:?\s*(.+?)(?:\.\s|\.$|\n\s*\n|\n-)', text, re.I | re.S)
    if not m:
        return []
    return [n.strip(' .`"\'') for n in re.split(r'[,\n]', m.group(1)) if re.fullmatch(r'\s*[A-Za-z][\w]*\s*\.?', n)]


def _box(p):
    c, s = p['center_mm'], p['size_mm']
    return [c[i] - s[i] / 2 for i in range(3)], [c[i] + s[i] / 2 for i in range(3)]


def _gap(a, b):
    (alo, ahi), (blo, bhi) = _box(a), _box(b)
    return max(max(blo[i] - ahi[i], alo[i] - bhi[i], 0) for i in range(3))


def plan_bounds(parts):
    boxes = [_box(p) for p in parts]
    lo = [min(b[0][i] for b in boxes) for i in range(3)]
    hi = [max(b[1][i] for b in boxes) for i in range(3)]
    return lo, hi, [hi[i] - lo[i] for i in range(3)]


def _parent(part, by_name):
    text = str(part.get('attachment') or part.get('attached_to') or '').lower()
    best = None
    for name, other in by_name.items():
        if other is part or not name:
            continue
        if re.search(r'\b' + re.escape(name.lower()) + r'\b', text) and (best is None or len(name) > len(best['name'])):
            best = other
    return best


def _count(parts, stem):
    return sum(1 for p in parts if re.search(stem, p['name'], re.I))


def validate_plan(plan, request):
    issues = []
    parts = plan['parts']
    by_name = {p['name']: p for p in parts}
    lo, hi, size = plan_bounds(parts)
    target, width, height = plan.get('target_length_mm'), plan.get('max_width_mm'), plan.get('max_height_mm')
    if target and abs(size[0] - target) > max(1.0, target * 0.06):
        issues.append('Planned parts span X %.1f..%.1f = %.1f mm, but the target length is %g mm. Move/resize parts so the '
                      'whole model (snout to tail tip) spans %g mm.' % (lo[0], hi[0], size[0], target, target))
    if width and size[1] > width + 0.5:
        issues.append('Planned width Y is %.1f mm; maximum is %g mm (wings included).' % (size[1], width))
    if height and size[2] > height + 0.5:
        issues.append('Planned height Z is %.1f mm; maximum is %g mm.' % (size[2], height))
    if lo[2] < -0.5:
        issues.append('Planned parts go below Z=0 (lowest %.1f mm).' % lo[2])
    for stem, n in requested_counts(request).items():
        have = _count(parts, stem)
        if have < n:
            issues.append('Request asks for %d %ss but the plan has %d. Add the missing %s parts.' % (n, stem, have, stem))
    if False:  # Reference proportions, not a minimum use of allowed width.
        issues.append('Plan uses only %.0f of the allowed %g mm width; wings/limbs look too small. Make the wings span most of the width.' % (size[1], width))
    head, body, tail = (by_name.get(n) or next((p for p in parts if p['name'].lower() == n.lower()), None) for n in ('Head', 'Body', 'Tail'))
    if head and body:
        if _box(body)[0][0] < _box(head)[0][0] - 0.5:
            issues.append('Body starts at X %.1f, in front of the head (head front X %.1f). Head/snout must be the front (-X) end.' % (_box(body)[0][0], _box(head)[0][0]))
        if False:  # Thin subjects may be correct for their reference.
            issues.append('Body is very thin (%s mm). Make it a rounded, chunky ellipsoid.' % body['size_mm'])
    if body and tail and tail['center_mm'][0] < body['center_mm'][0]:
        issues.append('Tail must be behind the body (+X side).')
    names = {p['name'].casefold() for p in parts}
    for name in plan.get('required_parts', []):
        if name.casefold() not in names:
            issues.append('Required part "%s" is not in the parts list.' % name)
    for part in parts:
        parent = _parent(part, by_name)
        if parent is not None:
            gap = _gap(part, parent)
            overlap = min(min(_box(part)[1][i], _box(parent)[1][i]) - max(_box(part)[0][i], _box(parent)[0][i]) for i in range(3))
            if gap > 0.5 or overlap < 0.2:
                issues.append('%s does not touch %s (%.1f mm gap). Attached parts must overlap their parent.' % (part['name'], parent['name'], gap))
    return issues


def repair_plan(plan, request):
    """Deterministic fixes for common planner mistakes. Returns a list of what was changed."""
    fixes = []
    parts = plan['parts']
    by_name = {p['name']: p for p in parts}
    find = lambda n: next((p for p in parts if p['name'].lower() == n), None)
    head, body = find('head'), find('body')
    target = plan.get('target_length_mm') or plan_bounds(parts)[2][0]
    width_limit, height_limit = plan.get('max_width_mm'), plan.get('max_height_mm')
    if head and body:
        blo, bhi = _box(body)
        front = head['center_mm'][0]
        if blo[0] < _box(head)[0][0] - 0.5 and bhi[0] > front:
            body['size_mm'][0] = bhi[0] - front
            body['center_mm'][0] = (bhi[0] + front) / 2
            fixes.append('Trimmed Body so it starts at the head instead of in front of it.')
    if body and min(body['size_mm'][1], body['size_mm'][2]) < body['size_mm'][0] * 0.18:
        want = body['size_mm'][0] * 0.3
        body['size_mm'][1] = min(want, (width_limit or want * 3) * 0.45)
        body['size_mm'][2] = min(want * 0.8, (height_limit or want * 3) * 0.6)
        body['center_mm'][2] = max(body['center_mm'][2], body['size_mm'][2] / 2)
        fixes.append('Made Body chunkier (%.0f x %.0f mm cross-section).' % (body['size_mm'][1], body['size_mm'][2]))
    wings = [p for p in parts if re.search('wing', p['name'], re.I)]
    small = any(w['size_mm'][1] < width_limit * 0.25 for w in wings) if width_limit else False
    if width_limit and wings and (small or plan_bounds(parts)[2][1] < width_limit * 0.7):
        half_body = body['size_mm'][1] / 2 if body else 5
        span = max(width_limit * 0.45 - half_body, 8)
        for w in wings:
            sign = -1 if w['center_mm'][1] < 0 else 1
            w['size_mm'][1] = span
            w['size_mm'][0] = max(w['size_mm'][0], target * 0.3)
            w['size_mm'][2] = max(min(w['size_mm'][2], 4), 2.4)
            w['center_mm'][1] = sign * (half_body * 0.8 + span / 2)
            if body:
                w['center_mm'][0] = body['center_mm'][0] - body['size_mm'][0] * 0.1
                w['center_mm'][2] = max(body['center_mm'][2] + body['size_mm'][2] * 0.2, w['size_mm'][2] / 2)
        fixes.append('Enlarged wings to span about %.0f mm each.' % span)
    tail = find('tail')
    lo, hi, size = plan_bounds(parts)
    if tail and plan.get('target_length_mm') and size[0] < target * 0.94 and abs(_box(tail)[1][0] - hi[0]) < 1:
        extra = min(target - size[0], target * 0.45 - tail['size_mm'][0])
        if extra > 0:
            tail['size_mm'][0] += extra
            tail['center_mm'][0] += extra / 2
            fixes.append('Extended Tail by %.0f mm toward the %g mm target length.' % (extra, target))
    for part in parts:
        parent = _parent(part, by_name)
        if parent is None or _gap(part, parent) <= 0.5:
            continue
        (plo, phi), (clo, chi) = _box(parent), _box(part)
        for i in range(3):
            if clo[i] > phi[i]:
                part['center_mm'][i] -= clo[i] - phi[i] + 1.0
            elif chi[i] < plo[i]:
                part['center_mm'][i] += plo[i] - chi[i] + 1.0
        fixes.append('Moved %s to touch %s.' % (part['name'], parent['name']))
    need = requested_counts(request)
    body = next((p for p in parts if p['name'].lower() == 'body'), None)
    legs = [p for p in parts if re.search('leg', p['name'], re.I)]
    if body and legs and need.get('leg', 0) > len(legs):
        blo, bhi = _box(body)
        for leg in list(legs):
            if len([p for p in parts if re.search('leg', p['name'], re.I)]) >= need['leg']:
                break
            twin = json.loads(json.dumps(leg))
            front = leg['center_mm'][0] < body['center_mm'][0]
            twin['name'] = re.sub('front', 'Back', leg['name'], flags=re.I) if front else re.sub('back|rear', 'Front', leg['name'], flags=re.I)
            if twin['name'] == leg['name']:
                twin['name'] = leg['name'] + ('_Back' if front else '_Front')
            mirrored = bhi[0] - (leg['center_mm'][0] - blo[0]) if front else blo[0] + (bhi[0] - leg['center_mm'][0])
            margin = (bhi[0] - blo[0]) * 0.18
            twin['center_mm'][0] = min(max(mirrored, blo[0] + margin), bhi[0] - margin)
            parts.append(twin)
            fixes.append('Added %s (request needs %d legs).' % (twin['name'], need['leg']))
    for stem in ('wing', 'eye', 'horn', 'ear'):
        group = [p for p in parts if re.search(stem, p['name'], re.I)]
        if need.get(stem) == 2 and len(group) == 1:
            twin = json.loads(json.dumps(group[0]))
            twin['center_mm'][1] = -twin['center_mm'][1]
            twin['name'] = re.sub('left', 'Right', group[0]['name'], flags=re.I) if re.search('left', group[0]['name'], re.I) \
                else re.sub('right', 'Left', group[0]['name'], flags=re.I) if re.search('right', group[0]['name'], re.I) else group[0]['name'] + '_2'
            parts.append(twin)
            fixes.append('Mirrored %s to make %s.' % (group[0]['name'], twin['name']))
    return fixes


PLAN_PROMPT = """Return ONE JSON object only, no code, no comments.
Axes: X = length (head/snout at -X, tail at +X), Y = left(-Y)/right(+Y), Z = height up from the bed at Z=0. Units mm.
Keys: target_length_mm, max_width_mm, max_height_mm (numbers or null), require_horizontal (bool), separate_color_objects (bool),
required_parts (list of exact names), parts (list), assumptions (list of strings).
Each part: {"name": str, "shape": one of ellipsoid|box|cylinder|tapered|wing, "center_mm": [x,y,z], "size_mm": [x,y,z],
"color_rgba": [r,g,b,1], "attachment": "<exact parent part name> or none"}.
size_mm is the FULL bounding box of that part. Rules:
- The union of all part boxes must match the requested length/width/height. Do the arithmetic: min X of the snout to max X of the tail = target length.
- Every attached part's box must overlap its parent's box by 1-3 mm (eyes and horns overlap the head, legs overlap the body, wings overlap the body, tail overlaps the body).
- Include every requested count (e.g. four legs = four leg parts named Leg_Front_Left, Leg_Front_Right, Leg_Back_Left, Leg_Back_Right).
- Wings: shape "wing", lying flat, size_mm = [chord along X, span along Y, thickness Z >= 2.4]. Left wing at -Y, right at +Y.
- Head, body, snout and eyes: shape "ellipsoid". Legs: shape "cylinder", vertical (size Z largest), bottoms at Z=0. Tail: shape "tapered" along X. Horns: "tapered".
- Keep everything above Z=0. Thin features at least 2.4 mm thick.
- For a low dragon with no height given, assume max height 40 mm and say so in assumptions. Do not force dragon parts on non-dragon subjects."""


def _check_shape(data):
    if not isinstance(data.get('parts'), list) or not data['parts']:
        raise ValueError('Plan must contain a nonempty parts list.')
    if not isinstance(data.get('required_parts', []), list):
        raise ValueError('required_parts must be a list of strings.')
    data['required_parts'] = [n for n in data.get('required_parts', []) if isinstance(n, str)]
    for p in data['parts']:
        if not isinstance(p, dict) or not isinstance(p.get('name'), str) or not p['name'].strip():
            raise ValueError('Each planned part needs a name.')
        p['name'] = re.sub(r'\W+', '_', p['name'].strip())
        for field in ('center_mm', 'size_mm'):
            v = p.get(field)
            if not isinstance(v, list) or len(v) != 3 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v):
                raise ValueError(p['name'] + ': needs finite three-value center_mm and size_mm.')
            p[field] = [float(x) for x in v]
        if any(x <= 0 for x in p['size_mm']):
            raise ValueError(p['name'] + ': sizes must be positive.')
    for field in ('require_horizontal', 'separate_color_objects'):
        data[field] = bool(data.get(field, True))
    for field in ('target_length_mm', 'max_width_mm', 'max_height_mm'):
        v = data.get(field)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0):
            data[field] = None


def quality_make_plan(cfg, job, base, chat, req):
    opts = settings()
    text = req['instructions']
    prior = None
    if req.get('parent_job'):
        p = ROOT / 'Jobs' / req['parent_job'] / 'quality_plan.json'
        if p.is_file():
            prior = json.loads(p.read_text(encoding='utf-8'))
    best, best_issues, feedback, log = None, None, '', []
    for round_number in range(3):
        raw = chat(cfg, cfg['coding_model'], [
            {'role': 'system', 'content': PLAN_PROMPT},
            {'role': 'user', 'content': base[:14000] + '\nPRIOR PLAN:\n' + json.dumps(prior) + ('\n\nFIX THESE PROBLEMS IN YOUR PREVIOUS PLAN:\n' + feedback if feedback else '')}], 2400)
        (job / 'plan_response.txt').write_text(raw, encoding='utf-8')
        try:
            data = json_object(raw)
            _check_shape(data)
        except ValueError as e:
            feedback = str(e)
            log.append('round %d: %s' % (round_number + 1, feedback))
            continue
        for key, fn in (('target_length_mm', explicit_length), ('max_width_mm', explicit_width), ('max_height_mm', explicit_height)):
            stated = fn(text)
            if stated:
                data[key] = stated
            elif prior and prior.get(key) and not data.get(key):
                data[key] = prior[key]
        names = required_names(text)
        data['required_parts'] = list(dict.fromkeys(data.get('required_parts', []) + names))
        issues = validate_plan(data, text)
        log.append('round %d: %d issue(s)' % (round_number + 1, len(issues)))
        if best is None or len(issues) < len(best_issues):
            best, best_issues = data, issues
        if not issues:
            break
        feedback = '\n'.join('- ' + i for i in issues) + '\nYour previous JSON:\n' + json.dumps({'parts': data['parts']})[:5000]
    if best is None:
        raise RuntimeError('Construction planning failed: ' + feedback)
    fixes = []  # Do not silently rewrite silhouette/pose using generic anatomy rules.
    best['plan_fixes'] = fixes
    best['plan_issues'] = validate_plan(best, text)
    best['plan_log'] = log
    best['length_tolerance_fraction'] = opts.get('length_tolerance_fraction', 0.03)
    best['bed_tolerance_mm'] = opts.get('bed_tolerance_mm', 0.15)
    best['require_closed_parts'] = opts.get('require_closed_parts', True)
    best['requested_counts'] = requested_counts(text)
    best['request'] = text
    (job / 'quality_plan.json').write_text(json.dumps(best, indent=2), encoding='utf-8')
    if best['plan_issues']:
        raise RuntimeError('Reference layout still violates constraints after planning: ' + '; '.join(best['plan_issues']))
    return best


COLORS = {'orange': (1.0, 0.45, 0.05, 1), 'purple': (0.45, 0.15, 0.7, 1), 'green': (0.1, 0.75, 0.2, 1), 'red': (0.8, 0.1, 0.1, 1),
          'blue': (0.1, 0.3, 0.85, 1), 'yellow': (0.95, 0.85, 0.1, 1), 'black': (0.05, 0.05, 0.05, 1), 'white': (0.95, 0.95, 0.95, 1),
          'gray': (0.5, 0.5, 0.5, 1), 'grey': (0.5, 0.5, 0.5, 1), 'brown': (0.4, 0.22, 0.08, 1), 'pink': (0.95, 0.5, 0.7, 1),
          'gold': (0.85, 0.65, 0.1, 1), 'silver': (0.75, 0.75, 0.78, 1), 'teal': (0.0, 0.55, 0.55, 1)}


def color_map(text):
    """Reads lines like 'Orange: head, snout, body, legs, and tail.' -> {'head': rgba, ...}."""
    found = {}
    for m in re.finditer(r'(?im)^[\s\-*]*([a-z]+)\s*:\s*([^\n]+)$', text):
        rgba = COLORS.get(m.group(1).lower())
        if rgba:
            for word in re.findall(r'[a-z]+', m.group(2).lower()):
                if word not in ('and', 'the', 'or', 'with'):
                    found.setdefault(word.rstrip('s'), rgba)
    return found


def _part_color(part, colors):
    words = [w.rstrip('s') for w in re.findall(r'[a-z]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', part['name']).lower())]
    for word in words:
        if word in colors:
            return colors[word]
    rgba = part.get('color_rgba') or part.get('color')
    if isinstance(rgba, list) and len(rgba) in (3, 4) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rgba):
        scale = 255.0 if max(rgba) > 1 else 1.0
        values = [min(max(float(v) / scale, 0.0), 1.0) for v in rgba]
        return tuple(values + [1.0] * (4 - len(values)))
    words = [w.rstrip('s') for w in re.findall(r'[a-z]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', part['name']).lower())]
    for word in words:
        if word in colors:
            return colors[word]
    return colors.get('body', (0.8, 0.5, 0.2, 1))


def _f(v):
    return format(round(float(v), 2), 'g')


def _t(values):
    return '(' + ', '.join(_f(v) for v in values) + ')'


def plan_to_script(plan):
    """Deterministic, always-valid Blender script built directly from the plan using trusted helpers."""
    parts = plan['parts']
    by_name = {p['name']: p for p in parts}
    lo, hi, size = plan_bounds(parts)
    mid = [(lo[i] + hi[i]) / 2 for i in range(3)]
    colors = color_map(plan.get('request', ''))
    lines = ['# Plan-built script: every part comes straight from the construction plan.', 'mats = {}',
             'def mat(name, rgba):', '    if name not in mats:', '        mats[name] = make_material(name, rgba)', '    return mats[name]', '']
    for index, p in enumerate(parts):
        name, c, s = p['name'], p['center_mm'], [max(v, 2.4) for v in p['size_mm']]
        shape = str(p.get('shape', '')).lower() + ' ' + name.lower()
        rgba = _part_color(p, colors)
        m = 'mat(%r, %s)' % ('Color_' + '_'.join(str(int(round(v * 100))) for v in rgba[:3]), _t(rgba))
        axis = max(range(3), key=lambda i: s[i])
        a, b = list(c), list(c)
        a[axis] -= s[axis] / 2
        b[axis] += s[axis] / 2
        radius = min(s[j] for j in range(3) if j != axis) / 2
        parent = _parent(p, by_name)
        anchor = parent['center_mm'] if parent else mid
        dist = lambda q: sum((q[i] - anchor[i]) ** 2 for i in range(3))
        if re.search(r'leg|foot|feet|paw', name, re.I):
            top = max(c[2] + s[2] / 2, (parent['center_mm'][2] if parent else c[2]))
            r = max(min(s[0], s[1]) / 2, 2.5)
            lines.append('part_%d = make_cylinder_between(%r, %s, %s, %s, %s)' % (index, name, _t((c[0], c[1], 0)), _t((c[0], c[1], max(top, 4))), _f(r), m))
        elif re.search(r'body|head|snout|torso|belly|muzzle|eye', name, re.I) and 'box' not in shape:
            lines.append('part_%d = make_ellipsoid(%r, %s, %s, %s)' % (index, name, _t(c), _t(s), m))
        elif 'wing' in shape or 'membrane' in shape or 'fin' in shape:
            side = 'left' if c[1] < 0 else 'right'
            sign = -1 if c[1] < 0 else 1
            root_y = c[1] - sign * (s[1] / 2 + 1.5)
            lines.append('part_%d = make_wing(%r, %r, root_x=%s, root_y=%s, z_bottom=%s, span_mm=%s, chord_mm=%s, thickness_mm=%s, material=%s)' % (
                index, name, side, _f(c[0]), _f(root_y), _f(c[2] - s[2] / 2), _f(s[1] + 1.5), _f(s[0]), _f(min(s[2], 6)), m))
        elif 'taper' in shape or 'cone' in shape or 'tail' in shape or 'horn' in shape:
            start, end = (a, b) if dist(a) <= dist(b) else (b, a)
            lines.append('part_%d = make_tapered_between(%r, %s, %s, %s, %s, %s)' % (index, name, _t(start), _t(end), _f(radius), _f(max(radius * 0.35, 1.2)), m))
        elif 'cylinder' in shape or 'leg' in shape or 'tube' in shape or 'neck' in shape:
            lines.append('part_%d = make_cylinder_between(%r, %s, %s, %s, %s)' % (index, name, _t(a), _t(b), _f(radius), m))
        elif 'box' in shape or 'cube' in shape or 'block' in shape or 'base' in shape:
            lines.append('part_%d = make_box(%r, %s, %s, %s)' % (index, name, _t(c), _t(s), m))
        else:
            lines.append('part_%d = make_ellipsoid(%r, %s, %s, %s)' % (index, name, _t(c), _t(s), m))
    target, width, height = plan.get('target_length_mm'), plan.get('max_width_mm'), plan.get('max_height_mm')
    lines += ['', 'ground_assembly()',
              'fit_assembly(target_length_mm=%s, max_width_mm=%s, max_height_mm=%s)' % (target, width, height),
              'flatten_underside(1.5)',
              'assert_assembly_bounds(target_length_mm=%s, max_width_mm=%s, max_height_mm=%s)' % (target, width, height)]
    return '\n'.join(lines) + '\n'


def quality_geometry_gate(meshes, points, attempt, report):
    import bpy
    import bmesh
    plan = json.loads((attempt.parent / 'quality_plan.json').read_text(encoding='utf-8'))
    (attempt / 'quality_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    dims = [hi[i] - lo[i] for i in range(3)]
    errors = []
    target = plan.get('target_length_mm')
    if target:
        tol = max(0.5, target * float(plan.get('length_tolerance_fraction', 0.03)))
        if abs(dims[0] - target) > tol:
            errors.append('Overall X length is %.1f mm; required %g mm +/-%.1f. Call fit_assembly(target_length_mm=%g, ...) at the end.' % (dims[0], target, tol, target))
    if plan.get('max_width_mm') and dims[1] > plan['max_width_mm'] + 0.1:
        errors.append('Width Y is %.1f mm; maximum %g mm (wings included).' % (dims[1], plan['max_width_mm']))
    if plan.get('max_height_mm') and dims[2] > plan['max_height_mm'] + 0.1:
        errors.append('Height Z is %.1f mm; maximum %g mm.' % (dims[2], plan['max_height_mm']))
    if plan.get('require_horizontal') and dims[2] >= dims[0]:
        errors.append('Model is taller than it is long; it must lie horizontally along X.')
    if abs(lo[2]) > float(plan.get('bed_tolerance_mm', 0.15)):
        errors.append('Lowest Z is %.2f mm; call ground_assembly() so the bottom sits on Z=0.' % lo[2])
    names = {o.name.casefold() for o in meshes}
    for name in plan.get('required_parts', []):
        if name.casefold() not in names:
            errors.append('Missing required mesh object named exactly: ' + name)
    for stem, n in (plan.get('requested_counts') or {}).items():
        have = sum(1 for o in meshes if re.search(stem, o.name, re.I))
        if have < n:
            errors.append('Found %d %s object(s); the request needs %d.' % (have, stem, n))
    if plan.get('separate_color_objects') and len(meshes) < 2:
        errors.append('Keep separate named mesh objects; do not join everything into one.')
    boxes = {}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                bm.transform(obj.matrix_world)
                vs = [v.co for v in bm.verts]
                boxes[obj.name] = ([min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)])
                if plan.get('require_closed_parts', True):
                    open_edges = sum(1 for e in bm.edges if not e.is_manifold)
                    if open_edges:
                        errors.append('%s: %d open/non-manifold edges. Build it with a helper (closed solid).' % (obj.name, open_edges))
                    elif abs(bm.calc_volume(signed=True)) < 1e-3:
                        errors.append(obj.name + ': zero enclosed volume (flat). Give it real thickness.')
            finally:
                bm.free()
        finally:
            evaluated.to_mesh_clear()
    if len(boxes) > 1:
        names_list = list(boxes)
        touching = lambda a, b: all(boxes[a][0][i] <= boxes[b][1][i] + 0.3 and boxes[b][0][i] <= boxes[a][1][i] + 0.3 for i in range(3))
        seen, todo = {names_list[0]}, [names_list[0]]
        while todo:
            cur = todo.pop()
            for other in names_list:
                if other not in seen and touching(cur, other):
                    seen.add(other)
                    todo.append(other)
        for name in names_list:
            if name not in seen:
                errors.append(name + ': floating - it does not touch the rest of the model.')
    report['quality_geometry'] = {'passed': not errors, 'bounds_min_mm': lo, 'bounds_max_mm': hi, 'dimensions_mm': dims, 'issues': errors}
    if errors:
        raise RuntimeError('QUALITY GEOMETRY CHECK FAILED:\n' + '\n'.join(errors[:20]))


def quality_extra_previews(scene, camera, center, radius, attempt):
    import bpy
    from mathutils import Vector
    old = (camera.location.copy(), camera.rotation_euler.copy(), scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y)
    size = min(max(int(settings().get('review_preview_size', 512)), 256), 1024)
    try:
        scene.render.resolution_x = scene.render.resolution_y = size
        for name, direction in [('preview_side.png', (0, -1, 0.05)), ('preview_top.png', (0, 0, 1))]:
            camera.location = center + Vector(direction).normalized() * max(radius * 4, 10)
            camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
            scene.render.filepath = str(attempt / name)
            bpy.ops.render.render(write_still=True)
    finally:
        camera.location, camera.rotation_euler, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y = old
    try:  # small copy of the reference image for the visual reviewer (keeps vision context small)
        req = json.loads((attempt.parent / 'request.json').read_text(encoding='utf-8'))
        ref = attempt.parent / req.get('image_file', '')
        if req.get('image_file') and ref.is_file():
            img = bpy.data.images.load(str(ref))
            w, h = img.size
            k = 448 / max(w, h, 1)
            if k < 1:
                img.scale(max(int(w * k), 1), max(int(h * k), 1))
            img.filepath_raw = str(attempt / 'reference_small.png')
            img.file_format = 'PNG'
            img.save()
    except Exception:
        pass


def quality_visual_review(cfg, attempt, plan, chat):
    from image_fidelity import compare_reference
    return compare_reference(cfg, attempt, plan, chat)

PLAN_PROMPT += '\nREFERENCE FIDELITY: Plan the particular visible subject, not a generic animal or row of primitives. Preserve head/body/tail ratios and appendage roots/pose from the visual brief unless written constraints override them. Fit the envelope by planning dimensions, not squeezing afterward. Centers/sizes are true bounding envelopes; roots need overlap, not tangent boxes. Curved surfaces are built by the coder. For crouched subjects use bent limbs/feet, not universal vertical posts. Locate eyes on the head surface and state horn direction. Written colors override inferred colors. Preserve part counts; exclude forbidden detail.'
