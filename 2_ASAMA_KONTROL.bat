@echo off
setlocal
chcp 65001 >nul
title 2. ASAMA - ComfyUI Kontrol v0.2.2
cd /d "%~dp0"

echo ============================================================
echo 2. ASAMA - COMFYUI KONTROL v0.2.2
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [HATA] 1. ASAMA Python ortami bulunamadi.
  pause
  exit /b 1
)

echo [ADIM] Dosya yapisi kontrol ediliyor
".venv\Scripts\python.exe" "tests\test_stage2.py"
if %ERRORLEVEL% neq 0 (
  echo [HATA] 2. ASAMA dosya testi basarisiz.
  pause
  exit /b 1
)

echo.
echo [ADIM] ComfyUI baslatiliyor
call "comfyui\start_headless.bat"
if %ERRORLEVEL% neq 0 (
  echo [HATA] ComfyUI baslatma komutu basarisiz.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" "comfyui\wait_for_server.py" --timeout 600
if %ERRORLEVEL% neq 0 (
  echo [HATA] ComfyUI API yanit vermedi.
  echo [BILGI] logs\comfyui\server.log dosyasini kontrol et.
  pause
  exit /b 1
)

echo.
echo [ADIM] API saglik kontrolu
".venv\Scripts\python.exe" "comfyui\healthcheck.py"
if %ERRORLEVEL% neq 0 (
  echo [HATA] ComfyUI saglik kontrolu basarisiz.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo [OK] 2. ASAMA v0.2.2 TAMAMEN HAZIR
echo [OK] ComfyUI: http://127.0.0.1:8188
echo ============================================================
echo.
pause
exit /b 0
