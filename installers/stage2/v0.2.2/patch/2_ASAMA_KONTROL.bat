@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

".venv\Scripts\python.exe" "tests\test_stage2.py"
if %ERRORLEVEL% neq 0 exit /b 1

call "comfyui\start_headless.bat"
if %ERRORLEVEL% neq 0 exit /b 1

".venv\Scripts\python.exe" "comfyui\wait_for_server.py" --timeout 600
if %ERRORLEVEL% neq 0 exit /b 1

".venv\Scripts\python.exe" "comfyui\healthcheck.py"
if %ERRORLEVEL% neq 0 exit /b 1

echo [OK] 2. ASAMA v0.2.2 TAMAMEN HAZIR
pause
