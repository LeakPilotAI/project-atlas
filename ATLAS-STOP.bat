@echo off
setlocal
cd /d "%~dp0"
title Stop Atlas
echo Stopping Project Atlas (Python + atlas-postgres/redis)...
echo Docker Desktop and Genesis will stay running.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
echo.
echo Atlas is stopped. You can close this window.
timeout /t 4 >nul
endlocal
