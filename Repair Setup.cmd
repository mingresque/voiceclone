@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_launch.ps1" -Repair
if errorlevel 1 (
  echo.
  echo Repair failed. See the message above and the logs folder.
  pause
)
endlocal
