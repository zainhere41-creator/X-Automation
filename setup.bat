@echo off
setlocal EnableDelayedExpansion
title X Posting Automation - Setup
color 0A

echo ============================================================
echo  X Posting Automation - Full Setup
echo ============================================================
echo.
echo  This script will set up everything needed to run the bot:
echo.
echo    - Verify Python 3.10+ is installed
echo    - Verify Node.js 16+ is installed
echo    - Verify Google Chrome is installed
echo    - Install Visual C++ Redistributable (if needed)
echo    - Install all Python packages
echo    - Install Playwright Chromium browser
echo    - Install Electron app dependencies
echo.
echo  Requirements before running this:
echo    - Python 3.10 or newer (from python.org)
echo    - Node.js 16 or newer (from nodejs.org)
echo    - Google Chrome (from google.com/chrome)
echo.
echo  This may take 5-10 minutes.
echo ============================================================
echo.

cd /d "%~dp0"

REM =============================================
REM Step 1: Create required folders
REM =============================================
echo [Step 1/8] Creating folders...
if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "profiles" mkdir "profiles"
if not exist "config" mkdir "config"
echo   [OK] Folders created
echo.

REM =============================================
REM Step 2: Check Python
REM =============================================
echo [Step 2/8] Checking Python...
echo.

set PYTHON_CMD=
python --version >nul 2>&1
if !errorlevel! equ 0 set PYTHON_CMD=python& goto :python_found
python3 --version >nul 2>&1
if !errorlevel! equ 0 set PYTHON_CMD=python3& goto :python_found
py --version >nul 2>&1
if !errorlevel! equ 0 set PYTHON_CMD=py& goto :python_found

echo   [ERROR] Python not found!
echo.
echo   Please install Python 3.10+ from: https://www.python.org/downloads/
echo   IMPORTANT: Check "Add Python to PATH" during install.
echo   Then run this setup.bat again.
echo.
pause
exit /b 1

:python_found
for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VER=%%i
echo   [OK] !PY_VER!
echo.

REM =============================================
REM Step 3: Check Node.js
REM =============================================
echo [Step 3/8] Checking Node.js...
echo.

node --version >nul 2>&1
if !errorlevel! neq 0 (
    echo   [ERROR] Node.js not found!
    echo.
    echo   Please install Node.js 16+ from: https://nodejs.org/
    echo   Choose the LTS version. Run this setup.bat again after install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
echo   [OK] Node.js !NODE_VER!
echo.

REM =============================================
REM Step 4: Check Google Chrome
REM =============================================
echo [Step 4/8] Checking Google Chrome...
echo.

set CHROME_FOUND=0
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1

if !CHROME_FOUND! equ 0 (
    echo   [ERROR] Google Chrome not found!
    echo.
    echo   Please install Chrome from: https://www.google.com/chrome/
    echo   Then run this setup.bat again.
    echo.
    pause
    exit /b 1
)

echo   [OK] Google Chrome found
echo.

REM =============================================
REM Step 5: Install Visual C++ Redistributable
REM =============================================
echo [Step 5/8] Checking Visual C++ Redistributable...
echo.

REM Check if VC++ is already installed by looking for the registry key
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64" >nul 2>&1
if !errorlevel! equ 0 (
    echo   [OK] Already installed
    goto :vcpp_done
)

echo   Downloading Visual C++ Redistributable...
powershell -Command "$ProgressPreference='SilentlyContinue'; try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%TEMP%\vc_redist.x64.exe' -TimeoutSec 120 } catch { exit 1 }"

if exist "%TEMP%\vc_redist.x64.exe" (
    echo   Installing Visual C++ Redistributable...
    "%TEMP%\vc_redist.x64.exe" /install /quiet /norestart
    del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
    echo   [OK] Installed
) else (
    echo   [WARNING] Could not download VC++ Redistributable.
    echo   Download manually from: https://aka.ms/vs/17/release/vc_redist.x64.exe
)

:vcpp_done
echo.

REM =============================================
REM Step 6: Install Python dependencies
REM =============================================
echo [Step 6/8] Installing Python packages...
echo.

%PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1
cd python_backend
%PYTHON_CMD% -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo   [ERROR] Failed to install Python packages.
    cd ..
    pause
    exit /b 1
)
%PYTHON_CMD% -m pywin32_postinstall -install >nul 2>&1
cd ..
echo   [OK] Python packages installed
echo.

REM =============================================
REM Step 7: Install Playwright browsers
REM =============================================
echo [Step 7/8] Installing Playwright Chromium...
echo   (Downloads ~200MB, takes a few minutes)
echo.

%PYTHON_CMD% -m playwright install chromium
if !errorlevel! neq 0 (
    echo   [WARNING] Playwright install had issues.
    echo   Try manually: %PYTHON_CMD% -m playwright install chromium
) else (
    echo   [OK] Playwright Chromium installed
)
echo.

REM =============================================
REM Step 8: Install Electron dependencies
REM =============================================
echo [Step 8/8] Installing Electron dependencies...
echo.

cd electron

REM =============================================
REM Strategy: Use mirror for faster/more reliable download
REM Default GitHub releases CDN is often blocked by
REM corporate networks, firewalls, and some ISPs.
REM =============================================

REM Attempt 1: npm install (downloads zip, extract-zip may fail on Node 26+)
echo   Attempt 1/3: Installing Electron via npm...
echo   (This may take a few minutes - downloading ~200MB)
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_SKIP_BINARY_DOWNLOAD=0
call npm install
if !errorlevel! equ 0 (
    if exist "node_modules\electron\dist\electron.exe" (
        goto :electron_ok
    )
)
echo   [INFO] npm install completed but electron.exe not found.
echo.

REM Attempt 2: extract-zip failed silently, use PowerShell to extract the cached zip
echo   Attempt 2/3: extract-zip failed, using PowerShell fallback...
echo   (This happens on Node.js 26+ due to extract-zip incompatibility)
echo.

REM Find the electron version from package.json using node for reliable JSON parsing
set "ELECTRON_VER="
for /f "usebackq" %%a in (`node -e "try{console.log(require('./node_modules/electron/package.json').version)}catch(e){process.exit(1)}"`) do set "ELECTRON_VER=%%a"
REM Fallback: try findstr if node parsing failed
if "!ELECTRON_VER!"=="" (
    for /f "tokens=*" %%v in ('type node_modules\electron\package.json ^| findstr /C:"version"') do set "ELECTRON_VER_RAW=%%v"
    for /f tokens^=4^ delims^=:,^" %%a in ("!ELECTRON_VER_RAW!") do set "ELECTRON_VER=%%a"
)
set "ELECTRON_VER=!ELECTRON_VER: =!"
echo   Electron version: !ELECTRON_VER!
echo.

REM Find the cached zip
set "ELECTRON_ZIP="
for /f "delims=" %%f in ('dir /s /b "%LOCALAPPDATA%\electron\Cache\electron-!ELECTRON_VER!-win32-x64.zip" 2^>nul') do (
    set "ELECTRON_ZIP=%%f"
)

REM If not found in cache, download it
if "!ELECTRON_ZIP!"=="" (
    echo   Cached zip not found, downloading...
    echo   (This may take a few minutes)
    node -e "const{downloadArtifact}=require('@electron/get');downloadArtifact({version:'!ELECTRON_VER!',artifactName:'electron',platform:'win32',arch:'x64'}).then(p=>console.log(p)).catch(e=>{console.error(e);process.exit(1)})" > "%TEMP%\electron_zip_path.txt" 2>&1
    if !errorlevel! equ 0 (
        set /p ELECTRON_ZIP=<"%TEMP%\electron_zip_path.txt"
    ) else (
        echo   [WARNING] Download failed, trying alternative method...
        REM Try direct download with node
        node -e "const{downloadArtifact}=require('@electron/get');downloadArtifact({version:'!ELECTRON_VER!',artifactName:'electron',platform:'win32',arch:'x64',isExtracted:false}).then(p=>console.log(p)).catch(e=>{console.error(e);process.exit(1)})" > "%TEMP%\electron_zip_path.txt" 2>&1
        set /p ELECTRON_ZIP=<"%TEMP%\electron_zip_path.txt"
    )
)

REM Extract using PowerShell if we have the zip
if exist "!ELECTRON_ZIP!" (
    echo   Found zip: !ELECTRON_ZIP!
    if exist "node_modules\electron\dist" rmdir /s /q "node_modules\electron\dist" 2>nul
    powershell -Command "try { Add-Type -Assembly System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('!ELECTRON_ZIP!', 'node_modules\electron\dist'); Write-Host 'Extraction successful' } catch { Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }"
    if !errorlevel! equ 0 (
        echo electron.exe> node_modules\electron\path.txt
        if exist "node_modules\electron\dist\electron.exe" (
            goto :electron_ok
        )
    )
    echo   [WARNING] PowerShell extraction completed but electron.exe not found
) else (
    echo   [WARNING] Electron zip not found in cache or download
)
echo.

REM Attempt 3: Clean install with default CDN
echo   Attempt 3/3: Clean install with default CDN...
set ELECTRON_MIRROR=
rmdir /s /q node_modules 2>nul
call npm install
if exist "node_modules\electron\dist\electron.exe" (
    goto :electron_ok
)

REM Last resort: try extracting again after clean install
if exist "node_modules\electron\package.json" (
    set "ELECTRON_VER2="
    for /f "usebackq" %%a in (`node -e "try{console.log(require('./node_modules/electron/package.json').version)}catch(e){process.exit(1)}"`) do set "ELECTRON_VER2=%%a"
    if "!ELECTRON_VER2!"=="" (
        for /f "tokens=*" %%v in ('type node_modules\electron\package.json ^| findstr /C:"version"') do set "ELECTRON_VER_RAW2=%%v"
        for /f tokens^=4^ delims^=:,^" %%a in ("!ELECTRON_VER_RAW2!") do set "ELECTRON_VER2=%%a"
    )
    set "ELECTRON_VER2=!ELECTRON_VER2: =!"
    for /f "delims=" %%f in ('dir /s /b "%LOCALAPPDATA%\electron\Cache\electron-!ELECTRON_VER2!-win32-x64.zip" 2^>nul') do (
        set "ELECTRON_ZIP2=%%f"
    )
    if exist "!ELECTRON_ZIP2!" (
        echo   Extracting cached zip with PowerShell...
        if exist "node_modules\electron\dist" rmdir /s /q "node_modules\electron\dist" 2>nul
        powershell -Command "try { Add-Type -Assembly System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('!ELECTRON_ZIP2!', 'node_modules\electron\dist'); Write-Host 'Extraction successful' } catch { Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }"
        echo electron.exe> node_modules\electron\path.txt
        if exist "node_modules\electron\dist\electron.exe" (
            goto :electron_ok
        )
    )
)

REM All attempts failed
echo.
echo   [ERROR] Electron binary could not be installed.
echo.
echo   Possible causes:
echo     - Network issue downloading electron binary
echo     - Antivirus blocking the extraction
echo     - Node.js version incompatibility
echo.
echo   Manual fix:
echo     1. Temporarily disable antivirus
echo     2. Run: cd electron ^&^& npm install
echo     3. If extract-zip fails, find the zip in:
echo        %%LOCALAPPDATA%%\electron\Cache\
echo     4. Extract manually with PowerShell:
echo        Add-Type -Assembly System.IO.Compression.FileSystem
echo        [System.IO.Compression.ZipFile]::ExtractToDirectory('ZIP_PATH', 'node_modules\electron\dist')
echo     5. Create file: echo electron.exe ^> node_modules\electron\path.txt
echo     6. Re-enable antivirus
echo.
set ELECTRON_MIRROR=
cd ..
pause
exit /b 1

:electron_ok
set ELECTRON_MIRROR=
cd ..
echo   [OK] Electron dependencies installed
echo.

REM =============================================
REM Final: Verify everything
REM =============================================
echo ============================================================
echo  VERIFICATION
echo ============================================================
echo.

set ALL_OK=1

%PYTHON_CMD% -c "import fastapi" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] fastapi) else (echo   [FAIL] fastapi & set ALL_OK=0)
%PYTHON_CMD% -c "import uvicorn" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] uvicorn) else (echo   [FAIL] uvicorn & set ALL_OK=0)
%PYTHON_CMD% -c "import playwright" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] playwright) else (echo   [FAIL] playwright & set ALL_OK=0)
%PYTHON_CMD% -c "import greenlet" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] greenlet) else (echo   [FAIL] greenlet & set ALL_OK=0)
%PYTHON_CMD% -c "import apscheduler" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] apscheduler) else (echo   [FAIL] apscheduler & set ALL_OK=0)
%PYTHON_CMD% -c "import openpyxl" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] openpyxl) else (echo   [FAIL] openpyxl & set ALL_OK=0)
%PYTHON_CMD% -c "import win32com.client" >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] pywin32) else (echo   [FAIL] pywin32 & set ALL_OK=0)
node --version >nul 2>&1
if !errorlevel! equ 0 (echo   [OK] Node.js) else (echo   [FAIL] Node.js & set ALL_OK=0)
if exist "electron\node_modules\electron" (echo   [OK] Electron) else (echo   [FAIL] Electron & set ALL_OK=0)

echo.
if !ALL_OK! equ 1 (
    echo ============================================================
    echo  SETUP COMPLETE - All checks passed!
    echo ============================================================
) else (
    color 0E
    echo ============================================================
    echo  SETUP FINISHED WITH WARNINGS
    echo  Check the [FAIL] items above and fix them.
    echo  Restart PC and run setup.bat again if needed.
    echo ============================================================
)

echo.
echo ============================================================
echo  HOW TO USE:
echo.
echo  1. Generate profile shortcuts (auto-detects your Chrome profiles):
echo       python generate_profiles.py --use-existing
echo.
echo     Or create new profiles with a specific count:
echo       python generate_profiles.py --count 30
echo       python generate_profiles.py --count 10
echo.
echo  2. Double-click start.bat to open the app
echo  3. Go to Setup tab
echo  4. Select the "profiles" folder
echo  5. Load your XLSX file with post data
echo  6. Click "Launch Profiles" to open Chrome windows
echo  7. Log into X in each Chrome window
echo  8. Start automation!
echo.
echo  Each profile = one X account.
echo  Posts are distributed evenly across all profiles.
echo ============================================================
echo.
pause
