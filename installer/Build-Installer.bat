@echo off
setlocal
rem Builds dist\AI-Modeling-Studio-0.010-Setup.exe from this repo (needs NSIS 3.x: https://nsis.sourceforge.io).
cd /d "%~dp0"
set "MAKENSIS="
for %%M in (makensis.exe) do if not "%%~$PATH:M"=="" set "MAKENSIS=%%~$PATH:M"
if not defined MAKENSIS if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
if not defined MAKENSIS if exist "%ProgramFiles%\NSIS\makensis.exe" set "MAKENSIS=%ProgramFiles%\NSIS\makensis.exe"
if not defined MAKENSIS (
  echo NSIS makensis.exe was not found. Install NSIS 3.x, then run this again.
  pause & exit /b 1
)
if not exist "..\dist" mkdir "..\dist"
"%MAKENSIS%" -V2 setup.nsi
if errorlevel 1 ( echo BUILD FAILED. & pause & exit /b 1 )
echo.
echo Built: %~dp0..\dist\AI-Modeling-Studio-0.010-Setup.exe
powershell -NoProfile -Command "(Get-FileHash '..\dist\AI-Modeling-Studio-0.010-Setup.exe' -Algorithm SHA256).Hash"
pause
