# Update 0.017 build 2026-10-30-1: side-picture AI paint (option C) + "Has props included" + Prompt Builder sync

**INSTALLED on the PC** 2026-10-30 08:01 via Install-Update-0.017-Side-Picture-AI-Paint-r2.bat (sha256 e82d3371...). All 12 installer test steps passed on the PC (RUNTIME VERIFIED for the tested paths):
- **promptbuilder:** 210 presets, 20 holidays.
- **props:** the real filament step in the AI paint Python; with props the blue accent keeps its own filament.
- **multi:** real Blender side prep + combine on the mammoth → shape 99.7%, mirror, match 10.81 / 7.06 / 7.20 = option C.
- **Regressions passed:** accent (incl. the real fox), cleanup, colourcount, studio016, aipaintresult (4 jobs), stages, aipaint unit, defaults.
- **Backups:**
  - color-update-0.017-20261030-080125 = restores b4;
  - b4 backup 154812 kept;
  - b3 145747 removed;
  - the failed r1 attempt folder 075309 (FAIL_REASON) is kept as evidence.

**Still NOT VERIFIED (user to test):**
1. Prompt Builder tab in the browser.
2. The "Has props included" box on the upload form.
3. A real mammoth colour re-export through the studio. Expected:
   - the report says "Pictures used: front + right picture, then the right picture MIRRORED (95.6 %)";
   - the colour page line "Pictures used: ...";
   - shares about 41/17/8/34 (= test C);
   - about 7 extra minutes (front + side runs, both new).
4. The Bambu Studio check.

## r1 FAILED on the PC (2026-10-30 07:53), auto-rolled back
- **Cause:** test_props_017 imported numpy in the launcher Python (pythoncore-3.15 has no numpy), and test_accent_016b was assigned to the launcher Python.
- **Fix (test-only):** numpy work runs in the AI paint Python.
- **Lesson:** the sim must use a launcher Python WITHOUT numpy/PIL (/tmp/claude-0/nonumpy).

Workspace: /home/claude/u017 (cloud). To rebuild: `bash tools/build_all.sh`, then `python3 tools/make_installer.py`.
- **build_all.sh runs:** patch_props.py → port.py → copy hunyuan_color_ui.js → patch_multi.py.
- **Sources:** src/ai_paint_combine.py, src/ai_paint_side_prep.py, keep/test_*.py.
- **base/** = the PC's b4 files.
- **Sim:** /tmp/claude-0/isim/run017.sh (root /tmp/claude-0/i017), rb017.sh.

## Part 1: PROMPT_BUILDER_SYNC_V1
- Generated from the Turnaround Prompt Builder artifact (sha d8affbd9df5c).
- Studio note for holiday sheets: tick "Has props included".

## Part 2: PROPS_TOGGLE_V1
- Upload checkbox → request.json has_props → AI paint options props → AIPAINT_PROPS=1 → the filament step skips ACCENT_TO_OUTLINE.
- Ticking the box picks 9 colours.
- Figure detection / mask cleanup are NOT changed; that waits for a real holiday sheet.

## Part 3: MULTI_PICTURE_AI_PAINT_V1 (option C)
1. **Front run:** 6-40, "AI paint 1/2 (front picture)", when a side picture exists.
2. **Side step:**
   - `side_slot()` (approved left/right);
   - ai_paint_side_prep.py;
   - cache `<cv>/ai_paint_cache/side-<key>`;
   - side run 40-62, "AI paint 2/2";
   - ai_paint_combine.py (visible × cos², shape 90% / 1.5 mm, picture check IoU 0.80 / dE 12):
     - pass → mirror;
     - fail → an other-side run 66-78, "AI paint 3/3".
3. Any failure except cancel → front-only colours + `ai_paint_work/side/FAIL_REASON.txt` + report "PICTURES USED: FRONT ONLY".
4. Report "Pictures used" lines; aipaint_result `multi`; colour page line.
5. `AISTUDIO_AIPAINT_FRONT_ONLY=1` switches the side step off.

## Rollback
Power off, then run Rollback-Color-Update.bat → restores 0.016 build 2026-10-29-4.
