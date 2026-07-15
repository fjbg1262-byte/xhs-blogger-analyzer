@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo XHS Blogger Analyzer - first time setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found.
  echo Please install Python 3.9 or newer first: https://www.python.org/downloads/
  echo Remember to tick "Add Python to PATH" during installation.
  echo.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found.
  echo Please install Node.js LTS first: https://nodejs.org/
  echo.
  pause
  exit /b 1
)

echo Installing backend packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Backend package installation failed.
  pause
  exit /b 1
)

echo.
echo Installing frontend packages...
cd frontend
call npm install
if errorlevel 1 (
  echo.
  echo Frontend package installation failed.
  pause
  exit /b 1
)

cd /d "%~dp0"
if exist spider_xhs\package.json (
  echo.
  echo Installing collector packages...
  cd spider_xhs
  call npm install
  if errorlevel 1 (
    echo.
    echo Collector package installation failed.
    pause
    exit /b 1
  )
  cd /d "%~dp0"
)

cd /d "%~dp0"
echo.
echo Setup finished. Next time, double-click start_windows.bat.
echo.
pause
