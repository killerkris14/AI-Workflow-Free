@echo off
rem AI_STUDIO_OPTIONAL_WORKER_V1
"__PYTHON__" -u "%~dp0optional_worker_router.py"
exit /b %errorlevel%
