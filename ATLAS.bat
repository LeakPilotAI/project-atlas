@echo off
setlocal
cd /d "%~dp0"
title Project Atlas
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Atlas-Launch.ps1"
endlocal
