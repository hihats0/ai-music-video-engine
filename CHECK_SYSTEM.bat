@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call clipctl.bat system doctor
echo.
call clipctl.bat comfy status
pause
