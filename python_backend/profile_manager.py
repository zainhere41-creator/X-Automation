import subprocess
import sys
import time
import socket
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Import pywin32 for reading Windows shortcuts
try:
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    logger.warning("pywin32 not available - shortcut reading disabled")


class ProfileManager:
    """Manages Chrome profile lifecycle - launching, connection, disconnection, and shutdown."""
    
    def __init__(self, profiles_root: str = "profiles", base_port: int = 9222):
        """
        Initialize ProfileManager.
        
        Args:
            profiles_root: Path to accounts folder (contains subfolders with .lnk files)
            base_port: Base CDP port (9222 default)
        """
        self.profiles_root = Path(profiles_root)
        self.base_port = base_port
        self._ports: dict[int, int] = {}
        self._processes: dict[int, subprocess.Popen] = {}
        self._cdp_urls: dict[int, str] = {}
        self._shortcuts: dict[int, dict] = {}  # Maps profile_id -> shortcut data
        self._folder_names: dict[int, str] = {}  # Maps profile_id -> folder name
        self._temp_dirs: dict[int, str] = {}  # Maps profile_id -> temp user-data-dir path
    
    def read_shortcut(self, lnk_path: Path) -> Optional[dict]:
        """
        Read a Windows .lnk shortcut file and extract Chrome launch parameters.
        
        Returns dict with:
            - chrome_exe: Path to chrome.exe
            - user_data_dir: Chrome User Data directory
            - profile_directory: Profile folder name (e.g., "Profile 1")
        
        Returns None on error.
        """
        if not PYWIN32_AVAILABLE:
            logger.error("pywin32 not installed - cannot read shortcuts")
            return None
        
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(lnk_path))
            
            chrome_exe = shortcut.TargetPath
            arguments = shortcut.Arguments
            
            logger.info(f"Reading shortcut: {lnk_path.name}")
            logger.info(f"  Target: {chrome_exe}")
            logger.info(f"  Arguments: {arguments}")
            
            # Get default Chrome User Data location
            import os
            default_user_data = str(Path(os.getenv('LOCALAPPDATA')) / 'Google' / 'Chrome' / 'User Data')
            
            # Parse arguments to extract user-data-dir and profile-directory
            user_data_dir = None
            profile_directory = None
            
            # Extract --user-data-dir (multiple pattern attempts)
            if '--user-data-dir' in arguments:
                # Try with quotes
                match = re.search(r'--user-data-dir="([^"]+)"', arguments)
                if match:
                    user_data_dir = match.group(1)
                else:
                    # Try without quotes
                    match = re.search(r'--user-data-dir=([^\s]+)', arguments)
                    if match:
                        user_data_dir = match.group(1)
            
            # Extract --profile-directory (multiple pattern attempts)
            if '--profile-directory' in arguments:
                # Try with quotes
                match = re.search(r'--profile-directory="([^"]+)"', arguments)
                if match:
                    profile_directory = match.group(1)
                else:
                    # Try without quotes
                    match = re.search(r'--profile-directory=([^\s]+)', arguments)
                    if match:
                        profile_directory = match.group(1)
            
            # CRITICAL FIX: If no user-data-dir specified, Chrome uses default location
            if not user_data_dir:
                user_data_dir = default_user_data
                logger.info(f"  No --user-data-dir in shortcut, using Chrome's default: {user_data_dir}")
            
            # CRITICAL FIX: If no profile-directory specified, Chrome uses "Default"
            if not profile_directory:
                profile_directory = "Default"
                logger.info(f"  No --profile-directory in shortcut, using: {profile_directory}")
            
            # Verify the profile actually exists
            profile_path = Path(user_data_dir) / profile_directory
            
            if not profile_path.exists():
                logger.error(f"  ❌ Profile path does not exist: {profile_path}")
                logger.error(f"  This profile will be created empty (no cookies/login)")
                # Don't return None - still try to launch, user might want to set it up
            else:
                logger.info(f"  ✓ Profile path exists: {profile_path}")
                
                # Check for cookies
                cookies_path = profile_path / "Cookies"
                if cookies_path.exists():
                    logger.info(f"  ✓ Cookies found - profile has saved logins")
                else:
                    logger.warning(f"  ⚠ No Cookies file - profile may not have saved logins")
            
            return {
                "chrome_exe": chrome_exe,
                "user_data_dir": user_data_dir,
                "profile_directory": profile_directory
            }
            
        except Exception as e:
            logger.error(f"Failed to read shortcut {lnk_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def discover_profiles(self) -> list[int]:
        """
        Scan profiles_root for subfolders containing .lnk shortcut files.
        Each subfolder represents one account/profile.
        
        Returns list of profile IDs (1, 2, 3...) based on alphabetical folder order.
        """
        if not self.profiles_root.exists():
            logger.warning(f"Profiles root {self.profiles_root} does not exist")
            return []
        
        # Get all subdirectories
        subfolders = [d for d in self.profiles_root.iterdir() if d.is_dir()]
        
        if not subfolders:
            logger.warning(f"No subfolders found in {self.profiles_root}")
            return []
        
        # Sort alphabetically
        subfolders.sort(key=lambda d: d.name.lower())
        
        profiles = []
        for profile_id, subfolder in enumerate(subfolders, start=1):
            # Find first .lnk file in this subfolder
            lnk_files = list(subfolder.glob("*.lnk"))
            
            if not lnk_files:
                logger.warning(f"No .lnk file found in {subfolder.name} - skipping")
                continue
            
            lnk_path = lnk_files[0]
            logger.info(f"Reading shortcut: {subfolder.name}/{lnk_path.name}")
            
            # Read shortcut data
            shortcut_data = self.read_shortcut(lnk_path)
            
            if not shortcut_data:
                logger.warning(f"Could not read shortcut in {subfolder.name} - skipping")
                continue
            
            # Store shortcut data and folder name
            self._shortcuts[profile_id] = shortcut_data
            self._folder_names[profile_id] = subfolder.name
            profiles.append(profile_id)
            
            logger.info(f"Profile {profile_id} ({subfolder.name}): {shortcut_data['profile_directory']}")
        
        logger.info(f"Discovered {len(profiles)} profiles: {profiles}")
        logger.info(f"Folder names: {[self._folder_names[pid] for pid in profiles]}")
        
        return profiles
    
    def get_folder_names(self) -> dict[int, str]:
        """Return mapping of profile_id -> folder name for display purposes."""
        return self._folder_names.copy()
    
    def check_profiles_ready(self) -> dict[int, dict]:
        """
        Check if all discovered profiles are ready for automation.
        Returns dict with profile_id -> status info.
        
        Status info includes:
            - ready: bool - Profile has cookies and is ready for automation
            - exists: bool - Profile directory exists
            - has_cookies: bool - Profile has Cookies file
            - message: str - Human readable status
        """
        status = {}
        
        for profile_id, shortcut_data in self._shortcuts.items():
            user_data_dir = shortcut_data["user_data_dir"]
            profile_directory = shortcut_data["profile_directory"]
            profile_path = Path(user_data_dir) / profile_directory
            
            # Check multiple cookie file locations
            cookie_files = [
                profile_path / "Cookies",
                profile_path / "Network" / "Cookies",
                profile_path / "Cookies-journal"
            ]
            
            exists = profile_path.exists()
            
            # Check if ANY cookie file exists
            has_cookies = False
            found_cookie_files = []
            if exists:
                for cookie_file in cookie_files:
                    if cookie_file.exists():
                        has_cookies = True
                        found_cookie_files.append(cookie_file.name)
                        logger.debug(f"Profile {profile_id}: Found {cookie_file.name} ({cookie_file.stat().st_size} bytes)")
            
            ready = exists and has_cookies
            
            if ready:
                message = f"Ready - Profile has login data ({', '.join(found_cookie_files)})"
            elif not exists:
                message = "New profile - Need to log into X"
            else:
                # Profile exists but no cookies
                logger.warning(f"Profile {profile_id} path exists but no cookies found:")
                logger.warning(f"  Checked: {profile_path}")
                logger.warning(f"  Looking for: Cookies, Network/Cookies, Cookies-journal")
                
                # List what IS in the profile folder to help diagnose
                if profile_path.exists() and profile_path.is_dir():
                    try:
                        contents = list(profile_path.iterdir())
                        logger.warning(f"  Folder contains {len(contents)} items")
                        # Log first few items
                        for item in contents[:10]:
                            logger.warning(f"    - {item.name}")
                    except Exception as e:
                        logger.warning(f"  Could not list folder contents: {e}")
                
                message = "Profile exists but no cookies - May need to log in"
            
            status[profile_id] = {
                "ready": ready,
                "exists": exists,
                "has_cookies": has_cookies,
                "message": message,
                "folder_name": self._folder_names.get(profile_id, str(profile_id))
            }
        
        return status
    
    def _clean_locks(self, user_data_dir: str, profile_directory: str) -> None:
        """Remove Chrome singleton lock files to allow fresh launch."""
        # Build real profile path
        real_path = Path(user_data_dir) / profile_directory
        
        lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
        for lock_file in lock_files:
            lock_path = real_path / lock_file
            if lock_path.exists():
                try:
                    lock_path.unlink()
                    logger.debug(f"Deleted {lock_file} from {real_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete {lock_file}: {e}")
    
    def _is_port_open(self, port: int, timeout: float = 0.5) -> bool:
        """Check if a port is reachable."""
        try:
            with socket.create_connection(("localhost", port), timeout=timeout):
                return True
        except (socket.timeout, socket.error, ConnectionRefusedError, OSError):
            return False
    

    
    def _cleanup_temp_dirs(self):
        """Clean up all orphaned temp directories from previous runs."""
        for profile_id in list(self._temp_dirs.keys()):
            try:
                shutil.rmtree(self._temp_dirs[profile_id], ignore_errors=True)
                del self._temp_dirs[profile_id]
            except Exception:
                pass
        # Also clean any leftover temp dirs in system temp
        import glob as glob_mod
        for d in glob_mod.glob(str(Path(tempfile.gettempdir()) / "profile_*")):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
    
    def launch_profile(self, profile_id: int) -> bool:
        """Launch a single Chrome instance with CDP debugging enabled using shortcut data."""
        port = self.base_port + (profile_id - 1)
        
        # Get shortcut data
        shortcut_data = self._shortcuts.get(profile_id)
        if not shortcut_data:
            logger.error(f"Profile {profile_id}: No shortcut data available")
            return False
        
        chrome_exe = shortcut_data["chrome_exe"]
        user_data_dir = shortcut_data["user_data_dir"]
        profile_directory = shortcut_data["profile_directory"]
        folder_name = self._folder_names.get(profile_id, str(profile_id))
        
        logger.info(f"{'='*60}")
        logger.info(f"Launching Profile {profile_id} ({folder_name})")
        logger.info(f"{'='*60}")
        logger.info(f"Chrome: {chrome_exe}")
        logger.info(f"User Data: {user_data_dir}")
        logger.info(f"Profile: {profile_directory}")
        logger.info(f"CDP Port: {port}")
        
        # Check if port is already in use by another process
        if self._is_port_open(port, timeout=0.3):
            logger.warning(f"Port {port} is already in use!")
            
            # Check if it's OUR process (already launched)
            existing_process = self._processes.get(profile_id)
            if existing_process and existing_process.poll() is None:
                logger.info(f"Profile {profile_id}: Already running (PID {existing_process.pid}), reusing")
                self._ports[profile_id] = port
                self._cdp_urls[profile_id] = f"http://localhost:{port}"
                return True
            
            # Port is used by something else - try to kill it
            logger.warning(f"Port {port} used by another process, attempting to free it...")
            try:
                import subprocess as sp
                result = sp.run(
                    ['netstat', '-ano'], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts:
                            old_pid = int(parts[-1])
                            if old_pid > 0:
                                logger.info(f"Killing process {old_pid} on port {port}")
                                sp.run(['taskkill', '/F', '/PID', str(old_pid)], 
                                       capture_output=True, timeout=5)
                                time.sleep(1)
            except Exception as e:
                logger.warning(f"Could not free port {port}: {e}")
            
            # Re-check if port is now free
            if self._is_port_open(port, timeout=0.3):
                logger.error(f"Port {port} still in use after cleanup")
                return False
        
        # Build full profile path and check if it exists/has cookies
        profile_path = Path(user_data_dir) / profile_directory
        cookies_path = profile_path / "Cookies"
        
        profile_needs_setup = False
        
        if not profile_path.exists():
            logger.warning(f"Profile path does not exist yet: {profile_path}")
            logger.warning(f"Chrome will create a NEW profile - you'll need to log into X")
            profile_needs_setup = True
        elif not cookies_path.exists():
            logger.warning(f"No cookies found in profile")
            logger.warning(f"Profile exists but may not be logged into X")
            profile_needs_setup = True
        else:
            logger.info(f"✓ Profile has cookies - should be logged in")
        
        # Clean lock files
        if profile_path.exists():
            self._clean_locks(user_data_dir, profile_directory)
        
        # Clean up any orphaned temp dir from a previous failed launch
        if profile_id in self._temp_dirs:
            try:
                shutil.rmtree(self._temp_dirs[profile_id], ignore_errors=True)
            except Exception:
                pass
        
        # CRITICAL: Create isolated user-data-dir for this profile
        # Multiple Chrome instances cannot share the same user-data-dir
        # (SingletonLock conflict causes second instance to fail)
        isolated_user_data = tempfile.mkdtemp(prefix=f"profile_{profile_id}_")
        
        try:
            source_root = Path(user_data_dir)
            
            if source_root.exists():
                # Only copy essential files, NOT the entire User Data directory
                # This saves time and disk space (User Data can be 100GB+)
                skip_dirs = {'SingletonLock', 'SingletonSocket', 'SingletonCookie',
                             'Cache', 'Code Cache', 'GPUCache', 'Service Worker',
                             'Service Worker/ScriptCache', 'Service Worker/CacheStorage',
                             'IndexedDB', 'Local Storage', 'Session Storage',
                             'WebStorage', 'databases', 'blob_storage'}
                
                # 1. Copy Local State file (contains encryption keys)
                local_state = source_root / "Local State"
                if local_state.exists():
                    shutil.copy2(str(local_state), str(Path(isolated_user_data) / "Local State"))
                
                # 2. Copy the specific profile directory
                source_profile = source_root / profile_directory
                if source_profile.exists():
                    dest_profile = Path(isolated_user_data) / profile_directory
                    shutil.copytree(str(source_profile), str(dest_profile),
                                  ignore=lambda src, names: [n for n in names if n in skip_dirs])
                    logger.info(f"Copied profile directory: {profile_directory}")
                else:
                    # Create empty profile directory
                    dest_profile = Path(isolated_user_data) / profile_directory
                    dest_profile.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created empty profile directory: {profile_directory}")
                
                # 3. Copy Default profile if it exists (shared data)
                default_profile = source_root / "Default"
                if default_profile.exists() and profile_directory != "Default":
                    dest_default = Path(isolated_user_data) / "Default"
                    shutil.copytree(str(default_profile), str(dest_default),
                                  ignore=lambda src, names: [n for n in names if n in skip_dirs])
                
                logger.info(f"Isolated profile created: {isolated_user_data}")
            else:
                isolated_profile_dir = Path(isolated_user_data) / profile_directory
                isolated_profile_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created empty isolated profile: {isolated_profile_dir}")
            
            self._temp_dirs[profile_id] = isolated_user_data
        except Exception as e:
            logger.error(f"Failed to create isolated profile dir: {e}")
            import traceback
            logger.error(traceback.format_exc())
            isolated_user_data = user_data_dir
        
        # Build Chrome command
        # IMPORTANT: Do NOT use --restore-last-session on first launch (profile setup)
        # It should be used on subsequent launches
        cmd = [
            chrome_exe,
            f"--user-data-dir={isolated_user_data}",
            f"--profile-directory={profile_directory}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-session-crashed-bubble",
            "--disable-extensions",
            "--disable-component-extensions-with-background-pages",
        ]
        
        # Only restore session if profile already exists with cookies
        if not profile_needs_setup:
            cmd.append("--restore-last-session")
        else:
            # Open to X login page for first time setup
            logger.info(f"Opening X login page for initial setup...")
        
        logger.info(f"Command: {' '.join(cmd)}")
        
        try:
            # Launch Chrome process
            if sys.platform == "win32":
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            logger.info(f"✓ Chrome started (PID {process.pid})")
            
            if profile_needs_setup:
                logger.warning(f"!")
                logger.warning(f"! IMPORTANT: Profile needs setup")
                logger.warning(f"! Please log into X (Twitter) in the Chrome window that opened")
                logger.warning(f"! Do NOT close Chrome - just log in and keep it open")
                logger.warning(f"!")
            
            # Wait for CDP port
            logger.info(f"Waiting for CDP port {port}...")
            for attempt in range(30):
                if self._is_port_open(port):
                    # Verify Chrome process is actually running
                    if process.poll() is not None:
                        logger.error(f"Chrome process exited with code {process.returncode} while waiting for port {port}")
                        return False
                    logger.info(f"✓ CDP port {port} ready (attempt {attempt + 1})")
                    self._processes[profile_id] = process
                    self._ports[profile_id] = port
                    self._cdp_urls[profile_id] = f"http://localhost:{port}"
                    logger.info(f"{'='*60}")
                    return True
                time.sleep(0.5)
            
            # Final check: is process still alive?
            if process.poll() is not None:
                logger.error(f"Chrome process exited with code {process.returncode}")
                logger.error(f"Chrome failed to start. Check if Chrome is installed at: {chrome_exe}")
            else:
                logger.error(f"CDP port {port} not ready after 15 seconds (process still running, PID {process.pid})")
                logger.error(f"This may be a firewall issue. Try: netstat -ano | findstr {port}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to launch: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def launch_all_profiles(self) -> dict[int, bool]:
        """Launch all discovered profiles sequentially with 2-second delays."""
        # Clean up any orphaned temp dirs from previous runs
        self._cleanup_temp_dirs()
        
        profiles = self.discover_profiles()
        results = {}
        
        if not profiles:
            logger.warning("No profiles found to launch")
            return results
        
        total = len(profiles)
        logger.info(f"Starting launch sequence for {total} profiles...")
        
        for index, profile_id in enumerate(profiles, start=1):
            logger.info(f"[{index}/{total}] Launching Profile {profile_id}...")
            results[profile_id] = self.launch_profile(profile_id)
            
            if profile_id != profiles[-1]:  # Don't wait after last profile
                time.sleep(2)
        
        # Final verification: check all launched processes are actually running
        time.sleep(1)
        verified_count = 0
        for profile_id, success in results.items():
            if success:
                process = self._processes.get(profile_id)
                if process and process.poll() is None:
                    verified_count += 1
                    logger.info(f"Profile {profile_id}: Process verified (PID {process.pid})")
                else:
                    logger.error(f"Profile {profile_id}: Process died after launch!")
                    results[profile_id] = False
        
        success_count = sum(results.values())
        failed_count = total - success_count
        
        logger.info(f"Launch complete: {success_count}/{total} profiles verified running")
        if failed_count > 0:
            failed_ids = [pid for pid, success in results.items() if not success]
            logger.warning(f"Failed profiles: {failed_ids}")
        
        return results
    
    def detect_running_profiles(self) -> dict[int, bool]:
        """
        Detect profiles that are already running (opened outside the app).
        Checks CDP ports and auto-registers them if accessible.
        
        Returns dict of profile_id -> detected (True if found running)
        """
        profiles = self.discover_profiles()
        results = {}
        
        for profile_id in profiles:
            port = self.base_port + (profile_id - 1)
            folder_name = self._folder_names.get(profile_id, str(profile_id))
            
            if self._is_port_open(port, timeout=0.5):
                logger.info(f"Profile {profile_id} ({folder_name}): Detected running on port {port}")
                
                # Register the port and CDP URL
                self._ports[profile_id] = port
                self._cdp_urls[profile_id] = f"http://localhost:{port}"
                results[profile_id] = True
            else:
                results[profile_id] = False
        
        running_count = sum(results.values())
        logger.info(f"Detected {running_count}/{len(profiles)} profiles already running")
        
        return results
    
    async def connect(self, profile_id: int, playwright_instance):
        """
        Connect Playwright to running Chrome via CDP.
        CRITICAL: ONLY uses connect_over_cdp() - NEVER launch_persistent_context()
        """
        cdp_url = self._cdp_urls.get(profile_id)
        if not cdp_url:
            raise ValueError(f"Profile {profile_id}: No CDP URL available")
        
        try:
            # CRITICAL: ONLY use connect_over_cdp() - NEVER launch_persistent_context()
            browser = await playwright_instance.chromium.connect_over_cdp(cdp_url)
            logger.info(f"Profile {profile_id}: Connected to CDP")
            
            # Get first browser context
            contexts = browser.contexts
            if not contexts:
                raise RuntimeError(f"Profile {profile_id}: No browser contexts available")
            
            context = contexts[0]
            
            # Use existing page or create new one
            pages = context.pages
            if pages:
                page = pages[0]
                logger.debug(f"Profile {profile_id}: Using existing page")
            else:
                page = await context.new_page()
                logger.debug(f"Profile {profile_id}: Created new page")
            
            return browser, page
            
        except Exception as e:
            logger.error(f"Profile {profile_id}: Failed to connect via CDP: {e}")
            raise
    
    async def disconnect(self, browser) -> None:
        """
        Disconnect Playwright from Chrome without closing the browser.
        CRITICAL: ONLY calls browser.close() - NEVER context.close() or page.close()
        Chrome process remains running after disconnect.
        """
        try:
            # CRITICAL: ONLY call browser.close() - NEVER context.close() or page.close()
            await browser.close()
            logger.info("Disconnected from browser (Chrome stays running)")
        except Exception as e:
            logger.error(f"Error during browser disconnect: {e}")
    
    def is_profile_running(self, profile_id: int) -> bool:
        """
        Check if a profile's Chrome process is running.
        Uses multiple methods:
        1. Check if we have a tracked process and if it's still alive
        2. Check if the CDP port is accessible (catches already-open Chrome)
        """
        # First check if we have a tracked process
        process = self._processes.get(profile_id)
        if process and process.poll() is None:
            return True
        
        # If no tracked process or it died, check if CDP port is accessible
        # This catches cases where Chrome was already running or launched externally
        port = self.base_port + (profile_id - 1)
        if self._is_port_open(port, timeout=0.3):
            # Port is accessible! Auto-reconnect the profile
            if profile_id not in self._processes:
                logger.info(f"Profile {profile_id}: Detected running on port {port} (reconnecting)")
                self._ports[profile_id] = port
                self._cdp_urls[profile_id] = f"http://localhost:{port}"
            return True
        
        return False
    
    def get_status(self) -> dict[int, dict]:
        """Return port, running status, CDP URL, and folder name for all discovered profiles."""
        status = {}
        
        # Get all discovered profiles (not just launched ones)
        all_profiles = list(self._shortcuts.keys())
        
        # If no profiles discovered yet, return empty
        if not all_profiles:
            return status
        
        # Check status for ALL discovered profiles (even if not launched by us)
        # Use a set to track ports we've already added to prevent duplicates
        seen_ports = set()
        
        for profile_id in all_profiles:
            port = self._ports.get(profile_id, self.base_port + (profile_id - 1))
            
            # Skip if we've already added this port (prevents duplicates)
            if port in seen_ports:
                logger.debug(f"Profile {profile_id}: Skipping duplicate port {port}")
                continue
            
            seen_ports.add(port)
            is_running = self.is_profile_running(profile_id)
            
            status[profile_id] = {
                "port": port,
                "running": is_running,
                "cdp_url": self._cdp_urls.get(profile_id, f"http://localhost:{port}"),
                "folder_name": self._folder_names.get(profile_id, str(profile_id))
            }
        
        return status
    
    def shutdown_all(self) -> None:
        """Terminate all managed Chrome processes."""
        logger.info("Shutting down all Chrome profiles")
        
        for profile_id, process in list(self._processes.items()):
            try:
                if process.poll() is None:  # Process still running
                    logger.info(f"Profile {profile_id}: Terminating Chrome (PID {process.pid})")
                    process.terminate()
            except Exception as e:
                logger.error(f"Profile {profile_id}: Error terminating: {e}")
        
        # Wait 3 seconds for graceful shutdown
        time.sleep(3)
        
        # Force kill any remaining processes
        for profile_id, process in list(self._processes.items()):
            try:
                if process.poll() is None:
                    logger.warning(f"Profile {profile_id}: Force killing Chrome (PID {process.pid})")
                    process.kill()
            except Exception as e:
                logger.error(f"Profile {profile_id}: Error killing: {e}")
        
        # Clean up isolated temp directories
        for profile_id, temp_dir in self._temp_dirs.items():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Profile {profile_id}: Cleaned up temp dir")
            except Exception as e:
                logger.error(f"Profile {profile_id}: Error cleaning temp dir: {e}")
        
        # Clear internal state
        self._processes.clear()
        self._ports.clear()
        self._cdp_urls.clear()
        self._temp_dirs.clear()
        
        logger.info("All Chrome profiles shut down")
    
    def shutdown_profile(self, profile_id: int) -> bool:
        """Terminate a single Chrome profile process."""
        logger.info(f"Shutting down profile {profile_id}")
        
        process = self._processes.get(profile_id)
        
        if not process:
            logger.warning(f"Profile {profile_id}: No process to shut down")
            return False
        
        try:
            if process.poll() is None:  # Process still running
                logger.info(f"Profile {profile_id}: Terminating Chrome (PID {process.pid})")
                process.terminate()
                
                # Wait up to 3 seconds for graceful shutdown
                for _ in range(6):
                    time.sleep(0.5)
                    if process.poll() is not None:
                        break
                
                # Force kill if still running
                if process.poll() is None:
                    logger.warning(f"Profile {profile_id}: Force killing Chrome (PID {process.pid})")
                    process.kill()
                    process.wait()
                
                logger.info(f"Profile {profile_id}: Successfully shut down")
            
            # Remove from internal state
            del self._processes[profile_id]
            if profile_id in self._ports:
                del self._ports[profile_id]
            if profile_id in self._cdp_urls:
                del self._cdp_urls[profile_id]
            
            # Clean up isolated temp directory
            if profile_id in self._temp_dirs:
                try:
                    shutil.rmtree(self._temp_dirs[profile_id], ignore_errors=True)
                    del self._temp_dirs[profile_id]
                except Exception as e:
                    logger.error(f"Profile {profile_id}: Error cleaning temp dir: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Profile {profile_id}: Error during shutdown: {e}")
            return False
