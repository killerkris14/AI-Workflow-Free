# Windows .exe installer for AI Modeling Studio 0.010

File: AI-Modeling-Studio-0.010-Setup.exe (NSIS, LZMA, ~370 KB, unsigned -> SmartScreen "More info > Run anyway").
Contents: 73 studio program files (hash-identical to GAMING-2026 install 2026-10-27), ai_workflow_portal node, AnythingLLM skill, default settings templates, PowerShell engine. No jobs, images, models, backups, .bak, developer_tools, .studio_release.

## Options
- Smart (delta) / Full (force reinstall) / Check only (dry run).
- Models: Verify SHA-256 (re-download only missing/damaged) / Always re-download (replace only after new file verifies; damaged copies renamed .damaged-<stamp>, never deleted).
- Optional: llama.cpp + Qwen GGUF, Bambu Studio, AnythingLLM skill (worker-PC setup not included; existing settings kept).

## Pinned requirements (from collector 2026-10-27)
Python 3.15.1 (pymanager, per user); Blender 5.2.2 MSI + ThreeMF_io (blender_org); VC++ 14.x x64; ComfyUI portable 0.42.1 (torch 2.14.0+cu130), overlay install never touches models/custom_nodes/user/input/output; Hunyuan3D-2 MV d36f5881..., single 360bc281..., BiRefNet 9ab37426... (Comfy-Org HF repos); llama.cpp b11768 (cuda-12.4 zip names UNVERIFIED); Qwen2.5-VL-7B Q4_K_M + mmproj, Qwen2.5-Coder-14B Q4_K_M (HF cache blobs by sha, via ComfyUI python huggingface_hub); Bambu Studio 02.08.02.61 (winget); NVIDIA driver check only (>=580).

## Settings policy
Created only when missing (config.json, hunyuan_settings.json, studio_settings.json single-PC, service_manager_settings.json, optional_worker_router.json, models.ini without rpc, *_settings.json, Start-Model-Router.bat). New-PC config.json ships allow_generated_code_execution=false. Router default saved_endpoint 127.0.0.1:50052 because optional_worker_router.py rejects an empty endpoint (code issue, not changed).

## Verification done (cloud)
Payload hashes match installed files; engine parse OK; Linux pwsh runs: dry run, failure paths (blocked downloads -> FAIL_REASON + dependent steps skipped), twice-apply (2nd run 0 changes), Full keeps settings and backs up replaced files (keep 2). exe extracted with 7z, payload verified.
NOT VERIFIED: any run on Windows; download URLs (cloud blocked); pymanager --force, Blender extension CLI, winget pins.
