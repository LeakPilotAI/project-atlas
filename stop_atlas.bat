@echo off
REM Emergency stop (not installed to desktop). The launcher already stops on close.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
echo.
echo Atlas and Docker stopped.
pause
