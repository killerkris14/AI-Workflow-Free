# NOZZLE_OPTION_V1: builds the 0.4 mm copies of the studio's Bambu templates from the user's own Bambu system profiles.
# Method: resolve machine / process / filament chains (inherits + include) for the 0.6 presets used by the templates and for the
# 0.4 presets; apply ONLY the keys whose resolved value differs, plus the preset names. Everything else (colours, plate, gcode) is kept.
import json, re, sys, zipfile, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from resolve import res
SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
M06, M04 = 'Bambu Lab H2C 0.6 nozzle', 'Bambu Lab H2C 0.4 nozzle'
P06, P04 = '0.24mm Balanced Strength @BBL H2C 0.6 nozzle', '0.20mm High Quality @BBL H2C'
F06, F04 = 'Generic PLA @BBL H2C', 'Generic PLA @BBL H2C 0.4 nozzle'
num = lambda v: re.sub(r'^(-?\d+)\.0+$', r'\1', v) if isinstance(v, str) else [num(x) for x in v] if isinstance(v, list) else v
def diff(kind, a, b):
    A, B = res(kind, a), res(kind, b)
    return {k: B[k] for k in B if A.get(k) != B[k] and k != 'compatible_printers'}
DM, DP, DF = diff('machine', M06, M04), diff('process', P06, P04), diff('filament', F06, F04)
report = {'machine_changes': sorted(DM), 'process_changes': sorted(DP), 'filament_changes': sorted(DF), 'templates': {}}
for t in sorted(SRC.glob('bambu_template*.3mf')):
    if t.stem.endswith('_04'): continue
    z = zipfile.ZipFile(t); raw = z.read('Metadata/project_settings.config').decode('utf-8'); C = json.loads(raw)
    assert C['printer_settings_id'] == M06 and C['print_settings_id'] == P06 and set(C['filament_settings_id']) == {F06}, t.name + ': not the expected 0.6 template'
    nf = len(C['filament_settings_id']); changed = []
    for k, v in list(DM.items()) + list(DP.items()):
        if k not in C: raise SystemExit('%s: key %s missing in template' % (t.name, k))
        C[k] = num(v); changed.append(k)
    for k, v in DF.items():
        if k not in C: raise SystemExit('%s: filament key %s missing' % (t.name, k))
        tv = C[k]; v = num(v)
        C[k] = v * nf if isinstance(v, list) and len(tv) == nf * len(v) else v * nf * 3 if isinstance(v, list) and len(v) == 1 and len(tv) == nf * 3 else v; changed.append(k)
    C['printer_settings_id'] = M04; C['print_settings_id'] = P04; C['filament_settings_id'] = [F04] * nf
    C['print_compatible_printers'] = [M04]
    C['nozzle_volume_type'] = ['Standard', 'Standard']                     # BambuStudio.conf: "Bambu Lab H2C 0.4 nozzle": "Standard,Standard"
    for k in ('extruder_nozzle_stats', 'extruder_nozzle_stats_new'):
        if k in C: C[k] = ['Standard#1', 'Standard#3']
    left = [k for k, v in C.items() if '0.6 nozzle' in json.dumps(v)]
    if left: raise SystemExit('%s: still mentions 0.6 nozzle in %s' % (t.name, left))
    new = (json.dumps(C, indent=4, ensure_ascii=False).replace('\n', '\r\n') + '\r\n').encode('utf-8')
    dst = OUT / (t.stem + '_04.3mf')
    with zipfile.ZipFile(dst, 'w') as o:
        for i in z.infolist():
            data = new if i.filename == 'Metadata/project_settings.config' else z.read(i.filename)
            o.writestr(i, data, compress_type=i.compress_type)
    report['templates'][dst.name] = {'from': t.name, 'filaments': nf, 'colours': C['filament_colour'], 'keys_changed': len(changed) + 6, 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()}
(OUT / 'build_04_report.json').write_text(json.dumps(report, indent=1), encoding='utf-8'); print(json.dumps(report, indent=1)[:1500])
