; AI Modeling Studio 0.018 - Windows installer (Smart / Full)
; Build from the repo: installer\Build-Installer.bat (needs NSIS 3.x). Output goes to dist\.
Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 8
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

Name "AI Modeling Studio 0.018"
!ifndef OUTDIR
  !define OUTDIR "..\dist"
!endif
OutFile "${OUTDIR}\AI-Modeling-Studio-0.018-Setup.exe"
InstallDir "C:\AI-Workflow-Auto"
RequestExecutionLevel user
BrandingText "AI Modeling Studio 0.018 (setup build 2026-10-30-1)"
VIProductVersion "0.18.0.0"
VIAddVersionKey "ProductName" "AI Modeling Studio"
VIAddVersionKey "FileVersion" "0.018"
VIAddVersionKey "FileDescription" "AI Modeling Studio installer (Smart / Full)"
VIAddVersionKey "LegalCopyright" "kris"

!define MUI_ICON "..\studio\ai_studio.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "AI Modeling Studio 0.018 setup"
!define MUI_WELCOMEPAGE_TEXT "This installs AI Modeling Studio 0.018 and everything it needs:$\r$\n$\r$\n  - Python 3.15.1, Blender 5.2.2 + 3MF add-on$\r$\n  - ComfyUI portable 0.42.1 + portal node$\r$\n  - Hunyuan3D-2 (MV + single) and BiRefNet models$\r$\n  - AI paint runtime (Hunyuan3D-2 paint, ~19 GB) + ffmpeg video reader$\r$\n  - optional: llama.cpp + Qwen models, Bambu Studio, AnythingLLM skill$\r$\n$\r$\nSmart install checks each one and installs only what is missing or wrong. Full install re-installs every requirement.$\r$\n$\r$\nYour jobs, source images, model files and settings are never deleted. Power the studio off before continuing."
!define MUI_DIRECTORYPAGE_TEXT_TOP "Studio program folder. An existing installation here is updated in place (your settings and jobs are kept)."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom OptionsPage OptionsLeave
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TITLE "Setup finished"
!define MUI_FINISHPAGE_TEXT "The installer report (with a Copy all button) was shown at the end and saved in the studio logs folder.$\r$\n$\r$\nStart the studio with the AI Modeling Studio desktop icon. The header should read Version 0.018."
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Var RSmart
Var RFull
Var CCheck
Var RVerify
Var RRedl
Var CLlama
Var CBambu
Var CAnything
Var Mode
Var Models
Var Comps
Var DryArg

Function OptionsPage
  !insertmacro MUI_HEADER_TEXT "Install type" "Choose how setup handles the requirements."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateGroupBox} 0 0 100% 62u "Install type"
  Pop $0
  ${NSD_CreateRadioButton} 8u 11u 95% 12u "Smart install (recommended): check everything, install only what is missing or wrong"
  Pop $RSmart
  ${NSD_AddStyle} $RSmart ${WS_GROUP}
  ${NSD_Check} $RSmart
  ${NSD_CreateRadioButton} 8u 25u 95% 12u "Full install: force re-install of every requirement (jobs, models, settings kept)"
  Pop $RFull
  ${NSD_CreateCheckbox} 8u 41u 95% 12u "Check only - show what would be installed, change nothing"
  Pop $CCheck
  ${NSD_CreateGroupBox} 0 66u 100% 40u "Model files (Hunyuan3D, BiRefNet, Qwen - about 23 GB)"
  Pop $0
  ${NSD_CreateRadioButton} 8u 77u 95% 12u "Verify each file's SHA-256, download again only if missing or damaged (recommended)"
  Pop $RVerify
  ${NSD_AddStyle} $RVerify ${WS_GROUP}
  ${NSD_Check} $RVerify
  ${NSD_CreateRadioButton} 8u 90u 95% 12u "Always download again (slow; old copy replaced only after the new one verifies)"
  Pop $RRedl
  ${NSD_CreateGroupBox} 0 110u 100% 30u "Optional components"
  Pop $0
  ${NSD_CreateCheckbox} 8u 122u 38% 12u "llama.cpp + Qwen models"
  Pop $CLlama
  ${NSD_Check} $CLlama
  ${NSD_CreateCheckbox} 45% 122u 25% 12u "Bambu Studio"
  Pop $CBambu
  ${NSD_Check} $CBambu
  ${NSD_CreateCheckbox} 71% 122u 28% 12u "AnythingLLM skill"
  Pop $CAnything
  ${NSD_Check} $CAnything
  nsDialogs::Show
FunctionEnd

Function OptionsLeave
  ${NSD_GetState} $RFull $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Mode "Full"
  ${Else}
    StrCpy $Mode "Smart"
  ${EndIf}
  ${NSD_GetState} $RRedl $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Models "Redownload"
  ${Else}
    StrCpy $Models "Verify"
  ${EndIf}
  ${NSD_GetState} $CCheck $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $DryArg "-DryRun"
  ${Else}
    StrCpy $DryArg ""
  ${EndIf}
  StrCpy $Comps ""
  ${NSD_GetState} $CLlama $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Comps "$Comps,llama"
  ${EndIf}
  ${NSD_GetState} $CBambu $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Comps "$Comps,bambu"
  ${EndIf}
  ${NSD_GetState} $CAnything $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $Comps "$Comps,anythingllm"
  ${EndIf}
FunctionEnd

Section "Install"
  ; Payload is assembled from the repo layout (same structure the engine expects).
  SetOutPath "$PLUGINSDIR\payload\studio"
  File /r /x __pycache__ /x *.pyc /x *.bak /x test_color_coverage_011.py "..\studio\*.*"
  SetOutPath "$PLUGINSDIR\payload\custom_nodes"
  File /r /x __pycache__ /x *.pyc "..\comfyui\custom_nodes\*.*"
  SetOutPath "$PLUGINSDIR\payload\defaults"
  File /r "defaults\*.*"
  SetOutPath "$PLUGINSDIR\payload"
  File "engine.ps1"
  File "payload_manifest.json"
  SetOutPath "$PLUGINSDIR\payload\texture_paint"
  File "texture_paint\*.*"
  SetOutPath "$PLUGINSDIR\payload\test_assets"
  File "test_assets\*.*"
  DetailPrint "Mode: $Mode   Models: $Models   Components:$Comps $DryArg"
  DetailPrint "The setup engine runs in its own window and shows a report with a Copy all button when it finishes."
  ; 64-bit PowerShell: this setup .exe is 32-bit, so $SYSDIR would be redirected to SysWOW64 (32-bit PowerShell).
  StrCpy $1 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  IfFileExists "$1" +2 0
    StrCpy $1 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  DetailPrint "PowerShell: $1"
  ExecWait '"$1" -NoProfile -ExecutionPolicy Bypass -STA -File "$PLUGINSDIR\payload\engine.ps1" -Mode $Mode -Models $Models -InstallDir "$INSTDIR" -Components "$Comps" -Payload "$PLUGINSDIR\payload" $DryArg' $0
  ${If} $0 == 0
    DetailPrint "Setup engine finished: everything OK."
  ${Else}
    DetailPrint "Setup engine finished with items that need attention (exit $0). See the report in $INSTDIR\logs."
  ${EndIf}
SectionEnd
