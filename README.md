# AI Modeling Studio (AI-Workflow-Free)

Windows image-to-3D-print workflow: reference pictures -> background removal -> Hunyuan3D-2 multi-view mesh (ComfyUI) -> geometry check -> color transfer (Blender) -> Bambu Studio color 3MF.

Current version: **0.017 (build 2026-10-30-3)** - new PC: `AI-Modeling-Studio-0.017-Setup.exe`; existing 0.016 b5 install: `updates/0.017/` (r2, b2, b3)

## Requirements (pinned)
| Part | Version |
|---|---|
| Windows + NVIDIA GPU | driver 580+ |
| Python | 3.15.1 (Python install manager) |
| Blender | 5.2.2 + ThreeMF_io extension |
| ComfyUI portable | 0.42.1 (torch 2.14.0+cu130) |
| Models | Hunyuan3D-2 MV + single view, BiRefNet |
| AI paint runtime | uv 0.12.24, Python 3.12.15, torch 2.6.0+cu126, Hunyuan3D-2 paint (~19 GB) |
| Video reader | ffmpeg 7.1 |
| Optional | llama.cpp b11768 + Qwen2.5-VL-7B / Qwen2.5-Coder-14B, Bambu Studio, AnythingLLM skill |

## Repo layout
| Folder | Contents | Installed to |
|---|---|---|
| `studio/` | the program (launcher, UI, pipeline, tests, `bambu_template.3mf`, `anythingllm-skill/`) | `C:\AI-Workflow-Auto` |
| `comfyui/custom_nodes/ai_workflow_portal/` | ComfyUI node used by the workflows | `<ComfyUI>\custom_nodes` |
| `installer/` | `setup.nsi`, `engine.ps1`, `payload_manifest.json`, `defaults/` (settings templates for a new PC), `Build-Installer.bat` | - |
| `updates/<version>/` | single-file update .bat for an existing install, plus its source script | - |
| `tools/` | `Collect-Installer-Info.bat` (read-only system report with Copy all) | - |
| `docs/` | diagnoses and design notes per version | - |
| `old/` | earlier material (kept as is) | - |

Not in the repo: jobs, source images, logs, backups, model files, access tokens (see `.gitignore`).

## Install
- New PC, repair or upgrade: run `AI-Modeling-Studio-0.017-Setup.exe`. Smart = install only what is missing; Full = reinstall everything (jobs, models and settings kept). Tick "Check only" first to see what it would do.
- Existing install: run the update .bats for the next version in `updates/` in order (0.017: r2 -> b2 -> b3, needs 0.016 b5). Each checks the installed version first, backs up, self-tests and rolls back on failure.
- Older Setup .exe files in the repo root (0.010) are kept for history; use the 0.017 one.

## Build the installer
Install NSIS 3.x, then double-click `installer\Build-Installer.bat`. Output: `dist\AI-Modeling-Studio-0.017-Setup.exe`.

## Notes
- `.gitattributes` turns off line-ending conversion: installers check file SHA-256 hashes (e.g. `WORKER_SHA256` in `hunyuan_color_bridge.py`), so files must stay byte-identical.
- `studio/` matches the installed copy on GAMING-2026 as of 2026-10-30 (0.017 build 2026-10-30-3) (hashes in `installer/payload_manifest.json`).
