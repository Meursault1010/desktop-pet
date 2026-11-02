@echo off
setlocal
cd /d "%~dp0"

rem Launch the source-tree workbench for development.
rem The normal user launcher is start.bat, which prefers the portable release.

if not exist "console-v2\frontend\node_modules\electron\dist\electron.exe" goto missing
if not exist "console-v2\.venv\Scripts\python.exe" goto missing

%SystemRoot%\System32\tasklist.exe /FI "IMAGENAME eq yuki.exe" 2>nul | %SystemRoot%\System32\findstr.exe /I /C:"yuki.exe" >nul
if not errorlevel 1 goto oldrunning

if not exist "console-v2\frontend\dist\index.html" (
  echo [yuki] Building the workbench...
  pushd "console-v2\frontend"
  call npm run build
  if errorlevel 1 (
    popd
    echo [yuki] Build failed. Run npm install and npm run build in console-v2\frontend.
    pause
    exit /b 1
  )
  popd
)

cd /d "%~dp0console-v2\frontend"
set "ELECTRON_RUN_AS_NODE="
set "PET_PYTHON=%~dp0console-v2\.venv\Scripts\python.exe"
start "" "%~dp0console-v2\frontend\node_modules\electron\dist\electron.exe" "electron\main\index.cjs"
exit /b 0

:oldrunning
echo.
echo [yuki] The old packaged yuki is still running and would take over the window.
echo [yuki] Right-click the yuki tray icon, choose "Save and exit yuki", then run this again.
echo.
pause
exit /b 1

:missing
echo [yuki] Development runtime is missing: console-v2\frontend\node_modules or console-v2\.venv.
pause
exit /b 1
