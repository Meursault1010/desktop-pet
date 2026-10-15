@echo off
cd /d "%~dp0"
if exist "..\..\work\pet-venv\Scripts\python.exe" (
  "..\..\work\pet-venv\Scripts\python.exe" main.py
  if errorlevel 1 pause
  exit /b
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py
  if errorlevel 1 pause
  exit /b
)
python main.py
if errorlevel 1 pause
