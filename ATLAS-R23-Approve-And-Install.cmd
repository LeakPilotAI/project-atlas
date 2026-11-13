@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ATLAS R23 - LOCAL CODE-ONLY REVIEW AND INSTALL
set "ROOT=D:\Work\Project Atlas"
set "NATIVE=D:\AtlasRuntime\releases\119dd8626da32e74bd7f86db9de1c1a8fd2c20ac"
set "TEMP=%ROOT%\logs\temp"
set "TMP=%ROOT%\logs\temp"
set "TMPDIR=%ROOT%\logs\temp"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONNOUSERSITE=1"
if not exist "%ROOT%\logs\temp\" (
  echo REFUSED: Expected existing D: Atlas temporary directory missing.
  pause
  exit /b 2
)
if not exist "%NATIVE%\python\python.exe" (
  echo REFUSED: Original selected R21 Python executable missing.
  pause
  exit /b 2
)
cd /d "%ROOT%"
echo This requires YOUR locally visible Windows console and explicit typed R23 scope.
echo NO simulated account initialization, PAPER start, release selection, or live orders.
"%NATIVE%\python\python.exe" -I -B -S -c "import sys; p=r'D:\AtlasRuntime\releases\119dd8626da32e74bd7f86db9de1c1a8fd2c20ac'; sys.path[:0]=[r'D:\Work\Project Atlas',r'D:\Work\Project Atlas\backend',p+r'\python\Lib\site-packages']; from scripts.atlas_r23_local_operator_consent import main; raise SystemExit(main(['--approve-and-install']))"
set "RESULT=%ERRORLEVEL%"
echo.
echo R23 code-only local process finished with exit code %RESULT%.
echo The installation does NOT authorize PAPER or live trading.
echo Press any key to close. This window preserves the final status.
pause >nul
exit /b %RESULT%
