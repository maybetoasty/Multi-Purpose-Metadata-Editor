// preload.js - Secure bridge between UI and Node.js backend

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // --- Asynchronous, one-time calls (invoke/handle) ---
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  selectFile: () => ipcRenderer.invoke('select-file'),

  // --- Event-based, one-way calls (send) ---
  startBatchScript: (args) => ipcRenderer.send('start-batch-script', args),
  startSingleScript: (args) => ipcRenderer.send('start-single-script', args),

  // --- Event listeners (on) ---
  onBatchLog: (callback) =>
    ipcRenderer.on('on-batch-log', (_event, value) => callback(value)),
  onBatchComplete: (callback) =>
    ipcRenderer.on('on-batch-complete', (_event, value) => callback(value)),
    
  onSingleLog: (callback) =>
    ipcRenderer.on('on-single-log', (_event, value) => callback(value)),
  onSingleComplete: (callback) =>
    ipcRenderer.on('on-single-complete', (_event, value) => callback(value)),
});

