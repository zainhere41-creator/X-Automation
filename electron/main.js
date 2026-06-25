const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;

// ============================================================================
// Python Process Management
// ============================================================================

async function startPython() {
  return new Promise((resolve, reject) => {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
    const scriptPath = path.join(__dirname, '..', 'python_backend', 'main.py');
    
    console.log('========================================');
    console.log('Starting Python backend...');
    console.log(`Python: ${pythonPath}`);
    console.log(`Script: ${scriptPath}`);
    console.log('========================================');
    
    pythonProcess = spawn(pythonPath, [scriptPath], {
      cwd: path.join(__dirname, '..'),
      stdio: ['ignore', 'pipe', 'pipe']
    });
    
    pythonProcess.stdout.on('data', (data) => {
      console.log(`Python: ${data}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
      const errorMsg = data.toString();
      console.error(`Python Error: ${errorMsg}`);
      
      // Check for port already in use error
      if (errorMsg.includes('10048') || errorMsg.includes('address already in use')) {
        console.error('Port 8765 is already in use. Another instance may be running.');
      }
    });
    
    pythonProcess.on('exit', (code) => {
      console.error(`Python process exited with code ${code}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('python-crashed', { code });
      }
    });
    
    pythonProcess.on('error', (err) => {
      console.error('Failed to start Python process:', err);
      reject(err);
    });
    
    // Poll for Python backend to be ready
    let attempts = 0;
    const maxAttempts = 40; // Increased from 15 to 40 (20 seconds total)
    
    const checkHealth = () => {
      const req = http.get('http://127.0.0.1:8765/health', (res) => {
        if (res.statusCode === 200) {
          console.log('========================================');
          console.log('✓ Python backend ready and healthy!');
          console.log('✓ Health endpoint responded successfully');
          console.log('========================================');
          resolve();
        } else {
          console.log(`Backend returned status ${res.statusCode}, retrying...`);
          attempts++;
          if (attempts >= maxAttempts) {
            reject(new Error('Python backend failed to start within timeout'));
          } else {
            setTimeout(checkHealth, 500);
          }
        }
      });
      
      req.on('error', (err) => {
        console.log(`Waiting for backend... (attempt ${attempts + 1}/${maxAttempts})`);
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error('Python backend failed to start within timeout'));
        } else {
          setTimeout(checkHealth, 500);
        }
      });
    };
    
    setTimeout(checkHealth, 1000); // Wait 1 second before first check
  });
}

function killPython() {
  if (pythonProcess) {
    console.log('Terminating Python process...');
    const proc = pythonProcess;
    pythonProcess = null;
    
    proc.kill('SIGTERM');
    
    // Force kill after 3 seconds
    setTimeout(() => {
      if (proc && !proc.killed) {
        console.log('Force killing Python process...');
        proc.kill('SIGKILL');
      }
    }, 3000);
  }
}

// ============================================================================
// Window Management
// ============================================================================

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 700,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0f0f0f',
    title: 'X Posting Automation',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ============================================================================
// IPC Handlers
// ============================================================================

ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Chrome Profiles Folder'
  });
  
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('select-xlsx-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Excel Files', extensions: ['xlsx'] },
      { name: 'All Files', extensions: ['*'] }
    ],
    title: 'Select Excel File'
  });
  
  return result.canceled ? null : result.filePaths[0];
});

// ============================================================================
// App Lifecycle
// ============================================================================

app.whenReady().then(async () => {
  try {
    await startPython();
    createWindow();
  } catch (error) {
    dialog.showErrorBox(
      'Startup Error',
      `Failed to start Python backend:\n\n${error.message}\n\nPlease ensure Python and required packages are installed.`
    );
    app.quit();
  }
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('will-quit', () => {
  killPython();
});

app.on('window-all-closed', () => {
  killPython();
  app.quit();
});

// Handle process termination
process.on('SIGTERM', () => {
  killPython();
  app.quit();
});

process.on('SIGINT', () => {
  killPython();
  app.quit();
});
