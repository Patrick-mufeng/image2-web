@echo off
title Image2 - AI Image Generator
cd /d "%~dp0"

echo ========================================
echo   Image2 - AI Image Generator
echo ========================================
echo.

set PYTHON=python\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python runtime not found.
    echo Please run build_offline.bat first.
    pause
    exit /b 1
)

echo [1/2] Starting server...

:: Open browser after a short delay
start /b "" "%PYTHON%" -c "import time, webbrowser; time.sleep(2.5); webbrowser.open('http://localhost:8000')"

echo [2/2] Open browser at http://localhost:8000
echo.
echo Close this window or press Ctrl+C to stop.
echo.
"%PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level warning

echo.
echo Server stopped.
pause
