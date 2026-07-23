@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist "comfyui\python_embeded\python.exe" (
  echo [HATA] ComfyUI embedded Python bulunamadi.
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\comfyui\ensure_portable_layout.ps1"
if %ERRORLEVEL% neq 0 (
  echo [HATA] ComfyUI portable klasor baglantisi otomatik onarilamadi.
  exit /b 1
)

if not exist "comfyui\ComfyUI\main.py" (
  echo [HATA] ComfyUI portable klasor baglantisi bulunamadi.
  exit /b 1
)

".venv\Scripts\python.exe" "comfyui\healthcheck.py" --quiet >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [OK] ComfyUI zaten calisiyor: http://127.0.0.1:8188
  exit /b 0
)

start "ComfyUI Headless" /MIN cmd.exe /c call "%CD%\comfyui\run_server.bat"
echo [BILGI] ComfyUI baslatma komutu gonderildi.
exit /b 0
