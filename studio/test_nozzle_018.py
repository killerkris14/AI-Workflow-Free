# NOZZLE_OPTION_V1 installer test (0.018). Launcher Python (no numpy); numpy work runs in the AI paint Python. Temporary folders only.
#   python test_nozzle_018.py <studio folder> <texture_paint python>
import sys, os, json, base64, tempfile, shutil, queue, subprocess, traceback, zipfile, glob
from pathlib import Path
root = Path(sys.argv[1]).resolve(); tp_py = sys.argv[2]; sys.path.insert(0, str(root)); ok = True
def check(c, t):
    global ok
    print(('  ok   ' if c else '  FAIL ') + t, flush=True); ok = ok and bool(c)
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\0' * 64).decode()
COUNTS = {4: 'bambu_template_default', 5: 'bambu_template', 6: 'bambu_template_6', 7: 'bambu_template_7', 8: 'bambu_template_8', 9: 'bambu_template_9'}
def cfg(p):
    with zipfile.ZipFile(p) as z: return json.loads(z.read('Metadata/project_settings.config').decode('utf-8'))
try:
    # ---- 1. the 0.4 templates: Bambu's own H2C 0.4 presets, your colours and plate unchanged ----
    for n, stem in COUNTS.items():
        t6, t4 = root / (stem + '.3mf'), root / (stem + '_04.3mf')
        if not t4.is_file(): check(False, '%s missing' % t4.name); continue
        a, b = cfg(t6), cfg(t4)
        good = (b['printer_settings_id'] == 'Bambu Lab H2C 0.4 nozzle' and b['print_settings_id'] == '0.20mm High Quality @BBL H2C'
                and b['filament_settings_id'] == ['Generic PLA @BBL H2C 0.4 nozzle'] * n and b['nozzle_diameter'] == ['0.4', '0.4']
                and b['layer_height'] == '0.2' and b['line_width'] == '0.42' and b['filament_colour'] == a['filament_colour'] and len(b['filament_colour']) == n)
        with zipfile.ZipFile(t6) as z6, zipfile.ZipFile(t4) as z4:
            same = sorted(z6.namelist()) == sorted(z4.namelist()) and all(z6.read(x) == z4.read(x) for x in z6.namelist() if x != 'Metadata/project_settings.config')
        left = [k for k, v in b.items() if '0.6 nozzle' in json.dumps(v)]
        check(good and same and not left and a['printer_settings_id'] == 'Bambu Lab H2C 0.6 nozzle',
              '%s: H2C 0.4 nozzle (both), 0.20mm High Quality, Generic PLA 0.4 nozzle, %d colours = %s; model/plate files identical; 0.6 template untouched' % (t4.name, n, stem + '.3mf'))
    import hunyuan_bridge as HY, hunyuan_color_bridge as HB, ai_paint_stage as A
    tmp = Path(tempfile.mkdtemp(prefix='nozzle018-'))
    try:
        # ---- 2. upload: nozzle_mm stored per job; older jobs / pages = 0.6 ----
        HY.CONTEXT.update(config=lambda: {'allow_generated_code_execution': True}, JOBS=tmp, TASKS=queue.Queue(), status=lambda job, name, **kw: None)
        base = {'image_base64': PNG, 'length_mm': 120, 'quality': 'standard', 'authorize_processing': True, 'ai_paint_filaments': 4}
        j4 = tmp / HY.admit(dict(base, nozzle_mm=0.4))['id']; j6 = tmp / HY.admit(dict(base, nozzle_mm=0.6))['id']; jn = tmp / HY.admit(dict(base))['id']
        r = lambda j: json.loads((j / 'request.json').read_text())
        check(r(j4)['nozzle_mm'] == 0.4 and r(j6)['nozzle_mm'] == 0.6 and r(jn)['nozzle_mm'] == 0.6, 'upload: 0.4 -> 0.4, 0.6 -> 0.6, page without the toggle -> 0.6')
        bad = []
        for v in (0.5, True, '0.4', None, 4):
            try: HY.admit(dict(base, nozzle_mm=v)); bad.append(v)
            except ValueError: pass
        check(not bad, 'upload: anything other than 0.4 / 0.6 is refused (%s)' % (bad or 'none accepted'))
        old = tmp / 'old'; old.mkdir(); (old / 'request.json').write_text(json.dumps({'engine': 'hunyuan'}))
        check(HB.nozzle_mm(j4) == 0.4 and HB.nozzle_mm(j6) == 0.6 and HB.nozzle_mm(old) == 0.6, 'colour export reads the nozzle from the upload (older jobs = 0.6)')
        check(HB.ai_paint_best(j4).get('nozzle') == 0.4 and 'nozzle' not in HB.ai_paint_best(j6) and 'nozzle' not in HB.ai_paint_best(old), 'AI paint options: nozzle key only for 0.4 jobs (0.6 = exactly as 0.017)')
        check(HB.with_props({'enabled': True, 'filaments': 4, 'colours': 'auto', 'nozzle': 0.4}, j6) == {'enabled': True, 'filaments': 4, 'colours': 'auto'}
              and HB.with_props({'enabled': True, 'filaments': 4, 'colours': 'auto'}, j4).get('nozzle') == 0.4, 'custom export box follows the upload toggle only')
        # ---- 3. AI paint stage: template choice + validation ----
        check(A.template_name(6, 0.4) == 'bambu_template_6_04.3mf' and A.template_name(6) == 'bambu_template_6.3mf' and A.template_counts(root, 0.4) == [4, 5, 6, 7, 8, 9] and A.template_counts(root) == [4, 5, 6, 7, 8, 9],
              'AI paint stage finds all 0.4 and 0.6 templates (4-9 filaments)')
        if A.install_status(root)['installed']:
            check(A.options(HB.ai_paint_best(j4), root) == {'enabled': True, 'filaments': 4, 'colours': 'studio', 'nozzle': 0.4}, 'AI paint stage accepts nozzle 0.4')
            check(A.options(HB.ai_paint_best(j6), root) == {'enabled': True, 'filaments': 4, 'colours': 'studio'}, '0.6 -> options exactly as in 0.017')
            try: A.options({'enabled': True, 'nozzle': 0.5}, root); check(False, 'nozzle 0.5 refused')
            except ValueError: check(True, 'nozzle 0.5 refused')
        src = (root / 'ai_paint_stage.py').read_text(encoding='utf-8')
        check("AIPAINT_NOZZLE='0.4' if opts.get('nozzle') == 0.4 else '0.6'" in src and "'Nozzle: %s mm on both H2C nozzles" in src, 'AI paint run passes the nozzle to the filament step and the report names it')
        # ---- 4. real filament step (AI paint Python) at 0.6 and 0.4 on a synthetic model ----
        maker = tmp / 'make_model.py'
        maker.write_text("""import sys
from pathlib import Path
import numpy as np
from PIL import Image
tmp = Path(sys.argv[1]); n = 60; xs, ys = np.meshgrid(np.arange(n + 1), np.arange(n + 1)); V = np.c_[xs.ravel(), ys.ravel(), np.zeros(xs.size)].astype(float); T = []; col = []
GREY, WHITE, MID, DARK = (150, 152, 158), (213, 210, 208), (98, 100, 106), (69, 69, 74)
for y in range(n):
    for x in range(n):
        a = y * (n + 1) + x; c = GREY if x < 27 else WHITE if x < 42 else MID if x < 51 else DARK
        T += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]; col += [c, c]
prep = tmp / 'prep'; prep.mkdir(); np.savez_compressed(prep / 'mesh.npz', V=V, T=np.array(T), Vh=V)
img = np.zeros((240, 240, 4), np.uint8); img[..., 3] = 255
img[:, :108, :3] = GREY; img[:, 108:168, :3] = WHITE; img[:, 168:204, :3] = MID; img[:, 204:, :3] = DARK; img[100:104, 20:120, :3] = (20, 20, 22)
Image.fromarray(img).save(prep / 'ref_front.png')
for z in ('0.6', '0.4'):
    w = tmp / ('w' + z); w.mkdir(); np.save(w / 'tri_rgb.npy', np.array(col, np.float32) / 255)
print('MODEL_MADE')
""", encoding='utf-8')
        mk = subprocess.run([tp_py, '-I', str(maker), str(tmp)], capture_output=True, text=True, timeout=300)
        check(mk.returncode == 0 and 'MODEL_MADE' in mk.stdout, 'synthetic test model made in the AI paint Python' + ('' if mk.returncode == 0 else ': ' + mk.stderr[-300:]))
        res = {}
        for z in ('0.6', '0.4'):
            w = tmp / ('w' + z)
            p = subprocess.run([tp_py, str(root / 'ai_paint_filaments.py'), str(root), str(tmp / 'prep'), str(w), '4', 'studio'], capture_output=True, text=True, timeout=600, env=dict(os.environ, AIPAINT_NOZZLE=z, AIPAINT_PROPS='0'))
            res[z] = json.loads((w / 'filaments.json').read_text(encoding='utf-8')) if (w / 'filaments.json').is_file() else {'error': p.stderr[-400:]}
            f = (res[z].get('files') or [{}])[0]; c = cfg(f['file']) if f.get('file') else {}
            want = ('bambu_template_default_04.3mf', 'Bambu Lab H2C 0.4 nozzle') if z == '0.4' else ('bambu_template_default.3mf', 'Bambu Lab H2C 0.6 nozzle')
            check(res[z].get('ok') and f.get('template') == want[0] and c.get('printer_settings_id') == want[1] and res[z].get('nozzle_mm') == float(z),
                  'filament step %s mm: template %s, written 3MF says %s, detail %s' % (z, f.get('template'), c.get('printer_settings_id'), res[z].get('detail') or res[z].get('error')))
        check((res['0.6'].get('detail') or {}).get('speck_mm2') == 0.5 and (res['0.4'].get('detail') or {}).get('speck_mm2') == 0.25, 'finer colour detail only at 0.4 (specks 0.25 mm2 vs 0.5 mm2 at 0.6)')
        # ---- 5. a real AI paint job on this PC (read-only: work is done in a temporary folder) ----
        jobs = sorted(glob.glob(str(root / 'Jobs' / '*' / 'color_versions' / '*' / 'ai_paint_work' / 'tri_rgb.npy')), key=os.path.getmtime, reverse=True)
        jobs = [Path(p).parent for p in jobs if (Path(p).parent / 'prep' / 'mesh.npz').is_file()]
        if not jobs: print('  SKIPPED real job: no finished AI paint job with prep/mesh.npz in Jobs (synthetic test above still ran)', flush=True)
        else:
            jw = jobs[0]; out = {}
            for z in ('0.6', '0.4'):
                w = tmp / ('real' + z); w.mkdir(); shutil.copy2(jw / 'tri_rgb.npy', w / 'tri_rgb.npy')
                p = subprocess.run([tp_py, str(root / 'ai_paint_filaments.py'), str(root), str(jw / 'prep'), str(w), '4', 'studio'], capture_output=True, text=True, timeout=1200, env=dict(os.environ, AIPAINT_NOZZLE=z, AIPAINT_PROPS='0'))
                out[z] = json.loads((w / 'filaments.json').read_text(encoding='utf-8')) if (w / 'filaments.json').is_file() else {'error': p.stderr[-400:]}
            a, b = (out['0.6'].get('files') or [{}])[0], (out['0.4'].get('files') or [{}])[0]
            check(out['0.6'].get('ok') and out['0.4'].get('ok') and b.get('palette') == a.get('palette'),
                  'real job %s: both written, same filament colours %s; dark areas moved to the outline colour %s %% (0.6) -> %s %% (0.4)' % (
                      jw.parents[2].name, b.get('palette'), a.get('thin_dark_to_outline_percent'), b.get('thin_dark_to_outline_percent')))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    portal = (root / 'hunyuan_portal_ui.js').read_text(encoding='utf-8')
    i_len = portal.find("field(form,'Output length along X (mm)',length);"); i_nz = portal.find("field(form,'Nozzle (both H2C nozzles)',nzRow)"); i_q = portal.find("field(form,'Quality',quality)")
    check('NOZZLE_OPTION_V1' in portal and 0 < i_len < i_nz < i_q and 'nozzle_mm:nzMm' in portal and "'0.4 mm nozzle'" in portal and "'0.6 mm nozzle'" in portal and 'let nzMm=0.6' in portal,
          'upload form: 0.4 / 0.6 toggle right under "Output length along X (mm)", 0.6 by default, sent with the upload')
except Exception:
    traceback.print_exc(); ok = False
print('NOZZLE_018_TEST_PASSED' if ok else 'NOZZLE_018_TEST_FAILED', flush=True)
sys.exit(0 if ok else 1)
