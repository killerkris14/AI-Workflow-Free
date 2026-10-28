@echo off
cd /d "%~dp0"
py -3 start_ai_studio.py
if errorlevel 1 pause
