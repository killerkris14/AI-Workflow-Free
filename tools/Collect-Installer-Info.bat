@echo off
setlocal
title AI Modeling Studio - collect installer information (read-only)
set "AISTUDIO_COLLECTOR=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "$t=[IO.File]::ReadAllText($env:AISTUDIO_COLLECTOR); $m='#'+'POWERSHELL_BELOW#'; $i=$t.IndexOf($m); iex $t.Substring($i+$m.Length)"
echo.
pause
exit /b
#POWERSHELL_BELOW#
$ErrorActionPreference = 'Continue'
$Out = New-Object System.Text.StringBuilder
function W($s = '') { [void]$Out.AppendLine([string]$s) }
function Section($t) { W ''; W ('==================== ' + $t + ' ===================='); Write-Host ('Collecting: ' + $t) -ForegroundColor Cyan }
function Hash($p) { try { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } catch { return 'ERROR ' + $_.Exception.Message } }
function Run($exe, $argList) { try { $r = & $exe @argList 2>&1 | Out-String; return $r.Trim() } catch { return 'ERROR ' + $_.Exception.Message } }
$SecretKey = '(?i)(token|secret|password|passwd|api[_-]?key|auth)'
function Redact-Text($text) { return ($text -replace ('("[^"]*' + $SecretKey + '[^"]*"\s*:\s*)"[^"]*"'), '$1"<REDACTED>"') -replace ('(?m)^(\s*[^=\r\n]*' + $SecretKey + '[^=\r\n]*=\s*).*$'), '$1<REDACTED>' }
function Dump-File($p, $label) {
    $fi = Get-Item -LiteralPath $p
    W ('----- FILE ' + $label + '  (' + $fi.Length + ' bytes, sha256 ' + (Hash $p) + ') -----')
    if ($fi.Name -ieq 'access-token.txt') { W '<not collected: secret>'; return }
    try { W (Redact-Text ([IO.File]::ReadAllText($p))) } catch { W ('ERROR ' + $_.Exception.Message) }
    W ('----- END ' + $label + ' -----')
}
function Dump-Base64($p, $label, $max) {
    $fi = Get-Item -LiteralPath $p
    W ('----- BASE64 ' + $label + '  (' + $fi.Length + ' bytes, sha256 ' + (Hash $p) + ') -----')
    if ($fi.Length -gt $max) { W ('<too large for text (' + $fi.Length + ' bytes); please attach this file to the chat: ' + $p + '>') }
    else { $b = [Convert]::ToBase64String([IO.File]::ReadAllBytes($p)); for ($i = 0; $i -lt $b.Length; $i += 120) { W $b.Substring($i, [Math]::Min(120, $b.Length - $i)) } }
    W ('----- END ' + $label + ' -----')
}
$TextExt = @('.py', '.pyw', '.js', '.html', '.css', '.bat', '.cmd', '.ps1', '.txt', '.json', '.ini', '.md', '.toml', '.cfg', '.yaml', '.yml')

W 'AI Modeling Studio - installer information collector v1 (READ-ONLY: nothing is changed, installed or deleted)'
W ('Collected: ' + (Get-Date -Format s) + '   Computer: ' + $env:COMPUTERNAME + '   User: ' + $env:USERNAME)

# ---------- studio folder ----------
Section 'STUDIO FOLDER'
$root = $null; $links = @()
try {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('StartMenu'), [Environment]::GetFolderPath('CommonStartMenu'))) {
        if (-not $d -or -not (Test-Path -LiteralPath $d)) { continue }
        foreach ($f in (Get-ChildItem -LiteralPath $d -Filter *.lnk -Recurse -ErrorAction SilentlyContinue)) {
            $s = $shell.CreateShortcut($f.FullName)
            if ($s.Arguments -match 'studio_launcher|AI-Workflow|start_ai_studio' -or $s.TargetPath -match 'AI-Workflow|Bambu|blender|llama|ComfyUI|AnythingLLM') {
                W ('Shortcut: ' + $f.FullName); W ('  Target: ' + $s.TargetPath); W ('  Arguments: ' + $s.Arguments); W ('  WorkingDirectory: ' + $s.WorkingDirectory); W ('  Icon: ' + $s.IconLocation)
                foreach ($m in [regex]::Matches($s.Arguments, '"([^"]+studio_launcher\.pyw)"|(\S+studio_launcher\.pyw)')) { $v = $m.Groups[1].Value; if (-not $v) { $v = $m.Groups[2].Value }; $root = Split-Path $v -Parent }
            }
        }
    }
} catch { W ('Shortcut scan error: ' + $_.Exception.Message) }
if ($env:AISTUDIO_ROOT) { $root = $env:AISTUDIO_ROOT }
if (-not $root -and (Test-Path 'C:\AI-Workflow-Auto\app.py')) { $root = 'C:\AI-Workflow-Auto' }
W ('Installed studio folder: ' + $root)
if ($root) {
    W ''; W 'Top-level folders (name, file count, total MB - contents of Jobs/backups NOT listed):'
    foreach ($d in (Get-ChildItem -LiteralPath $root -Directory -Force)) {
        $files = @(Get-ChildItem -LiteralPath $d.FullName -File -Recurse -Force -ErrorAction SilentlyContinue)
        W ('  ' + $d.Name + '  files=' + $files.Count + '  MB=' + [Math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB, 1))
    }
    W ''; W 'Top-level files (sha256  size  name):'
    foreach ($f in (Get-ChildItem -LiteralPath $root -File -Force | Sort-Object Name)) { $hv = if ($f.Name -match '(?i)token|secret|\.key$|dpapi') { '<secret file: not hashed>' } else { Hash $f.FullName }; W ('  ' + $hv + '  ' + $f.Length + '  ' + $f.Name) }
    Section 'STUDIO TEXT FILES NEEDED FOR THE INSTALLER (secrets redacted)'
    foreach ($n in @('config.json', 'hunyuan_settings.json', 'autoroute_settings.json', 'autoroute_multi_view.json', 'autoroute_single_view.json', 'hunyuan_workflow_api.json', 'hunyuan_workflow_api_mv.json', 'hunyuan_workflow_api_single_view.json', 'quality_settings.json', 'mega_dragon_settings.json', 'job_cancel_settings.json', 'optional_worker_router.json', 'studio_settings.json', 'service_manager_settings.json', 'birefnet_discovery.json', 'color_update_version.json', 'models.ini', 'ui.html', 'visual_dashboard.html', 'archive_panel.html', 'start_ai_studio.py', 'studio_launcher.pyw', 'Start-AI-Studio.bat', 'Start-Hunyuan-Portal.bat', 'Start-Workflow.bat', 'Start-Model-Router.bat')) {
        $p = Join-Path $root $n; if (Test-Path -LiteralPath $p) { Dump-File $p $n } else { W ('----- MISSING ' + $n + ' -----') }
    }
    Section 'STUDIO BINARY FILES (base64)'
    foreach ($n in @('ai_studio.ico', 'bambu_template.3mf')) { $p = Join-Path $root $n; if (Test-Path -LiteralPath $p) { Dump-Base64 $p $n 600KB } else { W ('----- MISSING ' + $n + ' -----') } }
    foreach ($sub in @('anythingllm-skill', 'developer_tools', '.studio_release')) {
        Section ('FOLDER ' + $sub)
        $dp = Join-Path $root $sub
        if (-not (Test-Path -LiteralPath $dp)) { W 'not present'; continue }
        foreach ($f in (Get-ChildItem -LiteralPath $dp -File -Recurse -Force)) {
            $rel = $f.FullName.Substring($root.Length + 1)
            if ($TextExt -contains $f.Extension.ToLower() -and $f.Length -lt 300KB -and $f.Name -notmatch '(?i)key|token|dpapi') { Dump-File $f.FullName $rel } else { W ('  (listed only) ' + (Hash $f.FullName) + '  ' + $f.Length + '  ' + $rel) }
        }
    }
}

# ---------- Python ----------
Section 'PYTHON'
W ('py launcher: ' + (Run 'where.exe' @('py')))
W ('py --list: ' + (Run 'py' @('--list')))
W ('pymanager list: ' + (Run 'py' @('list')))
foreach ($p in @("$env:LOCALAPPDATA\Python\pythoncore-3.15-64\python.exe")) { if (Test-Path $p) { W ($p + ' -> ' + (Run $p @('-c', 'import sys,platform;print(sys.version);print(platform.platform())'))) } }
W ('Registry Python keys:'); try { Get-ChildItem 'HKCU:\Software\Python', 'HKLM:\Software\Python' -Recurse -ErrorAction SilentlyContinue | ForEach-Object { W ('  ' + $_.Name) } } catch {}
W ('Python install manager package: ' + (Run 'powershell' @('-NoProfile', '-Command', 'Get-AppxPackage *PythonSoftwareFoundation* | Select-Object Name,Version | Format-List | Out-String')))

# ---------- Blender ----------
Section 'BLENDER'
$cfgBlender = $null
if ($root -and (Test-Path (Join-Path $root 'config.json'))) { try { $cfgBlender = (Get-Content (Join-Path $root 'config.json') -Raw | ConvertFrom-Json).blender_exe } catch {} }
W ('config.json blender_exe: ' + $cfgBlender)
if ($cfgBlender -and (Test-Path $cfgBlender)) { W (Run $cfgBlender @('--version')) }
W 'Uninstall entries (Blender / Bambu / AnythingLLM / Python / VC++ / NVIDIA / Git):'
foreach ($k in @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
    Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'Blender|Bambu|AnythingLLM|Python|Visual C\+\+|NVIDIA Graphics|Git|7-Zip|llama' } | ForEach-Object { W ('  ' + $_.DisplayName + ' | ' + $_.DisplayVersion + ' | ' + $_.InstallLocation + ' | ' + $_.UninstallString + ' | ' + $_.PSChildName) }
}
$ext = Join-Path $env:APPDATA 'Blender Foundation\Blender'
if (Test-Path $ext) { W 'Blender user extensions:'; Get-ChildItem $ext -Recurse -Directory -Depth 4 -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'extensions\\[^\\]+\\[^\\]+$' } | ForEach-Object { W ('  ' + $_.FullName) } }

# ---------- ComfyUI ----------
Section 'COMFYUI'
$comfy = $null
if ($root -and (Test-Path (Join-Path $root 'hunyuan_settings.json'))) { try { $comfy = (Get-Content (Join-Path $root 'hunyuan_settings.json') -Raw | ConvertFrom-Json).comfy_root } catch {} }
W ('hunyuan_settings.json comfy_root: ' + $comfy)
if ($comfy -and (Test-Path $comfy)) {
    $base = if (Test-Path (Join-Path $comfy 'ComfyUI\main.py')) { $comfy } else { Split-Path $comfy -Parent }
    W ('Portable base: ' + $base)
    W 'Portable top level:'; Get-ChildItem $base -Force | ForEach-Object { W ('  ' + $_.Mode + '  ' + $_.Name) }
    $cu = Join-Path $base 'ComfyUI'
    $py = @((Join-Path $base 'python_embeded\python.exe'), (Join-Path $base 'python_embedded\python.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
    W ('Embedded python: ' + $py)
    foreach ($b in (Get-ChildItem $base -Filter *.bat -ErrorAction SilentlyContinue)) { Dump-File $b.FullName ('portable\' + $b.Name) }
    if ($py) { W 'pip freeze (embedded python):'; W (Run $py @('-m', 'pip', 'freeze', '--all')) }
    W ('git describe: ' + (Run 'git' @('-C', $cu, 'describe', '--tags', '--always'))); W ('git remote: ' + (Run 'git' @('-C', $cu, 'remote', '-v')))
    $node = Join-Path $cu 'custom_nodes\ai_workflow_portal'
    Section 'CUSTOM NODE ai_workflow_portal'
    if (Test-Path $node) { foreach ($f in (Get-ChildItem $node -File -Recurse -Force | Where-Object { $_.FullName -notmatch '__pycache__' })) { $rel = $f.FullName.Substring($node.Length + 1); if ($TextExt -contains $f.Extension.ToLower() -and $f.Length -lt 400KB) { Dump-File $f.FullName $rel } else { W ('  (listed only) ' + (Hash $f.FullName) + '  ' + $f.Length + '  ' + $rel) } } } else { W 'NOT FOUND' }
    Section 'COMFYUI MODEL FILES (sha256 - this takes a few minutes for the large files)'
    foreach ($f in (Get-ChildItem (Join-Path $cu 'models') -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 1MB })) { Write-Host ('  hashing ' + $f.Name); W ('  ' + (Hash $f.FullName) + '  ' + $f.Length + '  ' + $f.FullName.Substring($cu.Length + 1)) }
    $extra = Join-Path $cu 'extra_model_paths.yaml'; if (Test-Path $extra) { Dump-File $extra 'extra_model_paths.yaml' }
}

# ---------- llama.cpp ----------
Section 'LLAMA.CPP'
$srv = @('C:\llama\llama-server.exe') + @(Get-Command llama-server.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
foreach ($s in $srv) { W ('llama-server: ' + $s); W (Run $s @('--version')); W 'Folder:'; Get-ChildItem (Split-Path $s -Parent) -File | ForEach-Object { W ('  ' + $_.Length + '  ' + $_.Name) } }
foreach ($c in @("$env:LOCALAPPDATA\llama.cpp", "$env:USERPROFILE\.cache\llama.cpp", "$env:USERPROFILE\.cache\huggingface\hub")) {
    if (Test-Path $c) { W ('Model cache ' + $c + ':'); Get-ChildItem $c -File -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 50MB } | ForEach-Object { Write-Host ('  hashing ' + $_.Name); W ('  ' + (Hash $_.FullName) + '  ' + $_.Length + '  ' + $_.FullName) } }
}
W ('LLAMA_CACHE env: ' + $env:LLAMA_CACHE)

# ---------- other apps / system ----------
Section 'OTHER APPS AND SYSTEM'
$bambu = 'C:\Program Files\Bambu Studio\bambu-studio.exe'; if (Test-Path $bambu) { W ('Bambu Studio: ' + (Get-Item $bambu).VersionInfo.ProductVersion) }
foreach ($a in @("$env:LOCALAPPDATA\Programs\AnythingLLM", "$env:LOCALAPPDATA\Programs\anythingllm-desktop", "$env:APPDATA\anythingllm-desktop\storage\plugins\agent-skills")) { if (Test-Path $a) { W ('AnythingLLM path: ' + $a); Get-ChildItem $a -Depth 1 -ErrorAction SilentlyContinue | ForEach-Object { W ('  ' + $_.Name) } } }
W ('winget: ' + (Run 'winget' @('--version'))); W ('git: ' + (Run 'git' @('--version'))); W ('7z: ' + (Run 'where.exe' @('7z')))
W ('tar: ' + (Run 'tar' @('--version')))
W ('Windows: ' + [Environment]::OSVersion.VersionString + ' / ' + (Get-CimInstance Win32_OperatingSystem).Caption + ' ' + (Get-CimInstance Win32_OperatingSystem).Version)
W ('nvidia-smi: ' + (Run 'nvidia-smi' @('--query-gpu=name,driver_version,memory.total', '--format=csv,noheader')))
W ('PowerShell: ' + $PSVersionTable.PSVersion)
Get-PSDrive -PSProvider FileSystem | ForEach-Object { W ('Drive ' + $_.Name + ': free GB ' + [Math]::Round($_.Free / 1GB, 1)) }

$text = $Out.ToString()
$desk = [Environment]::GetFolderPath('Desktop'); if (-not $desk -or -not (Test-Path $desk)) { $desk = $env:TEMP }; if (-not $desk) { $desk = '.' }
$file = Join-Path $desk ('AIStudio-Installer-Info-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')
[IO.File]::WriteAllText($file, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ''; Write-Host ('Saved: ' + $file + '  (' + [Math]::Round($text.Length / 1KB) + ' KB)') -ForegroundColor Green
try {
    Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
    $f = New-Object System.Windows.Forms.Form; $f.Text = 'AI Modeling Studio - installer information (read-only)'; $f.Width = 1000; $f.Height = 650; $f.StartPosition = 'CenterScreen'
    $tb = New-Object System.Windows.Forms.TextBox; $tb.Multiline = $true; $tb.ReadOnly = $true; $tb.ScrollBars = 'Both'; $tb.WordWrap = $false; $tb.MaxLength = 0
    $tb.Dock = 'Fill'; $tb.Font = New-Object System.Drawing.Font('Consolas', 9); $tb.Text = $text
    $b = New-Object System.Windows.Forms.Button; $b.Text = ('Copy all (' + [Math]::Round($text.Length / 1KB) + ' KB) - if the chat rejects it, attach the .txt from your Desktop instead'); $b.Dock = 'Bottom'; $b.Height = 40
    $b.Add_Click({ [System.Windows.Forms.Clipboard]::SetText($tb.Text); $b.Text = 'Copied - paste it into the chat' })
    $f.Controls.Add($tb); $f.Controls.Add($b); [void]$f.ShowDialog()
} catch { Write-Host ('Could not open the window: ' + $_.Exception.Message) }
