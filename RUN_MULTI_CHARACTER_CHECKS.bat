@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title AI Music Video Engine - Multi Character Checks

echo ============================================================
echo MULTI-CHARACTER v1.1 ALPHA - READINESS CHECKS
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [HATA] .venv bulunamadi. Once UPDATE_AND_INSTALL.bat calistir.
  pause
  exit /b 1
)

echo [ADIM 1/4] Python kaynaklari derleniyor
".venv\Scripts\python.exe" -m compileall -q clipctl tests
if errorlevel 1 goto :failed

echo [ADIM 2/4] Unit testler calistiriliyor
".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 goto :failed

echo [ADIM 3/4] Zorunlu motor ve ComfyUI durumu kontrol ediliyor
call ".\clipctl.bat" goal status
if errorlevel 1 goto :failed

echo [ADIM 4/4] Opsiyonel solo lipsync durumu raporlaniyor
call ".\clipctl.bat" lipsync status
if errorlevel 1 (
  echo [BILGI] MuseTalk opsiyoneldir; group pipeline testi devam edebilir.
)

echo.
echo [OK] MULTI-CHARACTER STATIK VE MOTOR KONTROLLERI GECTI.
echo [SONRAKI] docs\LOCAL_GPU_ACCEPTANCE.md dosyasindaki duo testine gec.
echo.
pause
exit /b 0

:failed
echo.
echo [HATA] Multi-character readiness kontrolu gecmedi.
echo [BILGI] Ekrandaki HATA KODU ve TANI PAKETI yolunu sakla.
echo.
pause
exit /b 1
