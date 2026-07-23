@echo off
setlocal
chcp 65001 >nul
title 2. ASAMA v0.2.2 - Kalici ComfyUI Duzeltmesi
echo ============================================================
echo 2. ASAMA v0.2.2 - KALICI COMFYUI DUZELTMESI
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\apply_stage2_2.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (
  echo [OK] v0.2.2 uygulama komutu tamamlandi.
) else (
  echo [HATA] v0.2.2 uygulanamadi. Yukaridaki mesaji oku.
)
echo.
pause
exit /b %EXITCODE%
