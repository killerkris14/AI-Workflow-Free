# FAILURE REPORT v3 - compact, readable failure reports (one file per job).
import json
import re
from pathlib import Path

HINTS = [
    (r'finite coordinates of length 2|outline_xy', 'make_solid_profile outline points must be (x, y) pairs. Use z_bottom for height, or use make_wing for wings.'),
    (r'unexpected keyword argument', 'A helper was called with a wrong argument name. Use the exact signatures in the smart geometry contract.'),
    (r'missing \d+ required positional', 'A helper call is missing arguments. Use the exact signatures in the smart geometry contract.'),
    (r'is not defined', 'The script used a name that does not exist. Define it first or use a provided helper.'),
    (r'floating', 'Move floating parts so they overlap their parent by 1-2 mm.'),
    (r'target length|spans? .* mm', 'Resize/move parts so the whole model matches the target length, then call fit_assembly(...).'),
    (r'redefine|overwrite trusted', 'Call the provided helpers; do not define functions with the same names.'),
    (r'repeated an earlier', 'The AI coder returned the same script again. Press Retry, or simplify the request.'),
    (r'Visual review rejected', 'Fix the visible problems listed by the reviewer.'),
    (r'timed out', 'Blender took too long. Reduce segment counts or part count.'),
    (r'Model server|Connection refused|urlopen error', 'The model server is not reachable. Check that llama-server is running.'),
]


def fix_hint(text):
    for pattern, hint in HINTS:
        if re.search(pattern, text or '', re.I):
            return hint
    return ''


def condense_error(text, limit=900):
    """Keep only the useful part of a traceback: model.py lines and the final exception."""
    text = (text or '').strip()
    if not text:
        return ''
    if 'Traceback (most recent call last)' not in text:
        return text[-limit:]
    lines = text.splitlines()
    keep = []
    for i, line in enumerate(lines):
        if 'File "' in line and ('model.py' in line or '<string>' in line):
            keep.append(line.strip())
            if i + 1 < len(lines) and not lines[i + 1].lstrip().startswith('File '):
                keep.append('    ' + lines[i + 1].strip())
    starts = [i for i, l in enumerate(lines) if re.match(r'^[A-Za-z_.]*(Error|Exception|Interrupt)\b', l.strip())]
    tail = lines[starts[-1]:] if starts else lines[-1:]
    keep += [l.rstrip() for l in tail if l.strip()][:12]
    out = '\n'.join(dict.fromkeys(keep))
    return out[-limit:]


def _read(path, limit=None):
    try:
        text = Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    return text if limit is None else text[:limit]


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _log_tail(path, count=15):
    noise = ('Read prefs', 'Blender quit', 'Warning: Unable to', 'Color management', 'found bundled python', 'register_class')
    lines = [l.rstrip() for l in _read(path).splitlines() if l.strip() and not any(n in l for n in noise)]
    return lines[-count:]


def _attempt_section(attempt, previous_script):
    lines = ['', '=== ' + attempt.name.upper().replace('_', ' ') + ' ===']
    fb = _json(attempt / 'repair_feedback.json')
    checks = _json(attempt / 'checks.json')
    script = _read(attempt / 'model.py')
    source = fb.get('source') or ('plan-built' if script.startswith('# Plan-built') else 'AI coder')
    lines.append('Source: ' + source)
    stage = fb.get('stage') or checks.get('phase') or ('generation' if (attempt / 'generation_error.txt').exists() else '?')
    if checks.get('ok') and not fb:
        stage = 'passed'
    lines.append('Stage: ' + str(stage))
    err = fb.get('exception') or condense_error(_read(attempt / 'generation_error.txt') or checks.get('error', ''))
    if err:
        lines.append('Error:')
        lines += ['  ' + l for l in err.splitlines()]
    hint = fb.get('fix_hint') or fix_hint(err)
    if hint:
        lines.append('Fix hint: ' + hint)
    dims = checks.get('dimensions_mm')
    if dims:
        lines.append('Measured size (L x W x H mm): ' + ' x '.join('%.1f' % d for d in dims))
    for title, items in (('Geometry issues', checks.get('quality_geometry', {}).get('issues', [])),
                         ('Visual review issues', (checks.get('visual_review') or {}).get('issues', [])),
                         ('Helper warnings', checks.get('helper_warnings', []))):
        if items:
            lines.append(title + ':')
            lines += ['  - ' + str(i) for i in items[:12]]
    if script and script != previous_script:
        lines.append('Script (%d lines):' % len(script.splitlines()))
        lines += ['  ' + l for l in script[:6000].splitlines()]
        if len(script) > 6000:
            lines.append('  ... (truncated)')
    elif script:
        lines.append('Script: same as previous attempt.')
    else:
        raw = _read(attempt / 'raw_response.txt', 1500)
        if raw:
            lines.append('Raw AI response (first 1500 chars):')
            lines += ['  ' + l for l in raw.splitlines()]
    tail = _log_tail(attempt / 'blender.log')
    if tail and stage not in ('passed', 'generation'):
        lines.append('Blender log (last lines):')
        lines += ['  ' + l for l in tail]
    return lines, script or previous_script


def build_job_report(job):
    job = Path(job)
    st = _json(job / 'status.json')
    req = _json(job / 'request.json')
    plan = _json(job / 'quality_plan.json')
    final_error = condense_error(_read(job / 'error.txt') or st.get('error', ''), 600)
    lines = ['AI WORKFLOW FAILURE REPORT', 'Job: ' + job.name, 'State: ' + str(st.get('state', '?'))]
    if req.get('retry_of'):
        lines.append('Retry of: ' + req['retry_of'])
    if req.get('parent_job'):
        lines.append('Revision of: ' + req['parent_job'])
    if final_error:
        lines += ['', 'FINAL ERROR:'] + ['  ' + l for l in final_error.splitlines()]
        hint = fix_hint(final_error)
        if hint:
            lines.append('Fix hint: ' + hint)
    text = req.get('instructions', '')
    lines += ['', 'REQUEST:', '  ' + text[:1500].replace('\n', '\n  ') + (' ...' if len(text) > 1500 else '')]
    if plan.get('parts'):
        lines += ['', 'PLAN: target %s mm long, max width %s, max height %s' % (
            plan.get('target_length_mm'), plan.get('max_width_mm'), plan.get('max_height_mm'))]
        for p in plan['parts']:
            c, s = p.get('center_mm', []), p.get('size_mm', [])
            lines.append('  %-18s %-10s center %s size %s' % (p.get('name'), p.get('shape', ''),
                         ','.join('%g' % v for v in c), 'x'.join('%g' % v for v in s)))
        for title, key in (('Plan auto-fixes', 'plan_fixes'), ('Plan issues left', 'plan_issues')):
            if plan.get(key):
                lines.append(title + ':')
                lines += ['  - ' + str(i) for i in plan[key]]
    previous = ''
    for attempt in sorted(job.glob('attempt_*')):
        if attempt.is_dir():
            section, previous = _attempt_section(attempt, previous)
            lines += section
    return '\n'.join(lines) + '\n'


def write_attempt_failure(job, attempt, stage, error, root_failure=''):
    """Store concise per-attempt feedback, then refresh the job report."""
    path = Path(attempt) / 'repair_feedback.json'
    data = _json(path)
    data.setdefault('stage', stage)
    data.setdefault('exception', condense_error(error))
    data.setdefault('fix_hint', fix_hint(error))
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    write_job_failure(job, '')


def write_job_failure(job, error=''):
    job = Path(job)
    if error and not (job / 'error.txt').exists():
        (job / 'error.txt').write_text(error, encoding='utf-8')
    report = build_job_report(job)
    (job / 'FAIL_REASON.txt').write_text(report, encoding='utf-8')
    return report

# CURRENT_STAGE_FAILURE_REPORT_V1
_original_build_job_report_focus_v1 = build_job_report
_original_write_job_failure_focus_v1 = write_job_failure

def build_job_report(job, *args, **kwargs):
    from current_failure_focus import focused_report
    current = focused_report(job)
    return current if current is not None else _original_build_job_report_focus_v1(job, *args, **kwargs)

def write_job_failure(job, *args, **kwargs):
    from current_failure_focus import focused_report, save_current_report
    hint = args[0] if args and isinstance(args[0], str) else kwargs.get('error', '')
    current = focused_report(job, hint)
    try:
        previous = _original_write_job_failure_focus_v1(job, *args, **kwargs)
    except Exception:
        if current is None:
            raise
        save_current_report(job, current)
        return current
    if current is not None:
        save_current_report(job, current)
        return current
    return previous
