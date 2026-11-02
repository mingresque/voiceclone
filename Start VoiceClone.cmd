@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_launch.ps1"
if errorlevel 1 (
  echo.
  echo Setup or launch failed. See the message above and the logs folder.
  pause
)
endlocal
