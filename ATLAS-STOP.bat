@echo off
setlocal
cd /d "%~dp0"
title Stop Atlas
echo Project Atlas desktop Stop: checking protected shutdown path.
echo This shortcut is NOT yet connected to certified PAPER flattening.
echo No Docker Desktop or Genesis shutdown will be attempted.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
if errorlevel 1 (
    echo Atlas shutdown was NOT confirmed. The protected stop path refused or failed.
    echo Do not assume PAPER positions were closed or Atlas processes exited.
    echo Use the owning Atlas Control Center for observation-only shutdown.
    exit /b 1
)
echo.
echo Protected shutdown script returned success; independent PAPER flatness is NOT verified.
timeout /t 4 >nul
endlocal
