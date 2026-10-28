# 0.009 geometry check — first real run (job 20261027-192542-524cbcee, Christmas dragon, High)

## Evidence inspected
- geometry_check.json for attempts 1–3, preview_top.png per try, fit_front/fit_top for try 3
- Final export 20261027-192542-524cbcee-bambu-full-color.3mf and older 20261027-181407-cd67f187 (Ultra, pre-0.009) 3MF
- Evidence zip 20261027-192340 (job 181407; code incl. hunyuan_color.py GEOMETRY_CHECK_V1)

## Findings
- Old 181407 export: forked (doubled) tail, 2 mesh parts. Pre-0.009, no check ran.
- 0.009 tries: try 1 = single tail + detached floating loop; try 2 = forked tail (top extra 10.65%, correctly the worst); try 3 = single tail, swept sideways (top extra 6.92 / missing 5.83; front extra 5.41 / missing 3.13). Best-of-3 picked try 3 correctly.
- Final 192542 export: single tail. 4 parts: main + 3 tiny specks (48/12/12 faces).
- Root cause for no try passing: the AI reference sheet contradicts itself. Front AND back pictures both draw the tail curl on the viewer's right (impossible for one tail). Top draws it straight back; side draws a vertical curl.
  - Silhouette test: lower-body IoU front vs back as drawn 0.789, vs back mirrored 0.569 (a consistent pair should match better mirrored).
- Exported try-3 mesh matches the FRONT picture (tail on viewer's right from +X). The check's front overlay shows the mesh tail on the left while back fits almost perfectly (0.06% extra) — the alignment resolved the front/back conflict in favour of back. Not yet proven whether this is the alignment's free orientation choice (likely) or an export mirror (unlikely: mesh agrees with its conditioning front image).
- "extra geometry" label is misleading for try 3: extra ≈ missing in the same view = misplaced part, not a duplicate.
- Retry 2 rule "drop worst IoU view" dropped back — happened to be the contradicting view.

## Proposed 0.010 (implemented in 0.010 as items 1 and 2)
1. Pre-generation reference consistency check (front vs mirrored back silhouette), shown at checkpoint 1.
2. Reason classification: extra-only = "extra part", extra≈missing = "misplaced part / pictures disagree"; known contradictions stop blind retries.
3. Detached-piece count in the geometry check (not yet implemented).
Needs a known-good sheet to calibrate thresholds for #1.
