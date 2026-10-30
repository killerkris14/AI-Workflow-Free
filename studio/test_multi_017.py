# MULTI_PICTURE_AI_PAINT_V1 installer test (0.017). Launcher Python; temporary folders only; jobs are only read.
#   python test_multi_017.py <studio folder> <texture_paint python> <blender>
# Real-runtime check (when the mammoth job and the saved side run of the 2026-10-29 back-picture test are on this PC):
# Blender prepares the right picture, the texture_paint Python combines it with the stored front run, and the result must be
# the option C the user picked (same numbers as the test).
import sys, os, json, shutil, subprocess, tempfile, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); tp_py, blender = sys.argv[2], sys.argv[3]; sys.path.insert(0, str(root)); ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
try:
    import ai_paint_stage as A
    src = (root / 'ai_paint_stage.py').read_text(encoding='utf-8')
    check('MULTI_PICTURE_AI_PAINT_V1' in src and 'ai_paint_side_prep.py' in A.SCRIPTS and 'ai_paint_combine.py' in A.SCRIPTS, 'AI paint stage has the side-picture step and checks its scripts')
    check(A.install_status(root)['installed'], 'AI paint runtime + all scripts present: %s' % A.install_status(root)['problems'])
    check(A.multi_report({'used': False, 'failed': True, 'side_direction': 'right', 'error': 'x', 'fail_reason': 'y'})[0].startswith('PICTURES USED: FRONT ONLY'), 'a failed side run is reported as FRONT ONLY, never as a multi-picture result')
    tmp = Path(tempfile.mkdtemp(prefix='multi017-'))
    try:
        # side_slot follows the APPROVED direction (the user's labels), not the slot name
        f = tmp / 'cv'; f.mkdir()
        (f / 'reference_review.json').write_text(json.dumps({'views': [{'slot': 'front', 'direction_hint': 'front'}, {'slot': 'left', 'direction_hint': 'left'}]}))
        (f / 'reference_left.png').write_bytes(b'x'); (f / 'reference_front.png').write_bytes(b'x')
        (f / 'settings.json').write_text(json.dumps({'settings': {'views': {'left': {'direction': 'right'}}}}))
        check(A.side_slot(f) == {'slot': 'left', 'direction': 'right'}, 'side picture found by its approved direction (slot "left" approved as "right")')
        (f / 'settings.json').write_text(json.dumps({'settings': {'views': {'left': {'direction': 'top'}}}}))
        check(A.side_slot(f) is None, 'no left/right picture -> front picture only (as in 0.016)')
        job = root / 'Jobs' / '20261029-115943-62474460'; runs = sorted((root / 'tests').glob('back-picture-*/raw_runs/side'))
        st = json.loads((job / 'reference_color_state_v2.json').read_text(encoding='utf-8')) if (job / 'reference_color_state_v2.json').is_file() else {}
        cv = job / 'color_versions' / str(st.get('version')); fw = cv / 'ai_paint_work'
        if runs and (fw / 'tri_rgb.npy').is_file() and (cv / 'model-colored.blend').is_file():
            sd = tmp / 'side'; prep = sd / 'prep'
            r = subprocess.run([blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(root / 'ai_paint_side_prep.py'), '--', str(root), str(cv), str(prep), 'left', 'same'],
                               capture_output=True, text=True, timeout=900)
            check(r.returncode == 0 and 'SIDE_PREP_PASSED' in r.stdout, 'Blender prepares the mammoth right picture (real studio Blender)')
            w = tmp / 'front'; shutil.copytree(fw / 'prep', w / 'prep'); shutil.copy2(fw / 'tri_rgb.npy', w / 'tri_rgb_front.npy')
            run_ = sd / 'run'; run_.mkdir(); [shutil.copy2(runs[-1] / n, run_ / n) for n in ('tri_rgb.npy', 'paint.json')]
            r = subprocess.run([tp_py, str(root / 'ai_paint_combine.py'), str(w), str(run_), str(prep), str(sd / 'out'), '0'], capture_output=True, text=True, timeout=1800)
            cj = json.loads((sd / 'out' / 'combine.json').read_text(encoding='utf-8')) if (sd / 'out' / 'combine.json').is_file() else {'error': r.stderr[-500:]}
            m = (cj.get('match_to_your_pictures_deltaE') or {}).get('combined') or {}
            check(r.returncode == 0 and cj.get('method') == 'mirror' and (cj.get('shape_check') or {}).get('other_side_with_mirror_partner_percent', 0) >= 99,
                  'mammoth: shape check %s %% -> right picture mirrored onto the left (option C)' % (cj.get('shape_check') or {}).get('other_side_with_mirror_partner_percent'))
            want = {'front': 10.81, 'left': 7.06, 'back': 7.2}
            check(all(abs(m.get(k, 99) - v) <= 0.05 for k, v in want.items()), 'mammoth: same result as the option C you picked (match to your pictures %s, test %s)' % (m, want))
        else:
            print('  note mammoth job or the saved side run of the back-picture test not found - real-runtime check skipped', flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('MULTI_017_TEST_PASSED' if ok else 'MULTI_017_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('MULTI_017_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
