@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo X Posting Automation - Cleanup Script
echo ============================================================
echo.
echo This script will clean up running processes and temporary files.
echo.
echo WARNING: This will stop any running automation!
echo.
pause

echo.
echo [Step 1/4] Stopping Python backend processes...
set PROCESSES_KILLED=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" 2^>nul') do (
    set "PID=%%a"
    if "!PID!" neq "0" (
        echo   Stopping process !PID! on port 8765...
        taskkill /F /PID !PID! >nul 2>&1
        set /a PROCESSES_KILLED+=1
    )
)

if !PROCESSES_KILLED! gtr 0 (
    echo   [OK] Stopped !PROCESSES_KILLED! process^(es^)
    timeout /t 2 /nobreak >nul
) else (
    echo   [OK] No processes on port 8765
)

echo.
echo [Step 2/4] Checking for Chrome debugging instances...
set CHROME_KILLED=0

REM Check Chrome debugging ports 9222-9251 (supports up to 30 profiles)
for /L %%p in (9222,1,9251) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p" 2^>nul') do (
        set "PID=%%a"
        if "!PID!" neq "0" (
            echo   Stopping Chrome process !PID! on port %%p...
            taskkill /F /PID !PID! >nul 2>&1
            set /a CHROME_KILLED+=1
        )
    )
)

if !CHROME_KILLED! gtr 0 (
    echo   [OK] Stopped !CHROME_KILLED! Chrome process^(es^)
) else (
    echo   [OK] No Chrome debugging processes found
)

echo.
echo [Step 3/4] Cleaning temporary files...
set FILES_CLEANED=0

REM Clean log files (optional - ask user)
if exist "logs\app.log" (
    for %%A in ("logs\app.log") do set LOG_SIZE=%%~zA
    if !LOG_SIZE! gtr 10000000 (
        echo   Log file is large ^(!LOG_SIZE! bytes^)
        choice /C YN /M "Do you want to clear the log file"
        if !errorlevel! equ 1 (
            echo. > "logs\app.log"
            echo   [OK] Log file cleared
            set /a FILES_CLEANED+=1
        )
    ) else (
        echo   [OK] Log file size is normal
    )
)

REM Clean singleton locks in profiles
if exist "profiles\" (
    for /d %%d in (profiles\*) do (
        if exist "%%d\SingletonLock" (
            del "%%d\SingletonLock" >nul 2>&1
            set /a FILES_CLEANED+=1
        )
    )
    if !FILES_CLEANED! gtr 0 (
        echo   [OK] Cleaned !FILES_CLEANED! singleton lock file^(s^)
    )
)

echo.
echo [Step 4/4] Final verification...
netstat -ano | findstr ":8765" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [WARNING] Port 8765 is still in use
    echo   You may need to restart your computer
) else (
    echo   [OK] Port 8765 is clear
)

echo.
echo ============================================================
echo Cleanup Complete!
echo ============================================================
echo.
echo You can now safely run start.bat to start the application.
echo.
pause
