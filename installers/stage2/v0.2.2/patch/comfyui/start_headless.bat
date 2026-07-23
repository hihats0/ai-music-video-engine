@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist "comfyui\python_embeded\python.exe" exit /b 1
if not exist "comfyui\ComfyUI\main.py" exit /b 1

".venv\Scripts\python.exe" "comfyui\healthcheck.py" --quiet >nul 2>&1
if %ERRORLEVEL%==0 exit /b 0

start "ComfyUI Headless" /MIN cmd.exe /c call "%CD%\comfyui\run_server.bat"
exit /b 0
