@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

call "comfyui\start_headless.bat"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

".venv\Scripts\python.exe" "comfyui\wait_for_server.py" --timeout 600
if %ERRORLEVEL% neq 0 exit /b 1

start "" "http://127.0.0.1:8188"
exit /b 0
