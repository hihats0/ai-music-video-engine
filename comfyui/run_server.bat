@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"
set "COMFY_ROOT=%CD%"
set "PROJECT_ROOT=%COMFY_ROOT%\.."
set "PY=%COMFY_ROOT%\python_embeded\python.exe"
set "MAIN=%COMFY_ROOT%\ComfyUI\main.py"
set "COMFY_PACKAGE=%COMFY_ROOT%\ComfyUI\comfy"
set "LOGDIR=%PROJECT_ROOT%\logs\comfyui"
set "LOGFILE=%LOGDIR%\server.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

if not exist "%PY%" (
  echo [HATA] Embedded Python bulunamadi: %PY%
  exit /b 1
)

if not exist "%MAIN%" (
  echo [HATA] ComfyUI main.py bulunamadi: %MAIN%
  echo [BILGI] 2. ASAMA v0.2.2 paketini yeniden uygula.
  exit /b 1
)

if not exist "%COMFY_PACKAGE%" (
  echo [HATA] ComfyUI comfy paketi bulunamadi: %COMFY_PACKAGE%
  echo [BILGI] comfyui\ComfyUI baglantisi runtime klasorune gitmelidir.
  exit /b 1
)

echo ===== ComfyUI start %DATE% %TIME% =====>>"%LOGFILE%"
pushd "%COMFY_ROOT%"
"%PY%" -u -s ".\ComfyUI\main.py" --disable-auto-launch --listen 127.0.0.1 --port 8188 --windows-standalone-build >>"%LOGFILE%" 2>&1
set "ERR=%ERRORLEVEL%"
popd
exit /b %ERR%
