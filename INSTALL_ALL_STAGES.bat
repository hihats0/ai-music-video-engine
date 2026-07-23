@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title AI Music Video Engine - Install All Stages

echo ============================================================
echo AI MUSIC VIDEO ENGINE - TUM ASAMALARI KUR

echo Bu islem resmi Wan 2.2 5B model dosyalarini indirir.
echo Indirme kesilirse ayni dosyayi yeniden calistir; kaldigi yerden devam eder.
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [HATA] .venv Python ortami bulunamadi.
  echo [BILGI] UPDATE_AND_INSTALL.bat dosyasini calistir.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if %ERRORLEVEL% neq 0 goto :failure

call clipctl.bat goal install
if %ERRORLEVEL% neq 0 goto :failure

call clipctl.bat goal status
if %ERRORLEVEL% neq 0 goto :failure

echo.
echo [OK] TUM ASAMALAR KURULDU.
pause
exit /b 0

:failure
echo.
echo [HATA] Kurulum tamamlanamadi.
call clipctl.bat diagnose collect
echo [BILGI] Yukaridaki hata kodu ve tani ZIP yolunu sakla.
pause
exit /b 1
