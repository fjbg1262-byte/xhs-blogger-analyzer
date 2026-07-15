@echo off
setlocal
cd /d "%~dp0"

echo.
echo Starting XHS Blogger Analyzer...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_local.ps1"
if errorlevel 1 pause
exit /b %errorlevel%
