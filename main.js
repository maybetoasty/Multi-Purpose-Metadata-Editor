// main.js - Electron Main Process (Backend)

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { PythonShell } = require('python-shell');

// Define the path to our bundled assets (python scripts, exiftool)
const assetsPath = app.isPackaged
  ? path.join(process.resourcesPath, 'assets')
  : path.join(__dirname, 'assets');

// Function to get the correct exiftool executable path based on OS
function getExifToolPath() {
  const platform = process.platform;
  if (platform === 'win32') {
    return path.join(assetsPath, 'exiftool.exe');
  } else if (platform === 'darwin') { // macOS
    return path.join(assetsPath, 'exiftool');
  }
  return path.join(assetsPath, 'exiftool');
}

function createWindow() {
  const win = new BrowserWindow({
    width: 950, // Adjusted for no sidebar
    height: 950,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false // Easiest way to handle preload/fs
    },
    minWidth: 800, // Adjusted min width
    minHeight: 750,
  });

  win.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// --- IPC Handlers ---

// 1. Handle "select-folder" request (for Batch Fixer)
ipcMain.handle('select-folder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select Google Photos Takeout Folder'
  });
  if (canceled || filePaths.length === 0) return null;
  return filePaths[0];
});

// 2. Handle "select-file" request (for Single Editor)
ipcMain.handle('select-file', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openFile'],
    title: 'Select Media File',
    filters: [
      { name: 'Media Files', extensions: ['jpg', 'jpeg', 'heic', 'png', 'gif', 'webp', 'mp4', 'm4v', 'mov', 'JPG', 'HEIC', 'MP4', 'MOV'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  if (canceled || filePaths.length === 0) return null;
  return filePaths[0];
});


// 3. Handle "start-batch-script" request
ipcMain.on('start-batch-script', (event, { folderPath, timezoneMode }) => {
  const scriptName = 'batch_fixer_cli.py'; // Use new script name
  const scriptFullPath = path.join(assetsPath, scriptName);
  const exiftoolPath = getExifToolPath();

  const options = {
    mode: 'json',
    pythonPath: 'python3',
    scriptPath: assetsPath,
    args: [folderPath, timezoneMode, exiftoolPath],
  };

  if (!fs.existsSync(scriptFullPath)) {
       event.sender.send('on-batch-log', { tag: 'error', text: `[FATAL_ERROR] Python script not found at ${scriptFullPath}`});
       event.sender.send('on-batch-complete', { code: 1, signal: null });
       return;
  }
  if (!fs.existsSync(exiftoolPath)) {
      event.sender.send('on-batch-log', { tag: 'error', text: `[FATAL_ERROR] ExifTool not found at ${exiftoolPath}`});
      event.sender.send('on-batch-complete', { code: 1, signal: null });
      return;
  }

  const pyshell = new PythonShell(scriptName, options);

  pyshell.on('message', (message) => {
    event.sender.send('on-batch-log', message);
  });
  pyshell.on('stderr', (stderr) => {
    event.sender.send('on-batch-log', { tag: 'error', text: `[PYTHON_ERROR] ${stderr}` });
  });
  pyshell.end((err, code, signal) => {
    if (err) {
      event.sender.send('on-batch-log', { tag: 'error', text: `[PYTHON_SCRIPT_ERROR] ${err.message || err}`});
    }
    event.sender.send('on-batch-complete', { code, signal });
  });
});

// 4. Handle "start-single-script" request
ipcMain.on('start-single-script', (event, { filePath, dateStr, timeStr }) => {
  const scriptName = 'single_editor_cli.py'; // Use new script name
  const scriptFullPath = path.join(assetsPath, scriptName);
  const exiftoolPath = getExifToolPath();

  const options = {
    mode: 'json',
    pythonPath: 'python3',
    scriptPath: assetsPath,
    args: [filePath, dateStr, timeStr, exiftoolPath],
  };

  if (!fs.existsSync(scriptFullPath)) {
       event.sender.send('on-single-log', { tag: 'error', text: `[FATAL_ERROR] Python script not found at ${scriptFullPath}`});
       event.sender.send('on-single-complete', { code: 1, signal: null });
       return;
  }
  if (!fs.existsSync(exiftoolPath)) {
      event.sender.send('on-single-log', { tag: 'error', text: `[FATAL_ERROR] ExifTool not found at ${exiftoolPath}`});
      event.sender.send('on-single-complete', { code: 1, signal: null });
      return;
  }

  const pyshell = new PythonShell(scriptName, options);

  pyshell.on('message', (message) => {
    event.sender.send('on-single-log', message);
  });
  pyshell.on('stderr', (stderr) => {
    event.sender.send('on-single-log', { tag: 'error', text: `[PYTHON_ERROR] ${stderr}` });
  });
  pyshell.end((err, code, signal) => {
    if (err) {
      event.sender.send('on-single-log', { tag: 'error', text: `[PYTHON_SCRIPT_ERROR] ${err.message || err}`});
    }
    event.sender.send('on-single-complete', { code, signal });
  });
});

