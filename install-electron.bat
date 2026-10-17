@echo off
setlocal
cd /d "%~dp0console-v2"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
cd frontend
call npm.cmd ci --no-audit --no-fund
if errorlevel 1 goto failed
node node_modules/electron/install.js
if errorlevel 1 goto failed
call npm.cmd run build
if errorlevel 1 goto failed
echo Electron development setup complete. Use start-electron.bat.
pause
exit /b 0
:failed
echo Setup failed. Check Python, Node and the command output.
pause
exit /b 1
