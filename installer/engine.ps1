param(
    [ValidateSet('Smart', 'Full')] [string]$Mode = 'Smart',
    [ValidateSet('Verify', 'Redownload')] [string]$Models = 'Verify',
    [string]$InstallDir = 'C:\AI-Workflow-Auto',
    [string]$Components = 'llama,bambu,anythingllm',
    [string]$Payload = $PSScriptRoot,
    [switch]$DryRun,
    [switch]$NoWindow
)
# AI Modeling Studio 0.017 installer engine (run by the .exe; also runnable by hand).
# Smart = check every requirement and install only what is missing or wrong (delta).
# Full  = re-install every requirement. Jobs, source images, models and user settings are never deleted.
$ErrorActionPreference = 'Stop'
$VERSION = '0.017'; $BUILD = '2026-10-30-3'; $SETUP_BUILD = '2026-10-30-3'

# 64-bit guard (setup 2026-10-28-3): a 32-bit PowerShell on 64-bit Windows sees SysWOW64 instead of System32
# (no nvidia-smi), the 32-bit registry view (64-bit programs such as Bambu Studio look missing) and
# Program Files (x86). Relaunch this script in the 64-bit PowerShell with the same arguments.
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess -and $env:OS -eq 'Windows_NT') {
    $ps64 = Join-Path $env:WINDIR 'Sysnative\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path $ps64)) { Write-Host ('STOP: this installer must run in 64-bit PowerShell and ' + $ps64 + ' was not found. Nothing was changed.') -ForegroundColor Red; exit 3 }
    $relaunch = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-STA', '-File', $PSCommandPath, '-Mode', $Mode, '-Models', $Models, '-InstallDir', $InstallDir, '-Components', $(if ($Components) { $Components } else { ',' }), '-Payload', $Payload)
    if ($DryRun) { $relaunch += '-DryRun' }; if ($NoWindow) { $relaunch += '-NoWindow' }
    & $ps64 @relaunch
    exit $LASTEXITCODE
}
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Script:Log = New-Object System.Collections.Generic.List[string]
$Script:Results = New-Object System.Collections.Generic.List[object]
$Script:Failed = @{}
$Want = @{}; foreach ($c in ($Components -split ',')) { if ($c.Trim()) { $Want[$c.Trim().ToLower()] = $true } }
$IsWin = ($env:OS -eq 'Windows_NT')
$Temp = Join-Path ([IO.Path]::GetTempPath()) ('AIStudio-Setup-' + $Stamp); New-Item -ItemType Directory -Force -Path $Temp | Out-Null
$Downloads = Join-Path ([IO.Path]::GetTempPath()) 'AIStudio-Setup-Downloads'; New-Item -ItemType Directory -Force -Path $Downloads | Out-Null

# ---------------------------------------------------------------- pinned versions (from the working PC GAMING-2026)
$PIN = @{
    PythonVersion = '3.15.1'
    BlenderVersion = '5.2.2'
    BlenderMsi = 'https://download.blender.org/release/Blender5.2/blender-5.2.2-windows-x64.msi'
    ComfyVersion = '0.42.1'
    ComfyUrls = @('https://github.com/Comfy-Org/ComfyUI/releases/download/v0.42.1/ComfyUI_windows_portable_nvidia.7z',
                  'https://github.com/comfyanonymous/ComfyUI/releases/download/v0.42.1/ComfyUI_windows_portable_nvidia.7z')
    TorchVersion = '2.14.0+cu130'
    SevenZr = 'https://www.7-zip.org/a/7zr.exe'
    VcRedist = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
    LlamaBuild = '11768'
    LlamaZips = @('https://github.com/ggml-org/llama.cpp/releases/download/b11768/llama-b11768-bin-win-cuda-12.4-x64.zip',
                  'https://github.com/ggml-org/llama.cpp/releases/download/b11768/cudart-llama-bin-win-cuda-12.4-x64.zip')
    BambuVersion = '02.08.02.61'
}
$TP = @{   # AI paint runtime (texture_paint), installed 2026-10-28 on GAMING-2026 by Test-AI-Texture-Paint.bat; same pins
    UvVer = '0.12.24'; UvUrl = 'https://files.pythonhosted.org/packages/71/d7/d573b4eda67a7ee79fdef3476138ff3a4d18b2bc97980d048709add81ea0/uv-0.12.24-py3-none-win_amd64.whl'
    UvSha = '83f5dbd2389eb6f998e195faf7efb83199a3df825d4ec954b4d6e45f286ee52d'; PyVer = '3.12.15'
    Torch = 'torch==2.6.0+cu126'; TorchIndex = 'https://download.pytorch.org/whl/cu126'
    CrUrl = 'https://raw.githubusercontent.com/kijai/ComfyUI-Hunyuan3DWrapper/2609efa38f6a98292476f714839b7c1e5f9b699a/wheels/custom_rasterizer-0.1.0%2Btorch260.cuda126-cp312-cp312-win_amd64.whl'
    CrFile = 'custom_rasterizer-0.1.0+torch260.cuda126-cp312-cp312-win_amd64.whl'; CrSha = 'a1d0c3e8f463f97aa78104c382617498859064a297aee161466e6e015418fd3b'
    HyGit = 'https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git'; HyCommit = 'f8db63096c8282cb27354314d896feba5ba6ff8a'; HfRev = 'efb40d890aeade24c68ec7555eb206de8ba68c77'
}
$FF = @{ Url = 'https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip'
         ZipSha = 'fa7d4d7e795db0e2503f49f105f46ed5852386f0cfdd819899be3b65ebde24fc'; ExeSha = '2ce797a0f88d7f067180338fb227f7b1928ea727bd9a4d7a1d022f7c52af71a3' }
$NODE_SHA = '6485e6d0351e7492299ac387b91c8ac9d339eb89c09e5896cb5793a4ca36f8b8'
$COMFY_MODELS = @(
    @{ rel = 'models\checkpoints\hunyuan3d-dit-v2-mv_fp16.safetensors'; sha = 'd36f5881bcdc56726b73e517cd444c13c60732431622da7268145355c8d38e9c'; size = 4928151562
       url = 'https://huggingface.co/Comfy-Org/hunyuan3D_2.0_repackaged/resolve/main/split_files/hunyuan3d-dit-v2-mv_fp16.safetensors' },
    @{ rel = 'models\checkpoints\hunyuan3d-dit-v2_fp16.safetensors'; sha = '360bc281fc956d4acac0c3d36d5ec0ebf8cdddbf4b8892e894d12419388d479b'; size = 4928151562
       url = 'https://huggingface.co/Comfy-Org/hunyuan3D_2.0_repackaged/resolve/main/split_files/hunyuan3d-dit-v2_fp16.safetensors' },
    @{ rel = 'models\background_removal\birefnet.safetensors'; sha = '9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154'; size = 444473596
       url = 'https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors' }
)
$GGUF = @(
    @{ repo = 'ggml-org/Qwen2.5-VL-7B-Instruct-GGUF'; sha = '9258bf05b12686d097ff3b6b18d968ab393649780aa2b3cd67fec43d50554392'; size = 4683072032 },
    @{ repo = 'ggml-org/Qwen2.5-VL-7B-Instruct-GGUF'; sha = '2ddb555391bae966e412deab9e07b58afa18bcc06930ba0f1c78a3695ab9e506'; size = 853119712 },
    @{ repo = 'Qwen/Qwen2.5-Coder-14B-Instruct-GGUF'; sha = '310a553a856d7b238c05ed1b0cb877c4dca5b65c2286324854a1397149a00af2'; size = 8000444480 },
    @{ repo = 'Qwen/Qwen2.5-Coder-14B-Instruct-GGUF'; sha = '7a52538b39090d99ce93b1b05a406b805427171f890dbef8684c57fb28b2d96a'; size = 987665920 }
)
# Studio files that hold the user's own settings: created when missing, never overwritten.
$SETTINGS = @('config.json', 'hunyuan_settings.json', 'service_manager_settings.json', 'studio_settings.json', 'optional_worker_router.json',
              'models.ini', 'autoroute_settings.json', 'quality_settings.json', 'mega_dragon_settings.json', 'job_cancel_settings.json', 'Start-Model-Router.bat',
              'archive_retention.json', 'bambu_template.3mf', 'bambu_template_default.3mf', 'bambu_template_6.3mf', 'bambu_template_7.3mf', 'bambu_template_8.3mf', 'bambu_template_9.3mf')
# Bambu templates are the user's own printer/filament projects: copied from the payload only when missing, never overwritten.
$TEMPLATES = @('bambu_template.3mf', 'bambu_template_default.3mf', 'bambu_template_6.3mf', 'bambu_template_7.3mf', 'bambu_template_8.3mf', 'bambu_template_9.3mf')
$FOLDERS = @('Jobs', 'Archived-Jobs', 'Input', 'logs', 'backups', 'Photo-Text-Reports', 'Exporter-Inspection', 'anythingllm-skill')

# ---------------------------------------------------------------- helpers
function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c; $Script:Log.Add($m) }
function Hash($p) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } return $null }
function ReadJson($p) { try { return (Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null } }
function WriteText($p, $t) { $d = Split-Path $p -Parent; if ($d) { New-Item -ItemType Directory -Force -Path $d | Out-Null }; [IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false))) }
function Capture($exe, $argText, $timeoutSec = 120) {
    if (-not (Test-Path -LiteralPath $exe)) { return @{ code = -1; out = 'missing: ' + $exe } }
    $o = Join-Path $Temp ([guid]::NewGuid().ToString('N') + '.out'); $e = $o + '.err'
    $p = Start-Process -FilePath $exe -ArgumentList $argText -RedirectStandardOutput $o -RedirectStandardError $e -NoNewWindow -PassThru
    $null = $p.Handle
    if (-not $p.WaitForExit($timeoutSec * 1000)) { try { $p.Kill() } catch {}; return @{ code = -2; out = 'timeout' } }
    $p.WaitForExit()
    return @{ code = $p.ExitCode; out = ((Get-Content $o -Raw -ErrorAction SilentlyContinue) + "`n" + (Get-Content $e -Raw -ErrorAction SilentlyContinue)) }
}
function LastLine($s) { $l = @(($s -split "`r?`n") | Where-Object { $_.Trim() }); if ($l.Count) { return $l[-1].Trim() } return '' }
function Elevated($exe, $argText) {
    Say ('    (administrator permission requested for: ' + (Split-Path $exe -Leaf) + ' - click Yes)') 'Yellow'
    if ($DryRun -or -not $IsWin) { Say ('    DRY: ' + $exe + ' ' + $argText); return 0 }
    $p = Start-Process -FilePath $exe -ArgumentList $argText -Verb RunAs -Wait -PassThru
    return $p.ExitCode
}
function Download($url, $dest) {
    if ($DryRun) { Say ('    DRY: download ' + $url); return $false }
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    $part = $dest + '.part'
    $curl = if ($IsWin) { Join-Path $env:SystemRoot 'System32\curl.exe' } else { 'curl' }
    Say ('    downloading ' + $url)
    for ($i = 1; $i -le 3; $i++) {
        & $curl -L --fail --retry 5 --retry-delay 5 -C - -A 'AI-Modeling-Studio-Setup/0.017' -o $part $url
        if ($LASTEXITCODE -eq 0 -and (Test-Path $part)) { Move-Item -LiteralPath $part -Destination $dest -Force; return $true }
        Say ('    download attempt ' + $i + ' failed (curl exit ' + $LASTEXITCODE + ')') 'Yellow'
    }
    return $false
}
function Step($name, $deps, $block) {
    foreach ($d in $deps) { if ($Script:Failed.ContainsKey($d)) { Say ''; Say ('[' + $name + '] SKIPPED - needs "' + $d + '", which failed.') 'Yellow'; $Script:Results.Add([pscustomobject]@{ Step = $name; Result = 'SKIPPED (needs ' + $d + ')' }); $Script:Failed[$name] = $true; return } }
    Say ''; Say ('[' + $name + ']') 'Cyan'
    try { $r = & $block; if (-not $r) { $r = 'OK' }; if ($DryRun -and $r -notlike 'DRY*' -and $r -notlike 'already*' -and $r -notlike 'found*' -and $r -notlike 'NOT FOUND*' -and $r -notlike 'WARNING*') { $r = 'DRY: would do -> ' + $r }; $Script:Results.Add([pscustomobject]@{ Step = $name; Result = $r }); Say ('  -> ' + $r) 'Green' }
    catch {
        $Script:Failed[$name] = $true; $msg = $_.Exception.Message
        $Script:Results.Add([pscustomobject]@{ Step = $name; Result = 'FAILED: ' + $msg }); Say ('  -> FAILED: ' + $msg) 'Red'
        $fr = Join-Path $Temp ('FAIL_REASON-' + ($name -replace '[^A-Za-z0-9]', '_') + '.txt')
        WriteText $fr ("AI MODELING STUDIO INSTALLER - STEP FAILED`r`nStep: " + $name + "`r`nMode: " + $Mode + "  Models: " + $Models + "`r`nError: " + $msg + "`r`nScript stack: " + $_.ScriptStackTrace + "`r`nInstall folder: " + $InstallDir + "`r`nNEXT STEP: run the installer again in Smart mode; if it fails the same way, send this file and the installer report.`r`n")
        Say ('     details: ' + $fr)
    }
}

# ---------------------------------------------------------------- discover existing paths (keeps the user's layout)
$old = ReadJson (Join-Path $InstallDir 'hunyuan_settings.json')
$ComfyRoot = if ($old -and $old.comfy_root) { $old.comfy_root } elseif ($env:AISTUDIO_DEFAULT_COMFY) { $env:AISTUDIO_DEFAULT_COMFY } else { 'C:\ComfyUI_windows_portable\ComfyUI' }
$ComfyBase = if ((Split-Path $ComfyRoot -Leaf) -ieq 'ComfyUI') { Split-Path $ComfyRoot -Parent } else { $ComfyRoot }
$ComfyRoot = Join-Path $ComfyBase 'ComfyUI'
$ss = ReadJson (Join-Path $InstallDir 'studio_settings.json')
$LlamaDir = if ($ss -and $ss.llama_dir) { $ss.llama_dir } elseif ($env:AISTUDIO_DEFAULT_LLAMA) { $env:AISTUDIO_DEFAULT_LLAMA } else { 'C:\llama' }
$cfg = ReadJson (Join-Path $InstallDir 'config.json')
$BlenderExe = if ($cfg -and $cfg.blender_exe -and (Test-Path $cfg.blender_exe)) { $cfg.blender_exe } else { Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe' }
$PyDir = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.15-64'; $PyExe = Join-Path $PyDir 'python.exe'; $PywExe = Join-Path $PyDir 'pythonw.exe'
$EmbPy = Join-Path $ComfyBase 'python_embeded\python.exe'
$HFHub = Join-Path $env:USERPROFILE '.cache\huggingface\hub'

Say ('=== AI Modeling Studio ' + $VERSION + ' installer  -  ' + $Mode.ToUpper() + ' install  -  models: ' + $Models + ' ===') 'Cyan'
Say ('Setup build ' + $SETUP_BUILD + '   PowerShell ' + $PSVersionTable.PSVersion + ' ' + $(if ([Environment]::Is64BitProcess) { '64-bit' } else { '32-bit' }))
Say ('Started ' + (Get-Date -Format s) + ' on ' + $env:COMPUTERNAME + $(if ($DryRun) { '   (DRY RUN: nothing is changed)' } else { '' }))
Say ('Studio folder: ' + $InstallDir); Say ('ComfyUI: ' + $ComfyBase); Say ('llama.cpp: ' + $LlamaDir); Say ('Blender: ' + $BlenderExe)
Say ('Optional components: ' + (($Want.Keys | Sort-Object) -join ', '))
$running = $false; try { $cl = New-Object Net.Sockets.TcpClient; $running = $cl.BeginConnect('127.0.0.1', 8765, $null, $null).AsyncWaitHandle.WaitOne(600) -and $cl.Connected; $cl.Close() } catch {}
if ($running -and -not $DryRun) { Say 'The studio is running. Power it off with its own Power off control, then run the installer again. Nothing was changed.' 'Red'; $Script:Results.Add([pscustomobject]@{ Step = 'Start'; Result = 'FAILED: studio running' }); $Script:Failed['Start'] = $true }
else {

# ---------------------------------------------------------------- 1. system checks
Step 'NVIDIA driver (check only)' @() {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { return 'NOT FOUND - install the NVIDIA driver from nvidia.com (ComfyUI needs it). Not installed automatically.' }
    $r = (& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader) -join ' '
    $v = [double](($r -split ',')[1].Trim() -replace '[^0-9.]', '').Split('.')[0]
    if ($v -lt 580) { return ('WARNING: driver ' + $r + ' - CUDA 13 (ComfyUI torch cu130) needs driver 580 or newer.') }
    return ('found ' + $r.Trim())
}
Step 'Microsoft Visual C++ runtime' @() {
    $ok = $false; try { $ok = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction Stop).Installed -eq 1 } catch {}
    if ($ok -and $Mode -eq 'Smart') { return 'already installed' }
    $exe = Join-Path $Downloads 'vc_redist.x64.exe'; if (-not (Download $PIN.VcRedist $exe) -and -not $DryRun) { throw 'download failed' }
    $code = Elevated $exe $(if ($ok) { '/repair /quiet /norestart' } else { '/install /quiet /norestart' })
    if ($code -notin 0, 1638, 3010) { throw ('vc_redist exit code ' + $code) }
    return $(if ($ok) { 'repaired (Full)' } else { 'installed' })
}

# ---------------------------------------------------------------- 2. Python 3.15.1 (Python install manager, per user)
Step 'Python 3.15.1' @() {
    $have = LastLine (Capture $PyExe '-c "import sys,tkinter;print(sys.version.split()[0])"').out
    if ($have -eq $PIN.PythonVersion -and $Mode -eq 'Smart') { return ('already installed: ' + $PyExe) }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if (-not $py) {
        Say '    Python install manager missing - installing it with winget'
        if (-not $DryRun) { & winget install -e --id Python.PythonInstallManager --accept-package-agreements --accept-source-agreements --silent; $py = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\py.exe' }
    } else { $py = $py.Source }
    if (-not $DryRun) {
        if ($Mode -eq 'Full') { & $py install --force $PIN.PythonVersion; if ($LASTEXITCODE) { & $py install $PIN.PythonVersion } } else { & $py install $PIN.PythonVersion }
        $have = LastLine (Capture $PyExe '-c "import sys,tkinter;print(sys.version.split()[0])"').out
        if ($have -ne $PIN.PythonVersion) { throw ('Python check after install returned: ' + $have) }
    }
    return ('installed ' + $PIN.PythonVersion)
}

# ---------------------------------------------------------------- 3. Blender 5.2.2 + 3MF add-on
Step 'Blender 5.2.2' @() {
    $have = ((Capture $BlenderExe '--version' 60).out -split "`n")[0].Trim()
    if ($have -like ('Blender ' + $PIN.BlenderVersion + '*') -and $Mode -eq 'Smart') { return ('already installed: ' + $have) }
    $msi = Join-Path $Downloads 'blender-5.2.2-windows-x64.msi'
    if (-not (Download $PIN.BlenderMsi $msi) -and -not $DryRun) { throw 'Blender download failed' }
    $argText = if ($have -like 'Blender*') { '/i "' + $msi + '" REINSTALL=ALL REINSTALLMODE=amus /qn /norestart' } else { '/i "' + $msi + '" ALLUSERS=1 /qn /norestart' }
    $code = Elevated 'msiexec.exe' $argText
    if ($code -notin 0, 3010) { throw ('msiexec exit code ' + $code) }
    $script:BlenderExe = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe'
    if (-not $DryRun) { $have = ((Capture $BlenderExe '--version' 60).out -split "`n")[0].Trim(); if ($have -notlike ('Blender ' + $PIN.BlenderVersion + '*')) { throw ('Blender check after install: ' + $have) } }
    return ('installed ' + $PIN.BlenderVersion)
}
Step 'Blender 3MF add-on (ThreeMF_io)' @('Blender 5.2.2') {
    $ext = Join-Path $env:APPDATA 'Blender Foundation\Blender\5.2\extensions\blender_org\ThreeMF_io'
    if ((Test-Path $ext) -and $Mode -eq 'Smart') { return 'already installed' }
    if ($DryRun) { return 'DRY: would install from extensions.blender.org' }
    $r = Capture $BlenderExe '--online-mode --command extension install --sync --enable ThreeMF_io' 600
    Say ('    ' + ($r.out.Trim() -replace "`n", "`n    "))
    if (-not (Test-Path $ext)) { throw 'ThreeMF_io not present after install' }
    return 'installed'
}

# ---------------------------------------------------------------- 4. ComfyUI portable 0.42.1
Step 'ComfyUI portable 0.42.1' @('Microsoft Visual C++ runtime') {
    $verFile = Join-Path $ComfyRoot 'comfyui_version.py'
    $okVer = (Test-Path $verFile) -and ((Get-Content $verFile -Raw) -match ('__version__\s*=\s*"' + [regex]::Escape($PIN.ComfyVersion) + '"'))
    $torch = if (Test-Path $EmbPy) { LastLine (Capture $EmbPy '-s -c "import torch,numpy,PIL;print(torch.__version__)"' 180).out } else { 'missing' }
    if ($okVer -and $torch -eq $PIN.TorchVersion -and $Mode -eq 'Smart') { return ('already installed (torch ' + $torch + ')') }
    Say ('    found: version ok=' + $okVer + ', torch=' + $torch)
    $arc = Join-Path $Downloads 'ComfyUI_windows_portable_nvidia-0.42.1.7z'; $got = (Test-Path $arc)
    if (-not $got) { foreach ($u in $PIN.ComfyUrls) { if (Download $u $arc) { $got = $true; break } } }
    if (-not $got) { if ($DryRun) { return 'DRY: would download and extract' }; throw 'ComfyUI 0.42.1 download failed' }
    $seven = @('C:\Program Files\7-Zip\7z.exe', 'C:\Program Files (x86)\7-Zip\7z.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $seven) { $seven = Join-Path $Downloads '7zr.exe'; if (-not (Test-Path $seven) -and -not (Download $PIN.SevenZr $seven)) { throw '7-Zip extractor download failed' } }
    $work = Join-Path (Split-Path $ComfyBase -Parent) ('_comfy_setup_' + $Stamp)
    & $seven x $arc ('-o' + $work) -y -bsp0 -bso0; if ($LASTEXITCODE) { throw ('7-Zip exit ' + $LASTEXITCODE) }
    $inner = Get-ChildItem $work -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'ComfyUI\main.py') } | Select-Object -First 1
    if (-not $inner) { throw 'unexpected archive layout' }
    if (-not ((Get-Content (Join-Path $inner.FullName 'ComfyUI\comfyui_version.py') -Raw) -match '0\.42\.1')) { throw 'downloaded archive is not ComfyUI 0.42.1' }
    # Overlay: never touches models, custom nodes, user data, input or output.
    New-Item -ItemType Directory -Force -Path $ComfyBase | Out-Null
    $x = @((Join-Path $inner.FullName 'ComfyUI\models'), (Join-Path $inner.FullName 'ComfyUI\custom_nodes'), (Join-Path $inner.FullName 'ComfyUI\user'), (Join-Path $inner.FullName 'ComfyUI\input'), (Join-Path $inner.FullName 'ComfyUI\output'))
    & robocopy $inner.FullName $ComfyBase /E /NFL /NDL /NJH /NP /R:2 /W:2 /XD $x | Out-Null
    if ($LASTEXITCODE -ge 8) { throw ('robocopy exit ' + $LASTEXITCODE) }
    foreach ($d in 'models', 'custom_nodes', 'user', 'input', 'output') {   # add only missing default folders/files
        & robocopy (Join-Path $inner.FullName ('ComfyUI\' + $d)) (Join-Path $ComfyRoot $d) /E /XC /XN /XO /NFL /NDL /NJH /NP | Out-Null
    }
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    $torch = LastLine (Capture $EmbPy '-s -c "import torch,numpy,PIL;print(torch.__version__)"' 180).out
    if ($torch -ne $PIN.TorchVersion) { throw ('torch check after install: ' + $torch) }
    return ('installed ' + $PIN.ComfyVersion + ' (torch ' + $torch + ')')
}
Step 'ComfyUI node ai_workflow_portal' @('ComfyUI portable 0.42.1') {
    $dest = Join-Path $ComfyRoot 'custom_nodes\ai_workflow_portal\__init__.py'
    if ((Hash $dest) -eq $NODE_SHA -and $Mode -eq 'Smart') { return 'already installed' }
    if (-not $DryRun) { New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null; Copy-Item (Join-Path $Payload 'custom_nodes\ai_workflow_portal\__init__.py') $dest -Force; if ((Hash $dest) -ne $NODE_SHA) { throw 'hash check failed' } }
    return 'installed'
}
function ModelFile($m, $root) {
    $dest = Join-Path $root $m.rel
    $have = if (Test-Path $dest) { (Get-Item $dest).Length } else { -1 }
    if ($Models -eq 'Verify' -and $have -eq $m.size) {
        Say ('    verifying ' + (Split-Path $dest -Leaf) + ' (SHA-256, may take a minute)')
        if ((Hash $dest) -eq $m.sha) { return 'verified' }
        Say '    hash mismatch - file is damaged' 'Yellow'
    }
    $tmp = $dest + '.download'
    if (-not (Download $m.url $tmp)) { if ($DryRun) { return 'DRY: would download' }; throw ('download failed: ' + $m.url) }
    if ((Hash $tmp) -ne $m.sha) { Remove-Item $tmp -Force; throw ('downloaded file has the wrong SHA-256: ' + $m.url + ' - existing file left untouched') }
    if (Test-Path $dest) {
        if ((Hash $dest) -ne $m.sha) { Move-Item $dest ($dest + '.damaged-' + $Stamp) -Force; Say ('    damaged copy kept as ' + (Split-Path $dest -Leaf) + '.damaged-' + $Stamp + ' (delete it yourself when happy)') 'Yellow' }
    }
    Move-Item $tmp $dest -Force
    return 'downloaded + verified'
}
Step 'Hunyuan3D + BiRefNet models' @('ComfyUI portable 0.42.1') {
    $out = @(); foreach ($m in $COMFY_MODELS) { $out += ((Split-Path $m.rel -Leaf) + ': ' + (ModelFile $m $ComfyRoot)) }
    return ($out -join '; ')
}

# ---------------------------------------------------------------- 5. llama.cpp router + Qwen GGUF models (optional component)
if ($Want['llama']) {
    Step 'llama.cpp build 11768' @('Microsoft Visual C++ runtime') {
        $srv = Join-Path $LlamaDir 'llama-server.exe'
        $have = (Capture $srv '--version' 60).out
        if ($have -match ('build ' + $PIN.LlamaBuild) -and $Mode -eq 'Smart') { return 'already installed (build ' + $PIN.LlamaBuild + ')' }
        $stage = Join-Path $Temp 'llama'
        foreach ($u in $PIN.LlamaZips) { $z = Join-Path $Downloads (Split-Path $u -Leaf); if (-not (Test-Path $z) -and -not (Download $u $z)) { if ($DryRun) { return 'DRY: would download' }; throw ('download failed: ' + $u) }; Expand-Archive -LiteralPath $z -DestinationPath $stage -Force }
        if ((Capture (Join-Path $stage 'llama-server.exe') '--version' 60).out -notmatch ('build ' + $PIN.LlamaBuild)) { throw 'downloaded llama.cpp is not build 11768 - existing C:\llama left untouched' }
        if (Get-Process llama-server -ErrorAction SilentlyContinue) { throw 'llama-server.exe is running; power the studio off first' }
        New-Item -ItemType Directory -Force -Path $LlamaDir | Out-Null
        & robocopy $stage $LlamaDir /E /NFL /NDL /NJH /NP | Out-Null; if ($LASTEXITCODE -ge 8) { throw ('robocopy exit ' + $LASTEXITCODE) }
        return 'installed build ' + $PIN.LlamaBuild
    }
    Step 'Qwen vision + coder models (GGUF)' @('llama.cpp build 11768', 'ComfyUI portable 0.42.1') {
        $res = @()
        foreach ($g in $GGUF) {
            $blob = Join-Path $HFHub ('models--' + ($g.repo -replace '/', '--') + '\blobs\' + $g.sha)
            if ($Models -eq 'Verify' -and (Test-Path $blob) -and (Get-Item $blob).Length -eq $g.size) {
                Say ('    verifying ' + $g.repo + ' ' + $g.sha.Substring(0, 12)); if ((Hash $blob) -eq $g.sha) { $res += 'ok'; continue }
            }
            if ($DryRun) { $res += 'DRY: download'; continue }
            # Download through huggingface_hub (in ComfyUI's Python) into the same cache llama.cpp reads; the file is chosen by its SHA-256.
            $code = "import sys,hashlib`nfrom huggingface_hub import HfApi,hf_hub_download`nrepo,sha,force=sys.argv[1],sys.argv[2],sys.argv[3]=='1'`nfiles=[f for f in HfApi().list_repo_tree(repo,recursive=True) if getattr(f,'lfs',None) and f.lfs.sha256==sha]`nif not files: sys.exit('no file with sha '+sha+' in '+repo)`np=hf_hub_download(repo,files[0].path,force_download=force)`nprint('DOWNLOADED',files[0].path,p)`n"
            $f = Join-Path $Temp 'hfdl.py'; WriteText $f $code
            $r = Capture $EmbPy ('-s "' + $f + '" ' + $g.repo + ' ' + $g.sha + ' ' + $(if ($Models -eq 'Redownload') { '1' } else { '0' })) 7200
            Say ('    ' + $r.out.Trim())
            if ($r.code -or (Hash $blob) -ne $g.sha) { throw ('GGUF download/verify failed for ' + $g.repo) }
            $res += 'downloaded'
        }
        return ($res -join ', ')
    }
}

# ---------------------------------------------------------------- 6. studio program files (always) + settings (only when missing)
Step 'AI Modeling Studio 0.017 program files' @() {
    $src = Join-Path $Payload 'studio'; $man = Get-Content (Join-Path $Payload 'payload_manifest.json') -Raw | ConvertFrom-Json
    foreach ($f in $FOLDERS) { if (-not $DryRun) { New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir $f) | Out-Null } }
    $backup = Join-Path $InstallDir ('backups\installer-' + $VERSION + '-' + $Stamp); $changed = 0; $kept = 0; $created = 0; $records = @()
    foreach ($e in $man.files) {
        $dest = Join-Path $InstallDir $e.name; $cur = Hash $dest
        if ($SETTINGS -contains (Split-Path $e.name -Leaf)) { continue }
        if ($cur -eq $e.sha256 -and $Mode -eq 'Smart') { continue }
        if ($DryRun) { $changed++; continue }
        if ($cur) { New-Item -ItemType Directory -Force -Path (Split-Path (Join-Path $backup $e.name) -Parent) | Out-Null; Copy-Item $dest (Join-Path $backup $e.name) -Force }
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        Copy-Item (Join-Path $src $e.name) ($dest + '.update-tmp') -Force; Move-Item ($dest + '.update-tmp') $dest -Force
        if ((Hash $dest) -ne $e.sha256) { throw ('write verification failed: ' + $e.name) }
        $records += [pscustomobject]@{ name = $e.name; existed = [bool]$cur; old_sha256 = $cur; new_sha256 = $e.sha256 }; $changed++
    }
    # Settings: create from the shipped defaults (with this PC's paths) only when the file does not exist.
    $defaults = @{
        'config.json' = (Get-Content (Join-Path $Payload 'defaults\config.json') -Raw).Replace('__BLENDER_EXE__', ($BlenderExe -replace '\\', '\\'))
        'hunyuan_settings.json' = (Get-Content (Join-Path $Payload 'defaults\hunyuan_settings.json') -Raw).Replace('__COMFY_ROOT__', ($ComfyRoot -replace '\\', '\\'))
        'studio_settings.json' = (Get-Content (Join-Path $Payload 'defaults\studio_settings.json') -Raw).Replace('__COMFY_DIR__', ($ComfyBase -replace '\\', '\\')).Replace('__LLAMA_DIR__', ($LlamaDir -replace '\\', '\\')).Replace('__STAMP__', $Stamp)
        'service_manager_settings.json' = (Get-Content (Join-Path $Payload 'defaults\service_manager_settings.json') -Raw).Replace('__ROUTER__', ((Join-Path $InstallDir 'Start-Model-Router.bat') -replace '\\', '/'))
        'optional_worker_router.json' = (Get-Content (Join-Path $Payload 'defaults\optional_worker_router.json') -Raw).Replace('__LLAMA_DIR__', ($LlamaDir -replace '\\', '\\')).Replace('__MODELS_INI__', ((Join-Path $InstallDir 'models.ini') -replace '\\', '\\'))
        'models.ini' = (Get-Content (Join-Path $Payload 'defaults\models.ini') -Raw)
        'Start-Model-Router.bat' = (Get-Content (Join-Path $Payload 'defaults\Start-Model-Router.bat') -Raw).Replace('__PYTHON__', $PyExe)
    }
    foreach ($n in 'autoroute_settings.json', 'quality_settings.json', 'mega_dragon_settings.json', 'job_cancel_settings.json') { $defaults[$n] = Get-Content (Join-Path $src $n) -Raw }
    $defaults['archive_retention.json'] = "{`r`n  `"enabled`": true,`r`n  `"hours`": 24,`r`n  `"keep`": []`r`n}`r`n"
    foreach ($n in $defaults.Keys) {
        $dest = Join-Path $InstallDir $n
        if (Test-Path $dest) { $kept++; continue }
        if (-not $DryRun) { WriteText $dest $defaults[$n] }; $created++
    }
    foreach ($n in $TEMPLATES) {   # binary Bambu templates: copy only when missing
        $dest = Join-Path $InstallDir $n
        if (Test-Path $dest) { $kept++; continue }
        if (-not $DryRun) { Copy-Item (Join-Path $src $n) $dest }; $created++
    }
    if (-not $DryRun) {
        if (@($records | Where-Object { $_.existed }).Count) {
            New-Item -ItemType Directory -Force -Path $backup | Out-Null
            ([pscustomobject]@{ version = $VERSION; created = (Get-Date -Format s); mode = $Mode; files = $records } | ConvertTo-Json -Depth 5) | Set-Content (Join-Path $backup 'backup_manifest.json') -Encoding UTF8
            WriteText (Join-Path $backup 'RESTORE.cmd') ("@echo off`r`nrem Restores the studio files this installer replaced on " + $Stamp + ". Power the studio off first.`r`nrobocopy `"%~dp0.`" `"" + $InstallDir + "`" /E /XF backup_manifest.json RESTORE.cmd`r`necho Restored. Files the installer ADDED (not replaced) were left in place.`r`npause`r`n")
        }
        $vf = Join-Path $InstallDir 'color_update_version.json'; $cv = ReadJson $vf
        if ($changed -or -not $cv -or $cv.version -ne $VERSION -or $cv.build -ne $BUILD) { WriteText $vf ((@{ version = $VERSION; build = $BUILD; installed = (Get-Date -Format s); backup = $(if (Test-Path $backup) { $backup } else { '' }) } | ConvertTo-Json)) }
        # keep only the newest 2 installer backups
        Get-ChildItem (Join-Path $InstallDir 'backups') -Directory -Filter 'installer-*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -Skip 2 | ForEach-Object { Remove-Item $_.FullName -Recurse -Force; Say ('    removed old installer backup ' + $_.Name) }
    }
    return ('' + $changed + ' program file(s) installed/updated, ' + $created + ' setting file(s) created, ' + $kept + ' existing setting file(s) kept unchanged' + $(if (@($records | Where-Object { $_.existed }).Count) { '; backup: ' + $backup } else { '' }))
}
Step 'Desktop shortcut' @('AI Modeling Studio 0.017 program files', 'Python 3.15.1') {
    if ($DryRun -or -not $IsWin) { return 'DRY: would create "AI Modeling Studio" on the desktop' }
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AI Modeling Studio.lnk'
    $sh = New-Object -ComObject WScript.Shell; $s = $sh.CreateShortcut($lnk)
    $want = '"' + (Join-Path $InstallDir 'studio_launcher.pyw') + '"'
    if ((Test-Path $lnk) -and $s.TargetPath -ieq $PywExe -and $s.Arguments -eq $want -and $Mode -eq 'Smart') { return 'already correct' }
    $s.TargetPath = $PywExe; $s.Arguments = $want; $s.WorkingDirectory = $InstallDir; $s.IconLocation = (Join-Path $InstallDir 'ai_studio.ico') + ',0'; $s.Save()
    return 'created / updated'
}

# ---------------------------------------------------------------- 6b. video reader (ffmpeg 7.1, used for turntable video uploads)
Step 'Video reader (ffmpeg 7.1)' @('AI Modeling Studio 0.017 program files') {
    $dir = Join-Path $InstallDir 'tools\ffmpeg'; $exe = Join-Path $dir 'ffmpeg.exe'
    if ((Hash $exe) -eq $FF.ExeSha -and $Mode -eq 'Smart') { return 'already installed + verified' }
    $zip = Join-Path $Downloads 'ffmpeg-7.1-essentials_build.zip'
    if ((Hash $zip) -ne $FF.ZipSha) { if (-not (Download $FF.Url $zip)) { if ($DryRun) { return 'DRY: would download ffmpeg 7.1 (88 MB)' }; throw 'ffmpeg download failed' } }
    if ((Hash $zip) -ne $FF.ZipSha) { throw ('ffmpeg zip has the wrong SHA-256: ' + (Hash $zip)) }
    if ($DryRun) { return 'DRY: would unpack ffmpeg.exe' }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null; Add-Type -AssemblyName System.IO.Compression.FileSystem
    $za = [IO.Compression.ZipFile]::OpenRead($zip)
    try { foreach ($e in $za.Entries) {
        if ($e.FullName -eq 'ffmpeg-7.1-essentials_build/bin/ffmpeg.exe') { [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $exe, $true) }
        if ($e.FullName -eq 'ffmpeg-7.1-essentials_build/LICENSE') { [IO.Compression.ZipFileExtensions]::ExtractToFile($e, (Join-Path $dir 'LICENSE.txt'), $true) } } } finally { $za.Dispose() }
    if ((Hash $exe) -ne $FF.ExeSha) { throw 'ffmpeg.exe verification failed after unpacking' }
    return 'installed + verified'
}

# ---------------------------------------------------------------- 6c. AI paint runtime (texture_paint: Python 3.12 + torch 2.6 cu126 + Hunyuan3D-2 paint)
# Same pins and folder layout as the working PC. Each part is skipped when its state\*.done marker exists (Smart), so an existing
# runtime is not downloaded again. About 19 GB on a new PC. ComfyUI's Python is never touched.
Step 'AI paint runtime (Hunyuan3D-2 paint, ~19 GB)' @('AI Modeling Studio 0.017 program files', 'Python 3.15.1') {
    $root = Join-Path $InstallDir 'texture_paint'; $state = Join-Path $root 'state'; $dl = Join-Path $root 'downloads'; $scripts = Join-Path $root 'scripts'
    $uv = Join-Path $root 'tools\uv.exe'; $envDir = Join-Path $root 'env'; $tpPy = Join-Path $envDir 'Scripts\python.exe'
    $code = Join-Path $root 'code\Hunyuan3D-2'; $models = Join-Path $root 'models'
    $chk = "import sys;sys.path.insert(0,sys.argv[1]);import ai_paint_stage as A;s=A.install_status(sys.argv[1]);print('TP_STATUS',s['installed'],'|'.join(s['problems']))"
    $st = (Capture $PyExe ('-B -c "' + $chk + '" "' + $InstallDir + '"') 120).out
    if ($st -match 'TP_STATUS True' -and $Mode -eq 'Smart') { return 'already installed (fixed versions verified by the studio)' }
    Say ('    studio check: ' + (LastLine $st))
    if ($DryRun) { return 'DRY: would install uv, Python 3.12.15, torch 2.6.0+cu126, 42 locked packages, rasterizer wheel, Hunyuan3D-2 code @f8db630, models @efb40d8 (~19 GB)' }
    $free = (Get-PSDrive ($InstallDir.Substring(0, 1))).Free / 1GB
    if ($free -lt 40) { throw ('only {0:N1} GB free on the studio drive; the AI paint runtime needs about 40 GB while installing' -f $free) }
    foreach ($d in $state, $dl, $scripts, (Join-Path $root 'tools')) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    $done = { param($n) Test-Path (Join-Path $state ($n + '.done')) }; $mark = { param($n) New-Item -ItemType File -Force -Path (Join-Path $state ($n + '.done')) | Out-Null }
    if ($Mode -eq 'Full') { Get-ChildItem $state -Filter '*.done' -ErrorAction SilentlyContinue | Remove-Item -Force }
    $env:UV_CACHE_DIR = Join-Path $root 'cache\uv'; $env:UV_PYTHON_INSTALL_DIR = Join-Path $root 'python'; $env:UV_NO_CONFIG = '1'
    $env:HF_HOME = Join-Path $root 'cache\hf'; $env:HF_HUB_DISABLE_TELEMETRY = '1'
    function TpRun($exe, $argList, $what, $timeout = 7200) {
        $q = ($argList | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
        $r = Capture $exe $q $timeout; if ($r.code) { throw ($what + ' failed (exit ' + $r.code + '): ' + (LastLine $r.out)) }; return $r.out
    }
    if (-not (& $done 'uv') -or -not (Test-Path $uv)) {
        Say '    [1/7] uv'; $w = Join-Path $dl ('uv-' + $TP.UvVer + '-py3-none-win_amd64.whl')
        if ((Hash $w) -ne $TP.UvSha) { if (-not (Download $TP.UvUrl $w) -or (Hash $w) -ne $TP.UvSha) { throw 'uv download failed or wrong SHA-256' } }
        Add-Type -AssemblyName System.IO.Compression.FileSystem; $z = [IO.Compression.ZipFile]::OpenRead($w)
        try { $e = $z.GetEntry('uv-' + $TP.UvVer + '.data/scripts/uv.exe'); if (-not $e) { throw 'uv.exe not inside the wheel' }; [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $uv, $true) } finally { $z.Dispose() }
        & $mark 'uv'
    }
    if (-not (& $done 'python') -or -not (Test-Path $tpPy)) {
        Say ('    [2/7] Python ' + $TP.PyVer + ' (private copy, no PATH/registry changes)')
        TpRun $uv @('python', 'install', $TP.PyVer, '--no-registry', '--no-bin') 'uv python install' | Out-Null
        TpRun $uv @('venv', $envDir, '--python', $TP.PyVer, '--managed-python', '--clear') 'uv venv' | Out-Null; & $mark 'python'
    }
    if (-not (& $done 'torch')) { Say '    [3/7] PyTorch 2.6.0 + CUDA 12.6 (~2.5 GB)'; TpRun $uv @('pip', 'install', '--python', $tpPy, $TP.Torch, '--index-url', $TP.TorchIndex) 'torch install' | Out-Null; & $mark 'torch' }
    $t = (Capture $tpPy "-W ignore -c `"import torch;print('TORCHCHECK', torch.__version__, torch.cuda.is_available())`"" 300).out
    if ($t -notmatch 'TORCHCHECK 2\.6\.0\+cu126 True') { throw ('torch check failed (needs an NVIDIA GPU + driver): ' + (LastLine $t)) }
    if (-not (& $done 'deps')) {
        Say '    [4/7] 42 helper packages (exact versions, hash-checked)'; $lock = Join-Path $scripts 'paint_lock.txt'; Copy-Item (Join-Path $Payload 'texture_paint\paint_lock.txt') $lock -Force
        TpRun $uv @('pip', 'install', '--python', $tpPy, '--no-deps', '--require-hashes', '-r', $lock) 'package install' | Out-Null; & $mark 'deps'
    }
    if (-not (& $done 'rasterizer')) {
        Say '    [5/7] prebuilt custom_rasterizer wheel'; $w = Join-Path $dl $TP.CrFile
        if ((Hash $w) -ne $TP.CrSha) { if (-not (Download $TP.CrUrl $w) -or (Hash $w) -ne $TP.CrSha) { throw 'rasterizer wheel download failed or wrong SHA-256' } }
        TpRun $uv @('pip', 'install', '--python', $tpPy, '--no-deps', $w) 'rasterizer install' | Out-Null; & $mark 'rasterizer'
    }
    if ((Capture $tpPy '-W ignore -c "import torch, custom_rasterizer, custom_rasterizer_kernel; print(''import-ok'')"' 300).out -notmatch 'import-ok') { throw 'custom_rasterizer does not load' }
    if (-not (& $done 'code')) {
        Say '    [6/7] Hunyuan3D-2 code (git, fixed commit)'
        $git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
        if (-not $git) { & winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements --silent; $git = Join-Path $env:ProgramFiles 'Git\cmd\git.exe' }
        if (-not (Test-Path $git)) { throw 'git is needed for the Hunyuan3D-2 code and could not be installed (install Git for Windows, then run setup again)' }
        if (-not (Test-Path (Join-Path $code '.git'))) { New-Item -ItemType Directory -Force -Path (Split-Path $code) | Out-Null; TpRun $git @('clone', '--filter=blob:none', '--no-checkout', $TP.HyGit, $code) 'git clone' | Out-Null }
        TpRun $git @('-C', $code, 'checkout', '--force', $TP.HyCommit) 'git checkout' | Out-Null; & $mark 'code'
    }
    if (-not (& $done 'models')) {
        Say '    [7/7] Hunyuan3D-2 delight + paint-turbo models (~14.6 GB, each file SHA-256 checked; resumes)'
        $s = Join-Path $scripts 'download_models.py'; Copy-Item (Join-Path $Payload 'texture_paint\download_models.py') $s -Force
        $o = TpRun $tpPy @($s, $models, $TP.HfRev) 'model download/verification' 14400; Say ('    ' + (LastLine $o)); & $mark 'models'
    }
    $st = (Capture $PyExe ('-B -c "' + $chk + '" "' + $InstallDir + '"') 120).out
    if ($st -notmatch 'TP_STATUS True') { throw ('studio still reports the AI paint runtime as incomplete: ' + (LastLine $st)) }
    return 'installed + verified by the studio'
}

# ---------------------------------------------------------------- 7. optional: Bambu Studio, AnythingLLM skill
if ($Want['bambu']) {
    Step 'Bambu Studio 02.08.02.61' @() {
        $e = Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like 'Bambu Studio*' } | Select-Object -First 1
        if ($e -and $e.DisplayVersion -eq $PIN.BambuVersion -and $Mode -eq 'Smart') { return 'already installed ' + $e.DisplayVersion }
        if ($e -and $Mode -eq 'Smart') { return ('already installed ' + $e.DisplayVersion + ' (pinned ' + $PIN.BambuVersion + '; existing version kept, not changed)') }
        if ($DryRun) { return 'DRY: winget install Bambulab.Bambustudio' }
        # winget codes that mean "it is already there": 0x8A15002B no applicable update, 0x8A150061 already installed
        $already = @(-1978335189, -1978335135)
        $wargs = @('install', '-e', '--id', 'Bambulab.Bambustudio', '--version', $PIN.BambuVersion, '--accept-package-agreements', '--accept-source-agreements', '--silent')
        if ($Mode -eq 'Full') { $wargs += '--force' }
        & winget @wargs; $c1 = $LASTEXITCODE
        if ($c1 -in $already) { return ('already installed (winget exit ' + $c1 + ': already installed / no applicable update)') }
        if ($c1) {
            Say ('    pinned version install returned winget exit ' + $c1 + ' - trying the current winget version') 'Yellow'
            & winget install -e --id Bambulab.Bambustudio --accept-package-agreements --accept-source-agreements --silent $(if ($Mode -eq 'Full') { '--force' }); $c2 = $LASTEXITCODE
            if ($c2 -in $already) { return ('already installed (winget exit ' + $c2 + ': already installed / no applicable update)') }
            if ($c2) { throw ('winget exit ' + $c1 + ' (pinned ' + $PIN.BambuVersion + ') then ' + $c2 + ' (current version)') }
            return 'installed current winget version (pinned ' + $PIN.BambuVersion + ' not available)'
        }
        return 'installed ' + $PIN.BambuVersion
    }
}
if ($Want['anythingllm']) {
    Step 'AnythingLLM skill' @('AI Modeling Studio 0.017 program files') {
        $app = Join-Path $env:LOCALAPPDATA 'Programs\AnythingLLM\AnythingLLM.exe'; $note = ''
        if (-not (Test-Path $app)) {
            if ($DryRun) { $note = ' (DRY: would install AnythingLLM with winget)' }
            else { try { & winget install -e --id MintplexLabs.AnythingLLM --accept-package-agreements --accept-source-agreements --silent; $note = ' (AnythingLLM installed; open it once, then enable the skill)' } catch { $note = ' (WARNING: AnythingLLM app not installed: ' + $_.Exception.Message + ' - skill files copied anyway)' } }
        }
        $dst = Join-Path $env:APPDATA 'anythingllm-desktop\storage\plugins\agent-skills\image-to-blender-auto'
        $src = Join-Path $Payload 'studio\anythingllm-skill\image-to-blender-auto'
        $same = $true; foreach ($n in 'handler.js', 'plugin.json') { if ((Hash (Join-Path $dst $n)) -ne (Hash (Join-Path $src $n))) { $same = $false } }
        if ($same -and $Mode -eq 'Smart') { return 'already installed' + $note }
        if (-not $DryRun) { New-Item -ItemType Directory -Force -Path $dst | Out-Null; Copy-Item (Join-Path $src '*') $dst -Force }
        return 'installed' + $note
    }
}

# ---------------------------------------------------------------- 8. verification in the real runtimes
Step 'Verify: Python syntax of studio files' @('AI Modeling Studio 0.017 program files', 'Python 3.15.1') {
    if ($DryRun) { return 'DRY' }
    $f = Join-Path $Temp 'syntax.py'; WriteText $f "import ast,sys,pathlib`nbad=[]`nfor p in pathlib.Path(sys.argv[1]).glob('*.py*'):`n    try: ast.parse(p.read_text(encoding='utf-8-sig'),str(p))`n    except Exception as e: bad.append(p.name+': '+str(e))`nprint('\n'.join(bad) or 'SYNTAX_OK')`n"
    $r = Capture $PyExe ('-B "' + $f + '" "' + $InstallDir + '"'); if ($r.out -notmatch 'SYNTAX_OK') { throw $r.out.Trim() }; return 'all .py/.pyw files parse'
}
Step 'Verify: mirror check + retry rules (0.010 self-test)' @('AI Modeling Studio 0.017 program files', 'Python 3.15.1', 'ComfyUI portable 0.42.1') {
    if ($DryRun) { return 'DRY' }
    $r = Capture $PyExe ('-B "' + (Join-Path $InstallDir 'test_view_mirror_010.py') + '" "' + $InstallDir + '"') 600
    if ($r.out -notmatch 'VIEW_MIRROR_SELFTEST_PASSED') { throw ($r.out.Trim() -split "`n" | Select-Object -Last 15) -join ' | ' }
    return (($r.out -split "`n" | Where-Object { $_ -match 'checks passed' }) -join '').Trim()
}
Step 'Verify: Blender self-test (color export, alignment, geometry check)' @('AI Modeling Studio 0.017 program files', 'Blender 5.2.2') {
    if ($DryRun) { return 'DRY' }
    $r = Capture $BlenderExe ('--background --factory-startup --python-exit-code 1 --python "' + (Join-Path $InstallDir 'selftest_color_update.py') + '" -- "' + $InstallDir + '"') 1500
    if ($r.out -notmatch 'COLOR_UPDATE_SELFTEST_PASSED') { throw (($r.out.Trim() -split "`n" | Select-Object -Last 15) -join ' | ') }
    return 'COLOR_UPDATE_SELFTEST_PASSED'
}
$TpPy = Join-Path $InstallDir 'texture_paint\env\Scripts\python.exe'
foreach ($t in @(
    @{ n = 'Verify: 12-stage list'; f = 'test_stage_unify.py'; a = ''; m = 'STAGE_UNIFY_TEST_PASSED'; d = @() },
    @{ n = 'Verify: AI paint wiring'; f = 'test_ai_paint_stage.py'; a = ' unit'; m = 'AI_PAINT_UNIT_PASSED'; d = @('AI paint runtime (Hunyuan3D-2 paint, ~19 GB)') },
    @{ n = 'Verify: AI paint best settings'; f = 'test_ai_paint_defaults.py'; a = ''; m = 'AI_PAINT_DEFAULTS_TEST_PASSED'; d = @('AI paint runtime (Hunyuan3D-2 paint, ~19 GB)') },
    @{ n = 'Verify: colour page texts'; f = 'test_cleanup_016d.py'; a = ''; m = 'CLEANUP_016D_TEST_PASSED'; d = @() },
    @{ n = 'Verify: 4 / 9 / custom colours'; f = 'test_colour_count_016d.py'; a = ''; m = 'COLOUR_COUNT_016D_TEST_PASSED'; d = @('AI paint runtime (Hunyuan3D-2 paint, ~19 GB)') },
    @{ n = 'Verify: recommended colour amount'; f = 'test_colour_advice_017c.py'; a = ''; m = 'COLOUR_ADVICE_017C_TEST_PASSED'; d = @() },
    @{ n = 'Verify: Prompt Builder'; f = 'test_prompt_builder_017.py'; a = ''; m = 'PROMPT_BUILDER_017_TEST_PASSED'; d = @() },
    @{ n = 'Verify: Has props included'; f = 'test_props_017.py'; a = (' "' + $TpPy + '"'); m = 'PROPS_017_TEST_PASSED'; d = @('AI paint runtime (Hunyuan3D-2 paint, ~19 GB)') },
    @{ n = 'Verify: side picture AI paint'; f = 'test_multi_017.py'; a = (' "' + $TpPy + '" "' + $BlenderExe + '"'); m = 'MULTI_017_TEST_PASSED'; d = @('AI paint runtime (Hunyuan3D-2 paint, ~19 GB)', 'Blender 5.2.2') },
    @{ n = 'Verify: video upload, crop fix, archive auto-delete'; f = 'test_studio_016.py'; a = (' "' + (Join-Path $Payload 'test_assets\test_turntable.mp4') + '" "' + $EmbPy + '" "' + (Join-Path $InstallDir 'tools\ffmpeg\ffmpeg.exe') + '"'); m = 'STUDIO_016_TEST_PASSED'; d = @('Video reader (ffmpeg 7.1)', 'ComfyUI portable 0.42.1') }
)) {
    $tt = $t
    Step $tt.n (@('AI Modeling Studio 0.017 program files', 'Python 3.15.1') + $tt.d) {
        if ($DryRun) { return 'DRY' }
        $r = Capture $PyExe ('-B "' + (Join-Path $InstallDir $tt.f) + '" "' + $InstallDir + '"' + $tt.a) 2400
        if ($r.out -notmatch $tt.m) { throw (($r.out.Trim() -split "`n" | Where-Object { $_ -match 'FAIL|Error|rror:' } | Select-Object -First 8) -join ' | ') }
        return $tt.m
    }
}
}

# ---------------------------------------------------------------- report
Say ''; Say '==================== SUMMARY ====================' 'Cyan'
foreach ($r in $Script:Results) { Say (('{0,-62} {1}' -f $r.Step, $r.Result)) $(if ($r.Result -like 'FAILED*') { 'Red' } elseif ($r.Result -like 'SKIPPED*' -or $r.Result -like '*WARNING*') { 'Yellow' } else { 'Green' }) }
$nFail = @($Script:Results | Where-Object { $_.Result -like 'FAILED*' -or $_.Result -like 'SKIPPED*' }).Count
Say ''
if ($DryRun) { Say 'RESULT: CHECK ONLY - nothing was changed. Lines starting with DRY show what an install would do; "already ..." lines are up to date.' 'Cyan' }
elseif ($nFail) { Say ('RESULT: ' + $nFail + ' step(s) need attention. Each failure has a FAIL_REASON file in ' + $Temp + '. Run the installer again (Smart) after fixing.') 'Red' }
else { Say 'RESULT: everything installed and verified. Start the studio with the "AI Modeling Studio" desktop icon; the header should read Version 0.017.' 'Green' }
Say 'Never deleted: jobs, source images, model files, your settings. Damaged model copies are renamed, not deleted.'
$reportDir = if (Test-Path (Join-Path $InstallDir 'logs')) { Join-Path $InstallDir 'logs' } else { $Temp }
$report = Join-Path $reportDir ('installer-report-' + $Stamp + '.txt'); WriteText $report ($Script:Log -join "`r`n"); Say ('Report: ' + $report)
if (-not $NoWindow -and $IsWin) {
    try {
        Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
        $f = New-Object Windows.Forms.Form; $f.Text = 'AI Modeling Studio ' + $VERSION + ' installer - report'; $f.Width = 1000; $f.Height = 650; $f.StartPosition = 'CenterScreen'
        $tb = New-Object Windows.Forms.TextBox; $tb.Multiline = $true; $tb.ReadOnly = $true; $tb.ScrollBars = 'Both'; $tb.WordWrap = $false; $tb.MaxLength = 0; $tb.Dock = 'Fill'; $tb.Font = New-Object Drawing.Font('Consolas', 9); $tb.Text = ($Script:Log -join "`r`n")
        $b = New-Object Windows.Forms.Button; $b.Text = 'Copy all'; $b.Dock = 'Bottom'; $b.Height = 40; $b.Add_Click({ [Windows.Forms.Clipboard]::SetText($tb.Text); $b.Text = 'Copied - paste it into the chat' })
        $f.Controls.Add($tb); $f.Controls.Add($b); [void]$f.ShowDialog()
    } catch {}
}
exit $(if ($nFail) { 1 } else { 0 })
