# AI_PAINT_STAGE_V1 installer tests (studio 0.010 build 2026-10-28-5). Runs in the studio's launcher Python.
#   python test_ai_paint_stage.py <studio folder> unit
#       options validation, templates, runtime install check, bridge wiring, progress-log format vs the main UI bar parser
#   python test_ai_paint_stage.py <studio folder> real <colour-version folder> <blender exe> <test output folder>
#       REAL AI paint on a COPY of an existing colour version (the job itself is only read). Prints PROGRESS lines.
import sys, json, shutil, tempfile, time, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); mode = sys.argv[2]
sys.path.insert(0, str(root))
ok = True
def check(cond, text):
    global ok
    print(('  ok   ' if cond else '  FAIL ') + text, flush=True); ok = ok and bool(cond)
try:
    import ai_paint_stage as A
    if mode == 'unit':
        st = A.install_status(root)
        check(st['installed'], 'AI paint runtime present at the fixed versions: ' + ('yes' if st['installed'] else '; '.join(st['problems'])))
        counts = A.template_counts(root); check(4 in counts, 'Bambu templates found for filament counts %s (4 needed for the default)' % counts)
        for bad, why in (({'enabled': True, 'filaments': 3}, 'filaments 3'), ({'enabled': True, 'filaments': 10}, 'filaments 10'),
                         ({'enabled': True, 'filaments': True}, 'filaments true'), ({'enabled': True, 'colours': 'x'}, 'colours x'),
                         ({'enabled': 'yes'}, 'enabled "yes"'), ({'extra': 1}, 'unknown key'), ('text', 'not an object')):
            try: A.options(bad, root); check(False, 'rejects ' + why)
            except ValueError: check(True, 'rejects ' + why)
        check(A.options({'enabled': False}, root) is None and A.options(None, root) is None, 'disabled -> picture method only')
        check(A.options({'enabled': True}, root) == {'enabled': True, 'filaments': 4, 'colours': 'studio'}, 'default = 4 filaments, studio colours')
        import hunyuan_color_bridge as HB
        check({'model-bambu-aipaint.3mf', 'aipaint_report.txt', 'aipaint_front.png'} <= HB.FILES, 'bridge serves the AI paint files (exact-hash download only)')
        info = HB.ai_paint_info(); check(info['install']['installed'] == st['installed'] and info['filaments'] == counts, 'bridge reports AI paint availability to the UI')
        js = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8')
        check('AI_PAINT_STAGE_V1' in js and 'ai_paint:apSrc' in js and 'model-bambu-aipaint.3mf' in js, 'colour UI has the colour-source choice and AI paint download')
        # the main UI progress bar (JOB_PROGRESS_BAR_V1, console_tail) must read the AI paint log
        tmp = Path(tempfile.mkdtemp(prefix='aipaint-unit-'))
        try:
            job = tmp / 'job'; cv = job / 'color_versions' / '0123456789abcdef'; cv.mkdir(parents=True)
            (job / 'status.json').write_text('{"state":"RUNNING_BLENDER"}', encoding='utf-8')
            p = A.Progress(cv / 'ai_paint.log'); p.set(37, 'step 2/4 AI paint - AI paint views step 3/10 (50% | test)')
            t = HB.console_tail(job)
            check(t.get('progress') and t['progress']['percent'] == 37 and t['running'], 'main UI progress bar reads the AI paint log: %s' % (t.get('progress') or {}).get('line'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print('AI_PAINT_UNIT_PASSED' if ok else 'AI_PAINT_UNIT_FAILED', flush=True)
    elif mode == 'real':
        src, blender, out = Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
        out.mkdir(parents=True, exist_ok=False); cv = out / 'colour_version_copy'; cv.mkdir()
        names = ['model-colored.blend', 'settings.json', 'reference_review.json', 'reference_masks.npz'] + [p.name for p in src.glob('reference_*.png')]
        for n in names: shutil.copy2(src / n, cv / n)
        print('copied %d files of %s (read-only) to %s' % (len(names), src, cv), flush=True)
        t0 = time.time()
        r = A.run(root, cv, {'enabled': True, 'filaments': 4, 'colours': 'studio'}, blender, versions={'test': 'installer real AI paint test'})
        f = r['filaments']; p = r['paint']
        print('  ok   AI paint finished in %d s: %s colours, %d filaments, palette %s' % (time.time() - t0, f['mode'], f['filaments'], ' '.join(f['palette'])), flush=True)
        print('  ok   paint %s s, graphics memory peak %s MiB, offload %s, turned 180: %s, front check %s' % (p.get('paint_seconds'), p.get('vram_peak_allocated_MiB'), p.get('offload'), p.get('turned_180'), p.get('front_check')), flush=True)
        check(A.verified_result(cv) is not None, 'result files re-read and hash-verified: ' + str(cv / 'model-bambu-aipaint.3mf'))
        print('AI_PAINT_REAL_TEST_PASSED' if ok else 'AI_PAINT_REAL_TEST_FAILED', flush=True)
    else:
        raise SystemExit('unknown mode ' + mode)
except Exception:
    traceback.print_exc(); print('AI_PAINT_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
