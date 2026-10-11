@echo off
setlocal
cd /d "%~dp0"
echo Sandbox mode uses virtual test funds only. Configure .env first.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 app\server.py --port 8766 --db app/runtime/sandbox.sqlite
) else (
  python app\server.py --port 8766 --db app/runtime/sandbox.sqlite
)
if errorlevel 1 (
  echo Install Python 3.10 or later and check whether port 8766 is already in use.
  pause
)
endlocal
