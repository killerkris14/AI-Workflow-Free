@echo off
rem AI Modeling Studio - collect Bambu profiles for the 0.4 mm nozzle option (read-only, changes nothing)
set "AISTUDIO_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "$s=[IO.File]::ReadAllText($env:AISTUDIO_SELF); $i=$s.LastIndexOf('#'+'POWERSHELL_BELOW#'); Invoke-Expression $s.Substring($i+18)"
exit /b
#POWERSHELL_BELOW#
$ErrorActionPreference = 'Continue'
$L = New-Object System.Collections.Generic.List[string]
function A($t) { $L.Add([string]$t) }
A ('NOZZLE PROFILES 2 - collected ' + (Get-Date -Format s) + ' on ' + $env:COMPUTERNAME + '  (read-only: nothing is changed)')
$sys = Join-Path $env:APPDATA 'BambuStudio\system\BBL'
$Script:Seen = @{}
function Mini($raw) { ($raw -replace '\r?\n\s*', '').Trim() }   # JSON strings cannot hold raw line breaks, so this keeps the content exact
function Chain($kind, $name, $depth) {
    if ($depth -gt 8 -or -not $name) { return }
    $key = $kind + '/' + $name; if ($Script:Seen[$key]) { return }; $Script:Seen[$key] = 1
    $f = Join-Path (Join-Path $sys $kind) ($name + '.json')
    if (-not (Test-Path -LiteralPath $f)) { A ('### ' + $key + ' NOT FOUND'); return }
    $raw = Get-Content -LiteralPath $f -Raw
    A ('### ' + $key + ' sha256 ' + (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLower())
    A (Mini $raw)
    try { $j = $raw | ConvertFrom-Json } catch { return }
    if ($j.inherits) { Chain $kind $j.inherits ($depth + 1) }
    if ($kind -ne 'machine') { foreach ($i in @($j.include)) { if ($i) { Chain $kind $i ($depth + 1) } } }
}
foreach ($n in '0.20mm High Quality @BBL H2C', '0.24mm Balanced Strength @BBL H2C 0.6 nozzle') { Chain 'process' $n 0 }
foreach ($n in 'Generic PLA @BBL H2C 0.4 nozzle', 'Generic PLA @BBL H2C') { Chain 'filament' $n 0 }
foreach ($n in 'Bambu Lab H2C 0.4 nozzle', 'Bambu Lab H2C 0.6 nozzle') { Chain 'machine' $n 0 }
$mi = Join-Path $sys 'machine'
foreach ($f in Get-ChildItem -LiteralPath $mi -Filter 'Bambu Lab H2C 0.4 nozzle template*.json' -ErrorAction SilentlyContinue) { A ('### machine/' + $f.BaseName + ' sha256 ' + (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()) }
$bbl = Join-Path $env:APPDATA 'BambuStudio\system\BBL.json'
if (Test-Path $bbl) { $b = Get-Content -LiteralPath $bbl -Raw | ConvertFrom-Json; A ('### BBL.json version ' + $b.version) }
A '### END'
$text = $L -join "`r`n"
$name = 'Nozzle-Profiles-2-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt'
$dirs = @([Environment]::GetFolderPath('Desktop'), $env:TEMP, (Split-Path -Parent $env:AISTUDIO_SELF)) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$out = $null
foreach ($d in $dirs) { try { $p = Join-Path $d $name; [System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding($false))); $out = $p; break } catch {} }
if (-not $out) { $out = '(could not save a .txt - use Copy all)' }
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$f = New-Object System.Windows.Forms.Form; $f.Text = 'Nozzle profiles 2 (' + $text.Length + ' characters, saved to ' + $out + ')'; $f.Width = 1100; $f.Height = 760; $f.StartPosition = 'CenterScreen'
$bt = New-Object System.Windows.Forms.Button; $bt.Text = 'Copy all'; $bt.Dock = 'Top'; $bt.Height = 40
$tb = New-Object System.Windows.Forms.TextBox; $tb.Multiline = $true; $tb.MaxLength = 0; $tb.ScrollBars = 'Both'; $tb.WordWrap = $false; $tb.ReadOnly = $true; $tb.Dock = 'Fill'; $tb.Font = New-Object System.Drawing.Font('Consolas', 9); $tb.Text = $text
$bt.Add_Click({ [System.Windows.Forms.Clipboard]::SetText($tb.Text); $bt.Text = 'Copied - paste it into the chat (or attach the .txt from your Desktop)' })
$f.Controls.Add($tb); $f.Controls.Add($bt); [void]$f.ShowDialog()
