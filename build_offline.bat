@echo off
title Image2 - Build Offline Package
cd /d "%~dp0"

set PYTHON_DIR=python
set PYTHON_EXE=%PYTHON_DIR%\python.exe
set PYTHON_VER=3.11.9
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/python-%PYTHON_VER%-embed-amd64.zip
set ZIP_NAME=python-%PYTHON_VER%-embed-amd64.zip

echo ========================================
echo   Image2 - Offline Package Builder
echo ========================================
echo.

if exist "%PYTHON_EXE%" goto :CONFIG

REM Step 1: Download embedded Python
echo [1/4] Downloading embedded Python %PYTHON_VER%...
if not exist "%ZIP_NAME%" (
    powershell -Command "$wc = [System.Net.WebClient]::new(); Write-Host 'Downloading...'; $wc.DownloadFile('%PYTHON_URL%', '%ZIP_NAME%')"
    if errorlevel 1 (
        echo [ERROR] Download failed. Check your internet connection.
        pause & exit /b 1
    )
)

echo [2/4] Extracting...
powershell -Command "Expand-Archive -Path '%ZIP_NAME%' -DestinationPath '%PYTHON_DIR%' -Force"
if errorlevel 1 ( echo [ERROR] Extract failed. & pause & exit /b 1 )

:CONFIG
echo [3/4] Configuring Python...

REM Enable site-packages
set PTH_FILE=%PYTHON_DIR%\python311._pth
> "%PTH_FILE%" (
    echo python311.zip
    echo .
    echo Lib\site-packages
    echo.
    echo import site
)

REM Install pip
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Installing pip...
    if not exist "get-pip.py" (
        powershell -Command "[System.Net.WebClient]::new().DownloadFile('https://bootstrap.pypa.io/get-pip.py', 'get-pip.py')"
    )
    "%PYTHON_EXE%" get-pip.py --no-warn-script-location
    del get-pip.py 2>nul
)

REM Install deps
echo [4/4] Installing dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt --no-warn-script-location --index-url https://pypi.org/simple/
if errorlevel 1 ( echo [ERROR] Install failed. & pause & exit /b 1 )

REM Data dirs
for %%d in (data\images data\case_images data\meta_images) do if not exist %%d mkdir %%d

REM Cleanup
del "%ZIP_NAME%" 2>nul

echo.
echo ========================================
echo   Build complete!
echo   Run start.bat to launch.
echo ========================================
pause
