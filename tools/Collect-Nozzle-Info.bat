@echo off
rem AI Modeling Studio - collect info for the 0.4 / 0.6 mm nozzle option (read-only, changes nothing)
set "AISTUDIO_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "$s=[IO.File]::ReadAllText($env:AISTUDIO_SELF); $i=$s.LastIndexOf('#'+'POWERSHELL_BELOW#'); Invoke-Expression $s.Substring($i+18)"
exit /b
#POWERSHELL_BELOW#
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$L = New-Object System.Collections.Generic.List[string]
function A($t) { $L.Add([string]$t) }
function Sha($p) { try { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } catch { 'ERR ' + $_.Exception.Message } }
A ('NOZZLE OPTION INFO - collected ' + (Get-Date -Format s) + ' on ' + $env:COMPUTERNAME)
A '(read-only: nothing is changed)'
A ''
$studio = 'C:\AI-Workflow-Auto'
A '=== 1. INSTALLED STUDIO ==='
$vf = Join-Path $studio 'color_update_version.json'
if (Test-Path $vf) { A ((Get-Content -LiteralPath $vf -Raw).Trim()) } else { A ('NOT FOUND: ' + $vf) }
$ui = Join-Path $studio 'hunyuan_portal_ui.js'
if (Test-Path $ui) { A ('hunyuan_portal_ui.js sha256 ' + (Sha $ui)) }
$tplNames = @()
foreach ($t in Get-ChildItem -LiteralPath $studio -Filter 'bambu_template*.3mf' -ErrorAction SilentlyContinue) {
    A ('-- ' + $t.Name + '  ' + $t.Length + ' bytes  sha256 ' + (Sha $t.FullName) + '  modified ' + $t.LastWriteTime.ToString('s'))
    try {
        $z = [System.IO.Compression.ZipFile]::OpenRead($t.FullName)
        $e = $z.GetEntry('Metadata/project_settings.config')
        $r = New-Object System.IO.StreamReader($e.Open()); $j = $r.ReadToEnd() | ConvertFrom-Json; $r.Close(); $z.Dispose()
        foreach ($k in 'printer_settings_id', 'printer_model', 'printer_variant', 'nozzle_diameter', 'nozzle_type', 'extruder_variant_list', 'print_settings_id', 'layer_height', 'line_width', 'filament_settings_id', 'filament_colour') {
            A ('   ' + $k + ' = ' + (($j.$k | ForEach-Object { $_ }) -join ' | '))
        }
        $tplNames += @($j.filament_settings_id)
    } catch { A ('   could not read: ' + $_.Exception.Message) }
}
A ''
A '=== 2. BAMBU STUDIO ==='
$keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
foreach ($p in Get-ItemProperty $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*Bambu*' }) { A ($p.DisplayName + '  version ' + $p.DisplayVersion + '  ' + $p.InstallLocation) }
$bs = Join-Path $env:APPDATA 'BambuStudio'
A ('Bambu data folder: ' + $bs + '  exists: ' + (Test-Path $bs))
$sys = Join-Path $bs 'system\BBL'
$bblJson = Join-Path $bs 'system\BBL.json'
if (Test-Path $bblJson) { try { A ('system profile version: ' + ((Get-Content -LiteralPath $bblJson -Raw | ConvertFrom-Json).version)) } catch {} }
$appCfg = Join-Path $bs 'BambuStudio.conf'
if (Test-Path $appCfg) {
    A '-- BambuStudio.conf lines about presets / printers:'
    foreach ($ln in Get-Content -LiteralPath $appCfg) { if ($ln -match 'preset|printer|nozzle|machine|"filaments"|"print"|"version"') { A ('   ' + $ln.Trim()) } }
}
A ''
function DumpChain($folder, $name, $depth) {
    if ($depth -gt 6 -or -not $name) { return }
    $f = Join-Path $folder ($name + '.json')
    if (-not (Test-Path -LiteralPath $f)) { A ('   (not found: ' + $f + ')'); return }
    A ('----- FILE ' + $f + '  sha256 ' + (Sha $f))
    $raw = Get-Content -LiteralPath $f -Raw; A $raw
    try { $inh = ($raw | ConvertFrom-Json).inherits; if ($inh) { DumpChain $folder $inh ($depth + 1) } } catch {}
}
A '=== 3. H2C PRINTER (MACHINE) PROFILES ==='
$mf = Join-Path $sys 'machine'
if (Test-Path $mf) {
    A '-- all H2C machine profile names:'
    foreach ($f in Get-ChildItem -LiteralPath $mf -Filter '*H2C*.json' | Sort-Object Name) { A ('   ' + $f.BaseName) }
    foreach ($n in 'Bambu Lab H2C 0.4 nozzle', 'Bambu Lab H2C 0.6 nozzle') { A ''; A ('== chain for ' + $n); DumpChain $mf $n 0 }
} else { A ('NOT FOUND: ' + $mf) }
A ''
A '=== 4. H2C PROCESS PROFILES ==='
$pf = Join-Path $sys 'process'
if (Test-Path $pf) {
    A '-- all H2C process profile names:'
    foreach ($f in Get-ChildItem -LiteralPath $pf -Filter '*H2C*.json' | Sort-Object Name) { A ('   ' + $f.BaseName) }
    foreach ($n in '0.20mm Standard @BBL H2C', '0.24mm Balanced Strength @BBL H2C 0.6 nozzle', '0.30mm Standard @BBL H2C 0.6 nozzle') { A ''; A ('== chain for ' + $n); DumpChain $pf $n 0 }
} else { A ('NOT FOUND: ' + $pf) }
A ''
A '=== 5. H2C FILAMENT PROFILES ==='
$ff = Join-Path $sys 'filament'
if (Test-Path $ff) {
    A '-- all H2C filament profile names:'
    foreach ($f in Get-ChildItem -LiteralPath $ff -Filter '*H2C*.json' | Sort-Object Name) { A ('   ' + $f.BaseName) }
    $done = @{}
    foreach ($n in ($tplNames | Sort-Object -Unique)) {
        foreach ($m in @($n, ($n -replace ' 0\.6 nozzle$', ''), ($n + ' 0.6 nozzle'))) {
            if ($done[$m]) { continue }; $done[$m] = 1
            $f = Join-Path $ff ($m + '.json')
            if (Test-Path -LiteralPath $f) { A ''; A ('----- FILE ' + $f); A (Get-Content -LiteralPath $f -Raw) }
        }
    }
} else { A ('NOT FOUND: ' + $ff) }
A ''
A '=== 6. YOUR OWN SAVED PRESETS (names; H2C ones in full) ==='
$uf = Join-Path $bs 'user'
if (Test-Path $uf) {
    foreach ($f in Get-ChildItem -LiteralPath $uf -Recurse -Filter '*.json' -ErrorAction SilentlyContinue) {
        A ('   ' + $f.FullName.Substring($uf.Length))
        if ($f.Name -like '*H2C*' -and $f.Length -lt 200000) { A (Get-Content -LiteralPath $f.FullName -Raw) }
    }
} else { A ('no user preset folder: ' + $uf) }
A ''
A '=== END ==='
$text = $L -join "`r`n"
$name = 'Nozzle-Info-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt'
$dirs = @([Environment]::GetFolderPath('Desktop'), $env:TEMP, (Split-Path -Parent $env:AISTUDIO_SELF)) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$out = $null
foreach ($d in $dirs) { try { $p = Join-Path $d $name; [System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($false))); $out = $p; break } catch {} }
if (-not $out) { $out = '(could not save a .txt - use Copy all)' }
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$f = New-Object System.Windows.Forms.Form; $f.Text = 'Nozzle option info (saved to ' + $out + ')'; $f.Width = 1100; $f.Height = 760; $f.StartPosition = 'CenterScreen'
$b = New-Object System.Windows.Forms.Button; $b.Text = 'Copy all'; $b.Dock = 'Top'; $b.Height = 40
$tb = New-Object System.Windows.Forms.TextBox; $tb.Multiline = $true; $tb.ScrollBars = 'Both'; $tb.WordWrap = $false; $tb.ReadOnly = $true; $tb.Dock = 'Fill'; $tb.Font = New-Object System.Drawing.Font('Consolas', 9); $tb.Text = $text
$b.Add_Click({ [System.Windows.Forms.Clipboard]::SetText($tb.Text); $b.Text = 'Copied - paste it into the chat (or attach the .txt from your Desktop)' })
$f.Controls.Add($tb); $f.Controls.Add($b); [void]$f.ShowDialog()
