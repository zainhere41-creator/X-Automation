// API Base URL
const API_BASE = 'http://127.0.0.1:8765';

// Global state
let pollingIntervals = {};
let currentDataMode = null;  // 'xlsx'
let campaignConfig = {  // Store campaign configuration
  profiles: [],
  posts: [],
  dataSource: '',
  totalPosts: 0,
  basePort: 9222
};

// HTML escaping to prevent XSS
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================================
// API Client
// ============================================================================

async function apiCall(method, path, body = null) {
  try {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    
    if (body) {
      options.body = JSON.stringify(body);
    }
    
    const response = await fetch(`${API_BASE}${path}`, options);
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'API Error');
    }
    
    return data;
  } catch (error) {
    console.error(`API call failed: ${method} ${path}`, error);
    showToast('error', error.message);
    throw error;
  }
}

// ============================================================================
// Tab Navigation
// ============================================================================

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    showTab(tab);
  });
});

function showTab(tabName) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(tab => {
    tab.classList.remove('active');
  });
  
  // Deactivate all nav buttons
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  
  // Show selected tab
  document.getElementById(`tab-${tabName}`).classList.add('active');
  document.querySelector(`.nav-btn[data-tab="${tabName}"]`).classList.add('active');
}

// ============================================================================
// Polling System
// ============================================================================

function startPolling() {
  // Profile status every 3 seconds
  pollingIntervals.profiles = setInterval(async () => {
    try {
      const status = await apiCall('GET', '/profiles/status');
      updateProfileCards(status.profiles);
    } catch (e) {
      // Ignore errors during polling
    }
  }, 3000);
  
  // Queue stats every 5 seconds
  pollingIntervals.queue = setInterval(async () => {
    try {
      const stats = await apiCall('GET', '/queue/status');
      updateQueueStats(stats);
    } catch (e) {
      // Ignore errors during polling
    }
  }, 5000);
  
  // Logs every 3 seconds
  pollingIntervals.logs = setInterval(async () => {
    try {
      const data = await apiCall('GET', '/logs/recent');
      updateLogPanel(data.logs);
    } catch (e) {
      // Ignore errors during polling
    }
  }, 3000);
  
  // Automation status every 5 seconds
  pollingIntervals.automation = setInterval(async () => {
    try {
      const status = await apiCall('GET', '/automation/status');
      updateAutomationStatus(status);
    } catch (e) {
      // Ignore errors during polling
    }
  }, 5000);
}

function stopPolling() {
  for (const key in pollingIntervals) {
    clearInterval(pollingIntervals[key]);
  }
  pollingIntervals = {};
}

// ============================================================================
// UI Update Functions
// ============================================================================

function updateProfileCards(profiles) {
  const grid = document.getElementById('campaign-grid');
  
  if (!profiles || Object.keys(profiles).length === 0) {
    grid.innerHTML = '<div class="empty-message">No campaigns active</div>';
    return;
  }
  
  grid.innerHTML = '';
  
  for (const [profileId, data] of Object.entries(profiles)) {
    const card = document.createElement('div');
    card.className = 'campaign-card';
    card.dataset.profileId = profileId;
    
    const statusDot = data.running ? 
      '<span class="status-dot running"></span>' :
      '<span class="status-dot stopped"></span>';
    
    const profileName = data.folder_name || `Campaign ${profileId}`;
    
    card.innerHTML = `
      <div class="campaign-header">
        <h3>${profileName}</h3>
        ${statusDot}
        <button class="btn-edit-campaign" data-profile-id="${profileId}" title="Load More Posts (XLSX)">✏️</button>
        <button class="btn-delete-campaign" data-profile-id="${profileId}" title="Delete Campaign">🗑️</button>
      </div>
      <div class="campaign-info">
        <div class="info-row">
          <span class="info-label">Port:</span>
          <span class="info-value">${data.port}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Status:</span>
          <span class="info-value">${data.running ? 'Running' : 'Stopped'}</span>
        </div>
      </div>
      <div class="campaign-action clickable">
        <span class="view-details">View Details →</span>
      </div>
    `;
    
    // Make view details clickable
    const actionDiv = card.querySelector('.campaign-action');
    actionDiv.addEventListener('click', () => {
      showTab('campaigns');
      loadCampaignDetails();
    });
    
    // Add delete button handler
    const deleteBtn = card.querySelector('.btn-delete-campaign');
    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await handleDeleteCampaign(profileId, profileName);
    });
    
    // Add edit button handler - load more posts from new XLSX
    const editBtn = card.querySelector('.btn-edit-campaign');
    editBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const file = await window.electronAPI.selectXlsxFile();
      if (!file) return;
      
      try {
        const result = await apiCall('POST', '/setup/xlsx/append', { xlsx_path: file });
        showToast('success', `Added ${result.posts_added} posts (${result.total_pending} pending, ${result.total_sheets} sheets total)`);
        updateQueueStats(await apiCall('GET', '/queue/status'));
      } catch (error) {
        showToast('error', 'Failed to load XLSX: ' + (error.message || error));
      }
    });
    
    grid.appendChild(card);
  }
}

function updateQueueStats(stats) {
  document.getElementById('stat-total').textContent = stats.total || 0;
  document.getElementById('stat-done').textContent = stats.done || 0;
  document.getElementById('stat-pending').textContent = stats.pending || 0;
  document.getElementById('stat-failed').textContent = stats.failed || 0;
  
  // Update sheet tracking display
  const sheetsEl = document.getElementById('stat-sheets');
  if (sheetsEl) {
    sheetsEl.textContent = `${stats.completed_sheets || 0}/${stats.total_sheets || 0}`;
  }
  
  const sheetInfo = document.getElementById('sheet-tracking-info');
  if (sheetInfo) {
    if (stats.total_sheets > 0) {
      sheetInfo.textContent = `Current: ${stats.current_sheet || 'None'} | Remaining: ${stats.sheets_remaining || 0} sheets`;
      sheetInfo.classList.remove('hidden');
    } else {
      sheetInfo.textContent = '';
      sheetInfo.classList.add('hidden');
    }
  }
  
  // Also update setup tab stats
  document.getElementById('setup-stat-total').textContent = stats.total || 0;
  document.getElementById('setup-stat-pending').textContent = stats.pending || 0;
  document.getElementById('setup-stat-done').textContent = stats.done || 0;
  document.getElementById('setup-stat-failed').textContent = stats.failed || 0;
}

function updateLogPanel(logs) {
  const panel = document.getElementById('log-panel');
  panel.innerHTML = '';
  
  if (!logs || logs.length === 0) {
    panel.innerHTML = '<div class="empty-message">No logs yet</div>';
    return;
  }
  
  for (const line of logs) {
    const div = document.createElement('div');
    div.className = 'log-line';
    
    if (line.includes('ERROR')) {
      div.classList.add('log-error');
    } else if (line.includes('SUCCESS')) {
      div.classList.add('log-success');
    } else if (line.includes('SKIP') || line.includes('WARNING')) {
      div.classList.add('log-warning');
    }
    
    div.textContent = line;
    panel.appendChild(div);
  }
  
  // Auto-scroll to bottom
  panel.scrollTop = panel.scrollHeight;
}

function updateAutomationStatus(status) {
  const indicator = document.getElementById('scheduler-status');
  indicator.textContent = status.running ? 'Running' : 'Stopped';
  indicator.className = status.running ? 'status-running' : 'status-stopped';
  
  const timer = document.getElementById('next-run-timer');
  if (status.next_run) {
    const nextRun = new Date(status.next_run);
    const now = new Date();
    const diffMinutes = Math.floor((nextRun - now) / 60000);
    
    if (diffMinutes > 0) {
      timer.textContent = `${diffMinutes} min`;
    } else {
      timer.textContent = 'Soon';
    }
  } else {
    timer.textContent = '--';
  }
}

// ============================================================================
// Campaign Details Functions
// ============================================================================

async function loadCampaignDetails() {
  const container = document.getElementById('campaigns-container');
  container.innerHTML = '<div class="loading-message">Loading campaign details...</div>';
  
  try {
    // Get profiles status
    const profilesData = await apiCall('GET', '/profiles/status');
    
    // Get queue details
    const queueData = await apiCall('GET', '/campaigns/details');
    
    if (!profilesData.profiles || Object.keys(profilesData.profiles).length === 0) {
      container.innerHTML = '<div class="empty-message">No campaigns to display. Launch profiles first.</div>';
      return;
    }
    
    container.innerHTML = '';
    
    // Create detailed cards for each profile/campaign
    for (const [profileId, profileInfo] of Object.entries(profilesData.profiles)) {
      const campaignDetails = queueData.campaigns[profileId] || {
        pending: 0,
        done: 0,
        failed: 0,
        last_post: null,
        tasks: []
      };
      
      const card = document.createElement('div');
      card.className = 'campaign-detail-card';
      
      const statusClass = profileInfo.running ? 'status-running' : 'status-stopped';
      const statusText = profileInfo.running ? 'Running' : 'Stopped';
      
      // Get profile name from folder_name if available
      const profileName = profileInfo.folder_name || `Campaign ${profileId}`;
      
      card.innerHTML = `
        <div class="campaign-detail-header">
          <div class="campaign-title">
            <h2>${profileName}</h2>
            <span class="campaign-id">Profile ID: ${profileId}</span>
          </div>
          <div class="campaign-header-actions">
            <span class="campaign-status ${statusClass}">${statusText}</span>
            <button class="btn-delete-campaign-detail" data-profile-id="${profileId}" title="Delete Campaign">🗑️ Delete Campaign</button>
          </div>
        </div>
        
        <div class="campaign-detail-body">
          <div class="detail-section">
            <h3>Connection Info</h3>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Port Number:</span>
                <span class="detail-value">${profileInfo.port}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">CDP URL:</span>
                <span class="detail-value">http://localhost:${profileInfo.port}</span>
              </div>
            </div>
          </div>
          
          <div class="detail-section">
            <h3>Post Data Stats</h3>
            <div class="stats-grid">
              <div class="stat-card stat-pending">
                <span class="stat-number">${campaignDetails.pending}</span>
                <span class="stat-text">Pending</span>
              </div>
              <div class="stat-card stat-done">
                <span class="stat-number">${campaignDetails.done}</span>
                <span class="stat-text">Completed</span>
              </div>
              <div class="stat-card stat-failed">
                <span class="stat-number">${campaignDetails.failed}</span>
                <span class="stat-text">Failed</span>
              </div>
            </div>
          </div>
          
          <div class="detail-section">
            <h3>Automation Status</h3>
            <div class="automation-info">
              ${campaignDetails.last_post ? `
                <div class="detail-item">
                  <span class="detail-label">Last Post:</span>
                  <span class="detail-value">${new Date(campaignDetails.last_post).toLocaleString()}</span>
                </div>
              ` : `
                <div class="detail-item">
                  <span class="detail-label">Last Post:</span>
                  <span class="detail-value">Never</span>
                </div>
              `}
              <div class="detail-item">
                <span class="detail-label">Next Scheduled:</span>
                <span class="detail-value" id="next-post-${profileId}">--</span>
              </div>
            </div>
          </div>
          
          ${campaignDetails.tasks && campaignDetails.tasks.length > 0 ? `
            <div class="detail-section">
              <h3>Recent Tasks</h3>
              <div class="tasks-list">
                ${campaignDetails.tasks.map(task => `
                  <div class="task-item task-${escapeHtml(task.status)}">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    <div class="task-meta">
                      <span class="task-status">${escapeHtml(task.status.toUpperCase())}</span>
                      ${task.posted_at ? `<span class="task-time">${new Date(task.posted_at).toLocaleString()}</span>` : ''}
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      `;
      
      // Add delete button handler
      const deleteBtn = card.querySelector('.btn-delete-campaign-detail');
      deleteBtn.addEventListener('click', async () => {
        await handleDeleteCampaign(profileId, profileName);
        // Refresh the details view after deletion
        loadCampaignDetails();
      });
      
      container.appendChild(card);
    }
    
  } catch (error) {
    container.innerHTML = `<div class="error-message">Failed to load campaign details: ${error.message}</div>`;
  }
}

// Refresh button handler
document.addEventListener('DOMContentLoaded', () => {
  const refreshBtn = document.getElementById('btn-refresh-campaigns');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadCampaignDetails();
      showToast('success', 'Campaign details refreshed');
    });
  }
});

// ============================================================================
// Control Button Handlers
// ============================================================================

document.getElementById('btn-launch-profiles').addEventListener('click', async (event) => {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Launching...';
  
  try {
    const result = await apiCall('POST', '/profiles/launch');
    showToast('success', `Launched ${result.launched.length} profiles`);
    if (result.failed.length > 0) {
      showToast('warning', `Failed to launch: ${result.failed.join(', ')}`);
    }
  } catch (error) {
    showToast('error', 'Failed to launch profiles');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Launch Profiles';
  }
});

document.getElementById('btn-detect-profiles').addEventListener('click', async (event) => {
  const btn = event.target;
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = 'Detecting...';
  
  try {
    const result = await apiCall('POST', '/profiles/detect');
    
    if (result.count > 0) {
      showToast('success', `✓ Found ${result.count} profile(s) already running! They are now connected.`);
    } else {
      showToast('info', 'No running profiles found. Click "Launch Profiles" to start them.');
    }
    
    // Refresh the UI to show updated status
    setTimeout(async () => {
      try {
        const status = await apiCall('GET', '/profiles/status');
        updateProfileCards(status.profiles);
      } catch (e) {
        // Ignore polling errors
      }
    }, 500);
    
  } catch (error) {
    showToast('error', 'Failed to detect profiles: ' + error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
});

document.getElementById('btn-start-automation').addEventListener('click', async () => {
  try {
    // Auto-save sheets_per_run from main tab before starting
    const sheetsPerRun = parseInt(document.getElementById('sheets-per-run')?.value || 1);
    await apiCall('POST', '/settings/save', { sheets_per_run: sheetsPerRun });
    
    const settings = await apiCall('GET', '/settings');
    
    const config = {
      mode: settings.schedule_mode,
      interval_minutes: settings.interval_minutes,
      times: settings.fixed_times,
      min_minutes: settings.random_min_minutes,
      max_minutes: settings.random_max_minutes
    };
    
    const result = await apiCall('POST', '/automation/start', config);
    showToast('success', `Automation started (${settings.sheets_per_run} sheet(s) per run)`);
  } catch (error) {
    showToast('error', 'Failed to start automation');
  }
});

document.getElementById('btn-stop-automation').addEventListener('click', async () => {
  try {
    await apiCall('POST', '/automation/stop');
    showToast('success', 'Automation stopped');
  } catch (error) {
    showToast('error', 'Failed to stop automation');
  }
});

document.getElementById('btn-shutdown-profiles').addEventListener('click', async () => {
  const confirmed = confirm('Are you sure you want to shut down all Chrome profiles?');
  if (!confirmed) return;
  
  try {
    await apiCall('POST', '/profiles/shutdown');
    showToast('success', 'All profiles shut down');
  } catch (error) {
    showToast('error', 'Failed to shutdown profiles');
  }
});

document.getElementById('btn-run-now').addEventListener('click', async (event) => {
  const btn = event.target;
  
  // Auto-save sheets_per_run from main tab
  const sheetsPerRun = parseInt(document.getElementById('sheets-per-run')?.value || 1);
  await apiCall('POST', '/settings/save', { sheets_per_run: sheetsPerRun });
  
  // Check if profiles are running
  try {
    const status = await apiCall('GET', '/profiles/status');
    const runningProfiles = Object.values(status.profiles).filter(p => p.running);
    
    if (runningProfiles.length === 0) {
      showToast('warning', 'No profiles are running. Please launch profiles first.');
      return;
    }
    
    // Check if there are pending tasks
    const stats = await apiCall('GET', '/queue/status');
    if (stats.pending === 0) {
      showToast('warning', 'No pending tasks in queue. Go to Setup tab and Reset Queue to reload posts.');
      return;
    }
    
    // Confirm with user
    const confirmed = confirm(`Run manual post now?\n\nProfiles running: ${runningProfiles.length}\nPending tasks: ${stats.pending}\n\nThis will post one message per profile.\n\nMake sure:\n✓ Profiles are logged into X/Twitter\n✓ Chrome windows are visible (not minimized)\n✓ You have stable internet connection`);
    if (!confirmed) return;
    
    btn.disabled = true;
    btn.textContent = 'Posting... (check Chrome window)';
    
    const result = await apiCall('POST', '/automation/run-now');
    
    const newStats = await apiCall('GET', '/queue/status');
    const postsCompleted = stats.done !== newStats.done ? (newStats.done - stats.done) : 0;
    
    let message = '';
    if (postsCompleted > 0) {
      message = `${postsCompleted} post(s) completed!`;
    } else {
      message = 'Cycle completed.';
    }
    
    if (newStats.sheets_remaining > 0) {
      message += ` → ${newStats.current_sheet} loaded (${newStats.sheets_remaining} sheets remaining)`;
    } else if (newStats.pending === 0 && newStats.done > 0) {
      message += ' → All sheets completed!';
    }
    
    showToast('success', message);
  } catch (error) {
    showToast('error', 'Manual post failed: ' + error.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '▶ Run Now (Manual Post)';
  }
});

// Run Now Help Button
document.getElementById('btn-run-now-help').addEventListener('click', () => {
  const helpText = `
🔧 RUN NOW TROUBLESHOOTING GUIDE

✅ BEFORE CLICKING "RUN NOW":
1. Profiles must be RUNNING (green dot)
2. Must be LOGGED IN to X/Twitter
3. Must have PENDING tasks in queue
4. Chrome windows must be VISIBLE (not minimized)

❌ COMMON ISSUES:

1️⃣ "No profiles running"
   → Click "Launch Profiles" first
   → Wait for Chrome windows to open
   → Log into X/Twitter manually

2️⃣ "No pending tasks"
   → Go to Setup tab
   → Click "Reset Queue" button
   → Or load new XLSX file

3️⃣ "Page timeout" error
   → Check internet connection
   → Make sure X.com loads in browser
   → May need to disable CloudFlare protection

4️⃣ Posts not appearing
   → Check "Live Logs" at bottom
   → Look for error messages
   → See logs/app.log for details
   → Screenshots saved to logs/ folder

5️⃣ "Tweet box not found"
   → X/Twitter UI may have changed
   → Update config/selectors.json
   → See DEBUG_RUN_NOW.md file

📋 HOW TO DEBUG:
1. Watch Chrome window when clicking Run Now
2. Check "Live Logs" section for errors
3. Look at Queue Status numbers (Done/Failed)
4. Read logs/app.log for full details
5. Check logs/ folder for screenshots

📚 DETAILED GUIDE:
See DEBUG_RUN_NOW.md file in the application folder for complete troubleshooting steps.

✨ SUCCESS SIGNS:
• You see tweet being typed in Chrome
• Tweet appears on X timeline
• "Done" number increases in Queue Status
• "SUCCESS" messages in Live Logs
  `;
  
  alert(helpText);
});

// ============================================================================
// Advanced Settings Tab
// ============================================================================

// Schedule mode radio buttons
document.querySelectorAll('input[name="schedule-mode"]').forEach(radio => {
  radio.addEventListener('change', (e) => {
    const mode = e.target.value;
    document.getElementById('interval-config').classList.toggle('hidden', mode !== 'interval');
    document.getElementById('fixed-config').classList.toggle('hidden', mode !== 'fixed');
    document.getElementById('random-config').classList.toggle('hidden', mode !== 'random');
  });
});

// Concurrency slider
document.getElementById('concurrency-slider').addEventListener('input', (e) => {
  const value = parseInt(e.target.value);
  document.getElementById('concurrency-value').textContent = value;
  document.getElementById('concurrency-warning').classList.toggle('hidden', value < 4);
});

// Save Settings
document.getElementById('btn-save-settings').addEventListener('click', async () => {
  try {
    const settings = {
      concurrency: parseInt(document.getElementById('concurrency-slider').value),
      post_delay_min: parseInt(document.getElementById('post-delay-min').value),
      post_delay_max: parseInt(document.getElementById('post-delay-max').value),
      pre_submit_delay_min: parseFloat(document.getElementById('pre-submit-delay-min').value),
      pre_submit_delay_max: parseFloat(document.getElementById('pre-submit-delay-max').value),
      cycle_cooldown: parseInt(document.getElementById('cycle-cooldown').value),
      base_port: parseInt(document.getElementById('base-port').value),
      typing_delay_min: parseInt(document.getElementById('typing-delay-min').value),
      typing_delay_max: parseInt(document.getElementById('typing-delay-max').value),
      title_dots_count: parseInt(document.getElementById('title-dots-count').value),
      schedule_mode: document.querySelector('input[name="schedule-mode"]:checked').value,
      interval_minutes: parseInt(document.getElementById('interval-minutes').value),
      fixed_times: document.getElementById('fixed-times').value.split(',').map(s => s.trim()).filter(s => s),
      random_min_minutes: parseInt(document.getElementById('random-min').value),
      random_max_minutes: parseInt(document.getElementById('random-max').value),
      sheets_per_run: parseInt(document.getElementById('sheets-per-run')?.value || 1)
    };
    
    await apiCall('POST', '/settings/save', settings);
    showToast('success', 'Settings saved');
  } catch (error) {
    showToast('error', 'Failed to save settings');
  }
});

// Reset Settings
document.getElementById('btn-reset-settings').addEventListener('click', () => {
  document.getElementById('concurrency-slider').value = 2;
  document.getElementById('concurrency-value').textContent = '2';
  document.getElementById('post-delay-min').value = 3;
  document.getElementById('post-delay-max').value = 8;
  document.getElementById('pre-submit-delay-min').value = 1.0;
  document.getElementById('pre-submit-delay-max').value = 2.0;
  document.getElementById('cycle-cooldown').value = 30;
  document.getElementById('base-port').value = 9222;
  document.getElementById('typing-delay-min').value = 80;
  document.getElementById('typing-delay-max').value = 180;
  document.getElementById('title-dots-count').value = 2;
  document.querySelector('input[name="schedule-mode"][value="interval"]').checked = true;
  document.getElementById('interval-minutes').value = 30;
  document.getElementById('fixed-times').value = '';
  document.getElementById('random-min').value = 20;
  document.getElementById('random-max').value = 60;
  document.getElementById('concurrency-warning').classList.add('hidden');
  
  // Show mode config
  document.getElementById('interval-config').classList.remove('hidden');
  document.getElementById('fixed-config').classList.add('hidden');
  document.getElementById('random-config').classList.add('hidden');
});

// ============================================================================
// Setup Tab
// ============================================================================

// Initialize Setup Tab Event Listeners on DOM Load
document.addEventListener('DOMContentLoaded', () => {
  // Browse Profiles Folder
  const btnBrowseProfiles = document.getElementById('btn-browse-profiles');
  if (btnBrowseProfiles) {
    btnBrowseProfiles.addEventListener('click', async () => {
      const folder = await window.electronAPI.selectFolder();
      if (folder) {
        document.getElementById('profiles-folder-input').value = folder;
        
        try {
          const result = await apiCall('POST', '/setup/profiles', { profiles_root: folder });
          const resultDiv = document.getElementById('profiles-result');
          resultDiv.classList.remove('hidden');
          resultDiv.className = 'setup-result success';
          
          // Check if any profiles need setup
          const needSetup = Object.values(result.readiness || {}).filter(r => !r.ready);
          
          if (needSetup.length > 0) {
            // Show warning about profiles needing setup
            resultDiv.className = 'setup-result warning';
            let message = `Found ${result.count} accounts: ${result.folder_names.join(', ')}\n\n`;
            message += `⚠️ ${needSetup.length} profile(s) need setup:\n`;
            needSetup.forEach(status => {
              message += `  • ${status.folder_name}: ${status.message}\n`;
            });
            message += `\nClick "Launch Profiles" and log into X in the Chrome windows that open.`;
            resultDiv.textContent = message;
            resultDiv.style.whiteSpace = 'pre-line';
          } else {
            // All profiles ready
            resultDiv.textContent = `✓ Found ${result.count} accounts: ${result.folder_names.join(', ')} - All profiles ready!`;
          }
        } catch (error) {
          const resultDiv = document.getElementById('profiles-result');
          resultDiv.classList.remove('hidden');
          resultDiv.className = 'setup-result error';
          resultDiv.textContent = 'Error: ' + error.message;
        }
      }
    });
  }

  // Helper: handle XLSX load (used by both initial and append)
  async function loadXlsxFile(file, appendMode) {
    const endpoint = appendMode ? '/setup/xlsx/append' : '/setup/xlsx';
    const result = await apiCall('POST', endpoint, { xlsx_path: file });
    
    const resultDiv = document.getElementById('xlsx-result');
    resultDiv.classList.remove('hidden');
    resultDiv.className = 'setup-result success';
    
    if (appendMode) {
      resultDiv.textContent = `Appended ${result.posts_added} posts (${result.total_pending} pending, ${result.total_sheets} sheets total)`;
    } else {
      let summary = `Loaded ${result.total_sheets} sheets · ${result.total_posts} posts total`;
      if (result.skipped_count > 0) {
        summary += ` · ${result.skipped_count} rows skipped`;
      }
      resultDiv.textContent = summary;
      
      // Show skipped rows warning if any
      if (result.skipped && result.skipped.length > 0) {
        resultDiv.className = 'setup-result warning';
        let skippedDetails = summary + '\n\nSkipped rows:\n';
        result.skipped.forEach(s => {
          skippedDetails += `  • ${s.sheet} row ${s.row}: ${s.reason}\n`;
        });
        resultDiv.textContent = skippedDetails;
        resultDiv.style.whiteSpace = 'pre-line';
      }
      
      // Show sheet preview
      const previewTable = document.getElementById('preview-table');
      const tbody = document.getElementById('preview-tbody');
      tbody.innerHTML = '';
      result.preview.forEach((sheet, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${sheet.sheet}</td><td>${sheet.posts}</td><td>${sheet.status}</td>`;
        tbody.appendChild(row);
      });
      previewTable.classList.remove('hidden');
    }
    
    campaignConfig.dataSource = file;
    currentDataMode = 'xlsx';
    
    // Refresh queue stats
    const stats = await apiCall('GET', '/queue/status');
    updateQueueStats(stats);
    
    document.getElementById('section-append').classList.remove('hidden');
    document.getElementById('section-continue').classList.remove('hidden');
  }

  // Browse XLSX File (initial load)
  const btnBrowseXlsx = document.getElementById('btn-browse-xlsx');
  if (btnBrowseXlsx) {
    btnBrowseXlsx.addEventListener('click', async () => {
      const file = await window.electronAPI.selectXlsxFile();
      if (file) {
        try {
          await loadXlsxFile(file, false);
        } catch (error) {
          const resultDiv = document.getElementById('xlsx-result');
          resultDiv.classList.remove('hidden');
          resultDiv.className = 'setup-result error';
          resultDiv.textContent = 'Error: ' + error.message;
          document.getElementById('preview-table').classList.add('hidden');
        }
      }
    });
  }

  // Load Another XLSX (append mode)
  const btnLoadAnotherXlsx = document.getElementById('btn-load-another-xlsx');
  if (btnLoadAnotherXlsx) {
    btnLoadAnotherXlsx.addEventListener('click', async () => {
      const file = await window.electronAPI.selectXlsxFile();
      if (file) {
        try {
          const appendMode = document.getElementById('append-mode-toggle').checked;
          await loadXlsxFile(file, appendMode);
        } catch (error) {
          showToast('error', 'Failed to load XLSX: ' + error.message);
        }
      }
    });
  }
});

// Continue button - Navigate to review page (wrapped in DOMContentLoaded)
document.addEventListener('DOMContentLoaded', () => {
  const continueBtn = document.getElementById('btn-continue');
  if (continueBtn) {
    continueBtn.addEventListener('click', async () => {
      try {
        // Get profiles status
        const profilesData = await apiCall('GET', '/profiles/status');
        const launchedProfiles = profilesData.profiles || {};
        
        // Also check if profiles folder has been configured via setup
        const profilesFolderInput = document.getElementById('profiles-folder-input');
        const hasProfilesFolder = profilesFolderInput && profilesFolderInput.value.trim() !== '';
        
        // Check if we have either launched profiles OR a configured profiles folder
        if (Object.keys(launchedProfiles).length === 0 && !hasProfilesFolder) {
          showToast('warning', 'Please select a profiles folder first in Step 1');
          return;
        }
        
        // Get settings for port and scheduling info
        const settings = await apiCall('GET', '/settings');
        
        // Get queue status for posts
        let stats = await apiCall('GET', '/queue/status');
        
        if (stats.total === 0) {
          showToast('warning', 'Please load post data first in Step 2');
          return;
        }
        
        // If profiles exist, use them; otherwise create placeholder data from folder input
        let profiles;
        if (Object.keys(launchedProfiles).length > 0) {
          // Use launched profiles
          profiles = launchedProfiles;
        } else {
          // Create placeholder profiles from the profiles result
          // We need to re-check the profiles from setup to get the count
          const profilesResult = document.getElementById('profiles-result');
          if (profilesResult && profilesResult.textContent) {
            // Extract profile count from the result text (e.g., "Found 2 accounts")
            const match = profilesResult.textContent.match(/Found (\d+) accounts/);
            if (match) {
              const count = parseInt(match[1]);
              profiles = {};
              for (let i = 1; i <= count; i++) {
                profiles[i] = {
                  folder_name: `Profile ${i}`,
                  port: parseInt(settings.base_port) + (i - 1),
                  running: false
                };
              }
            } else {
              showToast('warning', 'Could not determine profile count. Please select profiles folder again.');
              return;
            }
          } else {
            showToast('warning', 'Please select a profiles folder first in Step 1');
            return;
          }
        }
        
        // Store campaign configuration
        campaignConfig.profiles = Object.entries(profiles).map(([id, data]) => ({
          id,
          name: data.folder_name || `Profile ${id}`,
          port: data.port || (parseInt(settings.base_port) + parseInt(id))
        }));
        
        campaignConfig.basePort = settings.base_port;
        
        // Get posts preview
        try {
          const queueData = await apiCall('GET', '/queue/tasks?limit=10');
          campaignConfig.posts = queueData.tasks || [];
        } catch (e) {
          // Fallback if endpoint doesn't exist
          campaignConfig.posts = [];
        }
        
        // Populate review page
        populateReviewPage(settings, stats);
        
        // Show review tab
        document.getElementById('nav-review').classList.remove('hidden');
        showTab('review');
        
      } catch (error) {
        showToast('error', 'Failed to load campaign data: ' + error.message);
      }
    });
  }
});

// Populate review page with campaign data
function populateReviewPage(settings, stats) {
  // Set default campaign name
  const now = new Date();
  document.getElementById('campaign-name-input').value = `Campaign ${now.toLocaleDateString()}`;
  
  // Data source
  document.getElementById('review-data-source').textContent = 'Excel (XLSX)';
  
  // Total posts and profiles
  document.getElementById('review-total-posts').textContent = stats.total;
  document.getElementById('review-total-profiles').textContent = campaignConfig.profiles.length;
  
  // Profiles grid
  const profilesGrid = document.getElementById('profiles-review-grid');
  profilesGrid.innerHTML = '';
  
  campaignConfig.profiles.forEach((profile, index) => {
    const card = document.createElement('div');
    card.className = 'profile-review-card';
    card.innerHTML = `
      <div class="profile-review-header">
        <span class="profile-icon">👤</span>
        <span class="profile-review-name">${escapeHtml(profile.name)}</span>
      </div>
      <div class="profile-review-details">
        <div class="profile-detail-row">
          <span class="profile-detail-label">Profile ID:</span>
          <span class="profile-detail-value">${profile.id}</span>
        </div>
        <div class="profile-detail-row">
          <span class="profile-detail-label">Debug Port:</span>
          <span class="port-badge">${profile.port}</span>
        </div>
        <div class="profile-detail-row">
          <span class="profile-detail-label">Posts Assigned:</span>
          <span class="profile-detail-value">${Math.ceil(stats.total / campaignConfig.profiles.length)}</span>
        </div>
      </div>
    `;
    profilesGrid.appendChild(card);
  });
  
  // Posts list
  const postsList = document.getElementById('posts-review-list');
  postsList.innerHTML = '';
  
  if (campaignConfig.posts.length > 0) {
    campaignConfig.posts.forEach((post, index) => {
      const item = document.createElement('div');
      item.className = 'post-review-item';
      const communityBadge = post.community ? `<span class="community-badge">${escapeHtml(post.community)}</span>` : '';
      item.innerHTML = `
        <span class="post-review-number">${index + 1}</span>
        <div style="display: inline-block; vertical-align: middle;">
          <div class="post-review-title">${escapeHtml(post.title || 'Untitled Post')} ${communityBadge}</div>
          <a href="${post.url || '#'}" class="post-review-url" target="_blank">${escapeHtml(post.url || 'No URL')}</a>
        </div>
      `;
      postsList.appendChild(item);
    });
  } else {
    // Fallback if we couldn't get tasks
    for (let i = 0; i < stats.total; i++) {
      const item = document.createElement('div');
      item.className = 'post-review-item';
      item.innerHTML = `
        <span class="post-review-number">${i + 1}</span>
        <div style="display: inline-block; vertical-align: middle;">
          <div class="post-review-title">Post ${i + 1}</div>
          <span class="post-review-url">Preview not available</span>
        </div>
      `;
      postsList.appendChild(item);
    }
  }
  
  // Scheduling configuration
  document.getElementById('review-schedule-mode').textContent = settings.schedule_mode.toUpperCase();
  
  if (settings.schedule_mode === 'interval') {
    document.getElementById('review-interval').textContent = `Every ${settings.interval_minutes} minutes`;
  } else if (settings.schedule_mode === 'fixed') {
    document.getElementById('review-interval').textContent = `Fixed times: ${settings.fixed_times.join(', ')}`;
  } else if (settings.schedule_mode === 'random') {
    document.getElementById('review-interval').textContent = `Random: ${settings.random_min_minutes}-${settings.random_max_minutes} min`;
  }
  
  document.getElementById('review-concurrency').textContent = `${settings.concurrency} parallel posts`;
}

// Back to setup button (wrapped in DOMContentLoaded)
document.addEventListener('DOMContentLoaded', () => {
  const backBtn = document.getElementById('btn-back-to-setup');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      showTab('setup');
    });
  }
});

// Save campaign button (wrapped in DOMContentLoaded)
document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.getElementById('btn-save-campaign');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const campaignName = document.getElementById('campaign-name-input').value.trim();
      
      if (!campaignName) {
        showToast('warning', 'Please enter a campaign name');
        return;
      }
      
      const confirmed = confirm(`Save campaign "${campaignName}"?\n\nAfter saving:\n1. Launch Profiles to open Chrome windows\n2. Log into X/Twitter in each window\n3. Click Start Automation to begin posting`);
      
      if (!confirmed) return;
      
      try {
        // Campaign is already loaded in backend via setup
        // Just confirm it's ready
        const stats = await apiCall('GET', '/queue/status');
        
        if (stats.total === 0) {
          showToast('error', 'No posts in queue. Please go back and reload your data.');
          return;
        }
        
        showToast('success', `✅ Campaign "${campaignName}" saved successfully!`);
        
        // Hide review nav button
        document.getElementById('nav-review').classList.add('hidden');
        
        // Go to main dashboard
        showTab('main');
        
        // Show helpful message
        setTimeout(() => {
          showToast('info', '👉 Next Step: Click "Launch Profiles" to start Chrome windows');
        }, 1500);
        
      } catch (error) {
        showToast('error', 'Failed to save campaign: ' + error.message);
      }
    });
  }
});

// Reset Queue
document.getElementById('btn-reset-queue').addEventListener('click', async () => {
  const confirmed = confirm('Are you sure you want to reset the queue? This will clear all tasks and reload from XLSX file.');
  if (!confirmed) return;
  
  try {
    const result = await apiCall('POST', '/setup/xlsx/reset');
    showToast('success', `Queue reset: ${result.tasks} posts loaded`);
    
    const stats = await apiCall('GET', '/queue/status');
    updateQueueStats(stats);
  } catch (error) {
    showToast('error', 'Failed to reset queue: ' + error.message);
  }
});

// ============================================================================
// Campaign Delete Handler
// ============================================================================

async function handleDeleteCampaign(profileId, profileName) {
  const confirmed = confirm(
    `⚠️ Delete Campaign?\n\n` +
    `Campaign: ${profileName}\n` +
    `Profile ID: ${profileId}\n\n` +
    `This will:\n` +
    `• Shut down the Chrome profile if running\n` +
    `• Delete all associated tasks from the database\n` +
    `• Remove all posting data for this campaign\n\n` +
    `This action cannot be undone!\n\n` +
    `Are you sure you want to delete this campaign?`
  );
  
  if (!confirmed) return;
  
  try {
    // Call backend API to delete campaign
    const result = await apiCall('DELETE', `/campaigns/${profileId}`);
    
    showToast('success', `Campaign "${result.profile_name}" deleted successfully. ${result.tasks_deleted} tasks removed.`);
    
    // Refresh the UI
    setTimeout(async () => {
      try {
        const status = await apiCall('GET', '/profiles/status');
        updateProfileCards(status.profiles);
        
        // Also refresh queue stats
        const stats = await apiCall('GET', '/queue/status');
        updateQueueStats(stats);
      } catch (e) {
        console.error('Error refreshing UI after delete:', e);
      }
    }, 500);
    
  } catch (error) {
    showToast('error', `Failed to delete campaign: ${error.message}`);
  }
}

// ============================================================================
// Toast Notifications
// ============================================================================

function showToast(type, message) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('toast-show');
  }, 10);
  
  setTimeout(() => {
    toast.classList.remove('toast-show');
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}

// ============================================================================
// Initialization
// ============================================================================

window.addEventListener('load', async () => {
  // Check backend status
  try {
    await apiCall('GET', '/health');
    const statusDot = document.getElementById('backend-status');
    const statusText = document.getElementById('backend-status-text');
    statusDot.className = 'status-dot running';
    statusText.textContent = 'Connected';
  } catch (error) {
    const statusDot = document.getElementById('backend-status');
    const statusText = document.getElementById('backend-status-text');
    statusDot.className = 'status-dot stopped';
    statusText.textContent = 'Disconnected';
  }
  
  // Load settings
  try {
    const settings = await apiCall('GET', '/settings');
    document.getElementById('concurrency-slider').value = settings.concurrency;
    document.getElementById('concurrency-value').textContent = settings.concurrency;
    document.getElementById('post-delay-min').value = settings.post_delay_min;
    document.getElementById('post-delay-max').value = settings.post_delay_max;
    document.getElementById('pre-submit-delay-min').value = settings.pre_submit_delay_min ?? 1.0;
    document.getElementById('pre-submit-delay-max').value = settings.pre_submit_delay_max ?? 2.0;
    document.getElementById('cycle-cooldown').value = settings.cycle_cooldown;
    document.getElementById('base-port').value = settings.base_port;
    document.getElementById('typing-delay-min').value = settings.typing_delay_min;
    document.getElementById('typing-delay-max').value = settings.typing_delay_max;
    document.getElementById('title-dots-count').value = settings.title_dots_count ?? 2;
    
    document.querySelector(`input[name="schedule-mode"][value="${settings.schedule_mode}"]`).checked = true;
    document.getElementById('interval-minutes').value = settings.interval_minutes;
    document.getElementById('fixed-times').value = (settings.fixed_times || []).join(', ');
    document.getElementById('random-min').value = settings.random_min_minutes;
    document.getElementById('random-max').value = settings.random_max_minutes;
    document.getElementById('sheets-per-run').value = settings.sheets_per_run || 1;
    
    // Update mode visibility
    document.getElementById('interval-config').classList.toggle('hidden', settings.schedule_mode !== 'interval');
    document.getElementById('fixed-config').classList.toggle('hidden', settings.schedule_mode !== 'fixed');
    document.getElementById('random-config').classList.toggle('hidden', settings.schedule_mode !== 'random');
    
    document.getElementById('concurrency-warning').classList.toggle('hidden', settings.concurrency < 5);
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
  
  // Start polling
  startPolling();
});

window.addEventListener('unload', () => {
  stopPolling();
});

// Handle Python crash
if (window.electronAPI && window.electronAPI.onPythonCrash) {
  window.electronAPI.onPythonCrash((data) => {
    const statusDot = document.getElementById('backend-status');
    const statusText = document.getElementById('backend-status-text');
    statusDot.className = 'status-dot stopped';
    statusText.textContent = 'Crashed';
    showToast('error', `Python backend crashed (code ${data.code}). Please restart the application.`);
    stopPolling();
  });
}
