@echo off
setlocal EnableExtensions
title Project Atlas

set "ROOT=D:\Work\Project Atlas"
set "BACKEND=%ROOT%\backend"
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
set "COMPOSE=docker"

cd /d "%ROOT%"
if errorlevel 1 (
  echo ERROR: Cannot cd to %ROOT%
  pause
  exit /b 1
)

echo ========================================
echo  Project Atlas — starting
echo ========================================

REM Kill any old Atlas/uvicorn python processes from prior runs
echo [1/4] Stopping old Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start Postgres + Redis
echo [2/4] Starting Docker (postgres + redis)...
docker compose up -d
if errorlevel 1 (
  echo.
  echo ERROR: docker compose failed.
  echo Make sure Docker Desktop is running, then try again.
  pause
  exit /b 1
)

echo Waiting for containers...
timeout /t 5 /nobreak >nul

docker compose ps

if not exist "%VENV_PY%" (
  echo ERROR: venv python not found: %VENV_PY%
  pause
  exit /b 1
)

cd /d "%BACKEND%"

echo [3/4] Verifying config...
"%VENV_PY%" -c "from app.core.config import get_settings; get_settings.cache_clear(); s=get_settings(); print('MICRO', s.perp_micro_max_open, s.perp_micro_max_triggers_per_day, s.perp_micro_min_vol, s.perp_micro_min_rr)"
if errorlevel 1 (
  echo ERROR: config check failed
  pause
  exit /b 1
)

echo [4/4] Starting Atlas API (uvicorn)...
echo.
echo Leave this window open while the bot runs.
echo Close this window or press Ctrl+C to stop the bot.
echo To fully stop Docker too, run stop_atlas.bat on the desktop.
echo.

"%VENV_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Atlas process exited.
pause
endlocal