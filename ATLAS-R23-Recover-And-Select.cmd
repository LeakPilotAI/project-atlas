@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ATLAS R23 - VERIFIED PARTIAL CODE RECOVERY THEN OPTIONAL SELECT
set "ROOT=D:\Work\Project Atlas"
set "NATIVE=D:\AtlasRuntime\releases\119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
set "TEMP=%ROOT%\logs\temp"
set "TMP=%ROOT%\logs\temp"
set "TMPDIR=%ROOT%\logs\temp"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONNOUSERSITE=1"
if not exist "%ROOT%\logs\temp\" (
  echo REFUSED: Original D: temporary directory missing.
  pause
  exit /b 2
)
if not exist "%NATIVE%\python\python.exe" (
  echo REFUSED: Original immutable selected R21 Python missing.
  pause
  exit /b 2
)
cd /d "%ROOT%"
echo This is NOT the failed original R23 installer. DO NOT run that installer again.
echo Read-only native audit verified 7910 existing files. This recovers ONLY 2853 missing files.
echo One LOCAL scope authorizes CODE-ONLY recovery; a DIFFERENT scope authorizes CODE-ONLY selection.
echo Neither scope initializes PAPER accounts, authorizes provider sessions or permits live orders.
"%NATIVE%\python\python.exe" -I -B -S -c "import sys; p=r'D:\AtlasRuntime\releases\119dd8626da32e74bd7f86db9de1c1a8fd2c20ac';sys.path[:0]=[r'D:\Work\Project Atlas',r'D:\Work\Project Atlas\backend',p+r'\python\Lib\site-packages'];from scripts.atlas_r23_local_recovery_consent import main;raise SystemExit(main(['--recover-and-select']))"
set "RESULT=%ERRORLEVEL%"
echo.
echo ATLAS R23 RECOVERY/SELECTION ended with process exit code %RESULT%.
echo If anything refused, preserve the exact terminal, ALL original journals and partial native files.
echo Never rerun this one-shot recovery after a partial failure. This never authorizes PAPER trading.
echo Press any key to close.
pause >nul
exit /b %RESULT%
