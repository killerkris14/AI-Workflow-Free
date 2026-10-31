0.4 mm nozzle templates (NOZZLE_OPTION_V1, 0.018)

build_04.py makes bambu_template*_04.3mf from the 0.6 templates in a studio folder:
  python build_04.py <folder with bambu_template*.3mf> <output folder>
It resolves the Bambu Studio system presets in profiles.json (H2C 0.4 / 0.6 machine, 0.20mm High Quality /
0.24mm Balanced Strength process, Generic PLA filament; Bambu Studio 02.08.02.61, profiles 02.08.00.06) and changes
only the settings that differ between the 0.6 and 0.4 presets. Rebuild when you re-save your 0.6 templates in
Bambu Studio (the 0.018 update stops if they no longer match). To refresh profiles.json run
tools\Collect-Nozzle-Profiles-2.bat and convert its "### kind/name" lines into {"kind/name": {...}}.
