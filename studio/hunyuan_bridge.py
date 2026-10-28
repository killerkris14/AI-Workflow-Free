# SOLID MESH REVIEW RECOVERY v1
# ON-DEMAND COMFY LEASE v1
"""Hunyuan portal adapter: stdlib HTTP client and persistent human checkpoints."""
import base64,copy,io,json,math,mimetypes,os,re,secrets,shutil,subprocess,time,traceback,urllib.parse,urllib.request,urllib.error,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CONTEXT={}
WAITING={'WAITING_IMAGE_APPROVAL','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'}

def cfg():return json.loads((ROOT/'hunyuan_settings.json').read_text(encoding='utf-8'))
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):
    path=Path(path);temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(path)
def state(job,name,**kw):
    print('[Hunyuan '+Path(job).name+'] '+name+': '+str(kw.get('note','')),flush=True)
    CONTEXT['status'](Path(job),name,**kw)
def request(route,body=None,timeout=60):
    url=cfg()['comfy_url'].rstrip('/')+route
    req=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
    except urllib.error.HTTPError as error:raise RuntimeError('ComfyUI HTTP %s: %s'%(error.code,error.read().decode(errors='replace')[:5000]))
def upload(path,subfolder):
    path=Path(path);boundary='----Portal'+uuid.uuid4().hex;pieces=[]
    for key,value in [('subfolder',subfolder),('type','input'),('overwrite','false')]:
        pieces.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+'\r\n').encode())
    pieces += [('--'+boundary+'\r\nContent-Disposition: form-data; name="image"; filename="'+path.name+'"\r\nContent-Type: '+(mimetypes.guess_type(path.name)[0] or 'application/octet-stream')+'\r\n\r\n').encode(),path.read_bytes(),('\r\n--'+boundary+'--\r\n').encode()]
    req=urllib.request.Request(cfg()['comfy_url'].rstrip('/')+'/upload/image',data=b''.join(pieces),headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(req,timeout=120) as response:data=json.load(response)
    return '/'.join(filter(None,[data.get('subfolder',''),data['name']]))
def records(value,suffix):
    found=[]
    if isinstance(value,dict):
        if isinstance(value.get('filename'),str) and value['filename'].lower().endswith(suffix):found.append(value)
        else:
            for v in value.values():found+=records(v,suffix)
    elif isinstance(value,list):
        for v in value:found+=records(v,suffix)
    elif isinstance(value,str) and value.lower().endswith(suffix):
        clean=value.replace('\\','/');p=Path(clean)
        if not p.is_absolute() and '..' not in p.parts:found.append({'filename':p.name,'subfolder':p.parent.as_posix() if p.parent!=Path('.') else '', 'type':'output'})
    return found

def download(record,path):
    params={k:str(record.get(k,'output' if k=='type' else '')) for k in ('filename','subfolder','type')}
    if params['type'] not in {'input','output','temp'}:raise ValueError('Unexpected ComfyUI file type.')
    url=cfg()['comfy_url'].rstrip('/')+'/view?'+urllib.parse.urlencode(params)
    with urllib.request.urlopen(url,timeout=180) as response:content=response.read()
    if not content:raise RuntimeError('ComfyUI returned an empty output.')
    Path(path).write_bytes(content)

def run_graph(job, attempt, graph, output_id, suffix, phase):
    info = request('/object_info')
    for node in graph.values():
        if node['class_type'] not in info:
            raise RuntimeError('ComfyUI node missing: ' + node['class_type'] + '. Restart/update ComfyUI after installing this patch.')
    result = request('/prompt', {'prompt': graph, 'client_id': 'portal-' + job.name})
    if result.get('node_errors'):
        raise RuntimeError('ComfyUI rejected nodes: ' + json.dumps(result['node_errors'])[:5000])
    prompt_id = result.get('prompt_id')
    if not prompt_id:
        raise RuntimeError('ComfyUI returned no prompt ID.')
    save(attempt / ('comfy_' + phase + '.json'), {'prompt_id': prompt_id, 'submitted': time.time(), 'graph': graph})
    start = time.monotonic()
    last = -1
    while time.monotonic() - start < float(cfg().get('timeout_seconds', 3600)):
        history = request('/history/' + urllib.parse.quote(prompt_id))
        entry = history.get(prompt_id)
        if entry:
            save(attempt / ('history_' + phase + '.json'), entry)
            status = entry.get('status', {})
            if status.get('status_str') == 'error':
                raise RuntimeError('ComfyUI execution failed: ' + json.dumps(status.get('messages', status))[-6500:])
            output = entry.get('outputs', {}).get(str(output_id), {})
            found = records(output, suffix)
            if found:
                return found[0]
            if status.get('completed'):
                raise RuntimeError('ComfyUI completed without expected ' + suffix + ' output. See history_' + phase + '.json.')
        elapsed = int(time.monotonic() - start)
        if elapsed // 10 != last:
            last = elapsed // 10
            state(job, 'PREPROCESSING_IMAGE' if phase.startswith('prepare') == True else 'GENERATING_MESH', attempt=int(attempt.name.split('_')[-1]), note='ComfyUI ' + phase + ' request active; ' + str(elapsed) + ' seconds elapsed.', comfy_prompt_id=prompt_id)
        time.sleep(2)
    raise RuntimeError('ComfyUI ' + phase + ' request timed out; prompt ' + prompt_id + ' may still be running. Do not resubmit until checked in ComfyUI.')

def preparation_graph(image,invert=False,use_original=False,prefix='portal/prepared'):
    info=request('/object_info')
    for name in ('LoadBackgroundRemovalModel','RemoveBackground','PortalPrepareSubject'):
        if name not in info:
            raise RuntimeError('ComfyUI node missing: '+name+'. Restart the configured ComfyUI instance after installing the portal node.')
    node=info['LoadBackgroundRemovalModel']
    inputs=node.get('input',{})
    schema=None
    for group in ('required','optional'):
        if 'bg_removal_name' in inputs.get(group,{}):
            schema=inputs[group]['bg_removal_name'];break
    def extract_options(value):
        if isinstance(value,dict):
            for key in ('options','values','choices'):
                if key in value:return extract_options(value[key])
            return []
        if isinstance(value,(list,tuple)):
            # Legacy: [[filenames], metadata]; modern: ['COMBO', {'options': filenames}].
            if value and all(isinstance(v,str) for v in value):
                return [v for v in value if v not in {'COMBO','STRING','IMAGE','MASK','BACKGROUND_REMOVAL'}]
            result=[]
            for part in value:
                for candidate in extract_options(part):
                    if candidate not in result:result.append(candidate)
            return result
        return []
    options=extract_options(schema)
    matches=[value for value in options if value.replace('\\','/').split('/')[-1].casefold()=='birefnet.safetensors']
    settings=cfg()
    comfy_root=Path(settings.get('comfy_root',''))
    expected=comfy_root/'models'/'background_removal'/'birefnet.safetensors'
    diagnostic={'comfy_url':settings.get('comfy_url'),'configured_comfy_root':str(comfy_root),
                'model_path':str(expected),'model_exists':expected.is_file(),
                'model_bytes':expected.stat().st_size if expected.is_file() else None,
                'raw_bg_removal_schema':schema,'available_models':options}
    (ROOT/'birefnet_discovery.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8')
    if not matches:
        if expected.is_file():
            reason='The model exists on disk, but the server is not listing it. Restart ComfyUI from the configured installation; another ComfyUI instance may be using this port.'
        else:
            reason='The model is absent from the configured model folder. Verify the ComfyUI folder chosen during installation before downloading another copy.'
        raise RuntimeError('BiRefNet discovery failed. '+reason+' Server: '+str(settings.get('comfy_url'))+
            '; expected: '+str(expected)+'; listed choices: '+repr(options)+
            '. Diagnostic: '+str(ROOT/'birefnet_discovery.json'))
    selected=matches[0]
    return {
        '9000':{'class_type':'LoadImage','inputs':{'image':image}},
        '9001':{'class_type':'LoadBackgroundRemovalModel','inputs':{'bg_removal_name':selected}},
        '9002':{'class_type':'RemoveBackground','inputs':{'bg_removal_model':['9001',0],'image':['9000',0]}},
        '9003':{'class_type':'PortalPrepareSubject','inputs':{'image':['9000',0],'mask':['9002',0],'invert_mask':bool(invert),'use_original':bool(use_original),'size':1024}},
        '9004':{'class_type':'SaveImage','inputs':{'images':['9003',0],'filename_prefix':prefix}}
    }


def build_mesh_graph(image,quality,seed,prefix):
    graph=load(ROOT/'hunyuan_workflow_api.json')
    graph['56']['inputs']['image']=image;graph['3']['inputs']['seed']=int(seed)
    if quality=='high':graph['3']['inputs']['steps']=30;graph['61']['inputs']['octree_resolution']=384
    if quality=='ultra':graph['3']['inputs']['steps']=40;graph['61']['inputs']['octree_resolution']=512
    graph['82']['inputs']['filename_prefix']=prefix
    return graph

def render_mesh(job,attempt,settings,export=False):
    settings={**settings,'export_final':bool(export)};save(attempt/'mesh_processing.json',settings)
    appcfg=CONTEXT['config']()
    command=[appcfg['blender_exe'],'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'hunyuan_blender.py'),'--',str(attempt),str(ROOT/'config.json')]
    state(job,'RUNNING_BLENDER',attempt=int(attempt.name.split('_')[-1]),note='Importing generated mesh, preparing previews'+(' and exporting 3MF.' if export else '.'))
    with (attempt/'blender.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=str(attempt),stdout=log,stderr=subprocess.STDOUT,timeout=appcfg.get('blender_timeout_seconds',900))
    if result.returncode:raise RuntimeError('Blender mesh processing failed:\n'+(attempt/'blender.log').read_text(encoding='utf-8',errors='replace')[-10000:])
    return load(attempt/'checks.json')

def _process_without_service_manager(job):
    job = Path(job)
    req = load(job / 'request.json')
    progress = load(job / 'hunyuan_progress.json')
    number = int(progress.get('candidate', 1))
    attempt = job / ('attempt_%02d' % number)
    attempt.mkdir(exist_ok=True)
    try:
        stage = progress['stage']
        if stage == 'prepare':
            state(job, 'PREPROCESSING_IMAGE', attempt=number, note='Removing background and centering subject.')
            name = upload(job / req['image_file'], 'portal/' + job.name)
            graph = preparation_graph(name, progress.get('invert', False), progress.get('use_original', False), 'portal/' + job.name + '/prepared')
            record = run_graph(job, attempt, graph, '9004', '.png', 'prepare')
            download(record, job / 'prepared.png')
            progress['stage'] = 'image_approval'
            save(job / 'hunyuan_progress.json', progress)
            state(job, 'WAITING_IMAGE_APPROVAL', attempt=number, note='Checkpoint 1: inspect the prepared image and confirm the goal.')
            return
        if stage == 'generate':
            state(job, 'GENERATING_MESH', attempt=number, note='Submitting image to Hunyuan3D.')
            if cfg().get('release_comfy_models', True):
                try:
                    request('/free', {'unload_models': True, 'free_memory': True})
                except Exception:
                    pass
            name = upload(job / 'prepared.png', 'portal/' + job.name)
            graph = build_mesh_graph(name, progress['quality'], progress['seed'], 'mesh/portal/' + job.name + '/candidate_%02d' % number)
            save(attempt / 'workflow_api.json', graph)
            record = run_graph(job, attempt, graph, '82', '.glb', 'mesh')
            download(record, attempt / 'source.glb')
            report = render_mesh(job, attempt, progress.get('transform', {'length_mm': req['length_mm'], 'rotate_x': 0, 'rotate_y': 0, 'rotate_z': 0}), False)
            report = auto_repair_if_needed(job, attempt, number, req, progress, report)
            report, retry = verify_geometry(job, attempt, number, progress, report)
            if retry:
                return _process_without_service_manager(job)          # next try with the fix chosen from this try's evidence
            progress['stage'] = 'model_approval'
            save(job / 'hunyuan_progress.json', progress)
            note = 'Checkpoint 2: compare the generated shape with the reference before export.' + (' ' + report['auto_repair']['note'] if report.get('auto_repair') else '') + (' ' + report['geometry_check_note'] if report.get('geometry_check_note') else '')
            state(job, 'WAITING_MODEL_APPROVAL', attempt=int(progress['candidate']), checks=report, note=note)
            return
        if stage == 'reprocess':
            report = render_mesh(job, attempt, progress['transform'], False)
            progress['stage'] = 'model_approval'
            save(job / 'hunyuan_progress.json', progress)
            state(job, 'WAITING_MODEL_APPROVAL', attempt=number, checks=report, note='Updated preview ready. Original source mesh preserved.')
            return
        if stage == 'export':
            report = render_mesh(job, attempt, progress['transform'], True)
            final = job / 'final'
            final.mkdir(exist_ok=True)
            for name in ('model.3mf', 'model.blend', 'model.glb', 'preview.png', 'preview_side.png', 'preview_top.png', 'checks.json', 'blender.log'):
                if (attempt / name).is_file():
                    shutil.copy2(attempt / name, final / name)
            save(final / 'hunyuan_job.json', {'request': req, 'processing': progress, 'comfy_workflow': load(attempt / 'workflow_api.json')})
            progress['stage'] = 'finished'
            save(job / 'hunyuan_progress.json', progress)
            state(job, 'SUCCEEDED', attempt=number, checks=report, note='Hunyuan mesh exported after human approval. Not a printability or articulation certificate.')
            return
        raise RuntimeError('Unexpected Hunyuan processing stage: ' + str(stage))
    except Exception:
        text = traceback.format_exc()
        (attempt / 'generation_error.txt').write_text(text, encoding='utf-8')
        save(attempt / 'repair_feedback.json', {'source': 'Hunyuan + ComfyUI', 'stage': progress.get('stage'), 'exception': text[-5000:], 'candidate': number})
        try:
            CONTEXT['write_attempt_failure'](job, attempt, 'hunyuan_' + progress.get('stage', 'unknown'), text)
        except Exception:
            pass
        raise

# AUTO_SOLID_REPAIR_V1: a newly generated mesh that fails the export topology checks gets the same 0.4 mm solid
# repair preview the "repair" button makes. The raw preview is archived; the user still approves before export.
AUTO_REPAIR_VOXEL_MM = 0.4
AUTO_REPAIR_STEPS_MM = (0.3, 0.4)   # REPAIR_DETAIL_V1 (0.007): finer voxels first, keeps more detail; 0.4 mm fallback
REVIEW_FILES = ('checks.json', 'mesh_processing.json', 'preview.png', 'preview_side.png', 'preview_top.png', 'model.blend', 'model.glb', 'model.3mf', 'blender.log', 'generation_error.txt', 'repair_feedback.json')

def mesh_needs_repair(items):
    # Same rule as repair_problematic() in hunyuan_blender.py, which export enforces.
    return not items or any(not item.get('vertices') or not item.get('faces') or item.get('non_manifold_edges') or item.get('orientation_mismatch_edges', 0) or item.get('degenerate_faces', 0)
                            or not math.isfinite(float(item.get('volume_mm3', 0))) or float(item.get('volume_mm3', 0)) < 1e-6 for item in items)

def auto_repair_if_needed(job, attempt, number, req, progress, report):
    transform = dict(progress.get('transform') or {})
    if transform.get('repair_voxel_mm') or progress.get('auto_repair_done') or not mesh_needs_repair(report.get('objects') or []):
        return report
    broken = sum(int(o.get('non_manifold_edges', 0)) for o in report.get('objects') or [])
    review = attempt / 'review_versions' / (time.strftime('%Y%m%d-%H%M%S-') + 'auto-raw-' + uuid.uuid4().hex[:8]); review.mkdir(parents=True)
    for name in REVIEW_FILES:
        if (attempt / name).is_file():
            shutil.copy2(attempt / name, review / name)
    save(review / 'previous_progress.json', progress)
    raw_transform = dict(transform)
    transform.setdefault('length_mm', req.get('length_mm', 120)); transform['allow_mesh_warnings'] = False
    progress.update(previous_review=str(review.relative_to(job)), solid_repair_approved=False, auto_repair_done=True)
    progress.setdefault('original_requested_result_type', progress.get('result_type', 'solid')); progress['result_type'] = 'solid'
    repaired = None; tried = []
    try:
        for voxel in AUTO_REPAIR_STEPS_MM:
            transform['repair_voxel_mm'] = voxel; progress['transform'] = dict(transform); save(job / 'hunyuan_progress.json', progress)
            state(job, 'RUNNING_BLENDER', attempt=number, note='Raw mesh has %d broken edges: applying automatic %.1f mm solid repair (raw preview kept).' % (broken, voxel))
            try:
                candidate = render_mesh(job, attempt, transform, False)
            except Exception:
                tried.append('%.1f mm: %s' % (voxel, traceback.format_exc().strip().splitlines()[-1][-200:]))
                if voxel == AUTO_REPAIR_STEPS_MM[-1]:
                    raise
                continue
            repaired = candidate
            if candidate.get('repair', {}).get('passed_topology_checks'):
                break
            tried.append('%.1f mm: did not pass topology checks' % voxel)
        AUTO_VOXEL = transform['repair_voxel_mm']
    except Exception:
        # Automatic repair failed: restore the raw preview so the user can choose; never leave a half-repaired state.
        detail = traceback.format_exc()[-1500:]
        progress.update(transform=raw_transform, auto_repair_done=True); progress.pop('previous_review', None)
        if 'original_requested_result_type' in progress:progress['result_type'] = progress['original_requested_result_type']
        save(job / 'hunyuan_progress.json', progress)
        report = render_mesh(job, attempt, raw_transform, False)
        report.setdefault('warnings', []).insert(0, 'Automatic %.1f mm solid repair failed, so this is the raw mesh (%d broken edges). Use Repair with another voxel size. Details: %s' % (AUTO_REPAIR_VOXEL_MM, broken, detail.strip().splitlines()[-1]))
        report['auto_repair'] = {'applied': False, 'voxel_mm': AUTO_REPAIR_VOXEL_MM, 'raw_broken_edges': broken, 'note': 'Automatic solid repair FAILED; showing the raw mesh.'}
        return report
    passed = bool(repaired.get('repair', {}).get('passed_topology_checks'))
    repaired['auto_repair'] = {'applied': True, 'voxel_mm': AUTO_VOXEL, 'raw_broken_edges': broken, 'passed_topology_checks': passed, 'raw_preview': str(review.relative_to(job)), 'earlier_attempts': tried,
                               'note': ('Automatic %.1f mm solid repair applied (raw mesh had %d broken edges); raw preview kept.' % (AUTO_VOXEL, broken) + (' Finer repair was not possible: ' + '; '.join(tried) + '.' if tried else '')) if passed else
                                       ('Automatic solid repair (%s) still fails the topology checks; try another voxel size.' % ', '.join('%.1f mm' % v for v in AUTO_REPAIR_STEPS_MM))}
    repaired.setdefault('warnings', []).insert(0, repaired['auto_repair']['note'])
    return repaired

# GEOMETRY_CHECK_V1 + ADAPTIVE_RETRY_V1 (0.009): every generated mesh is checked against ALL reference views (top included).
# A failed try is retried automatically with a fix chosen from its evidence; the best try is shown at checkpoint 2.
GEOMETRY_MAX_TRIES = 3

def geometry_views(progress):
    route = progress.get('autoroute') or {}
    views = []
    for panel in route.get('panels') or []:
        view = panel.get('view')
        if view in ('front', 'back', 'left', 'right', 'top'):
            views.append({'slot': view, 'direction_hint': view})
        elif view == 'main' and panel.get('reference_direction') in ('front', 'back', 'left', 'right', 'top'):
            views.append({'slot': 'main', 'direction_hint': panel['reference_direction']})
    return views

def run_geometry_check(job, attempt, progress):
    views = [v for v in geometry_views(progress) if (job / 'autoroute_prepared' / (v['slot'] + '.png')).is_file()]
    if not views or not (attempt / 'model.blend').is_file():
        return None
    folder = attempt / 'geometry_check'; folder.mkdir(exist_ok=True)
    save(folder / 'spec.json', {'blend': str(attempt / 'model.blend'), 'prepared': str(job / 'autoroute_prepared'), 'views': views, 'deadline_seconds': 300})
    appcfg = CONTEXT['config']()
    command = [appcfg['blender_exe'], '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(ROOT / 'hunyuan_color.py'), '--', str(folder), 'geometry_check']
    with (folder / 'check.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=str(folder), stdout=log, stderr=subprocess.STDOUT, timeout=appcfg.get('blender_timeout_seconds', 900))
    if result.returncode or not (folder / 'geometry_check.json').is_file():
        return {'error': (folder / 'check.log').read_text(encoding='utf-8', errors='replace')[-3000:]}
    return load(folder / 'geometry_check.json')

def next_fix(history, progress):
    """Choose the next try's fix from the evidence of the tries so far. Pure function (tested without Blender/ComfyUI)."""
    if len(history) >= GEOMETRY_MAX_TRIES or not history or history[-1].get('passed'):
        return None
    last = history[-1]; codes = {r['code'] for r in last.get('reasons', [])}
    # MISPLACED_PART_RETRY_V1 (0.010): a part drawn in different places by different pictures cannot be fixed by retrying.
    if codes == {'misplaced_part'} and len(history) >= 2:
        before = {r['view'] for r in history[-2].get('reasons', []) if r['code'] == 'misplaced_part'}
        again = sorted(before & {r['view'] for r in last.get('reasons', [])})
        if again:
            return {'stop': 'a part is in a different place than the %s picture shows on two tries in a row; the pictures disagree about it, so more tries are unlikely to help' % ', '.join(again)}
    fix = {'seed': secrets.randbelow(2 ** 53), 'changes': ['new seed']}
    if 'missing_geometry' in codes and progress.get('quality') == 'standard':
        fix['quality'] = 'high'; fix['changes'].append('quality Standard -> High (parts of the reference were missing)')
    repeated_extra = sum(1 for h in history if any(r['code'] == 'extra_geometry' for r in h.get('reasons', [])))
    if 'extra_geometry' in codes and repeated_extra >= 2:
        excluded = set(progress.get('geometry_excluded_views') or [])
        conditioning = [p['view'] for p in (progress.get('autoroute') or {}).get('panels') or [] if p.get('conditioning') and p['view'] not in excluded]
        if len(conditioning) > 2:
            fits = {v: last['views'].get(v, {}).get('iou', 1) for v in conditioning}
            worst = min(fits, key=fits.get)
            fix['exclude_view'] = worst; fix['changes'].append('leave the %s view out of the shape (it fits worst: IoU %.2f), extra geometry repeated' % (worst, fits[worst]))
    return fix

def view_mirror_summary(job):
    """VIEW_MIRROR_CHECK_V1 (0.010): one line about flipped/mirrored reference pictures for the checkpoint-2 note."""
    path = Path(job) / 'autoroute_prepared' / 'view_consistency.json'
    try:
        pairs = load(path).get('pairs') or [] if path.is_file() else []
    except Exception:
        return 'Mirror check report unreadable: ' + str(path)
    return ' '.join(p.get('message', '') for p in pairs if p.get('action') == 'flipped' or p.get('verdict') == 'mirrored')

def verify_geometry(job, attempt, number, progress, report):
    if not CONTEXT['config']().get('geometry_check', True):
        return report, False
    state(job, 'RUNNING_BLENDER', attempt=number, note='Checking the mesh against every reference view (top included).')
    try:
        check = run_geometry_check(job, attempt, progress)
    except Exception:
        check = {'error': traceback.format_exc()[-2000:]}
    if check is None:
        return report, False
    history = progress.setdefault('geometry_tries', [])
    entry = {'candidate': number, 'seed': progress.get('seed'), 'quality': progress.get('quality'), 'excluded_views': list(progress.get('geometry_excluded_views') or []),
             'transform': dict(progress.get('transform') or {}), 'passed': bool(check.get('passed')), 'score': check.get('score', -1), 'reasons': check.get('reasons', []),
             'views': {k: {'iou': v['iou'], 'far_extra_percent': v['far_extra_percent'], 'far_missing_percent': v['far_missing_percent']} for k, v in (check.get('views') or {}).items()},
             'error': check.get('error')}
    history.append(entry)
    fix = None if check.get('error') else next_fix(history, progress)
    stop_reason = fix.pop('stop', None) if fix else None
    if stop_reason:
        entry['fix_for_next_try'] = ['no more tries: ' + stop_reason]; fix = None
    if fix:
        entry['fix_for_next_try'] = fix['changes']
        progress['candidate'] = number + 1; progress['seed'] = fix['seed']; progress['stage'] = 'generate'
        if 'quality' in fix: progress['quality'] = fix['quality']
        if 'exclude_view' in fix: progress['geometry_excluded_views'] = sorted(set(progress.get('geometry_excluded_views') or []) | {fix['exclude_view']})
        save(job / 'hunyuan_progress.json', progress)
        state(job, 'GENERATING_MESH', attempt=number + 1, note='Try %d of %d failed the geometry check (%s). Retrying with: %s.' % (len(history), GEOMETRY_MAX_TRIES, ', '.join(r['code'].replace('_', ' ') + ' in ' + str(r['view'] or 'all views') for r in entry['reasons']), '; '.join(fix['changes'])))
        return report, True
    usable = [h for h in history if not h.get('error')]
    best = max(usable, key=lambda h: (h['passed'], h['score'])) if usable else entry
    if best['candidate'] != number:
        progress['candidate'] = best['candidate']; progress['transform'] = best['transform']; progress['quality'] = best['quality']
        report = load(job / ('attempt_%02d' % best['candidate']) / 'checks.json')
    if check.get('error'):
        report['geometry_check_note'] = 'Geometry check could not run (see attempt geometry_check/check.log); inspect the mesh yourself.'
    elif best['passed']:
        report['geometry_check_note'] = 'Geometry check PASSED on try %d of %d against every reference view.' % (history.index(best) + 1, len(history))
    else:
        report['geometry_check_note'] = 'Geometry check: no try passed in %d tries; showing the best one (try %d). Look at the yellow areas in the evidence.' % (len(history), history.index(best) + 1) + (' Stopped early: ' + stop_reason + '.' if stop_reason else '')
    mirror = view_mirror_summary(job)
    if mirror:
        report['geometry_check_note'] = report.get('geometry_check_note', '') + ' ' + mirror
    report['geometry_check'] = {'tries': history, 'shown_candidate': best['candidate']}
    return report, False

def process(job):
    from ai_service_manager import comfy_lease
    stage = load(Path(job) / 'hunyuan_progress.json').get('stage')
    if stage in {'prepare', 'generate'}:
        state(job, 'PREPROCESSING_IMAGE' if stage == 'prepare' else 'GENERATING_MESH', note='Starting or connecting to the image engine on demand. Read its console for model-loading progress.')
        with comfy_lease():
            return _process_without_service_manager(job)
    return _process_without_service_manager(job)


def positive_number(value,label,maximum=1000):
    value=float(value)
    if not math.isfinite(value) or not 1<=value<=maximum:raise ValueError(label+' must be between 1 and '+str(maximum)+'.')
    return value

def admit(payload,retry_req=None,retry_job=None):
    if not CONTEXT['config']().get('allow_generated_code_execution'):raise ValueError('Workflow processing is disabled in config.json.')
    if not payload.get('authorize_processing') and payload.get('authorize_generated_code') is not True:raise ValueError('Authorize mesh processing before submitting.')
    if retry_req:
        req=copy.deepcopy(retry_req);image_data=(retry_job/req['image_file']).read_bytes();ext=Path(req['image_file']).suffix
    else:
        instructions=str(payload.get('instructions','')).strip()
        if len(instructions)>15000:raise ValueError('Instructions exceed 15,000 characters.')
        image_data=base64.b64decode(payload.get('image_base64',''),validate=True)
        ext='.png' if image_data.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if image_data.startswith(b'\xff\xd8\xff') else ''
        if not ext:raise ValueError('Choose a PNG or JPEG.')
        req={'instructions':instructions,'parent_job':'','engine':'hunyuan','length_mm':positive_number(payload.get('length_mm',120),'Length'),'quality':payload.get('quality','standard'),'image_file':'reference'+ext}
    if len(image_data)>15*1024*1024:raise ValueError('Image exceeds 15 MB.')
    if req.get('quality') not in {'standard','high','ultra'}:raise ValueError('Unknown quality mode.')
    if retry_job:req['retry_of']=retry_job.name
    job_id=time.strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8];job=CONTEXT['JOBS']/job_id;job.mkdir()
    (job/req['image_file']).write_bytes(image_data);save(job/'request.json',req)
    save(job/'hunyuan_progress.json',{'stage':'prepare','candidate':1,'quality':req['quality'],'seed':990414131370839,'transform':{'length_mm':req['length_mm'],'rotate_x':0,'rotate_y':0,'rotate_z':0}})
    state(job,'QUEUED',instructions=req['instructions'],engine='hunyuan',retry_of=req.get('retry_of',''))
    CONTEXT['TASKS'].put(job);return {'id':job_id,'state':'QUEUED'}


def mesh_repair_answer(job,req,current,p,payload):
    choice=payload.get('choice')
    repair_active=bool(p.get('transform',{}).get('repair_voxel_mm'))
    if choice=='export' and repair_active:choice='export_repaired'
    if choice not in {'repair_solid','preview_original','export_repaired'}:return None
    if current not in {'FAILED','INTERRUPTED','WAITING_MODEL_APPROVAL','WAITING_JOINT_DESIGN'}:
        raise ValueError('Repair/review is only available for a stopped job at mesh review or after a failure. Refresh before submitting again.')
    if req.get('engine')!='hunyuan':raise ValueError('Not a Hunyuan job.')
    candidate=int(p.get('candidate',1))
    if candidate<1:raise ValueError('Invalid mesh candidate.')
    attempt=job/('attempt_%02d'%candidate)
    if not (attempt/'source.glb').is_file():raise ValueError('This candidate has no source.glb. A generated mesh must exist before it can be repaired.')
    if choice=='export_repaired':
        if current!='WAITING_MODEL_APPROVAL' or not repair_active:raise ValueError('Repair the mesh and inspect its new preview before exporting.')
        checks=load(attempt/'checks.json');repair=checks.get('repair',{})
        if not checks.get('ok') or not repair.get('applied') or not repair.get('passed_topology_checks'):
            raise ValueError('The repaired preview has not passed the topology checks. Try a different voxel size or return to the original preview.')
        if abs(float(repair.get('voxel_mm',-1))-float(p['transform']['repair_voxel_mm']))>1e-9:raise ValueError('Repair settings changed after preview. Run repair again.')
        p['result_type']='solid';p['stage']='export';p['transform']['allow_mesh_warnings']=False;p['solid_repair_approved']=True
    else:
        transform=dict(p.get('transform',{}));transform.setdefault('length_mm',req.get('length_mm',120));transform['allow_mesh_warnings']=False
        if choice=='repair_solid':
            if payload.get('confirm_solid_repair') is not True:raise ValueError('Confirm that repair changes the mesh and does not add articulation.')
            voxel=float(payload.get('voxel_mm',.35))
            if not math.isfinite(voxel) or not .05<=voxel<=2:raise ValueError('Voxel size must be 0.05 to 2.0 mm.')
            transform['repair_voxel_mm']=voxel
        else:transform.pop('repair_voxel_mm',None)
        # Retain old previews and settings before processing overwrites the candidate's working files.
        review=attempt/'review_versions'/(time.strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8]);review.mkdir(parents=True)
        for name in ('checks.json','mesh_processing.json','preview.png','preview_side.png','preview_top.png','model.blend','model.glb','model.3mf','blender.log','generation_error.txt','repair_feedback.json'):
            if (attempt/name).is_file():shutil.copy2(attempt/name,review/name)
        save(review/'previous_progress.json',p)
        p['previous_review']=str(review.relative_to(job));p['transform']=transform;p['stage']='reprocess';p['solid_repair_approved']=False
        if choice=='repair_solid':
            p.setdefault('original_requested_result_type',p.get('result_type','solid'));p['result_type']='solid'
        elif 'original_requested_result_type' in p:p['result_type']=p['original_requested_result_type']
    save(job/'hunyuan_progress.json',p)
    note='Repairing the retained mesh for a new solid preview; no Hunyuan regeneration.' if choice=='repair_solid' else 'Returning to original mesh preview.' if choice=='preview_original' else 'Repaired solid approved for strict export.'
    state(job,'QUEUED',attempt=candidate,note=note,error='',checks={});CONTEXT['TASKS'].put(job)
    return {'id':job.name,'state':'QUEUED'}

def answer(payload):
    job = CONTEXT['get_job'](payload.get('id', ''))
    req = load(job / 'request.json')
    if req.get('engine') != 'hunyuan':
        raise ValueError('Not a Hunyuan job.')
    current = load(job / 'status.json')['state']
    p = load(job / 'hunyuan_progress.json')
    choice = payload.get('choice')
    review = mesh_repair_answer(job, req, current, p, payload)
    if review is not None:
        return review
    if current == 'WAITING_IMAGE_APPROVAL':
        if choice in {'invert', 'original'}:
            p['stage'] = 'prepare'
            p['invert'] = choice == 'invert'
            p['use_original'] = choice == 'original'
        elif choice == 'continue':
            if payload.get('result_type', 'solid') not in {'solid', 'articulated'}:
                p['notes'] = str(payload.get('notes', ''))[:3000]
                save(job / 'hunyuan_progress.json', p)
                state(job, current, note='Other result requested. Notes saved; choose solid or articulation-requested before generation.')
                return {'waiting': True}
            p['stage'] = 'generate'
            p['goal'] = payload.get('goal', 'likeness')
            p['result_type'] = payload.get('result_type', 'solid')
            p['notes'] = str(payload.get('notes', ''))[:3000]
        elif choice == 'other':
            p['notes'] = str(payload.get('notes', ''))[:3000]
            save(job / 'hunyuan_progress.json', p)
            state(job, current, note='Notes saved. Select Continue, Invert mask or Use original. Automatic text-directed reshaping is not available.')
            return {'waiting': True}
        else:
            raise ValueError('Invalid image approval choice.')
    elif current == 'WAITING_MODEL_APPROVAL':
        if choice in {'regenerate', 'higher_detail'}:
            p['candidate'] += 1
            p['seed'] = secrets.randbelow(2 ** 53)
            p['stage'] = 'generate'
            if choice == 'higher_detail':
                p['quality'] = 'high' if p['quality'] == 'standard' else 'ultra'
        elif choice == 'adjust':
            transform = p.get('transform', {})
            transform['length_mm'] = positive_number(payload.get('length_mm', req['length_mm']), 'Length')
            for axis in ('x', 'y', 'z'):
                value = int(payload.get('rotate_' + axis, 0))
                if value not in {-180, -90, 0, 90, 180}:
                    raise ValueError('Rotation must be -180, -90, 0, 90, or 180.')
                transform['rotate_' + axis] = value
            transform['flatten'] = bool(payload.get('flatten', False))
            transform['remove_tiny'] = bool(payload.get('remove_tiny', False))
            p['transform'] = transform
            p['stage'] = 'reprocess'
        elif choice == 'export':
            if p.get('result_type') == 'articulated':
                p['stage'] = 'joint_design'
                p['notes'] = str(payload.get('notes', p.get('notes', '')))[:3000]
                save(job / 'hunyuan_progress.json', p)
                state(job, 'WAITING_JOINT_DESIGN', note='Articulation requested. Mesh preserved; no joints inserted. A validated joint preset and segment layout must be supplied before articulated export.')
                return {'waiting': True}
            p['stage'] = 'export'
            p.setdefault('transform', {})['allow_mesh_warnings'] = bool(payload.get('allow_mesh_warnings', False))
        elif choice == 'other':
            p['notes'] = str(payload.get('notes', ''))[:3000]
            save(job / 'hunyuan_progress.json', p)
            state(job, current, note='Notes saved. Choose regenerate, adjust, or export; free-text mesh editing is not implemented.')
            return {'waiting': True}
        else:
            raise ValueError('Invalid model approval choice.')
    elif current == 'SUCCEEDED' and choice == 'reopen':
        p['stage'] = 'model_approval'
        save(job / 'hunyuan_progress.json', p)
        state(job, 'WAITING_MODEL_APPROVAL', note='Original generated mesh retained. Review and adjust before exporting again.')
        return {'waiting': True}
    elif current == 'WAITING_JOINT_DESIGN' and choice == 'export_solid':
        p['result_type'] = 'solid'
        p['stage'] = 'export'
        p.setdefault('transform', {})['allow_mesh_warnings'] = bool(payload.get('allow_mesh_warnings', False))
    else:
        raise ValueError('Job is not waiting for this answer. Refresh before submitting again.')
    save(job / 'hunyuan_progress.json', p)
    state(job, 'QUEUED', note='Answer saved; waiting for the worker.')
    CONTEXT['TASKS'].put(job)
    return {'id': job.name, 'state': 'QUEUED'}

def install(namespace):
    CONTEXT.update(namespace)
    old_process=namespace['process'];old_handler=namespace['Handler']
    def routed_process(job):
        if load(Path(job)/'request.json').get('engine')=='hunyuan':return process(job)
        return old_process(job)
    class PortalHandler(old_handler):
        def reply(self,code,content,kind='application/json'):
            if code==200 and kind.startswith('text/html'):
                script=(ROOT/'hunyuan_portal_ui.js').read_text(encoding='utf-8').replace('__ACCESS_TOKEN__',namespace['TOKEN'])
                content=(content.decode('utf-8') if isinstance(content,bytes) else content)+'<script>'+script+'</script>'
            return super().reply(code,content,kind)
        def do_GET(self):
            route=self.path.split('?',1)[0]
            if not route.startswith('/hunyuan/'):return super().do_GET()
            if not self.authorized():return self.reply(403,{'error':'Missing/invalid workflow key.'})
            try:
                if route=='/hunyuan/config':
                    settings=cfg()
                    try:
                        info=request('/object_info',timeout=10)
                        needed={'LoadBackgroundRemovalModel','RemoveBackground','PortalPrepareSubject','VAEDecodeHunyuan3D','SaveGLB'}
                        missing=sorted(needed-set(info));online=True;problem='Missing nodes: '+', '.join(missing) if missing else ''
                    except Exception as error:online=False;problem=str(error)
                    return self.reply(200,{'comfy_url':settings['comfy_url'],'online':online,'problem':problem})
                parts=route.strip('/').split('/')
                if len(parts)==3 and parts[1]=='detail':
                    job=namespace['get_job'](parts[2]);req=load(job/'request.json')
                    if req.get('engine')!='hunyuan':return self.reply(200,{'engine':req.get('engine','procedural')})
                    progress=load(job/'hunyuan_progress.json');checks_path=job/('attempt_%02d'%int(progress.get('candidate',1)))/'checks.json'
                    return self.reply(200,{'request':req,'progress':progress,'status':load(job/'status.json'),'mesh_checks':load(checks_path) if checks_path.is_file() else {}})
                if len(parts)==4 and parts[1]=='asset':
                    job=namespace['get_job'](parts[2]);req=load(job/'request.json');p=load(job/'hunyuan_progress.json');name=parts[3]
                    if name=='original':path=job/req['image_file']
                    elif name=='prepared':path=job/'prepared.png'
                    elif name in {'preview.png','preview_side.png','preview_top.png','model.3mf','model.glb','source.glb'}:path=job/('attempt_%02d'%p.get('candidate',1))/name
                    else:raise ValueError('Unknown asset.')
                    kind='image/png' if path.suffix=='.png' else 'image/jpeg' if path.suffix in {'.jpg','.jpeg'} else 'application/octet-stream'
                    return self.reply(200,path.read_bytes(),kind)
                return self.reply(404,{'error':'Not found.'})
            except Exception as error:return self.reply(400,{'error':str(error)})
        def do_POST(self):
            if self.path not in {'/hunyuan/start','/hunyuan/answer','/retry'}:return super().do_POST()
            if not self.authorized():return self.reply(403,{'error':'Missing/invalid workflow key.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 2<=length<=22*1024*1024:raise ValueError('Invalid request size.')
                raw=self.rfile.read(length);payload=json.loads(raw)
                with namespace['ARCHIVE_LOCK']:
                    if self.path=='/retry':
                        original=namespace['get_job'](payload.get('id',''));req=load(original/'request.json')
                        if req.get('engine')!='hunyuan':
                            self.rfile=io.BytesIO(raw);return super().do_POST()
                        if load(original/'status.json').get('state') not in {'FAILED','INTERRUPTED'}:raise ValueError('Retry only failed/interrupted jobs.')
                        data=admit(payload,req,original)
                    elif self.path=='/hunyuan/start':data=admit(payload)
                    else:data=answer(payload)
                return self.reply(202,data)
            except Exception as error:return self.reply(400,{'error':str(error)})
    namespace['process']=routed_process;namespace['Handler']=PortalHandler


# PHOTO COLOR WORKFLOW INTEGRATION v1
from hunyuan_color_bridge import extend as _extend_photo_color
_extend_photo_color(globals())


# HUNYUAN PER-JOB AUTOROUTING v1
from hunyuan_autoroute import extend as _extend_hunyuan_autoroute
_extend_hunyuan_autoroute(globals())
