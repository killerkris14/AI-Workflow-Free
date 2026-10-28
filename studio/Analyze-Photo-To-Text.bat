@echo off
cd /d "%~dp0"
py -3 photo_to_text.py
if errorlevel 1 pause
