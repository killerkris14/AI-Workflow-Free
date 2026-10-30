# Installer test for update 0.016 (studio launcher Python). Temporary folders only; never touches jobs or settings.
#   python test_studio_016.py <studio folder> <test video> <ComfyUI python> <ffmpeg>
import sys, os, json, base64, shutil, tempfile, time, traceback, subprocess
from pathlib import Path
root = Path(sys.argv[1]).resolve(); video, comfy_py, ffmpeg = sys.argv[2], sys.argv[3], sys.argv[4]
sys.path.insert(0, str(root))
ok = True
def check(cond, text):
    global ok
    print(('  ok   ' if cond else '  FAIL ') + text, flush=True); ok = ok and bool(cond)
try:
    tmp = Path(tempfile.mkdtemp(prefix='studio016-'))
    try:
        # 1 ARCHIVE_RETENTION_V1
        import archive_retention as AR
        sroot = tmp / 'studio'; (sroot / 'logs').mkdir(parents=True); arch = sroot / 'Archived-Jobs'; jobs = sroot / 'Jobs'; arch.mkdir(); jobs.mkdir()
        for n in ('20261029-010101-aaaaaaaa', '20261029-010101-bbbbbbbb', '20261029-010101-cccccccc'): (arch / n).mkdir(); (arch / n / 'status.json').write_text('{}')
        (arch / 'not-a-job').mkdir(); (jobs / '20261029-020202-dddddddd').mkdir(); (jobs / '20261029-020202-dddddddd' / '.archived_at').write_text('1')
        (sroot / 'archive_retention.json').write_text(json.dumps({'enabled': True, 'hours': 24, 'keep': ['20261029-010101-cccccccc']}))
        t0 = time.time()
        d1 = AR.scan(arch, jobs, now=t0, root=sroot)
        check(d1 == [] and (arch / '20261029-010101-aaaaaaaa' / '.archived_at').is_file(), 'first scan only records the archive time (nothing deleted)')
        check(not (jobs / '20261029-020202-dddddddd' / '.archived_at').exists(), 'a restored job loses its archive time')
        d2 = AR.scan(arch, jobs, now=t0 + 23.9 * 3600, root=sroot)
        check(d2 == [], 'nothing deleted before 24 h')
        d3 = AR.scan(arch, jobs, now=t0 + 24.1 * 3600, root=sroot)
        check(sorted(d3) == ['20261029-010101-aaaaaaaa', '20261029-010101-bbbbbbbb'], 'after 24 h the archived jobs are deleted: %s' % d3)
        check((arch / '20261029-010101-cccccccc').is_dir() and (arch / 'not-a-job').is_dir() and (jobs / '20261029-020202-dddddddd').is_dir(), 'kept: job on the keep list, non-job folder, current jobs')
        (sroot / 'archive_retention.json').write_text(json.dumps({'enabled': False}))
        (arch / '20261029-030303-eeeeeeee').mkdir()
        check(AR.scan(arch, jobs, now=t0 + 99 * 3600, root=sroot) == [] and (arch / '20261029-030303-eeeeeeee').is_dir(), 'switched off in archive_retention.json -> nothing deleted')
        check('DELETED archived job 20261029-010101-aaaaaaaa' in (sroot / 'logs' / 'archive-retention.log').read_text(), 'every deletion is written to logs/archive-retention.log')
        # 2 VIDEO_VIEWS_V1 through the real admit() code path (ffmpeg + ComfyUI Python)
        import hunyuan_bridge as HY, queue
        os.environ['AISTUDIO_FFMPEG'] = ffmpeg; os.environ['AISTUDIO_COMFY_PYTHON'] = comfy_py
        jroot = tmp / 'jobs'; jroot.mkdir()
        HY.CONTEXT.update(config=lambda: {'allow_generated_code_execution': True}, JOBS=jroot, TASKS=queue.Queue(), status=lambda job, name, **kw: None)
        data = base64.b64encode(Path(video).read_bytes()).decode()
        t = time.time(); res = HY.admit({'video_base64': data, 'video_name': 'test_turntable.mp4', 'length_mm': 120, 'quality': 'standard', 'authorize_processing': True})
        job = jroot / res['id']; info = json.loads((job / 'video_source' / 'video_views.json').read_text())
        check((job / 'reference.png').is_file() and json.loads((job / 'request.json').read_text()).get('source') == 'video', 'video upload made a job with a reference sheet (%.1f s)' % (time.time() - t))
        frames = {k: v['frame_index'] for k, v in info['views'].items()}
        check(info['turn_frames'] == 30 and frames == {'front': 0, 'side_a': 7, 'back': 15, 'side_b': 23}, 'turntable test video: turn length %s frames, picked %s (expected 30; 0/7/15/23)' % (info['turn_frames'], frames))
        check(not list(jroot.glob('.video-*')) and not list((job / 'video_source').glob('source.*')), 'no temporary video files left behind (source video not kept)')
        try: HY.admit({'video_base64': base64.b64encode(b'not a video' * 50).decode(), 'video_name': 'bad.mp4', 'authorize_processing': True}); check(False, 'a broken video is refused')
        except ValueError as e: check('FAIL_REASON' in str(e), 'a broken video is refused with a FAIL_REASON file: ' + str(e)[:120])
        for f in (root / 'logs').glob('video-*-FAIL_REASON.txt'):
            if f.stat().st_mtime >= t - 5: f.unlink()          # the test's own failure report only
        # 3 WHITE_TIP_CROP_FIX_V1 in ComfyUI's Python on the video sheet and on a white-tip drawing
        r = subprocess.run([comfy_py, str(root / 'test_fd_016.py'), str(root), str(job / 'reference.png')], capture_output=True, text=True, timeout=300)
        for line in (r.stdout + r.stderr).strip().splitlines(): print('    ' + line)
        check(r.returncode == 0 and 'FD_016_PASSED' in r.stdout, 'figure detection keeps white parts that touch the background')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # 4 page files carry the 0.016 changes
    ui = (root / 'ui.html').read_text(encoding='utf-8'); shell = (root / 'studio_shell_ui.js').read_text(encoding='utf-8')
    portal = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8'); colour = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8'); bridge = (root / 'hunyuan_color_bridge.py').read_text(encoding='utf-8')
    check("fold('Full job status'" not in ui and "['Full job status','status']" not in portal, 'Full job status buttons removed')
    check('Killerkris14 Made it' in shell and "'Prompt Builder'" in shell and "'.3mf Repair'" in shell and "'Old Blender'" in shell, 'header text + tabs Prompt Builder / Image to 3D / .3mf Repair / Old Blender')
    check("studio_shell_ui.js" in bridge and 'archive_retention.start' in bridge, 'studio serves the new tabs script and starts archive auto-delete')
    check("'-texture-master.3mf'" not in colour and 'AI_PAINT_ONLY_V1' in colour, 'texture-master download removed, AI paint is the Bambu file')
    check("'9 colours','master'" in portal and 'all llms are on demand and close when done running.' in portal, 'upload form texts (4 / 9 colour toggle)')
    print('STUDIO_016_TEST_PASSED' if ok else 'STUDIO_016_TEST_FAILED', flush=True)
except Exception:
    traceback.print_exc(); print('STUDIO_016_TEST_ERROR', flush=True); ok = False
sys.exit(0 if ok else 1)
