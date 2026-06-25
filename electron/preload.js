const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Folder/file selection
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  selectXlsxFile: () => ipcRenderer.invoke('select-xlsx-file'),
  
  // Python crash handler
  onPythonCrash: (callback) => {
    ipcRenderer.on('python-crashed', (event, data) => callback(data));
  }
});
