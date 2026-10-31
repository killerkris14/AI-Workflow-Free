# AUTO_REVIEW_V1 installer test (0.018). Launcher Python (no numpy). Temporary folders only; your jobs are only READ.
#   python test_auto_review_018.py <studio folder>
import sys, json, tempfile, shutil, queue, traceback, glob, copy
from pathlib import Path
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root)); ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
try:
    import hunyuan_bridge as HY, hunyuan_color_bridge as HB, ai_paint_stage as A
    tmp = Path(tempfile.mkdtemp(prefix='autoreview018-'))
    try:
        conf = {'allow_generated_code_execution': True}; seen = []
        HY.CONTEXT.update(config=lambda: conf, JOBS=tmp, TASKS=queue.Queue(), status=lambda job, name, **kw: seen.append((name, kw.get('note', ''))))
        # ---- model review: a job like your 20261030-132300 (geometry try 1 passed 0.85, automatic 0.4 mm repair passed) ----
        good_p = {'stage': 'model_approval', 'candidate': 1, 'result_type': 'solid', 'transform': {'length_mm': 120.0, 'repair_voxel_mm': 0.4},
                  'geometry_tries': [{'candidate': 1, 'passed': True, 'score': 0.8513, 'reasons': [], 'error': None}]}
        good_r = {'ok': True, 'repair': {'applied': True, 'voxel_mm': 0.4, 'passed_topology_checks': True}, 'auto_repair': {'applied': True, 'voxel_mm': 0.4},
                  'warnings': ['Single-image shape is inferred. No automatic articulation ...']}
        R = lambda p=None, r=None: HY.auto_model_reasons(tmp, p or copy.deepcopy(good_p), r or copy.deepcopy(good_r))
        check(R() == [], 'model review: all checks passed -> approved automatically (the usual warnings text does not stop it)')
        cases = [('articulated', dict(good_p, result_type='articulated'), None), ('mesh checks failed', None, dict(good_r, ok=False)),
                 ('repair failed', None, dict(good_r, repair={'applied': True, 'voxel_mm': 0.4, 'passed_topology_checks': False})),
                 ('automatic repair failed', None, dict(good_r, auto_repair={'applied': False})),
                 ('geometry check failed', dict(good_p, geometry_tries=[{'candidate': 1, 'passed': False, 'score': 0.5, 'reasons': [{'code': 'missing_geometry'}]}]), None),
                 ('geometry check did not run', dict(good_p, geometry_tries=[]), None),
                 ('geometry check error', dict(good_p, geometry_tries=[{'candidate': 1, 'passed': False, 'error': 'Blender crashed'}]), None),
                 ('passing try belongs to another candidate', dict(good_p, candidate=2), None)]
        for name, p, r in cases:
            why = R(p, r); check(len(why) >= 1, 'model review stays manual when: %s -> "%s"' % (name, '; '.join(why)))
        conf['auto_approve_model'] = False; check(R() and 'switched off' in R()[0], 'model review: "auto_approve_model": false in config.json keeps it manual'); conf.pop('auto_approve_model')
        job = tmp / 'job1'; job.mkdir(); p = copy.deepcopy(good_p); HY.save(job / 'hunyuan_progress.json', p); seen.clear()
        HY.auto_model_export(job, p, good_r); q = HY.load(job / 'hunyuan_progress.json'); queued = HY.CONTEXT['TASKS'].get_nowait()
        check(q['stage'] == 'export' and q['transform']['allow_mesh_warnings'] is False and q['solid_repair_approved'] is True and q['auto_review_model']['approved'] is True
              and queued == job and seen and seen[-1][0] == 'QUEUED', 'model review approved: export queued exactly like "Export repaired solid" (strict checks kept), reason recorded')
        # ADVANCED_REVIEW_V1: "Advanced mesh and paint" ticked at upload -> both reviews manual for that job only
        import base64
        PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\0' * 64).decode()
        up = {'image_base64': PNG, 'length_mm': 120, 'quality': 'standard', 'authorize_processing': True, 'ai_paint_filaments': 4}
        ja = tmp / HY.admit(dict(up, advanced_review=True))['id']; jd = tmp / HY.admit(dict(up))['id']; jx = tmp / HY.admit(dict(up, advanced_review='yes'))['id']
        rq = lambda j: json.loads((j / 'request.json').read_text())
        check(rq(ja)['advanced_review'] is True and rq(jd)['advanced_review'] is False and rq(jx)['advanced_review'] is False, 'upload: "Advanced mesh and paint" ticked -> advanced_review true; not ticked / anything else -> false')
        wa = HY.auto_model_reasons(ja, copy.deepcopy(good_p), copy.deepcopy(good_r)); wd = HY.auto_model_reasons(jd, copy.deepcopy(good_p), copy.deepcopy(good_r))
        check(wa and 'Advanced mesh and paint' in wa[0] and wd == [], 'model review: manual for an Advanced upload, automatic for a normal upload (same checks): %s' % wa)
        while not HY.CONTEXT['TASKS'].empty(): HY.CONTEXT['TASKS'].get_nowait()
        src = (root / 'hunyuan_bridge.py').read_text(encoding='utf-8')
        check('reasons = auto_model_reasons(job, progress, report)' in src and "Automatic approval stopped for your review: " in src, 'mesh generation calls the automatic model review; a stop shows the reasons under the state guide')
        # ---- colour review: preview like your real jobs (view fits 0.81-0.96, front/back direction ambiguous, ~30 % mapped) ----
        good_c = {'preview_fingerprint': 'f' * 64, 'statistics': {'excluded_views': {}, 'mapped_faces': 48640, 'fallback_faces': 111444},
                  'alignment': {'orientation_ambiguous': True, 'views': [{'slot': 'left', 'proposed_iou': 0.8076, 'direction_ambiguous': False, 'poor_fit': False},
                                                                       {'slot': 'front', 'proposed_iou': 0.91, 'direction_ambiguous': True}, {'slot': 'back', 'proposed_iou': 0.84, 'direction_ambiguous': True}]},
                  'alignment_evidence': {'views': {'left': {'iou': 0.8089}, 'front': {'iou': 0.9047}, 'back': {'iou': 0.8496}}}}
        cj = tmp / 'cjob'; cj.mkdir(); (cj / 'request.json').write_text(json.dumps({'engine': 'hunyuan', 'ai_paint_filaments': 4}))
        installed = A.install_status(root)['installed']
        C = lambda c=None, cf=None: HB.auto_color_reasons(cj, c or copy.deepcopy(good_c), cf if cf is not None else {})
        if installed: check(C() == [], 'colour review: every picture fits -> approved automatically (ambiguous direction / low picture coverage alone do not stop it)')
        else: check(C() == ['AI paint is not installed'], 'colour review: without the AI paint runtime it stays manual')
        bad = copy.deepcopy(good_c); bad['alignment_evidence']['views']['left']['iou'] = 0.55
        check(any('left picture fits the model poorly' in w for w in C(bad)), 'colour review stays manual when a picture fits poorly (IoU 0.55 < 0.70): %s' % C(bad))
        bad = copy.deepcopy(good_c); bad['statistics']['excluded_views'] = {'back': 'poor fit'}
        check(any('back picture was left out' in w for w in C(bad)), 'colour review stays manual when a picture was left out of the colours')
        bad = copy.deepcopy(good_c); bad['alignment'] = {}; bad['alignment_evidence'] = {}
        check(any('no alignment evidence' in w for w in C(bad)), 'colour review stays manual without alignment evidence')
        check(C(None, {'auto_approve_color': False}) and 'switched off' in C(None, {'auto_approve_color': False})[0], 'colour review: "auto_approve_color": false keeps it manual')
        (cj / 'request.json').write_text(json.dumps({'engine': 'hunyuan', 'ai_paint_custom': True})); check(any('custom AI paint' in w for w in C()), 'colour review stays manual for custom AI paint uploads')
        (cj / 'request.json').write_text(json.dumps({'engine': 'hunyuan', 'ai_paint_filaments': 9, 'nozzle_mm': 0.4}))
        if installed:
            ec = HB.auto_export_config(cj, {'settings': {'views': {}}}, good_c)
            check(ec['bambu'] == {'filaments': HB.bambu_template_filaments(), 'unobserved': 'dominant', 'min_region_mm2': 4.0, 'shading': 'keep'} and ec['accept_uncovered'] is True
                  and ec['approved_preview_fingerprint'] == 'f' * 64 and ec['ai_paint'] == {'enabled': True, 'filaments': 9, 'colours': 'studio', 'nozzle': 0.4},
                  'colour export uses the one-click Export defaults + the upload choices (9 colours, 0.4 nozzle here): %s' % ec['ai_paint'])
        (cj / 'request.json').write_text(json.dumps({'engine': 'hunyuan', 'ai_paint_filaments': 4, 'advanced_review': True}))
        check(C() and 'Advanced mesh and paint' in C()[0], 'colour review: manual for an Advanced upload: %s' % C())
        cs = (root / 'hunyuan_color_bridge.py').read_text(encoding='utf-8')
        check("elif s.get('auto_color') and task.mode in {'align','preview'}:   # AUTO_REVIEW_V1" in cs and "enqueue(job,s,'export',ec)" in cs, 'automatic colour run continues into the export when the review passes')
        # ---- your finished jobs (read-only): what the automatic colour review would decide ----
        n = 0
        for f in sorted(glob.glob(str(root / 'Jobs' / '*' / 'color_versions' / '*' / 'checks.json'))):
            try:
                r = json.loads(Path(f).read_text(encoding='utf-8-sig')); r = r.get('color_workflow', r)
                if not (r.get('alignment') or {}).get('views'): continue
                why = HB.auto_color_reasons(Path(f).parents[2], r, {}); n += 1
                print('  info %s %s: %s' % (Path(f).parents[2].name, Path(f).parent.name, 'would be approved automatically' if not why else 'would stop: ' + '; '.join(why)), flush=True)
            except Exception as e: print('  info %s: could not read (%s)' % (f, e), flush=True)
        print('  info %d finished colour previews on this PC checked (read-only)' % n, flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    pu = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    i_sub = pu.find("const submit=make('button','Prepare image','primary')"); i_adv = pu.find("createTextNode('Advanced mesh and paint')")
    check(0 < i_sub < i_adv and 'form.append(submit,revWrap,message)' in pu and 'advanced_review:revBox.checked' in pu and "localStorage.setItem('aistudio-adv" not in pu,
          'upload form: "Advanced mesh and paint" toggle right under Prepare image, off by default (not remembered), sent with the upload')
    ui = (root / 'hunyuan_color_ui.js').read_text(encoding='utf-8')
    check("if(title==='Download Bambu full-color 3MF (open in Bambu Studio)'){n.id='bambu-download-main'" in ui and 'background:#1e9e57' in ui and 'font-size:19px' in ui,
          'colour page: "Download Bambu full-color 3MF (open in Bambu Studio)" is a big green button')
except Exception:
    traceback.print_exc(); ok = False
print('AUTO_REVIEW_018_TEST_PASSED' if ok else 'AUTO_REVIEW_018_TEST_FAILED', flush=True)
sys.exit(0 if ok else 1)
