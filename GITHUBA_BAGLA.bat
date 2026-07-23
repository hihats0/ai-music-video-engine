@echo off
setlocal
chcp 65001 >nul
title AI Music Video Engine - GitHub Baglantisi
echo ============================================================
echo AI MUSIC VIDEO ENGINE - GITHUB BAGLANTISI
echo ============================================================
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\connect_existing_install.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if "%EXITCODE%"=="0" (
  echo [OK] GitHub baglantisi tamamlandi.
) else (
  echo [HATA] GitHub baglantisi tamamlanamadi.
)
echo.
pause
exit /b %EXITCODE%
