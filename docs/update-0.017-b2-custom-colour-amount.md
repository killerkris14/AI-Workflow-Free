# Update 0.017 build 2026-10-30-2: Custom colour amount 5-8 (CUSTOM_COLOUR_COUNT_V1)

**INSTALLED on the PC** 2026-10-30 09:30. All 12 installer test steps passed on the PC.
- **Backups kept:** 0.017-080125 (restores 0.016 b4) and 0.017-093042 (restores 0.017 b1). The 0.016 b4 backup 154812 was removed (keep the last 2).
- **Note:** in this install the multi test's real mammoth check printed nothing (skipped). The old mammoth job 20261029-115943-62474460 is no longer in Jobs (probably archived). The user's new mammoth job is 20261030-081752-2a5a9d61.

## 0.017 multi-picture AI paint: END-TO-END on a real job (job 20261030-081752-2a5a9d61, version 96685fe7723841a1, 9 colours)
- **The report says:** "Pictures used: front + right picture, then the right picture MIRRORED onto the other side (95.6 % of it)".
  - shape 99.7%;
  - match: front only {back 7.8, front 10.42, left 9.65} → combined {back 7.22, front 10.75, left 7.13};
  - AI paint 672 s.
- **The user viewed it in Bambu Studio:** "the 9 color wooly mammoth looks great", but they don't own that many brown filaments.
- **Finding:** in the 9-colour file, 3 filaments are almost unused: #D2BB9F 0.1%, #B69D81 0.0%, #967457 0.1%.
  - Real use = 6 colours: #99603B 20.9, #834F2F 18.3, #6D4633 7.6, #72482F 4.8, #EEDEC8 7.6, #5D3C2B 40.6.
  - So a Custom 6 should look almost the same.
- **Idea (not built):** drop filaments under ~0.5% automatically, or warn about them.

## Change
- **hunyuan_portal_ui.js:**
  - a "Custom - 5, 6, 7 or 8 colours" button `#hunyuan-colour-custom-toggle` under 4 / 9, with row `#hunyuan-colour-custom` (5/6/7/8);
  - "Has props included" switches to 9 only when on 4.
- **hunyuan_bridge.admit:** ai_paint_filaments is an int 4-9, else 4.
- **hunyuan_color_bridge.ai_paint_best:** an int 4-9.
- **test_colour_count_016d.py:** updated.

## Verification
- **Cloud:** Playwright on the real app.py sim; installer sim; rollback.
- **PC:** the installer tests passed.
- **NOT VERIFIED:** the Custom button in the user's browser; a 5-8 colour export in Bambu.

**Rollback:** Rollback-Color-Update.bat → 0.017 build 2026-10-30-1.
