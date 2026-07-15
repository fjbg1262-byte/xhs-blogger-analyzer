@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo XHS Blogger Analyzer - local starter
echo ============================================
echo Keep the two opened windows running while using the tool.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Please run install_windows.bat after installing Python.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Please run install_windows.bat after installing Node.js.
  pause
  exit /b 1
)

start "XHS Analyzer Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"
start "XHS Analyzer Frontend" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 127.0.0.1"

echo Waiting for the local tool to start...
timeout /t 5 /nobreak >nul
start http://127.0.0.1:5173

echo.
echo If the page does not open, visit:
echo http://127.0.0.1:5173
echo.
pause
