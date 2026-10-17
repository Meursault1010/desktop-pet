@echo off
cd /d "%~dp0"
if not exist "app\xiaoju-console.exe" (
  echo The new desktop console has not been built. See FRONTEND.md.
  echo You can use start_legacy.bat for the original console.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Please run install.bat first to install the pet environment.
  pause
  exit /b 1
)
set "PET_PROJECT_DIR=%~dp0"
set "PET_PYTHON=%~dp0.venv\Scripts\python.exe"
start "" "%~dp0app\xiaoju-console.exe"
