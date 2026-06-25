# Troubleshooting Guide

## ⚠️ CRITICAL: Missing Visual C++ Redistributable

### Symptoms
- `ImportError: DLL load failed while importing greenlet`
- `ModuleNotFoundError: No module named '_greenlet'`
- `Unable to import playwright`
- Python package installation fails
- Setup.bat fails during package installation

### Root Cause
Fresh Windows installations are **missing Microsoft Visual C++ Redistributable** DLLs required by Python C extensions.

### Solution (5 minutes)
1. **Download:** https://aka.ms/vs/17/release/vc_redist.x64.exe
2. **Run** the installer
3. Click **"Install"**
4. **Restart your computer**
5. Run `setup.bat` again

### Why Is This Needed?
Python packages like `greenlet` (required by playwright) are C extensions that need Visual C++ runtime DLLs (`vcruntime140.dll`, `msvcp140.dll`) to load.

### Detailed Guide
See **FIX_VC_REDIST_ERROR.md** for complete instructions.

---

## "Failed to start Python backend" Error

### Symptoms
- Error dialog: "Startup Error - Failed to start Python backend: Python backend failed to start within timeout"
- Electron app closes after showing error

### Common Causes & Solutions

#### 1. Port 8765 Already in Use (Most Common)

**Cause:** A previous instance of the Python backend is still running.

**Solution:**
```bash
# Run the cleanup script
cleanup.bat
```

Or manually:
```bash
# Find and kill process on port 8765
netstat -ano | findstr :8765
taskkill /F /PID [process_id]
```

#### 2. Python Not Installed or Not in PATH

**Check Python:**
```bash
python --version
```

**Solution:** Install Python 3.8+ and ensure it's added to PATH.

#### 3. Missing Python Dependencies

**Check if packages are installed:**
```bash
python -m pip list | findstr "fastapi uvicorn playwright"
```

**Solution:**
```bash
pip install -r python_backend/requirements.txt
```

#### 4. Playwright Browsers Not Installed

**Check installation:**
```bash
python -m playwright install chromium
```

**Solution:**
```bash
# Install browsers
python -m playwright install
```

#### 5. Firewall Blocking Port 8765

**Solution:** Add exception for Python in Windows Firewall or temporarily disable to test.

---

## Updated start.bat

The new `start.bat` includes automatic cleanup:
- Checks for existing processes on port 8765
- Kills them automatically
- Waits for port to be released
- Then starts the app

If issues persist after using the updated script, run `cleanup.bat` manually first.

---

## Manual Testing

Test the Python backend separately:
```bash
# Start Python backend manually
python python_backend/main.py
```

Expected output:
```
Starting uvicorn server on http://127.0.0.1:8765
Started server process [XXXX]
Waiting for application startup...
Application startup complete.
Uvicorn running on http://127.0.0.1:8765
```

If this works, the issue is with Electron communication. If not, check the error message.

---

## Checking Health Endpoint

Once backend is running:
```bash
# Test health endpoint
curl http://localhost:8765/health
```

Expected response: `{"status":"ok"}`

---

## Still Having Issues?

1. Check logs:
   - `logs/app.log` - Python backend logs
   - Console output when running `start.bat`

2. Run `setup.bat` again to ensure all dependencies are installed

3. Restart your computer to clear any stuck processes

4. Make sure no antivirus is blocking Python or Electron
