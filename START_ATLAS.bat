@echo off
setlocal EnableExtensions
title Project Atlas ? One-Click Start
cd /d "D:\Work\Project Atlas"

echo ========================================
echo  PROJECT ATLAS - One-Click Start
echo  Ports: API 8000 / Postgres 5432 / Redis 6379
echo  Discord: DM-only  ^|  Docker Desktop must be running
echo ========================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERROR] docker not found in PATH. Open Docker Desktop first.
  pause
  exit /b 1
)

echo [1/5] Ensuring Postgres + Redis are up...
docker compose up -d
if errorlevel 1 (
  echo [ERROR] docker compose failed. Is Docker Desktop running?
  pause
  exit /b 1
)

echo [2/5] Waiting for containers...
timeout /t 8 /nobreak >nul

echo [3/5] Stopping any old Atlas API on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul

if not exist "D:\Work\Project Atlas\backend\.venv\Scripts\python.exe" (
  echo [ERROR] venv missing: backend\.venv
  pause
  exit /b 1
)

if not exist "D:\Work\Project Atlas\backend\.env" (
  echo [ERROR] backend\.env missing
  pause
  exit /b 1
)

echo [4/5] Starting Atlas API minimized...
start "Atlas API" /MIN "D:\Work\Project Atlas\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir "D:\Work\Project Atlas\backend"

echo [5/5] Waiting for health...
set OK=0
for /l %%i in (1,1,20) do (
  timeout /t 2 /nobreak >nul
  curl.exe -s http://localhost:8000/health 2>nul | findstr /C:"\"status\":\"ok\"" >nul
  if not errorlevel 1 (
    set OK=1
    goto :healthy
  )
)

:healthy
if "%OK%"=="1" (
  echo.
  curl.exe -s http://localhost:8000/health
  echo.
  echo.
  echo Atlas is running minimized.
  echo Discord connects in a few seconds.
  echo Close this window anytime ? Atlas keeps running.
) else (
  echo.
  echo [WARN] Health not OK yet. Check: docker compose ps
)

echo.
pause
