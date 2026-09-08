@echo off
REM Same as desktop "Stop Atlas". Does not quit Docker Desktop.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
echo.
echo Atlas stopped. Docker Desktop and Genesis were not touched.
timeout /t 3 >nul
