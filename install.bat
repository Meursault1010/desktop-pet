@echo off
if exist "%~dp0releases\electron\yuki-win32-x64\yuki.exe" (
  echo yuki portable build is ready. Run start.bat.
  pause
  exit /b 0
)
call "%~dp0install-electron.bat"
