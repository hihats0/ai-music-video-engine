@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title AI Music Video Engine - Update and Install

echo ============================================================
echo AI MUSIC VIDEO ENGINE - GIT PULL + TUM ASAMALAR
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_and_install.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
  echo [OK] Motor guncel ve uretime hazir.
) else (
  echo [HATA] Islem tamamlanamadi.
  echo [BILGI] Ekrandaki HATA KODU, TANI PAKETI ve BOOTSTRAP LOG yollarini sakla.
)
echo.
pause
exit /b %EXITCODE%
