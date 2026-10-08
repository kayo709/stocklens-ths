@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ===========================================
echo   StockLens - evidence research demo
 echo ===========================================
echo.
echo Open browser: http://127.0.0.1:8000/
echo Press Ctrl+C to stop server.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
pause
