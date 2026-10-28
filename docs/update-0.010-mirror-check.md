
# Update 0.010 (build 2026-10-28-2): mirror check + misplaced-part label

Installer: Install-Update-0.010.bat (requires 0.009 build 2026-10-28-1; all 7 replaced files hash-checked against the 0.009 install).

## Status
- INSTALLED on GAMING-2026 (C:\AI-Workflow-Auto) 2026-10-27 20:24. Backup: backups\color-update-0.010-20261027-202432.
- RUNTIME VERIFIED on the user's PC: syntax (launcher Python 3.15), 21 mirror/retry checks via the real prepare-stage function and ComfyUI Python (incl. real Christmas sheet: back mirrored, 0.885 vs 0.825), Blender 5.2 self-test PASSED.
- NOT VERIFIED: header shows 0.010 after restart; real job with flipped back (checkpoint 1 + 2); thresholds on a known-consistent AI sheet.

## Changes
- NEW view_consistency.py (ComfyUI Python): front vs back (left vs right) silhouette test. Back as drawn matching front better than flipped = mirrored. auto_flip (default) flips back.png, keeps back.as_drawn.png, writes view_consistency.json + evidence PNG. Setting autoroute_settings.json "mirror_check": auto_flip | warn | off. Thresholds: asymmetry >= 0.04, margin >= 0.02 and >= 0.25 x asymmetry.
- hunyuan_autoroute.py: check_view_mirroring() after sheet cleanup; message in checkpoint-1 note; failure never blocks, writes view_consistency_error.txt.
- hunyuan_color.py: geometry check labels extra+missing (missing >= 2% and >= 0.5 x extra) as misplaced_part; same pass/fail limits.
- hunyuan_bridge.py: same view misplaced twice in a row -> stop retries with reason; checkpoint-2 note mentions flipped picture.
- hunyuan_color_bridge.py: WORKER_SHA256 pin updated. job_layout_ui.js: labels/legend. selftest_color_update.py: moved-tail case. Rollback-Color-Update.bat: version 0.010.
- Backups: keep 2 newest completed color-update backups; failed-attempt folders (FAIL_REASON.txt) kept.

## Evidence (cloud, bpy 5.2.3 + pwsh 7.4 simulation)
- Real sheet: as drawn 0.885 vs flipped 0.825 -> mirrored. Mesh-rendered true front/back -> consistent.
- Real try-3 mesh, 0.009 code: front 5.41/3.13, top 6.52/5.39 (reproduces user run). With flipped back: front 0.04, back 0.01; only top misplaced_part; score 0.42 -> 0.55. Forked old mesh: top extra 9.95, score 0.37 (still lower).
- Installer simulation: install, re-run (no change), rollback, failed-test auto-rollback, tampered-file stop.
