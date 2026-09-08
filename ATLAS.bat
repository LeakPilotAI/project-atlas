@echo off
setlocal
cd /d "%~dp0"
title Project Atlas
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Launch.ps1"
REM If the window is still around after launch exits (Ctrl+C), sweep leftovers.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Stop.ps1"
endlocal
