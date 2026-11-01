# AI Modeling Studio (AI-Workflow-Free)

Windows image-to-3D-print workflow: reference pictures -> background removal -> Hunyuan3D-2 multi-view mesh (ComfyUI) -> geometry check -> color transfer (Blender) -> Bambu Studio color 3MF.

Current version: **0.018 (build 2026-10-30-1)** - new PC: `AI-Modeling-Studio-0.018-Setup.exe`; existing 0.017 build 2026-10-30-3 install: `updates/0.018/Install-Update-0.018-Nozzle-And-Auto-Review.bat`

## Requirements (pinned)


| Part | Version |
|---|---|
| Windows + NVIDIA GPU 3080 10Gb Card OR BETTER !!!| driver 580+ |
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
| `tools/` | `Collect-Installer-Info.bat` (read-only system report with Copy all), `Collect-Nozzle-Info.bat` / `Collect-Nozzle-Profiles-2.bat` (Bambu profiles), `nozzle-templates/` (rebuilds the 0.4 templates) | - |
| `docs/` | diagnoses and design notes per version | - |
| `old/` | earlier material (kept as is) | - |

Not in the repo: jobs, source images, logs, backups, model files, access tokens (see `.gitignore`).

## Install
- New PC, repair or upgrade: run `AI-Modeling-Studio-0.018-Setup.exe`. Smart = install only what is missing; Full = reinstall everything (jobs, models and settings kept). Tick "Check only" first to see what it would do.
- Existing install: run the update .bats for the next version in `updates/` in order (0.017: r2 -> b2 -> b3, needs 0.016 b5; 0.018 needs 0.017 build 2026-10-30-3). Each checks the installed version first, backs up, self-tests and rolls back on failure.
- Older Setup .exe files in the repo root (0.010) are kept for history; use the newest one.

## Build the installer
Install NSIS 3.x, then double-click `installer\Build-Installer.bat`. Output: `dist\AI-Modeling-Studio-0.018-Setup.exe`.

## Notes
- `.gitattributes` turns off line-ending conversion: installers check file SHA-256 hashes (e.g. `WORKER_SHA256` in `hunyuan_color_bridge.py`), so files must stay byte-identical.
- `studio/` matches the installed copy on GAMING-2026 as of 2026-10-30 (0.018 build 2026-10-30-1) (hashes in `installer/payload_manifest.json`).

## Using the studio (0.018)
- Upload form: **Nozzle** 0.4 / 0.6 mm (both H2C nozzles; 0.4 = `bambu_template*_04.3mf`, 0.20mm High Quality, finer colour detail).
- Reviews run by themselves: the model review and the colour review approve automatically when every check passes and stop with the
  reasons under the state guide when something fails. Tick **Advanced mesh and paint** (under Prepare image) to review a job yourself.
  `config.json`: `"auto_approve_model": false` / `"auto_approve_color": false` switch the automatic reviews off for all jobs.
