@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call comfyui\stop_server.bat
pause
exit /b %ERRORLEVEL%
