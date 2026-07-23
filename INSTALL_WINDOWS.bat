@echo off
setlocal
cd /d "%~dp0"

echo =====================================================
echo AI Music Video Engine - Cekirdek Kurulum
echo.
echo Bu surum ComfyUI veya model kurmaz.
echo Sadece terminal motorunu ve klasor sistemini hazirlar.
echo =====================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [HATA] Python bulunamadi.
        echo Python 3.11 veya 3.12 kurup tekrar deneyin.
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Sanal Python ortami olusturuluyor...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 goto :error
) else (
    echo [1/4] Sanal Python ortami zaten var.
)

echo [2/4] pip guncelleniyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if %errorlevel% neq 0 goto :error

echo [3/4] Gerekli kucuk paketler kuruluyor...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 goto :error

echo [4/4] Cekirdek klasorler hazirlaniyor...
".venv\Scripts\python.exe" -m clipctl system init
if %errorlevel% neq 0 goto :error

echo.
echo [BASARILI] Cekirdek kurulum tamamlandi.
echo Simdi CHECK_SYSTEM.bat dosyasini calistirin.
pause
exit /b 0

:error
echo.
echo [HATA] Kurulum tamamlanamadi.
echo Pencereyi kapatmadan once yukaridaki hata mesajini okuyun.
pause
exit /b 1
