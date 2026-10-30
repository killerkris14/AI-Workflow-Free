# STAGE_UNIFY_V1 installer test ("AI UI Unifi" 0.015). Runs in the studio's launcher Python on temporary job folders only.
#   python test_stage_unify.py <studio folder>
import sys, json, tempfile, shutil, traceback
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
ok = True
def check(cond, text):
    global ok
    print(('  ok   ' if cond else '  FAIL ') + text, flush=True); ok = ok and bool(cond)
try:
    import hunyuan_color_bridge as HB
    check(len(HB.STAGES) == 12, 'one stage list with 12 stages: ' + ' / '.join(HB.STAGES))
    tmp = Path(tempfile.mkdtemp(prefix='stage-unify-'))
    try:
        V = '0123456789abcdef'
        def job(state, stage, phase=None, auto=True, **extra):
            j = tmp / ('20261028-000000-%08x' % (abs(hash((state, stage, phase, auto, str(extra)))) % 16**8)); shutil.rmtree(j, ignore_errors=True); j.mkdir()
            (j / 'request.json').write_text(json.dumps({'engine': 'hunyuan'}))
            (j / 'status.json').write_text(json.dumps(dict({'id': j.name, 'state': state, 'engine': 'hunyuan', 'note': 'test'}, **extra)))
            p = {'stage': stage}
            if auto: p['autoroute'] = {'route': 'mv', 'panels': []}
            if phase:
                p.update(color_protocol=2, color_version=V)
                (j / 'reference_color_state_v2.json').write_text(json.dumps({'protocol': 2, 'job_id': j.name, 'revision': 1, 'version': V, 'phase': phase, 'settings': {'views': {}}}))
            (j / 'hunyuan_progress.json').write_text(json.dumps(p))
            return j
        cases = [(('QUEUED', 'prepare', None, False), 1, 'queued'), (('PREPROCESSING_IMAGE', 'route_analyze', None), 2, 'running'),
                 (('WAITING_IMAGE_APPROVAL', 'route_review', None), 3, 'waiting'), (('PREPROCESSING_IMAGE', 'prepare', None), 2, 'running'),
                 (('WAITING_IMAGE_APPROVAL', 'image_approval', None), 3, 'waiting'), (('QUEUED', 'generate', None), 4, 'queued'),
                 (('GENERATING_MESH', 'generate', None), 4, 'running'), (('RUNNING_BLENDER', 'generate', None), 5, 'running'),
                 (('RUNNING_BLENDER', 'reprocess', None), 5, 'running'), (('WAITING_MODEL_APPROVAL', 'model_approval', None), 6, 'waiting'),
                 (('WAITING_JOINT_DESIGN', 'joint_design', None), 6, 'waiting'), (('RUNNING_BLENDER', 'export', None), 7, 'running'),
                 (('SUCCEEDED', 'finished', None), 7, 'done'), (('RUNNING_BLENDER', 'color_prepare', 'preparing'), 8, 'running'),
                 (('WAITING_MODEL_APPROVAL', 'color_mask_approval', 'mask_review'), 8, 'waiting'), (('RUNNING_BLENDER', 'color_align', 'aligning'), 9, 'running'),
                 (('RUNNING_BLENDER', 'color_preview', 'previewing'), 10, 'running'), (('WAITING_MODEL_APPROVAL', 'color_approval', 'preview_review'), 11, 'waiting'),
                 (('RUNNING_BLENDER', 'color_export', 'exporting'), 12, 'running'), (('SUCCEEDED', 'finished', 'complete'), 12, 'done'),
                 (('FAILED', 'generate', None), 4, 'stopped'), (('FAILED', 'color_failed', 'failed'), 8, 'stopped')]
        for args, want, kind in cases:
            d = HB.stage_info(job(*args))
            check(d['count'] == 12 and d['index'] == want and d['kind'] == kind,
                  '%-24s %-20s %-15s -> stage %2d of %d (%s)%s' % (args[0], args[1], args[2] or '', d['index'], d['count'], d['kind'], '' if d['index'] == want and d['kind'] == kind else '  EXPECTED %d (%s)' % (want, kind)))
        d = HB.stage_info(job('SUCCEEDED', 'finished', 'complete'))
        check(d['overall_percent'] == 100.0, 'finished workflow = 100% overall')
        d = HB.stage_info(job('RUNNING_BLENDER', 'export', None))
        # the task share comes from the newest task log (on a real PC that can be the ComfyUI service log), so compute the expectation from it
        t = d['task'].get('progress') if d['task'].get('running') else None; tp = t['percent'] if t else 0
        want = round(100.0 * (6 + tp / 100.0) / 12, 1)
        check(abs(d['overall_percent'] - want) < 0.05, 'stage 7 running: 6 of 12 finished + %s percent of the current task (%s) = %s percent overall (got %s)' % (tp, (t or {}).get('line', 'no task log')[:60], want, d['overall_percent']))
        j = tmp / '20261028-000000-proc0001'; j.mkdir(); (j / 'status.json').write_text(json.dumps({'id': j.name, 'state': 'GENERATING_SCRIPT'}))
        check(HB.stage_info(j) == {'engine': 'procedural'}, 'text-to-Blender jobs keep their own 7-stage list')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ui = (root / 'ui.html').read_text(encoding='utf-8'); lay = (root / 'job_layout_ui.js').read_text(encoding='utf-8'); por = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    check(ui.count('STAGE_UNIFY_V1') == 3, 'ui.html: note-only changes do not rebuild, panels kept, no legacy list for Hunyuan jobs')
    check('studio-stage-block' in lay and '/hunyuan-color/stage/' in lay and 'STAGE_UNIFY_V1' in lay, 'job_layout_ui.js: fixed 12-stage block with stage bar + task bar')
    check(por.count('STAGE_UNIFY_V1') == 3 and 'guided-color-stages\');[' not in por, 'hunyuan_portal_ui.js: current-stage card updated in place, no second stage list')
    print('STAGE_UNIFY_TEST_PASSED' if ok else 'STAGE_UNIFY_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('STAGE_UNIFY_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
