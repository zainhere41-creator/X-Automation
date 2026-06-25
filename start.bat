@echo off
setlocal enabledelayedexpansion
title X Posting Automation
echo ========================================
echo X Posting Automation - Starting...
echo ========================================
echo.

REM Ensure we're in the correct directory
cd /d "%~dp0"

REM Check if electron binary exists
if not exist "electron\node_modules\electron\dist\electron.exe" (
    echo [ERROR] Electron binary not found!
    echo.
    echo The electron executable is missing. Please run setup.bat first
    echo to install all dependencies.
    echo.
    pause
    exit /b 1
)

REM Check if Python backend exists
if not exist "python_backend\main.py" (
    echo [ERROR] Python backend not found!
    echo.
    echo The python_backend folder is missing. Please re-download the project.
    echo.
    pause
    exit /b 1
)

REM Kill any existing Python backend on port 8765
echo Checking for existing Python backend...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765"') do (
    set "PID=%%a"
    if "!PID!" neq "0" (
        echo Killing process !PID! on port 8765...
        taskkill /F /PID !PID! >nul 2>&1
    )
)

REM Wait for port to be released
timeout /t 2 /nobreak >nul

REM Start Electron (it manages the Python backend internally)
cd electron
echo Starting Electron app...
echo.
call npm start
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Electron app failed to start!
    echo.
    echo Possible fixes:
    echo   1. Run setup.bat to reinstall dependencies
    echo   2. Check if port 8765 is already in use
    echo   3. Check if antivirus is blocking the app
    echo.
    cd ..
    pause
    exit /b 1
)
cd ..
