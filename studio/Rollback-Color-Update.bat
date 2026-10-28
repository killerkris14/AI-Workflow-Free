@echo off
setlocal
title AI Modeling Studio - rollback color update
set "AISTUDIO_UPDATER=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "$t=[IO.File]::ReadAllText($env:AISTUDIO_UPDATER); $m='#'+'POWERSHELL_BELOW#'; $i=$t.IndexOf($m); iex $t.Substring($i+$m.Length)"
echo.
pause
exit /b
#POWERSHELL_BELOW#
$env:AISTUDIO_ROLLBACK_VERSION = '0.010'
function Hash($p) { if ($p -and (Test-Path -LiteralPath $p -PathType Leaf)) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() } return $null }
function Find-Root {
    if ($env:AISTUDIO_ROOT) { return (Resolve-Path -LiteralPath $env:AISTUDIO_ROOT).Path }
    $cands = @()
    try {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'))) {
            if (-not $d -or -not (Test-Path -LiteralPath $d)) { continue }
            foreach ($f in (Get-ChildItem -LiteralPath $d -Filter *.lnk -ErrorAction SilentlyContinue)) {
                $s = $shell.CreateShortcut($f.FullName)
                foreach ($m in [regex]::Matches($s.Arguments, '"([^"]+studio_launcher\.pyw)"|(\S+studio_launcher\.pyw)')) {
                    $v = $m.Groups[1].Value; if (-not $v) { $v = $m.Groups[2].Value }; $cands += (Split-Path $v -Parent)
                }
            }
        }
    } catch {}
    $cands = @($cands | Select-Object -Unique | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'hunyuan_color_bridge.py') })
    if ($cands.Count -eq 1) { return $cands[0] }
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = 'Select the INSTALLED AI Modeling Studio folder (contains app.py and studio_launcher.pyw)'
    if ($dlg.ShowDialog() -eq 'OK') { return $dlg.SelectedPath }
    throw 'Installed studio folder not found. Nothing was changed.'
}
function Studio-Running {
    if ($env:AISTUDIO_SKIP_RUNNING_CHECK) { return $false }
    try { $c = New-Object System.Net.Sockets.TcpClient; $iar = $c.BeginConnect('127.0.0.1', 8765, $null, $null); $ok = $iar.AsyncWaitHandle.WaitOne(800) -and $c.Connected; $c.Close(); return $ok } catch { return $false }
}
function Restore-Backup($backup, $root) {
    $bm = Get-Content -LiteralPath (Join-Path $backup 'backup_manifest.json') -Raw | ConvertFrom-Json
    $problems = @()
    foreach ($r in $bm.files) {
        $dest = Join-Path $root $r.name
        Remove-Item -LiteralPath ($dest + '.update-tmp') -Force -ErrorAction SilentlyContinue
        if ($r.existed) {
            Copy-Item -LiteralPath (Join-Path $backup $r.name) -Destination $dest -Force
            if ((Hash $dest) -ne $r.old_sha256) { $problems += ('Restore verification failed: ' + $r.name) }
        } else {
            $cur = Hash $dest
            if ($cur -eq $r.new_sha256) { Remove-Item -LiteralPath $dest -Force }
            elseif ($cur) { $problems += ($r.name + ' was changed after install and was KEPT (remove it manually only if you do not want it).') }
        }
    }
    $verFile = Join-Path $root 'color_update_version.json'; $prev = Join-Path $backup 'color_update_version.json.previous'
    if (Test-Path -LiteralPath $prev) { Copy-Item -LiteralPath $prev -Destination $verFile -Force } else { Remove-Item -LiteralPath $verFile -Force -ErrorAction SilentlyContinue }
    $bm.state = 'rolled_back'; ($bm | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath (Join-Path $backup 'backup_manifest.json') -Encoding UTF8
    return ,$problems
}

function Main {
    $ErrorActionPreference = 'Stop'
    if ($env:AISTUDIO_ROLLBACK_VERSION) { $ver = $env:AISTUDIO_ROLLBACK_VERSION } else { $manifest = Get-Content -LiteralPath (Join-Path (Split-Path -Parent $env:AISTUDIO_UPDATER) 'update_manifest.json') -Raw | ConvertFrom-Json; $ver = $manifest.version }
    Write-Host ('=== AI Modeling Studio color update ' + $ver + ' - ROLLBACK ===') -ForegroundColor Cyan
    $root = Find-Root
    if (Studio-Running) { throw 'The studio is running. Power it off first, then run rollback again. Nothing was changed.' }
    # Newest completed install of any color-update version (folder names end in yyyyMMdd-HHmmss).
    $dirs = @(Get-ChildItem -LiteralPath (Join-Path $root 'backups') -Directory -Filter 'color-update-*' -ErrorAction SilentlyContinue | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'backup_manifest.json') } | Sort-Object { $_.Name.Substring([Math]::Max(0, $_.Name.Length - 15)) } -Descending)
    $pick = $null
    foreach ($d in $dirs) { $bm = Get-Content -LiteralPath (Join-Path $d.FullName 'backup_manifest.json') -Raw | ConvertFrom-Json; if ($bm.state -eq 'complete') { $pick = $d; break } }
    if (-not $pick) { Write-Host 'No completed color update installation backup found. Nothing was changed.' -ForegroundColor Yellow; return }
    Write-Host ('Studio folder: ' + $root); Write-Host ('Restore from: ' + $pick.FullName)
    if (-not $env:AISTUDIO_ASSUME_YES) { if ((Read-Host ('Type YES to undo the color update installed ' + $pick.Name.Substring([Math]::Max(0, $pick.Name.Length - 15)) + ' (' + $pick.Name + ')')) -ne 'YES') { Write-Host 'Cancelled. Nothing was changed.'; return } }
    $left = Restore-Backup $pick.FullName $root
    if ($left.Count) { Write-Host ('Rollback finished with notes: ' + ($left -join '; ')) -ForegroundColor Yellow }
    else { Write-Host 'Rollback complete and verified. Jobs, settings and exports were not touched.' -ForegroundColor Green }
}

try { Main } catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
}
