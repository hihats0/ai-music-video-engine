@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo AI Music Video Engine baslatiliyor...
call clipctl.bat system check
if %ERRORLEVEL% neq 0 (
  echo [UYARI] Sistem kontrolunde eksikler var. ComfyUI yine de deneniyor.
)

call comfyui\start_headless.bat
if %ERRORLEVEL% neq 0 (
  echo [HATA] ComfyUI baslatilamadi.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "comfyui\wait_for_server.py" --timeout 600
if %ERRORLEVEL% neq 0 (
  echo [HATA] API yanit vermedi. logs\comfyui\server.log dosyasini kontrol et.
  pause
  exit /b 1
)

echo.
echo [OK] Motor hazir. API: http://127.0.0.1:8188
echo Arayuzu gerektiginde comfyui\start_interface.bat ile acabilirsin.
pause
exit /b 0
