IMAGE TO BLENDER AUTO - STARTER PACKAGE
=======================================
Generated for your Blender path and Clonephaze 3MF operator. Not runtime-tested on your Windows machine.
Only static syntax and ZIP integrity checks were performed when this package was built.

WHAT YOU GET
Local browser UI plus an AnythingLLM skill; original image -> vision description -> coding model -> Blender background execution -> three total modeling attempts maximum -> 3MF, blend, preview and checks. Revisions preserve history in new jobs. One queued workflow job executes at a time.

SAFETY FIRST
AI-generated Python runs automatically with your Windows user's permissions. The AST restrictions and prompts are NOT a security sandbox. bpy exposes file/system-capable operations and clever code can bypass simple checks. Prefer a dedicated low-privilege Windows account or isolated machine without sensitive files. Back up work. Do not run as Administrator. Loopback binding and an access token protect the workflow API from casual network access, not other software already running as your user.
This package is disabled by default. Enabling it explicitly opts in to generated-code execution for all jobs submitted while enabled. There is no per-job execution approval.

INSTALL
1. Extract contents to C:\AI-Workflow-Auto (app.py must be directly inside that folder, not one level deeper).
2. Ensure Python 3.10 or later: open Command Prompt and run py -3 --version. No pip packages required.
3. Close Blender after saving your work. Run Inspect-Exporter.bat under the SAME Windows user where the extension is installed. It launches Blender using your normal saved user preferences, explicitly enables bl_ext.blender_org.ThreeMF_io, and does NOT use --factory-startup. Inspect Exporter-Inspection\inspection.log and exporter_properties.json. Expect inspection exit code 0. This does not execute AI code.
4. Keep the remote RPC server at 192.168.0.97:50052 running. Keep its llama.cpp version compatible with the main machine. RPC is for your trusted LAN only, not the internet.
5. Stop the old main llama-server with Ctrl+C. Do NOT run two servers on port 8080.
6. Run C:\llama\llama-server.exe --help and confirm --models-preset and --models-max exist. Update main/remote binaries together if needed; preserve your working installation.
7. Run Start-Model-Router.bat. models.ini uses your RPC connection. For a single-PC setup remove rpc and split-mode lines. Initial ctx-size is 16384 so script generation has room. If memory allocation fails, reduce to 12288 and use simpler tasks, or reduce n-gpu-layers; this is a starting setting, not measured for your hardware. Very long scripts/history need more context or simpler tasks.
8. First model requests may download large files. Check logs for vision projector loading and GPU/RPC allocation. --models-max 1 requests one loaded model at a time; the router swaps automatically.
9. After reading safety notes, edit config.json: change "allow_generated_code_execution": false to true. Keep valid JSON. This is the explicit execution opt-in.
10. Run Start-Workflow.bat. Keep both batch windows open. Browser opens at http://127.0.0.1:8765 . If it does not open, type that address manually.
11. Upload a simple PNG/JPEG and try: 'Create a simple snowman, 90 mm tall, three white spherical body sections, a small orange cone nose, two black eyes, and a blue hat. Use separate named mesh objects and materials. No articulation.'
12. Wait for SUCCEEDED. Read the preview and download model.3mf. Open it in Bambu Studio and check dimensions, object placement, color/material mapping, and slicing before printing. Check 90 mm height especially: the package uses one coordinate unit per mm and scene scale .001, but real exporter/slicer behavior must be verified once.

OUTPUTS
Jobs\<ID>\attempt_01, attempt_02, etc retain code and logs.
Jobs\<ID>\final contains model.3mf, model.blend, preview.png, checks.json, model.py, blender.log.
State SUCCEEDED means execution, basic geometry checks, readable 3MF mesh archive, saved blend and nonempty PNG passed. It does NOT verify visual accuracy, watertightness, printable walls/clearances, articulation, correct slicer grouping, or perfect material mapping.
The Workbench preview shows diffuse material colors, not full texture/shader appearance.
3MF is a geometry/material export, not a guaranteed ready-to-print Bambu project with your printer, filament, supports and process profiles. The separate preview.png is always generated; an embedded 3MF thumbnail is not promised.

EXPORT SETTINGS
The package calls your actual bpy.ops.export_mesh.threemf operator. It explicitly selects model meshes, applies modifiers during export, uses global_scale 1, and leaves unverified enum settings at the extension's registered defaults.
Inspection generates exporter_properties.json with exact types/defaults/enum choices.
For Bambu/Orca color export, inspect use_orca_format and mmu_slicer_format and choose the correct values in config.json -> export_settings using EXACT documented enum identifiers from your local inspection. Do not guess enum names. Changing preferences in a GUI export dialog does not necessarily change the defaults in a fresh background process.
If the first exported test has bad colors/grouping, send exporter_properties.json plus a screenshot of the working manual export settings. We can pin the correct options. The package intentionally does not invent these values.
A 3MF export failure, bad addon setting, preview problem, timeout or server/API failure stops the job rather than wasting geometry-repair attempts. Only script syntax/policy failures and modeling/geometry exceptions trigger up to two automatic repairs.

REVISIONS
Use the revision box under a successful browser job. Example: 'Make the head 20 percent larger. Keep body dimensions and colors unchanged.'
A new job is created. The prior description, cumulative requirements and successful Python script go back to the coding model. It emits a complete revised script. This encourages preservation but does not guarantee unchanged geometry. Compare previews and dimensions. Parent files are never overwritten. Failed jobs cannot be revision parents.

ANYTHINGLLM INTEGRATION - AFTER BROWSER TEST PASSES
1. Launch the workflow once so access-token.txt exists.
2. In AnythingLLM set Generic OpenAI base URL http://127.0.0.1:8080/v1 and model coder (not local-ai). Use a nonempty dummy key only if the UI requires one. Change agent/workspace overrides too. Server has no API-key auth configured and is bound to loopback.
3. Open AnythingLLM Desktop storage. Normal Windows path: %APPDATA%\anythingllm-desktop\storage
4. Copy the image-to-blender-auto folder from anythingllm-skill into storage\plugins\agent-skills\
   Final files: storage\plugins\agent-skills\image-to-blender-auto\plugin.json and handler.js
5. If installed elsewhere, edit ROOT in handler.js to match. Restart AnythingLLM and enable Image to Blender Auto in Agent Skills. Exit old agent session before a fresh one.
6. Copy reference.png into C:\AI-Workflow-Auto\Input.
7. Send:
   @agent Use Image to Blender Auto to start a job from C:\AI-Workflow-Auto\Input\reference.png. Make a simple 100 mm tall approximation with separate objects for each color. Return the job ID only; do not repeatedly poll.
8. Inspect browser dashboard for preview/downloads. AnythingLLM does not automatically display local PNGs or attach local files in this implementation.
9. For revisions:
   @agent Use Image to Blender Auto with action revise, parent_job EXACT_JOB_ID, and instructions: Make the head larger and preserve the rest.
10. The controller handles queues, retries, export and preview; the AnythingLLM agent only submits requests. Tool selection depends on your agent model's abilities. If it refuses/does not invoke the skill, use the browser while troubleshooting the skill. Do not confuse a text claim with an actual job folder.
Avoid unrelated model chats during generation to reduce router switching contention. Browser refresh does not query AI.

TROUBLESHOOTING
Inspection fails: inspect inspection.log; verify addon is installed under the same user and executable version. Do not use --factory-startup.
Port 8080 busy: stop old llama-server. Port 8765 busy: stop previous workflow instance.
Connection refused: router is not running or API URL is wrong.
Images unsupported: check vision model selection and mmproj loading in server log.
Out of memory: stop other GPU tasks, use a smaller context or partial CPU offload. No memory fit guarantee.
QUEUED: waits behind current job. Controller restart marks unfinished jobs INTERRUPTED; it does not silently rerun generated code.
FAILED: read error.txt and attempt logs. Send those rather than a screenshot of only 'failed'.
Render-only failure: successful attempt may retain model.blend/3mf even though final status is FAILED. Do not assume missing final folder means geometry was lost.
Stop workflow only when idle. Closing it during a Blender run may leave Blender running; stop that specific workflow Blender process via Task Manager before restarting. Do not kill another Blender session with unsaved work.
Do not expose either service to the public internet. No cloud APIs are used by the code except downloads your model server may perform.
