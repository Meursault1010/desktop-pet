@echo off
setlocal
cd /d "%~dp0"
if exist "releases\electron\yuki-win32-x64-breathing\yuki-win32-x64\yuki.exe" (
  set "YUKI_DIR=%~dp0releases\electron\yuki-win32-x64-breathing\yuki-win32-x64"
  goto launch
)
if exist "releases\electron\yuki-win32-x64\yuki.exe" (
  set "YUKI_DIR=%~dp0releases\electron\yuki-win32-x64"
  goto launch
)
if not exist "console-v2\frontend\node_modules\electron\dist\electron.exe" goto missing
if not exist "console-v2\.venv\Scripts\python.exe" goto missing
if not exist "console-v2\frontend\dist\index.html" goto missing
set "PET_PYTHON=%~dp0console-v2\.venv\Scripts\python.exe"
cd /d "%~dp0console-v2\frontend"
start "" "%~dp0console-v2\frontend\node_modules\electron\dist\electron.exe" "electron\main\index.cjs"
exit /b 0
:launch
icacls "%YUKI_DIR%" /grant "*S-1-15-2-1:(OI)(CI)(RX)" /T /C
start "" "%YUKI_DIR%\yuki.exe"
exit /b 0
:missing
echo Electron build is missing. Run install-electron.bat for development,
echo or build-electron.ps1 to create the portable release.
pause
exit /b 1
