# Changelog

## 0.018 (build 2026-10-30-1) - 0.4 / 0.6 mm nozzle, automatic reviews, Advanced toggle, big green download
- NOZZLE_OPTION_V1: "Nozzle (both H2C nozzles)" 0.4 / 0.6 toggle under "Output length along X (mm)" (0.6 default, last choice
  remembered in the browser). 0.4 jobs use new bambu_template*_04.3mf copies built from Bambu's own presets (Bambu Lab H2C 0.4 nozzle,
  0.20mm High Quality @BBL H2C, Generic PLA @BBL H2C 0.4 nozzle; same colours) and finer colour detail (specks 0.25 mm2, dark-to-outline
  below 1.0 mm / 5 mm2; 0.6 unchanged 0.5 mm2 / 1.5 mm / 10 mm2). Builder: tools/nozzle-templates/.
- AUTO_REVIEW_V1: model review approves itself when the geometry check passed against every picture, mesh checks passed and the solid
  repair passed; colour review approves itself when every picture fits (IoU >= 0.70, none left out) and AI paint is ready. Otherwise the
  review stays manual with the reasons in the status note. config.json "auto_approve_model" / "auto_approve_color": false switch it off.
- ADVANCED_REVIEW_V1: "Advanced mesh and paint" toggle under Prepare image (off by default, not remembered) = manual reviews for that job.
- "Download Bambu full-color 3MF (open in Bambu Studio)" is a big green button.
- Changed: ai_paint_filaments.py, ai_paint_stage.py, hunyuan_bridge.py, hunyuan_color_bridge.py, hunyuan_color_ui.js, hunyuan_portal_ui.js.
  New: bambu_template{_default,,_6,_7,_8,_9}_04.3mf, test_nozzle_018.py, test_auto_review_018.py.
- Status: INSTALLED on GAMING-2026 2026-10-30 17:33 (all 15 installer tests passed). Colour auto-approval RUNTIME VERIFIED in the cloud
  (real app.py + Blender on the mammoth job). NOT VERIFIED: model auto-approval inside a real mesh generation, a full new job, a 0.4 file
  in Bambu Studio. Known limitation: the picture-method backup file (only when AI paint fails) still uses the 0.6 template.
- Setup .exe rebuilt for 0.018 (payload 109 files hash-checked; engine simulated: dry run, install, re-run = 0 changes, edited template
  kept). The .exe itself NOT VERIFIED on Windows.

## 0.017 (build 2026-10-30-3) - side-picture AI paint, props toggle, custom + recommended colour amount
- MULTI_PICTURE_AI_PAINT_V1: AI paint now runs on the front picture AND the side picture. If the model is mirror-symmetric
  (shape check: >= 90 % of the other side has a mirror partner within 1.5 mm) the side run is mirrored onto the other side
  (no extra paint time); otherwise the other side gets its own run. Side run cached per colour version; a failed side run
  falls back to front-only colours with a FAIL_REASON. Real job (9-colour mammoth 20261030-081752): mirrored 95.6 %,
  match to the side picture 9.65 -> 7.13 deltaE. New: ai_paint_combine.py, ai_paint_side_prep.py.
- PROPS_TOGGLE_V1: "Has props included" toggle in the uploader (holiday props are kept in the model and colour models);
  Prompt Builder page updated to the new chat build.
- CUSTOM_COLOUR_COUNT_V1 (b2): Custom button under 4 / 9 colours - choose 5, 6, 7 or 8 filaments.
- COLOUR_ADVICE_V1 (b3): right after a picture is chosen the browser recommends a colour amount (nothing uploaded;
  deltaE merge 14, colours >= 1 % count, +1 outline) and pre-selects it.
- Setup .exe rebuilt for 0.017: also installs the AI paint runtime (uv, Python 3.12.15, torch 2.6.0+cu126, locked packages,
  rasterizer wheel, Hunyuan3D-2 paint code + models, ~19 GB, needs 40 GB free) and ffmpeg 7.1; Bambu templates 6-9 and
  archive_retention.json created only when missing; verify steps for every 0.015-0.017 self-test.
- Updates for an existing 0.016 b5 install: updates/0.017/ (r2, then b2, then b3). Or run the 0.017 Setup .exe in Smart mode.
- Status: INSTALLED and self-tests PASSED on GAMING-2026 (r2, b2, b3). Option C END-TO-END VERIFIED on the mammoth job.
  Setup .exe: built (NSIS 3.09), payload hash-checked, engine simulated (dry run, install, re-run = 0 changes, edited template kept).
  The .exe itself NOT VERIFIED on Windows yet.
- Known open issue: a props job (job 20261030-141136) stopped in Blender solid repair - "Repair grid estimate is too large
  (24836184 cells)" (limit 20,000,000 at voxel 0.4 mm). Not fixed in 0.017.

## 0.016 (build 2026-10-29-1, builds b2-b5)
- Studio shell (header, tabs, Prompt Builder), Bambu download = AI paint file only, white-tip crop fix, turntable video
  upload (ffmpeg 7.1), archived jobs auto-deleted after 24 h. b2 black eyes, b3 AI paint download fix, b4 text clean-up +
  4 or 9 colours, b5 Prompt Builder sync.

## 0.015 (builds up to 2026-10-28-7)
- AI paint (Hunyuan3D-2 texture paint) as the colour stage, unified 12-stage UI, AI paint defaults.

## 0.012 - 0.014
- Internal builds folded into 0.015 / 0.016. Note: the 0.011 colour-coverage update below was never installed; its
  studio changes are superseded by 0.015+ (test_color_coverage_011.py is kept in the repo but not shipped).

## 0.011 (build 2026-10-28-4) - more picture color + hidden-area fill
- Fix (SELF_HIT_OCCLUSION_FIX_V1): the color-stage visibility test no longer counts a face as hidden by ITSELF
  (non-planar quads: the sample point sat micrometres under its own surface). Real job 20261027-192542 (Christmas dragon):
  colour straight from the pictures 29.6% -> 57.5% of the surface, same pictures/alignment/settings.
- New Bambu export choice "Hidden areas" (HIDDEN_AREA_FILL_V1): fill from the nearest picture colour - all / 15 mm / 5 mm,
  or only small gaps (1.5 mm, old behaviour). Filled areas are reported as INFERRED. Real job, fill "all": 0% left without colour
  (57.5% picture, 9.1% mirror side, 33.4% inferred from neighbours).
- Report fix: filled triangles that happened to get filament 1 were counted as "no reference colour".
- Changed: hunyuan_color.py, bambu_color_export.py (export v0.007), hunyuan_color_bridge.py, hunyuan_color_ui.js, Rollback-Color-Update.bat.
  New: test_color_coverage_011.py. Update: updates/0.011/Install-Update-0.011.bat (requires 0.010).
- Installer source (installer/) bumped to 0.011; the Setup .exe in the repo root is still 0.010 until rebuilt.
- Status: CHECKED + RUNTIME VERIFIED in the cloud (bpy 5.2.3 on the real job; update installer simulated: install, re-run, rollback,
  failed-test rollback, edited-file stop). NOT VERIFIED on the PC yet.

## 0.010 Windows .exe installer (setup build 2026-10-28-3)
- Fix: the setup engine ran in 32-bit PowerShell (the .exe is 32-bit, so System32 was redirected to SysWOW64).
  Result on GAMING-2026: false "NVIDIA driver NOT FOUND" (nvidia-smi is 64-bit only) and a false Bambu Studio failure
  (64-bit uninstall entry invisible; winget then returned 0x8A15002B "no applicable update", i.e. already installed).
- setup.nsi now starts %WINDIR%\Sysnative PowerShell (64-bit); engine.ps1 relaunches itself in 64-bit PowerShell if started 32-bit,
  and prints the PowerShell bitness in the report header.
- Bambu Studio: also checks per-user installs; winget 0x8A15002B / 0x8A150061 are reported as already installed;
  Smart keeps an existing different Bambu version instead of reinstalling it.
- Program files unchanged (still 0.010 build 2026-10-28-2).

## 0.010 Windows .exe installer (build 2026-10-28-2)
- NSIS + PowerShell installer: Smart (install only missing/wrong), Full (force reinstall), Check only.
- Models: verify SHA-256 or always re-download. Optional: llama.cpp + Qwen, Bambu Studio, AnythingLLM skill.
- Settings created only when missing; replaced program files backed up (2 newest kept) with RESTORE.cmd.
- Status: CHECKED (cloud dry runs, failure paths, twice-apply). NOT VERIFIED on Windows yet.

## 0.010 (build 2026-10-28-2) - mirror check + misplaced-part label
- New view_consistency.py: detects a mirrored back (or right) picture and flips it (original kept as back.as_drawn.png). Setting `mirror_check`: auto_flip | warn | off.
- Geometry check labels extra + missing in one view as "misplaced part"; same view misplaced twice stops retries.
- Status: INSTALLED and RUNTIME VERIFIED on GAMING-2026 (21 checks + Blender self-test). Real job with a flipped back NOT VERIFIED.
- Details: docs/update-0.010-mirror-check.md

## 0.009 (build 2026-10-28-1) - geometry check
- Silhouette IoU geometry check with retries (best-of-3). Diagnosis of the first real run: docs/diagnosis-0.009-christmas-dragon-tail.md
