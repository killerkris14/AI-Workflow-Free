# Update 0.017 build 2026-10-30-3: recommended colour amount after choosing an image (COLOUR_ADVICE_V1)

**INSTALLED on the PC** 2026-10-30 11:07 (Install-Update-0.017-b3-Recommended-Colours.bat, sha256 ec4ea2ca...). All 13 installer test steps passed on the PC.
- **Backups kept:**
  - 0.017-093042: restores 0.017 b1.
  - 0.017-110734: restores 0.017 b2.
- The backup that restored 0.016 b4 (080125) was removed (keep the last 2). A rollback to 0.016 is no longer possible with Rollback-Color-Update.bat.

**User request:** look at the uploaded image and recommend a colour amount, pre-selected before "Prepare image" is pressed.

## How it works (browser JavaScript in hunyuan_portal_ui.js; nothing uploaded; ~10-60 ms)
- **Trigger:** `image` input 'change'. Image files only; videos are skipped.
- **Steps:**
  1. Scale the image to 400 px.
  2. Background = light, colourless pixels (min ≥ 200, spread ≤ 28, or alpha < 128) flood-filled from the border.
  3. Lab colours. Outline pixels = L < 32 and chroma < 25.
  4. Flat pixels = foreground, not near an outline, not at the edge.
  5. Lab bins (4 units) → deterministic farthest-point start of 16 colours → k-means (30 iterations).
  6. Merge the closest pair (plain deltaE76) until the closest pair is more than **14** apart.
  7. Colours ≥ 1% count, + 1 for the outline/darkest filament.
  8. Recommendation = clamp 4..9.
- **Style check:** dark < 25% and top-12 bins ≥ 50% → flat; otherwise a "shaded drawing" note.
- **Accents:** colours of 0.1-1% → note "prints in the outline colour at 4".
- **UI:**
  - box `#hunyuan-colour-advice` under the buttons: "Recommended for this picture: N colours" + swatches + text;
  - pre-selects 4 / 9 / Custom N;
  - if "Has props included" is ticked and the result is 4 → 9;
  - the user can change the amount afterwards; a new image re-recommends.

## Calibration (real sheets on the PC, Chromium; merge thresholds 12-16 tried, 14 chosen)

| Sheet | Recommended | Notes |
|---|---|---|
| fox 20261028-194817 | 4 | the blue eyes were NOT detected as an accent |
| mammoth 20261029-115943 | 4 | an accent note shown; the 9-colour AI file used about 6 meaningful filaments (browns from drawing shading) |
| 6-colour dragon 20261028-183107 | 6 | |
| Christmas dragon 20261028-092803 | 7 | |
| shaded sheet 20261027-192542 | 12 → 9 | |

## Verification
- **Cloud:** Playwright on the real app.py sim; installer sim; rollback.
- **PC:** the installer tests passed (static checks of the installed JS + all regressions).

**NOT VERIFIED:** the box in the user's browser; whether the recommended amounts give good prints.

**Rollback:** Rollback-Color-Update.bat → 0.017 build 2026-10-30-2.
