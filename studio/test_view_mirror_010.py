"""AI Modeling Studio 0.010 self-test: mirror check (VIEW_MIRROR_CHECK_V1), misplaced-part label and retry stop.
Run with the studio's launcher Python from the installed folder:  python test_view_mirror_010.py [installed folder]
Uses temporary folders only. If the Christmas-dragon job 20261027-181407-cd67f187 exists, its prepared front/back
pictures are COPIED to a temp folder and checked (the job itself is never modified)."""
import json, shutil, struct, sys, tempfile, zlib, importlib, traceback
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent).resolve()
sys.path.insert(0, str(root))
passed = 0


def check(cond, msg):
    global passed
    if not cond:
        raise AssertionError(msg)
    passed += 1
    print('  ok  ' + msg, flush=True)


def png(path, rows):
    """rows: list of lists of (r,g,b,a). Minimal stdlib PNG writer."""
    h = len(rows); w = len(rows[0])
    raw = b''.join(b'\x00' + bytes(c for px in row for c in px) for row in rows)
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def figure(tail_side, size=120):
    """Body + wings symmetric, tail curl on one image side ('right' or 'left'). Green opaque on transparent."""
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            body = 45 <= x < 75 and 20 <= y < 100
            wings = 20 <= y < 50 and (15 <= x < 45 or 75 <= x < 105) and abs(x - 60) - (y - 20) < 45
            tx = x if tail_side == 'right' else size - 1 - x
            tail = 75 <= tx < 108 and 85 <= y < 100 or 98 <= tx < 108 and 65 <= y < 100
            row.append((40, 140, 40, 255) if body or wings or tail else (255, 255, 255, 0))
        rows.append(row)
    return rows


try:
    print('AI Modeling Studio 0.010 self-test  (folder: %s)' % root, flush=True)
    import hunyuan_autoroute as A
    import hunyuan_bridge as B
    work = Path(tempfile.mkdtemp(prefix='aistudio-0010-'))
    try:
        # ---------- 1. mirror check through the real stage function (spawns ComfyUI's Python) ----------
        def job_with(back_side, name, top=True):
            job = work / name; prep = job / 'autoroute_prepared'; prep.mkdir(parents=True)
            png(prep / 'front.png', figure('right')); png(prep / 'back.png', figure(back_side))
            if top:
                png(prep / 'top.png', figure('right'))
            return job
        panels = [{'view': 'front'}, {'view': 'back'}, {'view': 'top'}]

        job = job_with('right', 'mirrored')              # back drawn with the tail on the SAME side as front = mirrored
        original = (job / 'autoroute_prepared' / 'back.png').read_bytes()
        note = A.check_view_mirroring(job, panels, job / 'view_consistency.log')
        rep = json.loads((job / 'autoroute_prepared' / 'view_consistency.json').read_text(encoding='utf-8'))
        pair = rep['pairs'][0]
        check(pair['verdict'] == 'mirrored' and pair['action'] == 'flipped', 'mirrored back picture detected and flipped (%s)' % note.strip()[:90])
        check((job / 'autoroute_prepared' / 'back.as_drawn.png').read_bytes() == original, 'original back picture kept byte-for-byte as back.as_drawn.png')
        check((job / 'autoroute_prepared' / 'back.png').read_bytes() != original, 'prepared back picture is the flipped one')
        check((job / 'autoroute_prepared' / 'front.png').is_file() and (job / 'autoroute_prepared' / 'top.png').is_file(), 'front and top untouched')
        flipped_once = (job / 'autoroute_prepared' / 'back.png').read_bytes()
        A.check_view_mirroring(job, panels, job / 'view_consistency.log')            # run twice: must not flip back again
        check((job / 'autoroute_prepared' / 'back.png').read_bytes() == flipped_once, 'running the check twice does not double-flip')
        check((job / 'autoroute_prepared' / 'back.as_drawn.png').read_bytes() == original, 'second run keeps the original')
        check((job / 'autoroute_prepared' / 'view_consistency_front_back.png').is_file(), 'evidence picture written')

        job = job_with('left', 'consistent')             # tail on opposite sides = a consistent front/back pair
        before = (job / 'autoroute_prepared' / 'back.png').read_bytes()
        A.check_view_mirroring(job, panels, job / 'view_consistency.log')
        pair = json.loads((job / 'autoroute_prepared' / 'view_consistency.json').read_text(encoding='utf-8'))['pairs'][0]
        check(pair['verdict'] == 'consistent' and pair['action'] == 'none', 'consistent pair left alone')
        check((job / 'autoroute_prepared' / 'back.png').read_bytes() == before and not (job / 'autoroute_prepared' / 'back.as_drawn.png').exists(), 'consistent back picture not modified')

        job = work / 'no_back'; (job / 'autoroute_prepared').mkdir(parents=True); png(job / 'autoroute_prepared' / 'front.png', figure('right'))
        check(A.check_view_mirroring(job, [{'view': 'front'}, {'view': 'left'}], job / 'x.log') == '', 'no front/back pair: check skipped quietly')

        job = work / 'broken'; (job / 'autoroute_prepared').mkdir(parents=True)
        (job / 'autoroute_prepared' / 'front.png').write_bytes(b'not a png'); png(job / 'autoroute_prepared' / 'back.png', figure('right'))
        note = A.check_view_mirroring(job, panels, job / 'v.log')
        check('FAILED' in note and (job / 'autoroute_prepared' / 'view_consistency_error.txt').is_file(), 'a broken picture is reported (not hidden) and does not crash the stage')

        # ---------- 2. real Christmas-dragon sheet, if that job is on this PC (copied, never modified) ----------
        real = root / 'Jobs' / '20261027-181407-cd67f187' / 'autoroute_prepared'
        if (real / 'front.png').is_file() and ((real / 'back.as_drawn.png').is_file() or (real / 'back.png').is_file()):
            job = work / 'real'; prep = job / 'autoroute_prepared'; prep.mkdir(parents=True)
            shutil.copy2(real / 'front.png', prep / 'front.png')
            shutil.copy2(real / 'back.as_drawn.png' if (real / 'back.as_drawn.png').is_file() else real / 'back.png', prep / 'back.png')
            A.check_view_mirroring(job, panels[:2], job / 'v.log')
            pair = json.loads((prep / 'view_consistency.json').read_text(encoding='utf-8'))['pairs'][0]
            check(pair['verdict'] == 'mirrored', 'REAL Christmas sheet: back picture found mirrored (as drawn %.3f vs flipped %.3f)' % (pair['iou_as_drawn'], pair['iou_flipped']))
        else:
            print('  --  real Christmas-dragon job not found; synthetic checks only', flush=True)

        # ---------- 3. retry rules (pure function) ----------
        prog = {'quality': 'standard', 'autoroute': {'panels': [{'view': v, 'conditioning': True} for v in ('front', 'back', 'left')]}}
        mis = lambda view: {'passed': False, 'reasons': [{'code': 'misplaced_part', 'view': view, 'value': 6.5, 'missing': 5.4}], 'views': {}}
        ext = lambda view: {'passed': False, 'reasons': [{'code': 'extra_geometry', 'view': view, 'value': 10.6, 'missing': 3.1}], 'views': {'front': {'iou': .75}, 'back': {'iou': .70}, 'left': {'iou': .72}}}
        f = B.next_fix([mis('top')], prog)
        check(f and 'stop' not in f and f['changes'] == ['new seed'], 'first misplaced part: retry with a new seed')
        f = B.next_fix([mis('top'), mis('top')], prog)
        check(f and 'stop' in f and 'top' in f['stop'], 'misplaced part in the same view twice: stop retrying, say why')
        f = B.next_fix([mis('front'), mis('top')], prog)
        check(f and 'stop' not in f, 'misplaced part in different views: keep trying')
        f = B.next_fix([ext('top'), ext('top')], prog)
        check(f and f.get('exclude_view') == 'back', 'doubled tail rule unchanged (repeated extra -> drop worst view)')
        f = B.next_fix([mis('top'), ext('top')], prog)
        check(f and 'exclude_view' not in f, 'misplaced parts do not count as repeated extra geometry')

        # ---------- 4. verify_geometry: the stop reason reaches the checkpoint-2 note ----------
        job = work / 'retry'; (job / 'attempt_02').mkdir(parents=True); (job / 'autoroute_prepared').mkdir()
        (job / 'attempt_01').mkdir(); (job / 'attempt_01' / 'checks.json').write_text('{}', encoding='utf-8')
        json.dump({'pairs': [{'action': 'flipped', 'verdict': 'mirrored', 'message': 'The back picture looked MIRRORED.'}]}, open(job / 'autoroute_prepared' / 'view_consistency.json', 'w'))
        progress = dict(prog, candidate=2, seed=1, transform={}, geometry_tries=[dict(mis('top'), candidate=1, score=.4, seed=0, quality='standard', transform={}, excluded_views=[])])
        saved = (B.run_geometry_check, B.state, dict(B.CONTEXT))
        try:
            B.run_geometry_check = lambda j, a, p: dict(mis('top'), score=.55)
            B.state = lambda *a, **k: None
            B.CONTEXT['config'] = lambda: {'geometry_check': True}
            report, retry = B.verify_geometry(job, job / 'attempt_02', 2, progress, {})
        finally:
            B.run_geometry_check, B.state = saved[0], saved[1]; B.CONTEXT.clear(); B.CONTEXT.update(saved[2])
        check(retry is False and 'Stopped early' in report['geometry_check_note'], 'checkpoint 2 says why retries stopped')
        check('MIRRORED' in report['geometry_check_note'], 'checkpoint 2 mentions the flipped back picture')
        check(report['geometry_check']['shown_candidate'] == 2, 'best try still shown')
        check(progress['geometry_tries'][-1]['fix_for_next_try'][0].startswith('no more tries'), 'evidence table records the stop')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print('%d checks passed' % passed)
    print('VIEW_MIRROR_SELFTEST_PASSED', flush=True)
except Exception:
    traceback.print_exc()
    print('VIEW_MIRROR_SELFTEST_FAILED', flush=True)
    sys.exit(1)
