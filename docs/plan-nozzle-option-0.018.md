# Update 0.018 build 2026-10-30-1: 0.4 / 0.6 nozzle toggle + automatic model/colour review + big green download - BUILT, NOT YET INSTALLED

Install-Update-0.018-Nozzle-And-Auto-Review.bat (sha256 a58c2a9f63549ccf8d2f6892d0858ac626162c952199a595931b7c42ba0196e2).
Supersedes the earlier Install-Update-0.018-Nozzle-0.4-or-0.6.bat (08d47ac8..., never installed; removed from outputs).
Requires 0.017 build 2026-10-30-3 AND the 6 installed 0.6 templates at the hashes collected from the PC (stops otherwise).

## User decisions (2026-10-30)
- Toggle under "Output length along X (mm)", one always selected, default 0.6; 0.4 = both H2C nozzles 0.4.
- 0.4 print profile "0.20mm High Quality @BBL H2C"; 0.4 also gets finer colour detail.
- "Auto complete the model review and the color review; only manual when it fails something." Big green
  "Download Bambu full-color 3MF (open in Bambu Studio)" button. Combine all into 0.018 before installing.

## Part 1 NOZZLE_OPTION_V1 (evidence: Collect-Nozzle-Info + Collect-Nozzle-Profiles-2; Bambu Studio 02.08.02.61, profiles 02.08.00.06)
- Templates = H2C 0.6 nozzle / 0.24mm Balanced Strength / Generic PLA @BBL H2C (only valid for 0.6/0.8); flattened config, 580 keys.
- Method check: resolving the 0.6 system chains (inherits + include) reproduces the existing 0.6 templates -> method valid.
- 0.4 = only keys whose resolved value differs: machine 8, process 59, filament name; nozzle_volume_type Standard,Standard;
  extruder_nozzle_stats Standard#1/Standard#3. Tools: /home/claude/u018/tools/build_04.py + resolve.py + profiles.json.
- Code: hunyuan_portal_ui.js (#hunyuan-nozzle, localStorage 'aistudio-nozzle-mm'), hunyuan_bridge.nozzle_choice -> request.json nozzle_mm,
  hunyuan_color_bridge.nozzle_mm + 'nozzle' key only for 0.4, ai_paint_stage template_name/AIPAINT_NOZZLE/report line,
  ai_paint_filaments DETAIL 0.6 = 0.5 mm2 / 1.5 mm / 10 mm2 (unchanged), 0.4 = 0.25 / 1.0 / 5.
- Real jobs: 0.6 output byte-identical to 0.017; 0.4 mammoth thin-dark-to-outline 2.73 -> 1.33 % (4 col); fox ~0.3-0.6 % triangles changed.
- Limitation: picture-method backup export (hash-pinned hunyuan_color.py) still uses the 0.6 template.

## Part 2 AUTO_REVIEW_V1
- Already existed: AUTO_COLOR_AFTER_EXPORT_V1 + AUTOMATIC_COLOR_RUN_V1 (mask review auto-approved), so the colour run stopped only at the final preview.
- Model (hunyuan_bridge.auto_model_reasons / auto_model_export, called after verify_geometry in the generate stage): approved when
  solid (not articulated), checks ok, auto repair not failed, repaired solid passed topology at the same voxel, geometry check ran for the
  shown candidate and passed. Export = same as "Export repaired solid"/"Export" (allow_mesh_warnings False, solid_repair_approved).
  Recorded in hunyuan_progress auto_review_model. Manual reprocess/adjust stays manual. Off: config.json "auto_approve_model": false.
- Colour (hunyuan_color_bridge.auto_color_reasons / auto_export_config, in run_task after an AUTOMATIC align/preview): approved when not a
  custom-AI-paint upload, AI paint installed + options valid (incl. nozzle/props/count), every view fit IoU >= 0.70 (evidence IoU),
  no poor_fit, no excluded view, template readable. Export = one-click UI defaults (template filaments, dominant, 4 mm2, keep, accept
  neutral areas) + ai_paint_best. Not stopping on orientation/direction ambiguity or low picture coverage: present in ALL real approved jobs
  (front/back direction_ambiguous, ~30-38 % mapped). Real fits 0.81-0.96 -> 6/6 real previews on the PC would auto-approve.
  ADVANCED_REVIEW_V1: upload toggle "Advanced mesh and paint" under Prepare image (#hunyuan-advanced-review-box, off by default, NOT
  remembered) -> request.json advanced_review true -> both reviews manual for that job (colour still auto-runs masks -> preview, = 0.017).
  Playwright: default false sent, ticked true sent, unticked after reload.
  Off: "auto_approve_color": false. A stop shows "Automatic approval stopped for your review: <reasons>" in the status note.
- hunyuan_color_ui.js button(): the AI paint download is a big green button (#bambu-download-main, #1e9e57, 19 px).

## Verification (cloud)
- test_nozzle_018 + test_auto_review_018 + all 13 earlier tests: 15/15 PASSED in the installer sim (numpy-free launcher); second run
  ALREADY INSTALLED; rollback byte-identical to 0.017 b3; failed test -> auto rollback + FAIL_REASON; re-saved template -> stop.
- RUNTIME (cloud, real app.py + bpy Blender, real mammoth 20261029-115943 job): Automatic colour went prepare -> masks auto -> align ->
  colour review auto-approved -> export (model-bambu.3mf) with no manual step; settings.json shows the defaults + auto_review_color.
  AI paint is a stub in the cloud (no GPU) and failed there as expected.
- NOT RUNTIME VERIFIED: the model auto-approval inside a real mesh generation (needs ComfyUI/Hunyuan; unit-tested only);
  install on the PC; a full new job end to end; 0.4 file opened in Bambu Studio; real 0.4 print.
- Workspace /home/claude/u018 (base/ src/ new/ out/ build/ tools/patch_nozzle.py + patch_auto.py + make_installer.py),
  sim root /tmp/claude-0/i018 (snapshot i018_snap), isim/run018.sh, run018f.sh, rb018.sh, integration root /tmp/claude-0/ie018.

## Rollback
Power off, run Rollback-Color-Update.bat -> 0.017 build 2026-10-30-3 (removes the _04 templates and both tests).
