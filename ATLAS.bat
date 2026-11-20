@echo off
setlocal
cd /d "%~dp0"
title Project Atlas
REM Legacy startup is blocked until accepted native PAPER commissioning.
REM Never invoke a shutdown/flatten fallback after failed startup: no session
REM identity, financial cut or owned process roster was established.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Launch.ps1"
set "ATLAS_LAUNCH_EXIT=%ERRORLEVEL%"
if not "%ATLAS_LAUNCH_EXIT%"=="0" (
    echo Atlas startup was NOT confirmed. No PAPER session was authorized.
    echo Do not assume any positions were closed or any shutdown completed.
)
exit /b %ATLAS_LAUNCH_EXIT%