"""
Multi-Profile Generator - Create Profile Folders and Shortcuts

This script generates:
- N profile folders (1/, 2/, 3/, ..., N/)
- Chrome shortcuts with correct port numbers
- Profile directories (Profile 1, Profile 2, ..., Profile N)

Usage:
    # Auto-detect existing Chrome profiles (recommended for any laptop):
    python generate_profiles.py --use-existing

    # Create new profiles with specific count:
    python generate_profiles.py --count 30
    python generate_profiles.py --count 20 --start-profile 1
    python generate_profiles.py --count 30 --auto
"""

import sys
import os
import argparse
from pathlib import Path

try:
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("ERROR: pywin32 is required. Install with: pip install pywin32")
    sys.exit(1)


def detect_chrome_exe() -> str:
    """Auto-detect Chrome executable path."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def detect_user_data_dir() -> str:
    """Auto-detect Chrome User Data directory."""
    local_app = os.getenv("LOCALAPPDATA")
    if local_app:
        user_data = os.path.join(local_app, "Google", "Chrome", "User Data")
        if os.path.isdir(user_data):
            return user_data
    return None


def detect_existing_profiles(user_data_dir: str) -> list[str]:
    """
    Auto-detect existing Chrome profiles from User Data directory.
    Returns list of profile directory names (e.g., ["Default", "Profile 1", "Profile 3"]).
    """
    profiles = []
    user_data_path = Path(user_data_dir)
    
    if not user_data_path.exists():
        return profiles
    
    # Chrome profiles are directories that contain a "Preferences" file
    # or a "Secure Preferences" file
    for item in user_data_path.iterdir():
        if not item.is_dir():
            continue
        
        # Skip system directories
        if item.name in ['ShaderCache', 'GrShaderCache', 'GPUCache', 'Cache',
                         'Code Cache', 'Service Worker', 'Service Worker/ScriptCache',
                         'Service Worker/CacheStorage', 'IndexedDB', 'Local Storage',
                         'Session Storage', 'WebStorage', 'databases', 'blob_storage',
                         'File System', 'GCM Store', 'Extension State', 'Extension Rules',
                         'Extension Scripts', 'Extension Cookies', 'Managed Extension',
                         'Platform Notifications', 'Sync Extension Settings',
                         'WebrtcNetworkCache', 'JumpListIcons', 'JumpListIconsMostVisited',
                         'JumpListIconsRecentlyClosed', 'BudgetDatabase',
                         'heavy_ad_intervention', 'Subresource Filter']:
            continue
        
        # Check if it's a profile directory (has Preferences or Secure Preferences)
        preferences = item / "Preferences"
        secure_preferences = item / "Secure Preferences"
        
        if preferences.exists() or secure_preferences.exists():
            profiles.append(item.name)
    
    # Sort naturally (Default first, then Profile 1, Profile 2, etc.)
    def sort_key(name):
        if name == "Default":
            return (0, 0)
        if name.startswith("Profile "):
            try:
                num = int(name.split(" ")[1])
                return (1, num)
            except ValueError:
                return (2, name)
        return (3, name)
    
    profiles.sort(key=sort_key)
    return profiles


def generate_profiles(count: int, base_port: int = 9222, start_profile_num: int = 1,
                      user_data_dir: str = None, profiles_root: str = "profiles",
                      auto: bool = False, use_existing: bool = False):
    """
    Generate N profile folders with correct shortcuts.

    Args:
        count: Number of profiles to generate
        base_port: Starting port (default 9222)
        start_profile_num: Starting Chrome profile number (default 1)
        user_data_dir: Chrome User Data directory (auto-detected if None)
        profiles_root: Root folder to create profiles in
        auto: If True, skip confirmation prompt
        use_existing: If True, use existing Chrome profiles instead of creating new ones
    """
    # Auto-detect Chrome executable
    chrome_exe = detect_chrome_exe()
    if not chrome_exe:
        print("ERROR: Google Chrome not found.")
        print("Please install Chrome from: https://www.google.com/chrome/")
        sys.exit(1)

    # Auto-detect user data dir if not provided
    if not user_data_dir:
        user_data_dir = detect_user_data_dir()
        if not user_data_dir:
            print("ERROR: Chrome User Data directory not found.")
            print("Expected at: %%LOCALAPPDATA%%\\Google\\Chrome\\User Data")
            print("Please install Chrome or specify --user-data-dir manually.")
            sys.exit(1)

    profiles_path = Path(profiles_root)
    profiles_path.mkdir(exist_ok=True)

    # Auto-detect existing Chrome profiles
    existing_profiles = detect_existing_profiles(user_data_dir)
    
    if use_existing and existing_profiles:
        print("=" * 70)
        print(f"USING EXISTING CHROME PROFILES")
        print("=" * 70)
        print()
        print(f"Chrome:        {chrome_exe}")
        print(f"Profiles dir:  {profiles_path.absolute()}")
        print(f"User Data Dir: {user_data_dir}")
        print(f"Base port:     {base_port}")
        print(f"Found {len(existing_profiles)} existing profiles:")
        for i, profile in enumerate(existing_profiles, 1):
            print(f"  {i}. {profile}")
        print()
        
        if not auto:
            response = input(f"Create shortcuts for these {len(existing_profiles)} profiles? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                print("Cancelled.")
                return
        
        # Generate shortcuts for existing profiles
        print()
        print("Creating shortcuts...")
        print()
        
        shell = win32com.client.Dispatch("WScript.Shell")
        created = 0
        
        for i, profile_dir in enumerate(existing_profiles, 1):
            folder_path = profiles_path / str(i)
            folder_path.mkdir(exist_ok=True)
            
            port = base_port + (i - 1)
            shortcut_path = folder_path / f"{i}.lnk"
            
            try:
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.TargetPath = chrome_exe
                
                arguments = (
                    f'--profile-directory="{profile_dir}" '
                    f'--user-data-dir="{user_data_dir}" '
                    f'--remote-debugging-port={port}'
                )
                
                shortcut.Arguments = arguments
                shortcut.Description = f"Chrome {profile_dir} - Port {port}"
                shortcut.Save()
                
                created += 1
                print(f"  Profile {i:2d}: Folder={folder_path.name:3s}  Port={port}  ChromeProfile={profile_dir}")
                
            except Exception as e:
                print(f"  Profile {i}: FAILED - {e}")
        
        print()
        print("=" * 70)
        print(f"DONE: Created {created}/{len(existing_profiles)} shortcuts")
        print("=" * 70)
        
    else:
        # Generate new profiles with sequential numbers
        print("=" * 70)
        print(f"GENERATING {count} PROFILES")
        print("=" * 70)
        print()
        print(f"Chrome:        {chrome_exe}")
        print(f"Profiles dir:  {profiles_path.absolute()}")
        print(f"User Data Dir: {user_data_dir}")
        print(f"Base port:     {base_port}")
        print(f"Port range:    {base_port} - {base_port + count - 1}")
        print(f"Profiles:      Profile {start_profile_num} - Profile {start_profile_num + count - 1}")
        if existing_profiles:
            print(f"Note: Found {len(existing_profiles)} existing profiles: {', '.join(existing_profiles)}")
        print()

        if not auto:
            response = input(f"Create {count} profiles? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                print("Cancelled.")
                return

        print()
        print("Creating profiles...")
        print()

        shell = win32com.client.Dispatch("WScript.Shell")
        created = 0

        for i in range(1, count + 1):
            folder_path = profiles_path / str(i)
            folder_path.mkdir(exist_ok=True)

            port = base_port + (i - 1)
            profile_dir = f"Profile {start_profile_num + i - 1}"
            shortcut_path = folder_path / f"{i}.lnk"

            try:
                shortcut = shell.CreateShortCut(str(shortcut_path))
                shortcut.TargetPath = chrome_exe

                arguments = (
                    f'--profile-directory="{profile_dir}" '
                    f'--user-data-dir="{user_data_dir}" '
                    f'--remote-debugging-port={port}'
                )

                shortcut.Arguments = arguments
                shortcut.Description = f"Chrome Profile {i} - Port {port}"
                shortcut.Save()

                created += 1
                print(f"  Profile {i:2d}: Folder={folder_path.name:3s}  Port={port}  ChromeProfile={profile_dir}")

            except Exception as e:
                print(f"  Profile {i}: FAILED - {e}")

        print()
        print("=" * 70)
        print(f"DONE: Created {created}/{count} profiles")
        print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Open the app (double-click start.bat)")
    print("  2. Go to Setup tab")
    print(f"  3. Select the profiles folder: {profiles_path.absolute()}")
    print("  4. Load your XLSX file with posts")
    print("  5. Launch Profiles and start automation")
    print()


def main():
    parser = argparse.ArgumentParser(description="Generate multiple Chrome profiles with shortcuts")
    parser.add_argument("--count", type=int, default=30, help="Number of profiles (default: 30)")
    parser.add_argument("--base-port", type=int, default=9222, help="Starting port (default: 9222)")
    parser.add_argument("--start-profile", type=int, default=1, help="Starting Chrome profile number (default: 1)")
    parser.add_argument("--user-data-dir", type=str, help="Chrome User Data directory (auto-detected if omitted)")
    parser.add_argument("--output", type=str, default="profiles", help="Output folder (default: profiles)")
    parser.add_argument("--auto", action="store_true", help="Skip confirmation prompt (non-interactive)")
    parser.add_argument("--use-existing", action="store_true", help="Use existing Chrome profiles instead of creating new ones")

    args = parser.parse_args()

    if args.count < 1 or args.count > 1000:
        print("ERROR: Count must be between 1 and 1000")
        sys.exit(1)

    if args.base_port < 1024 or args.base_port > 65000:
        print("ERROR: Base port must be between 1024 and 65000")
        sys.exit(1)

    # Check if output folder already has profiles
    output_path = Path(args.output)
    if output_path.exists():
        existing = [d for d in output_path.iterdir() if d.is_dir()]
        if existing and not args.auto:
            print(f"WARNING: {args.output}/ already contains {len(existing)} folders")
            response = input("Overwrite existing profiles? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                print("Cancelled.")
                sys.exit(0)

    generate_profiles(
        count=args.count,
        base_port=args.base_port,
        start_profile_num=args.start_profile,
        user_data_dir=args.user_data_dir,
        profiles_root=args.output,
        auto=args.auto,
        use_existing=args.use_existing,
    )


if __name__ == "__main__":
    main()
