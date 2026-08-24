@echo off
setlocal
title Project Atlas — STOP
set "ROOT=D:\Work\Project Atlas"

echo ========================================
echo  Project Atlas — stopping everything
echo ========================================

echo [1/2] Force-closing Python...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/2] Stopping Docker containers...
cd /d "%ROOT%"
docker compose down

echo.
echo Done. Bot and Docker stack stopped.
pause
endlocal