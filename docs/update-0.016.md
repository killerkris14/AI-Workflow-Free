# Update 0.016 (build 2026-10-29-1) - INSTALLED on GAMING-2026 2026-10-29 09:52

## First real job after 0.016: fox re-run 20261029-100218-508c5672, colour version 99bda0c7755343c5 (2026-10-29)
- **Crop fix END-TO-END VERIFIED:** the tail tip is now pointed and white in the mesh and in both 3MFs.
  - BiRefNet kept the white tip.
  - The flat tail top is gone.
- **Front check worked as intended:**
  - try 1 (not turned): front view 0.1366, back view 0.110. The AI's azim-0 view showed the fox's back and azim-180 showed the face.
  - The turned repaint gave 0.1072 / 0.1385, with the face on azim 0.
  - (The new mesh's approved alignment points backwards, unlike the old job.)
- **AI paint 3MF:** DRAWING mode, 4 filaments #95979E #D5D2D0 #5BA1D4 (blue, eyes, 0.1%) #45454A; shares 60.9 / 19.6 / 0.1 / 19.4 %.
  - The cloud render matches the sheet well: dark legs, white chest/cheeks, blue eyes, white pointed tail tip.
  - It is at least as good as the bake-off "A current" render.
- **The user's Bambu screenshot ("worse than the 4-way test") matches the PICTURE-METHOD model-bambu.3mf**, not the AI paint file.
  - That file has 5 filaments #9799A1 #E5E3E1 #6D6E75 #B8B6B4 #46474C, and white patches on the cheeks and sides.
  - Confirmed by rendering both files from the screenshot angle (image sent to the user).
  - The job status is SUCCEEDED with ai_paint ok=true, so the 0.016 UI should only offer the AI paint file.
  - **Suspected cause:** a browser page loaded before the 0.016 install (old JS shows the picture-method file as "Download Bambu full-color 3MF"). NOT confirmed. Asked the user to press Ctrl+F5, check that the header says 0.016, and re-download.
  - Sent the AI paint 3MF directly in chat: 20261029-100218-508c5672-AI-paint-4colours.3mf.
- **Observation:** the DRAWING palette spends 1 of the 4 filaments on the blue eyes (0.1% of the surface). The mid-dark grey from the earlier run (#5A5C62, 21.5%) is gone.
  - This is a design trade-off (eyes vs a 4th grey); no change has been made.

## Status
- **INSTALLED** at 09:52 (backup: backups\color-update-0.016-20261029-095212). All 5 installer tests PASSED on the PC:
  - syntax;
  - studio016: retention 7/7; video admit() with the real ffmpeg 7.1 + ComfyUI python_embeded on the test turntable (turn 30, frames 0/7/15/23, 1.3 s); broken video refused with a FAIL_REASON; white-tip crop fix and the checkerboard rule; video sheet gives 4 views; page markers;
  - stages (22 cases);
  - AI paint defaults;
  - AI paint unit.
- **ffmpeg:** downloaded and verified into C:\AI-Workflow-Auto\tools\ffmpeg\ffmpeg.exe.
- **Settings and backups:** created archive_retention.json; pruned backup color-update-0.015-20261028-193350; kept 0.015 b7 (202211) + 0.016. The tidy-up removed "Claude outputs".
- **NOT VERIFIED on the PC:**
  - the UI in the running studio (header, tabs, kept text, Prompt Builder, 404 page, AI paint-only download);
  - a real turntable video;
  - archive auto-delete in the running studio;
  - the .bat self-delete.

## User decisions (2026-10-29)
- Version 0.016.
- Bambu file = AI paint only.
- Video = turntable, ffmpeg allowed.
- Update files = chat download only.
- Include the crop fix + archive auto-delete (24 h).
- "Best" AI paint = 4 filaments + studio colours; the box "Click here if you want more than 4 Filament colors!" = custom.

## Changes (markers)
- **STUDIO_SHELL_V1** (studio_shell_ui.js): header, tabs, status bundle, sessionStorage drafts, Prompt Builder, .3mf Repair placeholder.
- **UI text edits:** hunyuan_portal_ui.js, ui.html, job_layout_ui.js (version after #connection, SMOOTH_TASK_BAR_V1).
- **AI_PAINT_ONLY_V1** (hunyuan_color_ui.js): only the AI paint download (<job>-bambu-full-color.3mf); the picture-method file only as a backup when AI paint fails; no texture-master download. The worker is unchanged.
- **WHITE_TIP_CROP_FIX_V1** (figure_detection.py 0.016).
- **VIDEO_VIEWS_V1:** video_views.py + hunyuan_bridge.admit(video_base64); ffmpeg 7.1 in tools\ffmpeg.
- **ARCHIVE_RETENTION_V1:** archive_retention.py.
- **Cloud build workspace:** /home/claude/u016v.

## Rollback
Power off, then run Rollback-Color-Update.bat → 0.015 build 2026-10-28-7 (also removes ffmpeg + archive_retention.json).
