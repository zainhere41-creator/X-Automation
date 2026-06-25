# 🚀 X Posting Automation

**Professional desktop application for automating X (Twitter) posting across multiple Chrome profiles**

[![Status](https://img.shields.io/badge/status-production%20ready-success)](.)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](.)
[![License](https://img.shields.io/badge/license-MIT-green)](.)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Advanced Features](#advanced-features)
- [Data Formats](#data-formats)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)
- [Safety & Best Practices](#safety--best-practices)

---

## 🎯 Overview

X Posting Automation is a powerful desktop application that enables automated posting to X (Twitter) using multiple Chrome profiles. Built with Electron (frontend) and Python (backend), it provides a professional, reliable solution for managing social media content across multiple accounts.

### Why This App?

- **Multi-Account Support** - Manage unlimited accounts simultaneously
- **Human-Like Behavior** - Randomized typing delays and intelligent scheduling
- **Reliable** - CDP-based connection keeps Chrome alive between posts
- **Flexible Scheduling** - Interval, fixed times, or random delay modes
- **Community Support** - Automatically tag posts to X communities
- **Excel Integration** - Load posts from Excel files with multi-tab scheduling
- **Production Ready** - Comprehensive error handling and logging

---

## ✨ Features

### Core Features

- 🔄 **Multi-Profile Automation** - Post simultaneously across multiple accounts
- ⏰ **Smart Scheduling** - 3 scheduling modes (interval, fixed times, random)
- ✅ **Two-Page Campaign Workflow** - Visual review and verification before launching
- 📊 **Real-Time Dashboard** - Live status monitoring and statistics
- 🎯 **Queue Management** - Round-robin task distribution
- 📝 **Flexible Data Input** - XML or Excel (XLSX) file support
- 🏘️ **Community Tagging** - Auto-tag posts to X communities
- 🔍 **Campaign Analytics** - Detailed stats per profile
- 📈 **Live Logging** - Color-coded real-time logs
- 🎨 **Dark Theme UI** - Professional, easy-on-the-eyes interface
- 🔐 **Session Persistence** - Chrome profiles stay logged in

### Advanced Features

- **Visual Campaign Review** - Preview profiles, ports, and posts before saving
- **Guided Workflow** - Step-by-step campaign creation with validation
- **Tab-Based Scheduling** (Excel) - Each Excel tab = one posting run
- **Recycle Mode** - Repeat posts from one tab with delays
- **Profile Readiness Detection** - Checks if profiles are logged in
- **Screenshot Capture** - Auto-save screenshots on errors
- **Graceful Degradation** - Posts succeed even if community tagging fails
- **Database Migration** - Automatic schema updates
- **Run Now** - Manual posting for testing
- **Concurrency Control** - 1-5 parallel posts with risk warnings

---

## 🚀 Quick Start

### 1. Install Dependencies

**Windows:**
```bash
setup.bat
```

**Mac/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Prepare Chrome Profiles

Create numbered folders in `profiles/` directory:

```
profiles/
├── Account1/      (contains Chrome shortcut .lnk file)
├── Account2/      (contains Chrome shortcut .lnk file)
└── Account3/      (contains Chrome shortcut .lnk file)
```

**Create shortcuts:**
1. Open Chrome with desired profile
2. Right-click profile icon → Create Desktop Shortcut
3. Move shortcut into account folder

### 3. Prepare Post Data

**Option A: XML File**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<posts>
    <post>
        <title>Your tweet text here</title>
        <url>https://example.com/your-content</url>
        <community_url>https://twitter.com/i/communities/123456</community_url>
    </post>
</posts>
```

**Option B: Excel File**

| title | url | community_url |
|-------|-----|---------------|
| Tweet text | https://example.com | https://twitter.com/i/communities/123 |

### 4. Launch Application

**Windows:**
```bash
start.bat
```

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

### 5. Configure in UI

**NEW: Two-Page Campaign Workflow** 🎯

1. **Setup Tab** → Select profiles folder
2. **Setup Tab** → Load XML or Excel file
3. **Click "Continue"** → Opens Review page
4. **Review Tab** → Verify profiles, ports, and posts
5. **Review Tab** → Enter campaign name and click "Save Campaign"
6. **Main Tab** → Click "Launch Profiles"
7. **Log into X** in each Chrome window that opens
8. **Main Tab** → Click "Start Automation"

**📚 See [QUICK_START_NEW_CAMPAIGN.md](QUICK_START_NEW_CAMPAIGN.md) for detailed walkthrough**

---

## 💻 System Requirements

### Required

- **Operating System:** Windows 10+, macOS 10.15+, or Linux
- **Python:** 3.10 or higher
- **Node.js:** 16.0 or higher
- **Google Chrome:** Latest version
- **RAM:** 4GB minimum, 8GB recommended
- **Disk Space:** 500MB for application + Chrome profiles

### Optional

- **pywin32** (Windows) - For reading Chrome shortcuts
- **openpyxl** (Python) - For Excel file support

---

## 📦 Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd x-posting-automation
```

### Step 2: Install Python Dependencies

```bash
cd python_backend
pip install -r requirements.txt
playwright install chromium
cd ..
```

### Step 3: Install Electron Dependencies

```bash
cd electron
npm install
cd ..
```

### Step 4: Verify Installation

```bash
python test_setup.py
```

Expected output:
```
✓ PASS - Python imports
✓ PASS - Project structure
✓ PASS - Electron setup
```

---

## ⚙️ Configuration

### 1. Chrome Profiles

**Create Profile Shortcuts:**

1. **Windows:**
   - Find your Chrome profile shortcut
   - Right-click → Properties → Copy Target path
   - Ensure it includes: `--profile-directory="Profile X"`

2. **macOS:**
   - Open Terminal
   - Run: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --profile-directory="Profile 1"`
   - Create shortcut with this command

3. **Linux:**
   - Run: `google-chrome --profile-directory="Profile 1"`
   - Create .desktop file with this command

**Folder Structure:**
```
profiles/
├── Account1/
│   └── Chrome.lnk        (Windows shortcut)
├── Account2/
│   └── Chrome.lnk
└── Account3/
    └── Chrome.lnk
```

### 2. Selectors Configuration

Edit `config/selectors.json` if X UI changes:

```json
{
  "tweet_box": [
    "[data-testid='tweetTextarea_0']",
    "div[aria-label='Post text']"
  ],
  "submit_button": [
    "[data-testid='tweetButton']"
  ],
  "login_check": [
    "[data-testid='SideNav_AccountSwitcher_Button']"
  ],
  "community_button": [
    "[data-testid='communities']"
  ],
  "home_url": "https://x.com/home"
}
```

### 3. Settings

Configure in **Advanced Settings** tab or edit `config/settings.json`:

```json
{
  "concurrency": 2,
  "post_delay_min": 3,
  "post_delay_max": 8,
  "cycle_cooldown": 30,
  "base_port": 9222,
  "typing_delay_min": 80,
  "typing_delay_max": 180,
  "schedule_mode": "interval",
  "interval_minutes": 30
}
```

---

## 📖 Usage Guide

### Main Dashboard

**Profile Status:**
- Green dot = Running and ready
- Red dot = Stopped or not launched

**Control Buttons:**
- **Launch Profiles** - Start all Chrome instances with profiles
- **Start Automation** - Begin scheduled posting
- **Stop Automation** - Pause scheduled posting
- **Run Now** - Manual single-cycle post (for testing)
- **Shutdown Profiles** - Close all Chrome instances

**Queue Status:**
- **Total** - All tasks loaded
- **Pending** - Waiting to post
- **Done** - Successfully posted
- **Failed** - Posting errors

**Live Logs:**
- Color-coded messages (green=success, red=error, yellow=warning)
- Auto-scroll to latest
- Updated every 3 seconds

### Campaigns Detail Tab

View detailed information for each profile:
- Port number and CDP URL
- Post statistics (pending/done/failed)
- Last post timestamp
- Recent task history

### Advanced Settings Tab

**Scheduler Modes:**

1. **Interval Mode**
   - Posts every N minutes
   - Example: Every 30 minutes

2. **Fixed Times Mode**
   - Posts at specific times daily
   - Example: 09:00, 14:00, 20:00

3. **Random Delay Mode**
   - Random intervals between min/max
   - Example: Between 20-60 minutes

**Concurrency:**
- 1 = Safe sequential (lowest detection risk)
- 2-3 = Balanced (recommended)
- 4-5 = Fast (higher detection risk)

**Post Behavior:**
- **Typing Delay** - Milliseconds between keystrokes (80-180ms default)
- **Post Pause** - Seconds between posts (3-8s default)
- **Cycle Cooldown** - Minutes between full cycles (30min default)

### Setup Tab

**Step 1: Accounts Folder**
- Click "Browse" → Select profiles folder
- Shows detected accounts and readiness status

**Step 2: Post Data**
- Choose XML or Excel format
- Click "Browse" → Select data file
- Preview first 3 posts

**Step 3: Review & Continue**
- For Excel: Select scheduling type (tab-based or recycle)
- For XML: Just continue
- Click "Continue to Scheduling"

**Step 4: Queue Management**
- Reset Queue - Clear and reload all tasks
- View current queue statistics

---

## 🎯 Advanced Features

### Community Tagging

Automatically tag posts to X communities:

**XML Format:**
```xml
<post>
    <title>Watch Full Video</title>
    <url>https://example.com/video</url>
    <community_url>https://twitter.com/i/communities/1570853436589051907</community_url>
</post>
```

**Excel Format:**

| title | url | community_url |
|-------|-----|---------------|
| Watch Full Video | https://example.com | https://twitter.com/i/communities/1570853436589051907 |

**How to Find Community URL:**
1. Go to your X community page
2. Copy URL from browser address bar
3. Format: `https://twitter.com/i/communities/[COMMUNITY_ID]`

**Behavior:**
- If tagging succeeds → Post appears in timeline AND community
- If tagging fails → Post still succeeds to main timeline (graceful degradation)

### Excel Scheduling

**Tab-Based Mode:**
- Each Excel tab = one run
- Posts all content from Tab 1, then Tab 2, etc.
- Delay between tabs configurable
- Example: 7 tabs = 7 runs per day

**Recycle Mode:**
- Uses only one tab
- Repeats same posts with delay
- Good for evergreen content

**Excel Structure:**
```
Sheet1 (Run 1): 10 posts
Sheet2 (Run 2): 15 posts
Sheet3 (Run 3): 12 posts
```

**How It Works:**
1. Load Excel file → Shows total runs
2. Select mode → Tab-based or Recycle
3. Click Continue → Loads first run
4. System posts all tasks from Run 1
5. Waits configured delay
6. Loads Run 2 automatically
7. Repeats until all runs complete

### Profile Management

**Profile Readiness Check:**
- Automatically detects if profiles have X cookies
- Warns if login needed
- Shows status: "Ready" or "Needs Setup"

**Profile Launch:**
- Deletes singleton locks before launch
- Assigns unique CDP ports (9222, 9223, 9224...)
- Keeps Chrome processes alive between cycles
- Graceful shutdown with 3-second wait

---

## 📊 Data Formats

### XML Format (Detailed)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<posts>
    <!-- Standard post -->
    <post>
        <title>Your tweet content here</title>
        <url>https://example.com/article</url>
    </post>
    
    <!-- Post with community -->
    <post>
        <title>Watch Full Video</title>
        <url>https://youtube.com/watch?v=xyz</url>
        <community_url>https://twitter.com/i/communities/123456</community_url>
    </post>
</posts>
```

**Rules:**
- `<title>` - Required, tweet text (max 280 chars including URL)
- `<url>` - Required, must start with http:// or https://
- `<community_url>` - Optional, X community link

### Excel Format (Detailed)

**Flexible Column Names:**
- Title: `title`, `Title`, `TITLE`
- URL: `url`, `URL`, `link`, `Link`
- Community: `community_url`, `community`, `Community`, `community_link`

**Example:**

| title | url | community_url |
|-------|-----|---------------|
| Check out this tutorial | https://example.com/tutorial | https://twitter.com/i/communities/123 |
| Just my thoughts | https://example.com/blog | |
| New video live! | https://youtube.com/xyz | https://twitter.com/i/communities/456 |

**Multi-Tab Example:**

**Sheet1 (Morning Posts):**
| title | url |
|-------|-----|
| Good morning post | https://example.com/1 |
| Morning update | https://example.com/2 |

**Sheet2 (Afternoon Posts):**
| title | url |
|-------|-----|
| Afternoon check-in | https://example.com/3 |
| Update post | https://example.com/4 |

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "No profiles running"

**Symptoms:** Can't post, profiles show red dots

**Solutions:**
- Click "Launch Profiles" button
- Wait for Chrome windows to open
- Check if ports 9222+ are available
- Verify Chrome is installed correctly

---

#### 2. "No pending tasks"

**Symptoms:** Queue shows 0 pending

**Solutions:**
- Go to Setup tab
- Load XML or Excel file
- Check file format is correct
- Click "Reset Queue" to reload

---

#### 3. Posts fail with "not_logged_in"

**Symptoms:** Tasks marked as failed, error logs show not logged in

**Solutions:**
- Open Chrome windows
- Manually log into X on each profile
- Keep Chrome windows open
- Check cookies exist in profile folders

---

#### 4. "Tweet box not found"

**Symptoms:** Posts fail, screenshot shows wrong page

**Solutions:**
- X UI may have changed
- Update `config/selectors.json` with new selectors
- Use Chrome DevTools to find new selectors
- Check if X is loading correctly

---

#### 5. Community not tagged

**Symptoms:** Post succeeds but not in community

**Solutions:**
- Verify community URL is correct
- Check account has access to community
- Community tagging failing doesn't stop post
- Check logs for community-specific errors

---

#### 6. High failure rate

**Symptoms:** Many tasks marked as failed

**Solutions:**
- Reduce concurrency to 1 or 2
- Increase delays in Advanced Settings
- Check internet connection
- Verify accounts aren't rate-limited
- Check account standing on X

---

#### 7. Python backend won't start

**Symptoms:** Error dialog on startup

**Solutions:**
- Ensure Python 3.10+ installed
- Run: `pip install -r python_backend/requirements.txt`
- Run: `playwright install chromium`
- Check port 8765 isn't in use
- Check firewall isn't blocking Python

---

#### 8. Chrome won't launch

**Symptoms:** Profiles fail to start

**Solutions:**
- Verify Chrome is installed
- Check .lnk shortcuts are valid
- Ensure profiles folder structure is correct
- Close any existing Chrome instances
- Check ports 9222+ are available

---

### Debug Tools

**View Logs:**
```bash
# Real-time
tail -f logs/app.log

# Windows
type logs\app.log
```

**Check Database:**
```bash
python -c "import sqlite3; conn = sqlite3.connect('data/tasks.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM tasks WHERE status=\"pending\"'); print(f'Pending: {cursor.fetchone()[0]}')"
```

**Test Backend:**
```bash
curl http://localhost:8765/health
```

**Check Port Availability:**
```bash
# Windows
netstat -ano | findstr :8765

# Mac/Linux
lsof -i :8765
```

---

## 📡 API Reference

### Base URL
```
http://localhost:8765
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/setup/profiles` | Discover Chrome profiles |
| POST | `/setup/xml` | Load XML post data |
| POST | `/setup/xlsx` | Parse Excel file |
| POST | `/setup/xlsx/load` | Load specific Excel run |
| POST | `/profiles/launch` | Launch all profiles |
| GET | `/profiles/status` | Get profile status |
| POST | `/profiles/shutdown` | Shutdown all profiles |
| POST | `/automation/start` | Start scheduler |
| POST | `/automation/stop` | Stop scheduler |
| POST | `/automation/run-now` | Manual post cycle |
| GET | `/automation/status` | Get scheduler status |
| GET | `/queue/status` | Get queue statistics |
| POST | `/queue/reset` | Reset and reload queue |
| GET | `/campaigns/details` | Get campaign details |
| GET | `/settings` | Get current settings |
| POST | `/settings/save` | Save settings |
| GET | `/logs/recent` | Get recent logs |

### Example API Call

```javascript
// Get profile status
const response = await fetch('http://localhost:8765/profiles/status');
const data = await response.json();
console.log(data.profiles);
```

---

## 🔒 Safety & Best Practices

### Account Safety

✅ **DO:**
- Start with low concurrency (1-2)
- Use longer delays initially
- Monitor for rate limiting
- Test with small batches first
- Keep accounts in good standing
- Use human-like delays (80-180ms typing)

❌ **DON'T:**
- Use max concurrency (5) immediately
- Post too frequently
- Ignore rate limit warnings
- Run 24/7 without cooldowns
- Use suspicious content
- Spam communities

### Detection Prevention

**Best Settings for Safety:**
```json
{
  "concurrency": 2,
  "post_delay_min": 5,
  "post_delay_max": 10,
  "typing_delay_min": 100,
  "typing_delay_max": 200,
  "interval_minutes": 45
}
```

**Schedule Recommendation:**
- Use Random Delay mode (20-60 min range)
- Post during human hours (9 AM - 9 PM)
- Vary content
- Don't post identical content across accounts

### Data Privacy

- Chrome profiles stored locally
- No data sent to external servers
- Database encrypted at rest (if OS supports)
- Logs rotated automatically

### Legal Compliance

⚠️ **Important:** This tool is for legitimate automation of your own accounts. You must:
- Comply with X's Terms of Service
- Have permission to post on accounts
- Respect rate limits
- Not engage in spam or manipulation
- Follow all applicable laws

**Disclaimer:** The authors are not responsible for misuse or violations resulting from use of this software.

---

## 📚 Additional Resources

### Documentation Files

- **QUICK_START_NEW_CAMPAIGN.md** - 5-minute campaign setup guide (NEW! ✨)
- **CAMPAIGN_WORKFLOW.md** - Complete two-page workflow documentation
- **WORKFLOW_DIAGRAM.md** - Visual flowcharts and diagrams
- **FEATURE_TWO_PAGE_CAMPAIGN.md** - Detailed feature documentation
- **TROUBLESHOOTING.md** - Comprehensive troubleshooting guide
- **PRD_X_Posting.md** - Original product requirements
- **FULL_AUDIT_REPORT.md** - Complete system audit

### Community

- GitHub Issues - Bug reports and feature requests
- Discussions - Questions and community support

### Development

**Run Backend Only:**
```bash
cd python_backend
python main.py
```

**Run Frontend Only:**
```bash
cd electron
npm start
```

**Run Tests:**
```bash
python test_setup.py
```

---

## 🔄 Updates

### Version 2.0.0 (Current) - NEW! 🎉

- ✅ **Two-Page Campaign Workflow** - Visual review before launch
- ✅ **Review Tab** - Verify profiles, ports, and posts
- ✅ **Guided Setup** - Step-by-step campaign creation
- ✅ **Campaign Names** - Organize and identify campaigns
- ✅ **Port Visualization** - See assigned debugging ports
- ✅ **Posts Preview** - Review content before posting
- ✅ **Enhanced UX** - Better workflow with validation

### Version 1.0.0

- ✅ Multi-profile automation
- ✅ Three scheduling modes
- ✅ Community tagging
- ✅ Excel support
- ✅ Campaign analytics
- ✅ Dark theme UI

### Roadmap

- [ ] Media attachments (images/videos)
- [ ] Thread support (tweet chains)
- [ ] Reply automation
- [ ] Analytics dashboard
- [ ] Timezone scheduling
- [ ] Content templates

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

Built with:
- **Electron** - Cross-platform desktop apps
- **Python FastAPI** - Modern web framework
- **Playwright** - Browser automation
- **APScheduler** - Job scheduling
- **SQLite** - Embedded database

---

## 💬 Support

Need help? Check these resources:

1. **Documentation** - Read this README and TROUBLESHOOTING.md
2. **Logs** - Check `logs/app.log` for errors
3. **GitHub Issues** - Search existing issues
4. **Create Issue** - Report bugs or request features

---

**Made with ❤️ for social media automation**

