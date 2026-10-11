@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 app\server.py --port 8767 --offline-demo
) else (
  python app\server.py --port 8767 --offline-demo
)
if errorlevel 1 (
  echo Install Python 3.10 or later, then run this launcher again.
  pause
)
endlocal
