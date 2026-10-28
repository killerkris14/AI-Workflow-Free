# Changelog

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
