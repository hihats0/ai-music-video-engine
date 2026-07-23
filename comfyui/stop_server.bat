@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo [HATA] 1. Asama Python ortami bulunamadi.
  exit /b 1
)
".venv\Scripts\python.exe" "comfyui\stop_server.py"
exit /b %ERRORLEVEL%
