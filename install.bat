@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Installation complete. Open start.bat to run.
pause
exit /b 0
:failed
echo Installation failed. Check Python installation and network connection.
pause
exit /b 1
