// renderer.js - Frontend JavaScript for Unified App

// --- Global Variables ---
let selectedFolderPath = null;
let selectedFilePath = null;
const allViews = ['batch-view', 'single-view'];
const allNavs = ['nav-batch', 'nav-single'];

// --- Navigation ---
const navBatch = document.getElementById('nav-batch');
const navSingle = document.getElementById('nav-single');
const batchView = document.getElementById('batch-view');
const singleView = document.getElementById('single-view');

function showView(viewToShow, navToActivate) {
  // Hide all views
  allViews.forEach(id => document.getElementById(id).classList.add('hidden'));
  // Deactivate all nav buttons
  allNavs.forEach(id => document.getElementById(id).classList.remove('active'));
  
  // Show the selected view
  document.getElementById(viewToShow).classList.remove('hidden');
  // Activate the selected nav button
  document.getElementById(navToActivate).classList.add('active');
}

navBatch.addEventListener('click', () => showView('batch-view', 'nav-batch'));
navSingle.addEventListener('click', () => showView('single-view', 'nav-single'));

// --- Log Helper ---
function addLog(containerId, text, tag = null) {
  if (!text) return;
  const logContainer = document.getElementById(containerId);
  if (!logContainer) return;
  
  const line = document.createElement('div');
  line.textContent = text;
  
  if (tag === 'success') line.classList.add('log-success');
  else if (tag === 'error') line.classList.add('log-error');
  else if (tag === 'warning') line.classList.add('log-warning');
  else if (tag === 'info') line.classList.add('log-info');
  
  logContainer.appendChild(line);
  logContainer.scrollTop = logContainer.scrollHeight;
}

// ===================================================
// === LOGIC FOR BATCH FIXER (APP 1)
// ===================================================

const batchBrowseBtn = document.getElementById('batch-browse-btn');
const batchStartBtn = document.getElementById('batch-start-btn');
const batchClearBtn = document.getElementById('batch-clear-btn');
const batchFolderPath = document.getElementById('batch-folder-path');
const batchLog = document.getElementById('batch-log-container');
const batchProgressBar = document.querySelector('#batch-view .progress-bar');

batchBrowseBtn.addEventListener('click', async () => {
  const folderPath = await window.electronAPI.selectFolder();
  if (folderPath) {
    selectedFolderPath = folderPath;
    const displayPath = folderPath.length > 60 ? '...' + folderPath.substring(folderPath.length - 57) : folderPath;
    batchFolderPath.textContent = displayPath;
    batchFolderPath.classList.remove('text-zinc-400');
    batchFolderPath.classList.add('text-zinc-100');
    batchStartBtn.disabled = false;
  }
});

batchStartBtn.addEventListener('click', () => {
  const timezoneMode = document.querySelector('#batch-view input[name="timezone"]:checked')?.value;

  if (!selectedFolderPath) {
    addLog('batch-log-container', 'Please select a folder first.', 'error');
    return;
  }
  if (!timezoneMode) {
    addLog('batch-log-container', 'Please select a timezone option first.', 'error');
    return;
  }

  const confirmed = confirm(`Start processing photos in:\n${selectedFolderPath}\n\nTimezone mode: ${timezoneMode.toUpperCase()}\n\nThis will modify your photo files and organize JSONs. Continue?`);
  if (confirmed) {
    batchStartBtn.disabled = true;
    batchProgressBar.style.display = 'block';
    batchLog.innerHTML = '';
    
    window.electronAPI.startBatchScript({
      folderPath: selectedFolderPath,
      timezoneMode: timezoneMode,
    });
  }
});

batchClearBtn.addEventListener('click', () => {
  batchLog.innerHTML = '';
});

// Listen for batch logs
window.electronAPI.onBatchLog((message) => {
  if (message.tag === 'final_marker' && message.text === 'PROCESSING_COMPLETE') {
    addLog('batch-log-container', '🎉 Processing Complete!', 'success');
    batchStartBtn.disabled = false;
    batchProgressBar.style.display = 'none';
  } else {
    addLog('batch-log-container', message.text, message.tag);
  }
});

// Listen for batch script completion
window.electronAPI.onBatchComplete((result) => {
  console.log("Batch script process ended.");
  batchStartBtn.disabled = false; // Ensure button is re-enabled
  batchProgressBar.style.display = 'none';
});


// ===================================================
// === LOGIC FOR SINGLE EDITOR (APP 2)
// ===================================================

const singleBrowseBtn = document.getElementById('single-browse-btn');
const singleUpdateBtn = document.getElementById('single-update-btn');
const singleClearBtn = document.getElementById('single-clear-btn');
const singleFilePath = document.getElementById('single-file-path');
const singleDateEntry = document.getElementById('date-entry');
const singleTimeEntry = document.getElementById('time-entry');
const singleLog = document.getElementById('single-log-container');

singleBrowseBtn.addEventListener('click', async () => {
  const filePath = await window.electronAPI.selectFile();
  if (filePath) {
    selectedFilePath = filePath;
    const displayPath = filePath.length > 60 ? '...' + filePath.substring(filePath.length - 57) : filePath;
    singleFilePath.textContent = displayPath;
    singleFilePath.classList.remove('text-zinc-400');
    singleFilePath.classList.add('text-zinc-100');
    
    // Set default date/time based on current time
    const now = new Date();
    singleDateEntry.value = now.toISOString().split('T')[0]; // YYYY-MM-DD
    singleTimeEntry.value = now.toTimeString().split(' ')[0]; // HH:MM:SS
    
    singleUpdateBtn.disabled = false;
  }
});

singleUpdateBtn.addEventListener('click', () => {
  const dateStr = singleDateEntry.value;
  const timeStr = singleTimeEntry.value;

  if (!selectedFilePath) {
    addLog('single-log-container', 'Please select a media file first.', 'error');
    return;
  }
  if (!dateStr || !timeStr) {
    addLog('single-log-container', 'Please enter both a date and a time.', 'error');
    return;
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    addLog('single-log-container', 'Error: Date must be in YYYY-MM-DD format.', 'error');
    return;
  }
  if (!/^\d{2}:\d{2}:\d{2}$/.test(timeStr)) {
    addLog('single-log-container', 'Error: Time must be in HH:MM:SS format.', 'error');
    return;
  }

  const confirmed = confirm(`Update this file:\n${selectedFilePath}\n\nNew Date & Time:\n${dateStr} ${timeStr}\n\nContinue?`);
  if (confirmed) {
    singleUpdateBtn.disabled = true;
    singleLog.innerHTML = '';
    addLog('single-log-container', '🚀 Updating metadata...', 'success');
    
    window.electronAPI.startSingleScript({
      filePath: selectedFilePath,
      dateStr: dateStr,
      timeStr: timeStr
    });
  }
});

singleClearBtn.addEventListener('click', () => {
  singleLog.innerHTML = '';
});

// Listen for single editor logs
window.electronAPI.onSingleLog((message) => {
  if (message.tag === 'final_marker' && message.text === 'PROCESSING_COMPLETE') {
    addLog('single-log-container', '✅ Metadata Updated Successfully!', 'success');
    singleUpdateBtn.disabled = false;
  } else {
    addLog('single-log-container', message.text, message.tag);
  }
});

// Listen for single editor script completion
window.electronAPI.onSingleComplete((result) => {
  console.log("Single editor script process ended.");
  singleUpdateBtn.disabled = false; // Ensure button is re-enabled
});

