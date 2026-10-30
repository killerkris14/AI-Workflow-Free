# Color coverage diagnosis (0.010) — why so much of the print has no reference color

Job: 20261027-192542-524cbcee (Christmas dragon), color version 2fbc895fa4d748f6. Installed code = repo 0.010 (hashes match).
Method: read-only replay of hunyuan_color.transfer() rules per face in bpy 5.2.3 on the job's model-colored.blend, settings.json, reference_masks.npz. Replay matches the recorded material assignment 100% (209,536 faces).

## Real job numbers (bambu_report.txt)
- Reference color only 29.62% of surface; 17.62% symmetry; 13.20% neighbour fill; 39.56% no reference -> painted filament 1 (#31130F dark brown, policy "dominant"). Preview shows these as gray.
- Quantization error CIE76 dE mean 12.76, p95 24.05 (5 filaments, "distinct" palette, shading "reduce").
- Subject is small in the references: ~320-550 px across in 1024 px images (3.5-3.9 px/mm on a 120 mm model).

## Why faces got no reference color (share of total surface, current rules)
occluded 40.92 | local fit < 0.80 14.51 | outside mask 9.66 | grazing (facing <= 0.15) 4.92 | back-facing in all views 0.36

## Root cause of most "occluded": self-hit bug
- 88% of occlusion ray hits are the face's OWN polygon at 0.0007-0.013 mm (quads are non-planar; the sample at the quad's vertex average lies under its own triangulated surface, so the ray toward the camera hits itself).
- Ignoring own-polygon hits (no thresholds changed): mapped reference color 29.63% -> 57.54% of surface; truly occluded drops 40.92% -> 13.0%.

## Sensitivity (current rules otherwise)
local fit 0.6: 34.9% | local fit off: 36.8% | mask center-only: 29.7% | grazing 0.05: 30.6% (all much smaller than the self-hit fix).

## Proposed (item 1 and the fill implemented in 0.011, see below)
1. 0.011: occlusion test ignores hits on the face's own polygon (smallest change, biggest effect). Test: same job replay + real job in Blender + Bambu report.
2. Later, separate: nearest-color fill for remaining unseen areas (reported as inferred, distance setting); palette from true color averages or the user's real AMS colors (report dE); view blending to reduce speckle; optional bottom/right views; larger subject in references.

## Implemented in 0.011 (build 2026-10-28-4) - user chose "bug fix + fill hidden areas"
- SELF_HIT_OCCLUSION_FIX_V1 in hunyuan_color.transfer(): blocked() skips hits on the face's own polygon (owner map from loop_triangles).
- HIDDEN_AREA_FILL_V1: Bambu export setting fill_unseen = all | 15 | 5 | 1.5 (UI default all; old configs default 1.5). Fill grows nearest filament ring by ring; isolated parts stay unfilled. Report accounting fixed.
- Real job replay with the actual 0.011 code (bpy 5.2.3), same settings (5 filaments, dominant, 4 mm2, shading reduce):
  0.010 baseline reproduced exactly: 29.62 / 17.62 / 13.20 / 39.56 (picture / mirror / neighbours / none), dE 12.76.
  0.011 fill 1.5: 57.53 / 9.05 / 7.38 / 26.05 | fill 5: 57.53 / 9.05 / 17.15 / 16.28 | fill 15: 57.53 / 9.05 / 26.61 / 6.82 | fill all: 57.53 / 9.05 / 33.42 / 0.00. dE 11.97.
- Visual check of the exported 3MF paint (cloud render): body mostly red/green instead of dark brown; fill "all" paints the tail/antlers from neighbouring colours with streaks (e.g. green antlers where the drawing has brown) - inferred, not the drawing.
- Tests: test_color_coverage_011.py (old rule reproduces the bug 786/1600 faces, new 1600/1600; real occluder still hides; fill distances; report); selftest_color_update.py passes; update installer simulated (install, re-run, rollback, failed-test auto-rollback, edited-file stop).
- NOT VERIFIED on the PC: install, Blender 5.2.2 runtime, UI control, new color preview + export of a real job, opening in Bambu Studio.
- Next candidates (separate updates): palette from true averages / real AMS colours (dE ~12 is visible); view blending to reduce speckle; smarter fill for parts that differ from their neighbours.
