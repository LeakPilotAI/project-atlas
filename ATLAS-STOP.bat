@echo off
setlocal
cd /d "%~dp0"
title Stop Atlas
echo Stopping Project Atlas (Python + atlas-postgres/redis)...
echo Docker Desktop and Genesis will stay running.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
if errorlevel 1 (
    echo Atlas shutdown was NOT confirmed. The protected stop path refused or failed.
    echo Use the owning Atlas Control Center to close its observation host.
    exit /b 1
)
echo.
echo Atlas is stopped. You can close this window.
timeout /t 4 >nul
endlocal
