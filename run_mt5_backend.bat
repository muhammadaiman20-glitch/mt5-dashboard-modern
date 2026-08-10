@echo off
setlocal

cd /d "%~dp0"

if not exist "mt5_credentials.local.bat" (
    echo.
    echo mt5_credentials.local.bat not found.
    echo Copy mt5_credentials.example.bat to mt5_credentials.local.bat
    echo and fill in your MT5 login, password and server first.
    echo.
    pause
    exit /b 1
)

call mt5_credentials.local.bat

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3 ^(python.org^) and try again.
    pause
    exit /b 1
)

echo Installing/updating dependencies...
python -m pip install --quiet --upgrade -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency install failed. See the error above.
    pause
    exit /b 1
)

echo.
if "%MT5_AUTOTRADE_ENABLED%"=="1" (
    echo LIVE TRADING IS ENABLED - the auto-loop will place real orders.
) else (
    echo Live trading is OFF - the auto-loop will only log what it would do.
)
echo Starting MT5 backend on http://localhost:8081 ...
echo Open http://localhost:8081 in your browser to use the dashboard.
echo Press Ctrl+C to stop.
echo.

python test_mt5.py

pause
