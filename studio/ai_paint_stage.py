# AI_PAINT_STAGE_V1 (studio 0.010 build 2026-10-28-5)
"""AI texture paint as an option of the colour stage's Bambu export.

Runs AFTER the normal picture-projection export succeeded (model-bambu.3mf is kept untouched) and writes an extra
Bambu project, model-bambu-aipaint.3mf, into the same colour-version folder. Steps (each a separate process):
  1 prepare   - studio Blender: mesh in the studio's triangle order + approved front picture/mask   (ai_paint_prep.py)
  2 AI paint  - texture_paint Python: Hunyuan3D-2 delight + multiview paint-turbo                   (ai_paint_run.py)
                FRONT_CHECK_V1: if the AI's back view matches the front picture better, repaint turned 180 degrees
  2b side      - MULTI_PICTURE_AI_PAINT_V1 (0.017): if the job has an approved LEFT or RIGHT picture, a second AI paint run
                with it (cached per colour version), then ai_paint_combine.py: symmetric shape -> the side run is mirrored onto the
                other side (user's option C); otherwise a third run of the other side. Failure -> front picture only + FAIL_REASON.
  3 filaments - texture_paint Python: N filament colours (studio choice / drawing D2 / auto)        (ai_paint_filaments.py)
  4 previews  - studio Blender: 4 pictures of the written 3MF + 1 of the raw AI texture             (ai_paint_preview.py)
Progress: color_versions/<v>/ai_paint.log gets ONLY lines 'NN%| text (mm:ss)' -> the main UI progress bar (JOB_PROGRESS_BAR_V1).
Raw process output stays in color_versions/<v>/ai_paint_work/*.txt. Any failure writes ai_paint_work/FAIL_REASON.txt and raises.
Standard library only (runs inside the studio's own Python)."""
import hashlib, json, os, re, shutil, subprocess, threading, time, traceback
from pathlib import Path

# COLOUR_TEXT_CLEANUP_V1: the report shows the installed studio version (color_update_version.json), not a fixed old number
def _installed_version():
    try:
        v = json.loads((Path(__file__).resolve().parent / 'color_update_version.json').read_text(encoding='utf-8-sig'))
        return str(v.get('version') or '?'), str(v.get('build') or '?')
    except Exception:
        return '?', '?'
VERSION, BUILD = _installed_version()
HY_COMMIT = 'f8db63096c8282cb27354314d896feba5ba6ff8a'
HF_REV = 'efb40d890aeade24c68ec7555eb206de8ba68c77'
TEMPLATES = {4: 'bambu_template_default.3mf', 5: 'bambu_template.3mf', 6: 'bambu_template_6.3mf', 7: 'bambu_template_7.3mf', 8: 'bambu_template_8.3mf', 9: 'bambu_template_9.3mf'}
COLOURS = ('studio', 'drawing', 'auto')
PICTURES = ('aipaint_front.png', 'aipaint_left.png', 'aipaint_right.png', 'aipaint_back.png', 'aipaint_texture.png')
OUTPUTS = {'model-bambu-aipaint.3mf', 'aipaint_report.txt', 'aipaint_result.json', 'ai_paint.log'} | set(PICTURES)
SCRIPTS = ('ai_paint_prep.py', 'ai_paint_run.py', 'ai_paint_filaments.py', 'ai_paint_preview.py', 'ai_paint_side_prep.py', 'ai_paint_combine.py')
STEP_TIMEOUT = {'prepare': 900, 'paint': 5400, 'filaments': 1200, 'preview': 900, 'combine': 1800}


class Cancelled(Exception):
    pass


def digest(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def paths(root):
    tp = Path(root) / 'texture_paint'
    return {'tp': tp, 'python': tp / 'env' / 'Scripts' / 'python.exe', 'code': tp / 'code' / 'Hunyuan3D-2',
            'models': tp / 'models', 'hf': tp / 'cache' / 'hf'}


def git_head(code):
    g = code / '.git'
    head = (g / 'HEAD').read_text(encoding='utf-8').strip()
    if not head.startswith('ref:'): return head
    ref = head[4:].strip(); p = g / ref
    if p.is_file(): return p.read_text(encoding='utf-8').strip()
    packed = g / 'packed-refs'
    if packed.is_file():
        for line in packed.read_text(encoding='utf-8').splitlines():
            if line.endswith(' ' + ref): return line.split()[0]
    return head


def install_status(root):
    """Is the AI paint runtime (installed by Test-AI-Texture-Paint.bat) present at the expected fixed versions?"""
    root = Path(root); P = paths(root); problems = []
    for s in SCRIPTS:
        if not (root / s).is_file(): problems.append('studio script missing: ' + s)
    if not P['python'].is_file(): problems.append('AI paint Python missing: ' + str(P['python']))
    try:
        h = git_head(P['code'])
        if h != HY_COMMIT: problems.append('Hunyuan3D-2 code is at %s, expected %s' % (h[:12], HY_COMMIT[:12]))
    except Exception as e:
        problems.append('Hunyuan3D-2 code missing (%s)' % e)
    try:
        m = json.loads((P['models'] / 'models_manifest.json').read_text(encoding='utf-8'))
        if m.get('revision') != HF_REV: problems.append('AI paint models are revision %s, expected %s' % (str(m.get('revision'))[:12], HF_REV[:12]))
        if m.get('problems'): problems.append('AI paint model download had problems: %s' % m['problems'])
        if not m.get('files'): problems.append('AI paint model manifest lists no files')
    except Exception as e:
        problems.append('AI paint models missing (%s)' % e)
    return {'installed': not problems, 'problems': problems, 'version': VERSION, 'build': BUILD,
            'how_to_install': '' if not problems else 'Run Test-AI-Texture-Paint.bat once (it installs the AI paint runtime into texture_paint).'}


def template_name(n, nozzle=0.6):   # NOZZLE_OPTION_V1: 0.4 mm jobs use the *_04 copies (H2C 0.4 nozzle, 0.20mm High Quality)
    return TEMPLATES[n][:-4] + '_04.3mf' if nozzle == 0.4 else TEMPLATES[n]


def template_counts(root, nozzle=0.6):
    return [k for k in sorted(TEMPLATES) if (Path(root) / template_name(k, nozzle)).is_file() and not (Path(root) / template_name(k, nozzle)).is_symlink()]


def options(raw, root):
    """Validate the export box's ai_paint choice. None/disabled -> None (picture method only)."""
    if raw is None: return None
    if not isinstance(raw, dict) or set(raw) - {'enabled', 'filaments', 'colours', 'props', 'nozzle'}: raise ValueError('Invalid AI paint options')
    if raw.get('enabled') is not True:
        if raw.get('enabled') not in (False, None): raise ValueError('AI paint enabled must be true/false')
        return None
    n = raw.get('filaments', 4)
    if isinstance(n, bool) or not isinstance(n, int) or n not in TEMPLATES: raise ValueError('AI paint filaments must be 4-9')
    z = raw.get('nozzle', 0.6)                      # NOZZLE_OPTION_V1
    if isinstance(z, bool) or z not in (0.4, 0.6): raise ValueError('AI paint nozzle must be 0.4 or 0.6')
    if n not in template_counts(root, z): raise ValueError('No Bambu template with %d filaments (%s) in the studio folder' % (n, template_name(n, z)))
    c = raw.get('colours', 'studio')
    if c not in COLOURS: raise ValueError('AI paint colours must be studio, drawing or auto')
    st = install_status(root)
    if not st['installed']: raise ValueError('AI paint is not installed: ' + '; '.join(st['problems']))
    p = raw.get('props', False)                      # PROPS_TOGGLE_V1
    if not isinstance(p, bool): raise ValueError('AI paint props must be true/false')
    return dict({'enabled': True, 'filaments': n, 'colours': c}, **({'props': True} if p else {}), **({'nozzle': 0.4} if z == 0.4 else {}))   # keys only when set


class Progress:
    """Writes ONLY 'NN%| text (mm:ss)' lines to ai_paint.log (the UI bar's regex), plus a heartbeat every 15 s."""
    def __init__(self, path):
        self.path = path; self.t0 = time.time(); self.pct = 0; self.text = 'starting'; self.last = 0
        path.write_text('', encoding='utf-8')
    def set(self, pct, text):
        self.pct = max(0, min(100, int(pct))); self.text = text.replace('%', ' percent').replace('|', '/'); self.write()
    def write(self):
        e = int(time.time() - self.t0); self.last = time.time()
        with self.path.open('a', encoding='utf-8') as f: f.write('%3d%%| AI paint: %s (%d:%02d)\n' % (self.pct, self.text, e // 60, e % 60))
    def beat(self):
        if time.time() - self.last >= 15: self.write()


def kill_tree(p):
    try:
        if os.name == 'nt': subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True, timeout=30)
        else: p.kill()
    except Exception:
        p.kill()


def step(name, cmd, env, cwd, raw, prog, lo, hi, cancelled, label):
    """Run one step; its 'PROGRESS n text' lines are mapped to lo..hi of the overall bar. Returns the exit code."""
    prog.set(lo, label)
    flags = 0x08000000 if os.name == 'nt' else 0   # CREATE_NO_WINDOW
    with raw.open('w', encoding='utf-8', errors='replace') as log:
        log.write('COMMAND: %s\n\n' % ' '.join(map(str, cmd))); log.flush()
        p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=flags)
        latest = []
        def reader():
            for b in iter(p.stdout.readline, b''):
                line = b.decode('utf-8', 'replace').rstrip('\r\n'); log.write(line + '\n'); log.flush()
                m = re.match(r'PROGRESS (\d{1,3}) (.*)', line)
                if m: latest.append((int(m.group(1)), m.group(2)))
        th = threading.Thread(target=reader, daemon=True); th.start(); t0 = time.time()
        while p.poll() is None:
            time.sleep(0.5)
            if latest:
                n, t = latest[-1]; latest.clear(); prog.set(lo + (hi - lo) * min(n, 100) / 100, label + ' - ' + t)
            prog.beat()
            if cancelled():
                kill_tree(p); th.join(10); raise Cancelled('cancelled by the user during AI paint step ' + name)
            if time.time() - t0 > STEP_TIMEOUT[name]:
                kill_tree(p); th.join(10); raise RuntimeError('AI paint step %s took longer than %d s and was stopped' % (name, STEP_TIMEOUT[name]))
        th.join(30)
        return p.returncode


def lastline(t):
    rows = [r.strip() for r in str(t or '').splitlines() if r.strip()]
    return rows[-1][:400] if rows else ''


def readj(p):
    return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).is_file() else {}


# ---------------- MULTI_PICTURE_AI_PAINT_V1 (0.017) ----------------
def side_slot(folder):
    """The first approved picture whose approved direction is left or right (the user's own labels), else None."""
    try:
        cfg = json.loads((Path(folder) / 'settings.json').read_text(encoding='utf-8-sig')); views = (cfg.get('settings') or {}).get('views') or {}
        rev = json.loads((Path(folder) / 'reference_review.json').read_text(encoding='utf-8-sig'))
    except Exception:
        return None
    for rec in rev.get('views') or []:
        d = (views.get(rec.get('slot')) or {}).get('direction') or rec.get('direction_hint')
        if d in ('left', 'right') and (Path(folder) / ('reference_' + rec['slot'] + '.png')).is_file(): return {'slot': rec['slot'], 'direction': d}
    return None


def _paint_once(name, paint, env, root, logdir, prog, lo, hi, cancelled, label, out):
    """One AI paint run into <out> with the studio's rules: low-memory retry (exit 3) and FRONT_TURN_V1 repaint. Returns paint.json."""
    env = dict(env, PAINT_TURN='0', PAINT_OFFLOAD='model')
    c = step('paint', paint, env, root, logdir / ('step_%s.txt' % name), prog, lo, hi, cancelled, label)
    if c == 3:
        env['PAINT_OFFLOAD'] = 'sequential'
        c = step('paint', paint, env, root, logdir / ('step_%s_lowmem.txt' % name), prog, lo, hi, cancelled, label + ' (low graphics memory mode, slower)')
    pj = readj(out / 'paint.json')
    if c: raise RuntimeError('%s failed (exit %s) at %r: %s' % (label, c, pj.get('stage'), pj.get('error')))
    if (pj.get('front_check') or {}).get('front_points_at_back'):
        first = out / 'first_try_reversed'; first.mkdir()
        for n in ('views', 'paint.json', 'tri_rgb.npy', 'ai_texture.png', 'ai_textured.glb'):
            if (out / n).exists(): shutil.move(str(out / n), str(first / n))
        env['PAINT_TURN'] = '1'
        c = step('paint', paint, env, root, logdir / ('step_%s_turned.txt' % name), prog, lo, hi, cancelled, label + ' again, turned 180 degrees')
        pj = readj(out / 'paint.json')
        if c: raise RuntimeError('%s (turned 180) failed (exit %s) at %r: %s' % (label, c, pj.get('stage'), pj.get('error')))
    if not (out / 'tri_rgb.npy').is_file(): raise RuntimeError(label + ' reported success but tri_rgb.npy is missing')
    return pj


def _cache_key(root, prep_dir):
    pj = json.loads((prep_dir / 'prep.json').read_text(encoding='utf-8'))
    k = {'inputs': pj.get('inputs_sha256'), 'slot': pj.get('slot'), 'mode': pj.get('mode'), 'toward': pj.get('toward'), 'picture': digest(prep_dir / 'front_rgba.png'),
         'triangles': pj.get('triangles'), 'paint_script': digest(Path(root) / 'ai_paint_run.py'), 'hy': HY_COMMIT, 'hf': HF_REV}
    return hashlib.sha256(json.dumps(k, sort_keys=True).encode()).hexdigest()[:24]


def _side_run(kind, root, folder, sd, slot, mode, env, P, blend, prog, lo, hi, cancelled, label):
    """Prepare (Blender) + AI paint one side picture, or reuse the cached run of the same inputs. Returns (prep, run, info)."""
    prep, run_ = sd / ('prep_' + kind), sd / ('run_' + kind); sd.mkdir(parents=True, exist_ok=True)
    c = step('prepare', blend + [Path(root) / 'ai_paint_side_prep.py', '--', root, folder, prep, slot, mode], env, root, sd / ('step_prepare_%s.txt' % kind), prog, lo, lo + 2, cancelled, label + ' - prepare (Blender)')
    if c or not (prep / 'mesh.npz').is_file():
        e = (prep / 'prep_error.txt').read_text(encoding='utf-8', errors='replace') if (prep / 'prep_error.txt').is_file() else ''
        raise RuntimeError('%s prepare failed (exit %s): %s' % (label, c, lastline(e) or 'see step_prepare_%s.txt' % kind))
    key = _cache_key(root, prep); cdir = Path(folder) / 'ai_paint_cache'; hit = cdir / ('%s-%s' % (kind, key))
    run_.mkdir(parents=True, exist_ok=True)
    if (hit / 'tri_rgb.npy').is_file() and (hit / 'paint.json').is_file() and readj(hit / 'cache.json').get('tri_rgb_sha256') == digest(hit / 'tri_rgb.npy'):
        for n in ('tri_rgb.npy', 'paint.json'): shutil.copy2(hit / n, run_ / n)
        prog.set(hi, label + ' - reused the saved run of the same picture (no repaint needed)')
        return prep, run_, dict(readj(run_ / 'paint.json'), cache='reused ' + hit.name)
    paint = [P['python'], Path(root) / 'ai_paint_run.py', P['code'], P['models'], prep, run_]
    pj = _paint_once(kind, paint, env, root, sd, prog, lo + 2, hi, cancelled, label, run_)
    cdir.mkdir(exist_ok=True)
    for old in cdir.glob(kind + '-*'):              # keep only the newest saved run of this kind for this colour version
        shutil.rmtree(old, ignore_errors=True)
    tmp = cdir / ('.tmp-' + kind); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    for n in ('tri_rgb.npy', 'paint.json'): shutil.copy2(run_ / n, tmp / n)
    (tmp / 'cache.json').write_text(json.dumps({'tri_rgb_sha256': digest(tmp / 'tri_rgb.npy'), 'slot': slot, 'mode': mode, 'made': time.strftime('%Y-%m-%d %H:%M:%S')}), encoding='utf-8')
    tmp.rename(hit)
    return prep, run_, dict(pj, cache='new run saved as ' + hit.name)


def multi_picture(root, folder, work, front_turned, env, P, blend, prog, cancelled):
    """MULTI_PICTURE_AI_PAINT_V1. Writes work/tri_rgb.npy (combined) and returns the report dict. On any failure (not cancel) the
    front-picture-only colours are kept, FAIL_REASON.txt is written in work/side and the dict says so."""
    sel = side_slot(folder)
    if os.environ.get('AISTUDIO_AIPAINT_FRONT_ONLY') == '1': return {'used': False, 'reason': 'switched off (AISTUDIO_AIPAINT_FRONT_ONLY=1)'}
    if not sel: return {'used': False, 'reason': 'no approved left or right picture in this job - front picture only'}
    sd = work / 'side'; shutil.copy2(work / 'tri_rgb.npy', work / 'tri_rgb_front.npy')
    out = {'used': False, 'side_slot': sel['slot'], 'side_direction': sel['direction']}
    try:
        prep_s, run_s, pj_s = _side_run('side', root, folder, sd, sel['slot'], 'same', env, P, blend, prog, 40, 62, cancelled, 'step 2/4 AI paint 2/2 (%s picture)' % sel['direction'])
        out['side_run'] = {k: pj_s.get(k) for k in ('paint_seconds', 'vram_peak_allocated_MiB', 'offload', 'turned_180', 'front_check', 'cache')}
        comb = [P['python'], Path(root) / 'ai_paint_combine.py', work, run_s, prep_s, sd / 'combine', '1' if front_turned else '0']
        c = step('combine', comb, env, root, sd / 'step_combine.txt', prog, 62, 66, cancelled, 'step 2/4 combining the pictures (shape check)')
        cj = readj(sd / 'combine' / 'combine.json')
        if c == 10:
            other = cj.get('other_side_slot'); oslot, omode = (other, 'same') if other else (sel['slot'], 'opposite')
            od = 'left' if sel['direction'] == 'right' else 'right'
            prep_o, run_o, pj_o = _side_run('other', root, folder, sd, oslot, omode, env, P, blend, prog, 66, 78, cancelled,
                                           'step 2/4 AI paint 3/3 (%s side - shape not symmetric: %s)' % (od, cj.get('reason')))
            out['other_run'] = {k: pj_o.get(k) for k in ('paint_seconds', 'turned_180', 'cache')}
            c = step('combine', comb + [run_o, prep_o], env, root, sd / 'step_combine_other.txt', prog, 78, 80, cancelled, 'step 2/4 combining the pictures')
            cj = readj(sd / 'combine' / 'combine.json')
        if c or not cj.get('ok') or not (sd / 'combine' / 'tri_rgb.npy').is_file():
            raise RuntimeError('combining the pictures failed (exit %s): %s' % (c, lastline(cj.get('error')) or 'see side/step_combine*.txt'))
        shutil.copy2(sd / 'combine' / 'tri_rgb.npy', work / 'tri_rgb.npy')
        out.update(used=True, method=cj.get('method'), reason=cj.get('reason'), shape_check=cj.get('shape_check'), picture_check=cj.get('picture_check'),
                   seen_percent=cj.get('seen_percent'), other_side_mirrored_percent=cj.get('other_side_mirrored_percent'), other_side_run=cj.get('other_side_run'),
                   match_to_your_pictures_deltaE=cj.get('match_to_your_pictures_deltaE'), changed_percent_vs_front_only=cj.get('changed_percent_vs_front_only'))
        return out
    except Cancelled:
        raise
    except Exception as e:
        shutil.copy2(work / 'tri_rgb_front.npy', work / 'tri_rgb.npy')          # the front-only colours, exactly as before 0.017
        sd.mkdir(parents=True, exist_ok=True); fr = sd / 'FAIL_REASON.txt'
        fr.write_text('AI MODELING STUDIO - SIDE PICTURE AI PAINT FAILED (the AI paint file was made from the FRONT picture only)\n'
                      'Version: %s build %s\nSide picture: %s (%s)\nColour version folder: %s\nError: %s\n\nTRACEBACK:\n%s\n\nLogs: %s\\step_*.txt\n'
                      'NEXT DIAGNOSTIC STEP: send this file and the step_*.txt logs from the folder above.\n' % (
                          VERSION, BUILD, sel['slot'], sel['direction'], folder, e, traceback.format_exc(), sd), encoding='utf-8')
        prog.set(80, 'side picture FAILED - continuing with the front picture only (%s)' % (str(e).splitlines() or [''])[0][:120])
        out.update(used=False, failed=True, error=(str(e).strip().splitlines() or [type(e).__name__])[0][:400], fail_reason=str(fr))
        return out


def multi_report(m):
    if not m: return []
    if not m.get('used'):
        if m.get('failed'): return ['PICTURES USED: FRONT ONLY - the %s picture run FAILED: %s' % (m.get('side_direction'), m.get('error')), '  details: ' + str(m.get('fail_reason'))]
        return ['Pictures used: front only (%s)' % m.get('reason')]
    sc = m.get('shape_check') or {}; sp = m.get('seen_percent') or {}; mt = m.get('match_to_your_pictures_deltaE') or {}
    how = ('the %s picture MIRRORED onto the other side (%s %% of it)' % (m['side_direction'], m.get('other_side_mirrored_percent')) if m.get('method') == 'mirror'
           else 'a separate AI paint run of the other side (%s)' % ((m.get('other_side_run') or {}).get('kind')))
    lines = ['Pictures used: front + %s picture, then %s' % (m['side_direction'], how),
             '  shape check: %s %% of the other side has a mirror partner (pass mark %s %%) - %s' % (sc.get('other_side_with_mirror_partner_percent'), sc.get('pass_mark_percent'), m.get('reason')),
             '  seen directly: front %s %%, side %s %%, other side %s %%; not seen by any picture (top, belly, hidden parts, kept from the front run): %s %%' % (
                 sp.get('front_picture'), sp.get('side_picture'), sp.get('other_side'), sp.get('none')),
             '  side run: %s' % ((m.get('side_run') or {}).get('cache'))]
    if mt: lines.append('  match to your approved pictures (deltaE, lower = closer): front only %s -> combined %s' % (mt.get('front_only'), mt.get('combined')))
    return lines


def run(root, folder, opts, blender, cancelled=lambda: False, versions=None):
    """Make model-bambu-aipaint.3mf in the colour-version folder. Raises on failure (FAIL_REASON.txt written)."""
    root = Path(root); folder = Path(folder); P = paths(root); work = folder / 'ai_paint_work'
    for n in OUTPUTS:   # an earlier AI paint result of this version is replaced, never mixed with the new one
        if (folder / n).is_file() and n != 'ai_paint.log': (folder / n).unlink()
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True); prep = work / 'prep'
    prog = Progress(folder / 'ai_paint.log'); stage = 'start'; info = {'options': opts, 'version': VERSION, 'build': BUILD}
    env = dict(os.environ, HF_HOME=str(P['hf']), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               PYTHONUTF8='1', PYTHONUNBUFFERED='1', PAINT_OFFLOAD='model', PAINT_TURN='0',
               AIPAINT_PROPS='1' if opts.get('props') else '0',   # PROPS_TOGGLE_V1
               AIPAINT_NOZZLE='0.4' if opts.get('nozzle') == 0.4 else '0.6')   # NOZZLE_OPTION_V1
    env.pop('PYTHONHOME', None); env.pop('PYTHONPATH', None)
    blend = [blender, '--background', '--factory-startup', '--python-exit-code', '1', '--python']
    try:
        stage = 'install check'; st = install_status(root)
        if not st['installed']: raise RuntimeError('AI paint is not installed: ' + '; '.join(st['problems']))
        stage = 'free graphics memory'
        try:
            import ai_service_manager
            info['engines'] = ai_service_manager.stop_idle_services().get('note')
        except Exception as e:
            info['engines'] = 'could not stop the idle AI engines (%s) - the paint step falls back to low-memory mode if needed' % e
            prog.set(1, info['engines'])
        stage = 'prepare'
        c = step('prepare', blend + [root / 'ai_paint_prep.py', '--', root, folder, prep], env, root, work / 'step_1_prepare.txt', prog, 1, 6, cancelled, 'step 1/4 prepare (Blender)')
        if c or not (prep / 'mesh.npz').is_file():
            e = (prep / 'prep_error.txt').read_text(encoding='utf-8', errors='replace') if (prep / 'prep_error.txt').is_file() else ''
            raise RuntimeError('prepare failed (exit %s): %s' % (c, lastline(e) or 'see step_1_prepare.txt'))
        info['prep'] = readj(prep / 'prep.json')
        stage = 'AI paint'
        paint = [P['python'], root / 'ai_paint_run.py', P['code'], P['models'], prep, work]
        side = side_slot(folder) if os.environ.get('AISTUDIO_AIPAINT_FRONT_ONLY') != '1' else None   # MULTI_PICTURE_AI_PAINT_V1
        fhi, flabel = (40, 'step 2/4 AI paint 1/2 (front picture)') if side else (80, 'step 2/4 AI paint')
        c = step('paint', paint, env, root, work / 'step_2_paint.txt', prog, 6, fhi, cancelled, flabel)
        if c == 3:
            env['PAINT_OFFLOAD'] = 'sequential'; info['low_memory_retry'] = True
            c = step('paint', paint, env, root, work / 'step_2_paint_lowmem.txt', prog, 6, fhi, cancelled, flabel + ' (low graphics memory mode, slower)')
        pj = readj(work / 'paint.json')
        if c: raise RuntimeError('AI paint failed (exit %s) at %r: %s' % (c, pj.get('stage'), pj.get('error')))
        info['front_check_first'] = pj.get('front_check')
        if (pj.get('front_check') or {}).get('front_points_at_back'):
            # FRONT_TURN_V1: the approved front alignment points at the model's back -> keep the first try, repaint turned 180 deg
            first = work / 'first_try_front_reversed'; first.mkdir()
            for n in ('views', 'paint.json', 'tri_rgb.npy', 'ai_texture.png', 'ai_textured.glb'):
                if (work / n).exists(): shutil.move(str(work / n), str(first / n))
            env['PAINT_TURN'] = '1'
            c = step('paint', paint, env, root, work / 'step_2_paint_turned.txt', prog, 6, fhi, cancelled, flabel + ' again, model turned 180 degrees (front picture matched the back)')
            pj = readj(work / 'paint.json')
            if c: raise RuntimeError('AI paint (turned 180) failed (exit %s) at %r: %s' % (c, pj.get('stage'), pj.get('error')))
        info['paint'] = {k: pj.get(k) for k in ('paint_seconds', 'vram_peak_allocated_MiB', 'vram_free_start_MiB', 'offload', 'rasterizer', 'gpu',
                                                'gpu_capability', 'turned_180', 'front_check', 'uv_orientation_used', 'uv_orientation_warning')}
        if not (work / 'tri_rgb.npy').is_file(): raise RuntimeError('AI paint reported success but tri_rgb.npy is missing')
        stage = 'side picture'
        info['multi'] = multi_picture(root, folder, work, env.get('PAINT_TURN') == '1', env, P, blend, prog, cancelled)
        stage = 'filaments'
        c = step('filaments', [P['python'], root / 'ai_paint_filaments.py', root, prep, work, opts['filaments'], opts['colours']], env, root,
                 work / 'step_3_filaments.txt', prog, 80, 88, cancelled, 'step 3/4 filament colours -> Bambu 3MF')
        fj = readj(work / 'filaments.json')
        if c or not fj.get('ok'): raise RuntimeError('filament step failed (exit %s): %s' % (c, lastline(fj.get('error')) or 'see step_3_filaments.txt'))
        f = [x for x in fj['files'] if 'file' in x][0]; info['filaments'] = {k: f.get(k) for k in ('mode', 'requested', 'filaments', 'template', 'palette', 'share_percent', 'deltaE_mean', 'thin_dark_to_outline_percent', 'verify')}
        info['style'] = fj.get('style'); info['props'] = {'has_props': bool(opts.get('props')), 'accents_to_outline': fj.get('accents_to_outline')}
        info['nozzle'] = {'nozzle_mm': fj.get('nozzle_mm', 0.6), 'detail': fj.get('detail')}   # NOZZLE_OPTION_V1
        stage = 'previews'
        c = step('preview', blend + [root / 'ai_paint_preview.py', '--', root, prep, work], env, root, work / 'step_4_preview.txt', prog, 88, 99, cancelled, 'step 4/4 preview pictures (Blender)')
        if c: raise RuntimeError('preview pictures failed (exit %s) - see step_4_preview.txt' % c)
        stage = 'publish'
        shutil.copy2(work / 'AI-PAINT.3mf', folder / 'model-bambu-aipaint.3mf')
        for n in PICTURES: shutil.copy2(work / n, folder / n)
        info['files'] = {n: digest(folder / n) for n in ('model-bambu-aipaint.3mf',) + PICTURES}
        if info['files']['model-bambu-aipaint.3mf'] != digest(work / 'AI-PAINT.3mf'): raise RuntimeError('copied 3MF differs from the written one')
        (folder / 'aipaint_report.txt').write_text(report(info, versions), encoding='utf-8')
        info['report_sha256'] = digest(folder / 'aipaint_report.txt'); info['ok'] = True
        (folder / 'aipaint_result.json').write_text(json.dumps(info, indent=1, default=str), encoding='utf-8')
        prog.set(100, 'finished - model-bambu-aipaint.3mf written (%s colours, %d filaments)' % (info['filaments']['mode'], info['filaments']['filaments']))
        return {**info, 'result_sha256': digest(folder / 'aipaint_result.json')}
    except Exception as e:
        tb = traceback.format_exc(); cancelled_ = isinstance(e, Cancelled)
        msg = str(e).strip().splitlines()[0][:200] if str(e).strip() else type(e).__name__
        prog.set(prog.pct, ('CANCELLED' if cancelled_ else 'FAILED') + ' at ' + stage + ': ' + msg)
        try:
            (work / 'FAIL_REASON.txt').write_text(
                'AI MODELING STUDIO - AI PAINT FAILURE\nVersion: %s build %s\nStage: %s\nColour version folder: %s\nOptions: %s\n'
                'AI paint Python: %s\nHunyuan3D-2 code: %s (expected commit %s)\nModels: %s (expected revision %s)\nBlender: %s\n'
                'Step logs: %s\\step_*.txt\nVersions: %s\n\nERROR / TRACEBACK:\n%s\n\nNEXT DIAGNOSTIC STEP:\n%s\n' % (
                    VERSION, BUILD, stage, folder, opts, P['python'], P['code'], HY_COMMIT, P['models'], HF_REV, blender, work, versions, tb,
                    'Nothing to fix - the job was cancelled.' if cancelled_ else
                    'The picture-method Bambu file (model-bambu.3mf) is still valid. Send this file and the step_*.txt logs from the folder above.'),
                encoding='utf-8')
        except Exception as w:
            print('AI paint FAIL_REASON.txt could not be written: ' + str(w), flush=True)
        raise


def report(info, versions=None):
    f = info['filaments']; p = info['paint']; s = info.get('style') or {}
    fc = p.get('front_check') or {}
    lines = ['AI PAINT - Bambu full-color 3MF (download: <job>-bambu-full-color.3mf)', 'AI Modeling Studio %s (build %s)' % (VERSION, BUILD), '',
             'Colours: %s (asked: %s) with %d filaments, template %s' % (f['mode'].upper(), f['requested'], f['filaments'], f['template']),
             'Filament colours (1..%d): %s' % (f['filaments'], ' '.join(f['palette'])),
             'Share of the surface per filament (%%): %s' % ' / '.join(str(x) for x in f['share_percent']),
             'Mean colour difference to the AI texture (deltaE76): %s' % f.get('deltaE_mean')]
    if f['mode'] == 'drawing':
        lines.append('Drawing colours: filament colours from your approved pictures; the last filament is the outline colour; thin dark areas moved to it: %s %% of the surface' % f.get('thin_dark_to_outline_percent'))
    pr = info.get('props') or {}
    nz = info.get('nozzle') or {}; dt = nz.get('detail') or {}   # NOZZLE_OPTION_V1
    lines.append('Nozzle: %s mm on both H2C nozzles (chosen at upload)%s; colour detail: specks under %s mm2 merged, dark areas narrower than %s mm or under %s mm2 printed in the outline colour' % (
        nz.get('nozzle_mm', 0.6), ' - Bambu file: H2C 0.4 nozzle, 0.20mm High Quality, Generic PLA 0.4 nozzle' if nz.get('nozzle_mm') == 0.4 else '', dt.get('speck_mm2'), dt.get('line_width_mm'), dt.get('line_area_mm2')))
    lines += multi_report(info.get('multi'))
    lines.append('Props: %s' % ('HAS PROPS INCLUDED (ticked at upload) - small prop colours keep their own colour, nothing moved to the outline colour' if pr.get('has_props') else
                 'no props ticked at upload' + (' - small accents moved to the outline colour: %s' % ', '.join(a['colour'] for a in pr['accents_to_outline']) if pr.get('accents_to_outline') else '')))
    lines += ['Drawing style: %s %% dark pixels, %s %% in its 12 most common colours -> studio choice %s (%s)' % (
                  s.get('dark_pixels_percent'), s.get('top12_colours_percent'), str(s.get('recommended')).upper(), s.get('reason')), '',
              'Front picture: %s, mirrored copy used: %s' % (info['prep'].get('front_slot'), info['prep'].get('flip_applied_to_picture')),
              'Front check (lower = more alike): AI front view %s, AI back view %s; model turned 180 degrees: %s' % (
                  fc.get('diff_front_view'), fc.get('diff_back_view'), p.get('turned_180'))]
    if info.get('front_check_first') and p.get('turned_180'):
        ff = info['front_check_first']; lines.append('  first try (not turned): front view %s, back view %s -> the approved front alignment points at the model\'s back' % (ff.get('diff_front_view'), ff.get('diff_back_view')))
    if fc.get('front_points_at_back'): lines.append('  WARNING: still unclear which side is the front - check the preview pictures.')
    lines += ['AI paint: %s s, graphics memory peak %s MiB, offload %s, rasterizer %s, GPU %s' % (p.get('paint_seconds'), p.get('vram_peak_allocated_MiB'), p.get('offload'), p.get('rasterizer'), p.get('gpu')),
              'Texture orientation: %s%s' % (p.get('uv_orientation_used'), ('  NOTE: ' + p['uv_orientation_warning']) if p.get('uv_orientation_warning') else ''),
              'Bambu file re-read check: %s' % json.dumps(f.get('verify'), default=str)[:600], '',
              ('LIMITS: the front and side pictures guide the AI; the back, top and belly are painted by the AI and are a GUESS, not your drawing.' if (info.get('multi') or {}).get('used') else
               'LIMITS: only the FRONT picture guides the AI; the back, sides and top are painted by the AI and are a GUESS, not your drawing.'),
              'The colours are not checked in Bambu Studio by the studio: open the file in Bambu Studio and check them before printing.']
    if versions: lines.append('Versions: %s' % versions)
    return '\n'.join(lines) + '\n'


def verified_result(folder):
    """The stored AI paint result of a colour version, only if every file still matches its recorded SHA-256."""
    folder = Path(folder); p = folder / 'aipaint_result.json'
    if not p.is_file() or p.is_symlink(): return None
    r = json.loads(p.read_text(encoding='utf-8'))
    if not r.get('ok'): return None
    for n, h in (r.get('files') or {}).items():
        q = folder / n
        if n not in OUTPUTS or not q.is_file() or q.is_symlink() or digest(q) != h: return None
    if not (folder / 'aipaint_report.txt').is_file() or digest(folder / 'aipaint_report.txt') != r.get('report_sha256'): return None
    return {'files': r['files'], 'report_sha256': r['report_sha256'], 'result_sha256': digest(p), 'filaments': r.get('filaments'),
            'paint': r.get('paint'), 'style': r.get('style'), 'options': r.get('options'), 'multi': r.get('multi')}
