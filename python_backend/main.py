"""
FastAPI Server - Main entry point for X Posting Automation backend
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from playwright.async_api import async_playwright

from profile_manager import ProfileManager
from queue_manager import QueueManager
from posting_engine import PostingEngine
from scheduler import Scheduler
from xlsx_parser import parse_xlsx

# Project root is one level above this script (script/ not python_backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Also keep a reference for files that live inside python_backend/
BASE_DIR = Path(__file__).resolve().parent

# Ensure directories exist BEFORE logging setup
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
(PROJECT_ROOT / "data").mkdir(exist_ok=True)
(PROJECT_ROOT / "config").mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "logs" / "app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global components
profile_manager = None
queue_manager = None
posting_engine = None
scheduler = None
current_settings = {}
current_xlsx_data = None  # Store XLSX parsed data
playwright_instance = None  # Global Playwright instance, reused across cycles


# Pydantic models for request validation
class ProfilesRequest(BaseModel):
    profiles_root: str


class XLSXRequest(BaseModel):
    xlsx_path: str


class AutomationStartRequest(BaseModel):
    mode: str = Field(..., pattern="^(interval|fixed|random)$")
    interval_minutes: Optional[int] = None
    times: Optional[list[str]] = None
    min_minutes: Optional[int] = None
    max_minutes: Optional[int] = None


class SettingsRequest(BaseModel):
    concurrency: int = Field(default=2, ge=1, le=100)
    post_delay_min: int = Field(default=3, ge=0, le=600)
    post_delay_max: int = Field(default=8, ge=0, le=600)
    cycle_cooldown: int = Field(default=30, ge=0, le=1440)
    base_port: int = Field(default=9222, ge=1024, le=65535)
    typing_delay_min: int = Field(default=80, ge=10, le=1000)
    typing_delay_max: int = Field(default=180, ge=10, le=1000)
    pre_submit_delay_min: float = Field(default=1.0, ge=0.0, le=30.0)
    pre_submit_delay_max: float = Field(default=2.0, ge=0.0, le=30.0)
    title_dots_count: int = Field(default=2, ge=2, le=3)
    schedule_mode: str = "interval"
    interval_minutes: int = 30
    fixed_times: list[str] = []
    random_min_minutes: int = 20
    random_max_minutes: int = 60
    sheets_per_run: int = Field(default=1, ge=1, le=1000)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("=" * 60)
    logger.info("FastAPI Server Starting")
    logger.info("=" * 60)
    
    # Initialize global components
    global profile_manager, queue_manager, posting_engine, scheduler, current_settings
    global current_xlsx_data, playwright_instance
    
    profile_manager = ProfileManager(profiles_root=str(PROJECT_ROOT / "profiles"), base_port=9222)
    queue_manager = QueueManager(db_path=str(PROJECT_ROOT / "data" / "tasks.db"))
    posting_engine = PostingEngine(selectors_path=str(PROJECT_ROOT / "config" / "selectors.json"))
    scheduler = Scheduler()
    
    # Create global Playwright instance (reused across all cycles)
    playwright_instance = await async_playwright().start()
    logger.info("Playwright instance created")
    
    # Clear all campaign data on fresh start
    queue_manager.reset()
    current_xlsx_data = None
    logger.info("Cleared all campaign data on startup")
    
    # Load settings
    current_settings = load_settings()
    
    # Auto-detect any already-running profiles on startup
    try:
        detected = profile_manager.detect_running_profiles()
        running_count = sum(detected.values())
        if running_count > 0:
            logger.info(f"✓ Found {running_count} profiles already running on startup")
    except Exception as e:
        logger.warning(f"Error detecting running profiles on startup: {e}")
    
    logger.info("All components initialized successfully")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down server")
    if scheduler.is_running():
        scheduler.stop()
    profile_manager.shutdown_all()
    # Close queue manager database connection
    queue_manager.close()
    # Close Playwright instance
    if playwright_instance:
        await playwright_instance.stop()
        logger.info("Playwright instance stopped")


# Create FastAPI app
app = FastAPI(title="X Posting Automation", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Settings management functions
def load_settings() -> dict:
    """Load settings from JSON file or return defaults"""
    settings_path = PROJECT_ROOT / "config" / "settings.json"
    
    defaults = {
        "concurrency": 2,
        "post_delay_min": 3,
        "post_delay_max": 8,
        "cycle_cooldown": 30,
        "base_port": 9222,
        "typing_delay_min": 80,
        "typing_delay_max": 180,
        "schedule_mode": "interval",
        "interval_minutes": 30,
        "fixed_times": [],
        "random_min_minutes": 20,
        "random_max_minutes": 60,
        "sheets_per_run": 1,
        "pre_submit_delay_min": 1.0,
        "pre_submit_delay_max": 2.0,
        "title_dots_count": 2
    }
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                loaded = json.load(f)
                defaults.update(loaded)
                logger.info("Settings loaded from file")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
    
    return defaults


def save_settings(settings: dict):
    """Save settings to JSON file"""
    settings_path = PROJECT_ROOT / "config" / "settings.json"
    try:
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        logger.info("Settings saved to file")
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise


# API Endpoints

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.post("/setup/profiles")
async def setup_profiles(request: ProfilesRequest):
    """Discover Chrome profiles in specified folder"""
    try:
        profile_manager.profiles_root = Path(request.profiles_root)
        profiles = profile_manager.discover_profiles()
        
        if not profiles:
            raise HTTPException(status_code=400, detail="No subfolders with .lnk shortcut files found")
        
        # Get folder names for display
        folder_names = profile_manager.get_folder_names()
        folder_list = [folder_names.get(pid, str(pid)) for pid in profiles]
        
        # Check if profiles are ready for automation
        readiness = profile_manager.check_profiles_ready()
        
        logger.info(f"Discovered profiles: {folder_list}")
        
        # Log warnings for profiles that need setup
        for pid, status in readiness.items():
            if not status["ready"]:
                logger.warning(f"Profile {pid} ({status['folder_name']}): {status['message']}")
        
        return {
            "profiles": profiles,
            "folder_names": folder_list,
            "count": len(profiles),
            "readiness": readiness
        }
    except Exception as e:
        logger.error(f"Error in setup_profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/setup/xlsx")
async def setup_xlsx(request: XLSXRequest):
    """Parse XLSX file, load all sheets into queue, return preview"""
    global current_xlsx_data
    
    try:
        data = parse_xlsx(request.xlsx_path)
        
        if data.get("error"):
            raise HTTPException(status_code=400, detail=data["error"])
        
        if not data.get("sheets"):
            raise HTTPException(status_code=400, detail="No valid posts found in XLSX")
        
        current_xlsx_data = data
        
        profiles = profile_manager.discover_profiles()
        if not profiles:
            raise HTTPException(status_code=400, detail="No profiles available")
        
        loaded_count = queue_manager.load_posts(data["sheets"], profiles)
        
        sheets_per_run = current_settings.get("sheets_per_run", 1)
        estimated_runs = (len(data["sheets"]) + sheets_per_run - 1) // sheets_per_run
        
        preview = []
        for sheet in data["sheets"]:
            preview.append({
                "sheet": sheet["sheet_name"],
                "index": sheet["index"],
                "posts": len(sheet["posts"]),
                "status": "pending"
            })
        
        logger.info(f"Loaded {loaded_count} posts from {len(data['sheets'])} sheets")
        
        response = {
            "total_sheets": data["total_sheets"],
            "total_posts": data["total_posts"],
            "sheets_per_run": sheets_per_run,
            "estimated_runs": estimated_runs,
            "preview": preview
        }
        
        if data.get("skipped"):
            response["skipped"] = data["skipped"]
            response["skipped_count"] = len(data["skipped"])
            logger.warning(f"{len(data['skipped'])} rows were skipped during parsing")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in setup_xlsx: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/setup/xlsx/reset")
async def reset_xlsx_queue():
    """Reset queue and reload from current XLSX data"""
    try:
        if not current_xlsx_data:
            raise HTTPException(status_code=400, detail="No XLSX file loaded")
        
        profiles = profile_manager.discover_profiles()
        if not profiles:
            raise HTTPException(status_code=400, detail="No profiles available")
        
        loaded_count = queue_manager.load_posts(current_xlsx_data["sheets"], profiles)
        
        logger.info(f"Queue reset: {loaded_count} posts loaded from XLSX")
        return {"status": "reset", "tasks": loaded_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset_xlsx_queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/setup/xlsx/append")
async def append_xlsx(request: XLSXRequest):
    """Parse new XLSX file and append posts to existing queue"""
    global current_xlsx_data
    
    try:
        data = parse_xlsx(request.xlsx_path)
        
        if data.get("error"):
            raise HTTPException(status_code=400, detail=data["error"])
        
        if not data.get("sheets"):
            raise HTTPException(status_code=400, detail="No valid posts found in XLSX")
        
        # Merge with existing data
        if current_xlsx_data:
            existing_sheets = current_xlsx_data.get("sheets", [])
            current_xlsx_data["sheets"].extend(data["sheets"])
            current_xlsx_data["total_sheets"] = len(current_xlsx_data["sheets"])
            current_xlsx_data["total_posts"] += data["total_posts"]
        else:
            current_xlsx_data = data
        
        profiles = profile_manager.discover_profiles()
        if not profiles:
            raise HTTPException(status_code=400, detail="No profiles available")
        
        loaded_count = queue_manager.append_posts(data["sheets"], profiles)
        
        stats = queue_manager.get_stats()
        
        logger.info(f"Appended {loaded_count} posts from {len(data['sheets'])} sheets")
        return {
            "status": "appended",
            "posts_added": loaded_count,
            "total_pending": stats["pending"],
            "total_sheets": stats["total_sheets"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in append_xlsx: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/launch")
async def launch_profiles():
    """Launch all Chrome profiles"""
    try:
        results = profile_manager.launch_all_profiles()
        
        launched = [pid for pid, success in results.items() if success]
        failed = [pid for pid, success in results.items() if not success]
        
        logger.info(f"Launched: {launched}, Failed: {failed}")
        
        return {
            "launched": launched,
            "failed": failed
        }
    except Exception as e:
        logger.error(f"Error in launch_profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/detect")
async def detect_profiles():
    """Detect profiles that are already running"""
    try:
        results = profile_manager.detect_running_profiles()
        
        detected = [pid for pid, found in results.items() if found]
        not_found = [pid for pid, found in results.items() if not found]
        
        logger.info(f"Detected running: {detected}, Not running: {not_found}")
        
        return {
            "detected": detected,
            "not_found": not_found,
            "count": len(detected)
        }
    except Exception as e:
        logger.error(f"Error in detect_profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profiles/status")
async def get_profiles_status():
    """Get status of all profiles"""
    try:
        status = profile_manager.get_status()
        return {"profiles": status}
    except Exception as e:
        logger.error(f"Error in get_profiles_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/shutdown")
async def shutdown_profiles():
    """Shutdown all Chrome processes"""
    try:
        profile_manager.shutdown_all()
        logger.info("All profiles shut down")
        return {"status": "shutdown"}
    except Exception as e:
        logger.error(f"Error in shutdown_profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/automation/start")
async def start_automation(request: AutomationStartRequest):
    """Start posting automation with scheduler"""
    try:
        async def cycle_wrapper():
            await posting_engine.run_cycle(
                profile_manager,
                queue_manager,
                playwright_instance,
                current_settings
            )
        
        config = request.model_dump()
        scheduler.start(request.mode, config, cycle_wrapper)
        
        next_run = scheduler.get_next_run()
        
        logger.info(f"Automation started in {request.mode} mode")
        
        return {
            "status": "started",
            "next_run": next_run
        }
    except Exception as e:
        logger.error(f"Error in start_automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/automation/stop")
async def stop_automation():
    """Stop posting automation"""
    try:
        scheduler.stop()
        logger.info("Automation stopped")
        return {"status": "stopped"}
    except Exception as e:
        logger.error(f"Error in stop_automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/automation/run-now")
async def run_now():
    """Execute an immediate posting cycle (manual post)"""
    try:
        status = profile_manager.get_status()
        running_profiles = [pid for pid, data in status.items() if data.get("running", False)]
        
        if not running_profiles:
            raise HTTPException(status_code=400, detail="No profiles are running")
        
        stats = queue_manager.get_stats()
        if stats["pending"] == 0:
            raise HTTPException(status_code=400, detail="No pending tasks in queue")
        
        next_sheet = queue_manager.get_next_sheet_index()
        logger.info(f"Manual post triggered - {len(running_profiles)} profiles, {stats['pending']} pending tasks, next sheet: {next_sheet}")
        
        await posting_engine.run_cycle(
            profile_manager,
            queue_manager,
            playwright_instance,
            current_settings
        )
        
        new_stats = queue_manager.get_stats()
        logger.info("Manual post cycle completed")
        
        return {
            "status": "completed",
            "profiles_used": len(running_profiles),
            "current_sheet": new_stats["current_sheet"],
            "sheets_remaining": new_stats["sheets_remaining"],
            "pending": new_stats["pending"],
            "done": new_stats["done"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in run_now: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/automation/status")
async def get_automation_status():
    """Get automation status"""
    try:
        status = scheduler.get_status()
        return status
    except Exception as e:
        logger.error(f"Error in get_automation_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/status")
async def get_queue_status():
    """Get queue statistics with sheet tracking"""
    try:
        stats = queue_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error in get_queue_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/tasks")
async def get_queue_tasks(limit: int = 0):
    """Get queue tasks. limit=0 means all."""
    try:
        tasks = queue_manager.get_tasks(limit=limit)
        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"Error in get_queue_tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns/details")
async def get_campaigns_details():
    """Get detailed information for all campaigns"""
    try:
        details = queue_manager.get_all_campaigns_details()
        return details
    except Exception as e:
        logger.error(f"Error in get_campaigns_details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/queue/reset")
async def reset_queue():
    """Reset queue and reload from XLSX"""
    try:
        if not current_xlsx_data:
            raise HTTPException(status_code=400, detail="No XLSX file loaded")
        
        profiles = profile_manager.discover_profiles()
        if not profiles:
            raise HTTPException(status_code=400, detail="No profiles available")
        
        loaded_count = queue_manager.load_posts(current_xlsx_data["sheets"], profiles)
        logger.info(f"Queue reset: {loaded_count} posts loaded from XLSX")
        return {"status": "reset", "tasks": loaded_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset_queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings")
async def get_settings():
    """Get current settings"""
    return current_settings


@app.post("/settings/save")
async def save_settings_endpoint(request: SettingsRequest):
    """Save settings (supports partial updates)"""
    global current_settings
    
    try:
        # Merge incoming settings with existing (partial update support)
        incoming = request.model_dump(exclude_unset=True)
        current_settings.update(incoming)
        save_settings(current_settings)
        
        # Update base_port if changed
        profile_manager.base_port = current_settings["base_port"]
        
        logger.info(f"Settings saved: {list(incoming.keys())}")
        
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Error in save_settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/recent")
async def get_recent_logs():
    """Get recent log lines efficiently using tail-like reading"""
    try:
        log_path = PROJECT_ROOT / "logs" / "app.log"
        
        if not log_path.exists():
            return {"logs": []}
        
        # Read only the last 500 lines efficiently
        lines = []
        with open(log_path, 'rb') as f:
            # Seek to end and read last ~500KB (assuming ~100 bytes per line)
            f.seek(0, 2)
            file_size = f.tell()
            read_size = min(file_size, 50000)  # Read max 50KB
            f.seek(max(0, file_size - read_size))
            raw = f.read().decode('utf-8', errors='ignore')
            lines = raw.splitlines()[-500:]
        
        return {"logs": lines}
    except Exception as e:
        logger.error(f"Error in get_recent_logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profiles/diagnostics")
async def get_profile_diagnostics():
    """Get diagnostic information about profile configuration"""
    try:
        # Discover profiles
        profiles = profile_manager.discover_profiles()
        
        # Get status
        status = profile_manager.get_status()
        
        # Get folder names
        folder_names = profile_manager.get_folder_names()
        
        # Get readiness check
        readiness = profile_manager.check_profiles_ready()
        
        # Check port assignments
        port_info = {}
        for profile_id in profiles:
            expected_port = profile_manager.base_port + (profile_id - 1)
            actual_status = status.get(profile_id, {})
            
            port_info[profile_id] = {
                "expected_port": expected_port,
                "actual_port": actual_status.get("port"),
                "is_running": actual_status.get("running", False),
                "folder_name": folder_names.get(profile_id),
                "ready": readiness.get(profile_id, {}).get("ready", False),
                "message": readiness.get(profile_id, {}).get("message", "Unknown")
            }
        
        # Check task distribution
        task_distribution = {}
        try:
            conn = queue_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT profile_id, status, COUNT(*) as count
                FROM tasks
                GROUP BY profile_id, status
            """)
            
            for row in cursor.fetchall():
                profile_id = row[0]
                status_type = row[1]
                count = row[2]
                
                if profile_id not in task_distribution:
                    task_distribution[profile_id] = {"pending": 0, "done": 0, "failed": 0}
                
                task_distribution[profile_id][status_type] = count
        except Exception as e:
            logger.warning(f"Could not get task distribution: {e}")
        
        return {
            "total_profiles": len(profiles),
            "profile_ids": profiles,
            "port_info": port_info,
            "task_distribution": task_distribution,
            "base_port": profile_manager.base_port,
            "port_range": f"{profile_manager.base_port}-{profile_manager.base_port + len(profiles) - 1}"
        }
    except Exception as e:
        logger.error(f"Error in get_profile_diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/campaigns/{profile_id}")
async def delete_campaign(profile_id: int):
    """Delete a campaign and all its associated data"""
    try:
        # Get profile info before deletion
        profiles = profile_manager.get_status()
        
        if str(profile_id) not in profiles:
            raise HTTPException(status_code=404, detail=f"Campaign {profile_id} not found")
        
        profile_info = profiles[str(profile_id)]
        profile_name = profile_info.get("folder_name", f"Campaign {profile_id}")
        
        # Shut down the profile if running
        if profile_info.get("running", False):
            logger.info(f"Shutting down running profile {profile_id}")
            profile_manager.shutdown_profile(profile_id)
        
        # Delete all tasks associated with this profile
        deleted_tasks = queue_manager.delete_campaign_tasks(profile_id)
        
        logger.info(f"Deleted campaign {profile_id} ({profile_name}): {deleted_tasks} tasks removed")
        
        return {
            "status": "deleted",
            "profile_id": profile_id,
            "profile_name": profile_name,
            "tasks_deleted": deleted_tasks
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Main entry point
if __name__ == "__main__":
    logger.info("Starting uvicorn server on http://0.0.0.0:8765")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
