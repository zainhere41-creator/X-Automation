"""
Bulk Port Fix - Fix Port Numbers for All Existing Profiles

This script:
1. Scans all profile folders
2. Reads each shortcut
3. Updates port numbers to match ProfileManager's expectations
4. Works with any number of profiles (2, 20, 30, etc.)

Usage:
    python fix_all_ports.py
    python fix_all_ports.py --profiles-folder "C:/path/to/profiles"
    python fix_all_ports.py --base-port 9222
"""

import sys
import argparse
import re
from pathlib import Path

# Check for pywin32
try:
    import win32com.client
    PYWIN32_AVAILABLE = True
except ImportError:
    print("❌ ERROR: pywin32 is required")
    print("   Install with: pip install pywin32")
    sys.exit(1)


def fix_all_ports(profiles_root: str, base_port: int = 9222, dry_run: bool = False):
    """
    Fix port numbers for all profiles in a folder.
    
    Args:
        profiles_root: Path to profiles folder
        base_port: Base port number (default 9222)
        dry_run: If True, only show what would be changed without actually changing
    """
    
    profiles_path = Path(profiles_root)
    
    if not profiles_path.exists():
        print(f"❌ ERROR: Folder not found: {profiles_path}")
        sys.exit(1)
    
    # Get all subfolders
    subfolders = sorted([d for d in profiles_path.iterdir() if d.is_dir()], 
                       key=lambda d: d.name.lower())
    
    if not subfolders:
        print(f"❌ ERROR: No subfolders found in {profiles_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("BULK PORT FIX TOOL")
    print("=" * 70)
    print()
    print(f"Profiles folder: {profiles_path.absolute()}")
    print(f"Found {len(subfolders)} profile folders")
    print(f"Base port: {base_port}")
    print(f"Expected port range: {base_port} - {base_port + len(subfolders) - 1}")
    if dry_run:
        print(f"Mode: DRY RUN (no changes will be made)")
    print()
    
    # Collect shortcuts and check for issues
    shell = win32com.client.Dispatch("WScript.Shell")
    fixes_needed = []
    profiles_ok = []
    profiles_no_shortcut = []
    
    for profile_id, folder in enumerate(subfolders, start=1):
        # Find .lnk file
        lnk_files = list(folder.glob("*.lnk"))
        
        if not lnk_files:
            profiles_no_shortcut.append((profile_id, folder.name))
            continue
        
        lnk_path = lnk_files[0]
        expected_port = base_port + (profile_id - 1)
        
        try:
            shortcut = shell.CreateShortCut(str(lnk_path))
            arguments = shortcut.Arguments
            
            # Extract current port
            match = re.search(r'--remote-debugging-port[=\s]+(\d+)', arguments)
            
            if not match:
                # No port in shortcut - this is actually OK, ProfileManager will add it
                profiles_ok.append((profile_id, folder.name, "No port (OK)"))
                continue
            
            current_port = int(match.group(1))
            
            if current_port != expected_port:
                fixes_needed.append({
                    "profile_id": profile_id,
                    "folder": folder.name,
                    "lnk_path": lnk_path,
                    "current_port": current_port,
                    "expected_port": expected_port,
                    "arguments": arguments,
                    "target": shortcut.TargetPath
                })
            else:
                profiles_ok.append((profile_id, folder.name, current_port))
        
        except Exception as e:
            print(f"⚠ Profile {profile_id} ({folder.name}): Error reading shortcut - {e}")
    
    # Report
    print("Analysis Results:")
    print()
    
    if profiles_ok:
        print(f"✓ {len(profiles_ok)} profiles with correct ports:")
        for profile_id, folder, port in profiles_ok[:5]:  # Show first 5
            print(f"  Profile {profile_id:2d} ({folder:20s}): Port {port if isinstance(port, int) else port}")
        if len(profiles_ok) > 5:
            print(f"  ... and {len(profiles_ok) - 5} more")
        print()
    
    if profiles_no_shortcut:
        print(f"⚠ {len(profiles_no_shortcut)} profiles without shortcuts:")
        for profile_id, folder in profiles_no_shortcut:
            print(f"  Profile {profile_id:2d} ({folder})")
        print()
    
    if fixes_needed:
        print(f"❌ {len(fixes_needed)} profiles with INCORRECT ports:")
        print()
        for fix in fixes_needed:
            print(f"  Profile {fix['profile_id']:2d} ({fix['folder']:20s}): "
                  f"{fix['current_port']} → {fix['expected_port']}")
        print()
    else:
        print("✅ ALL PORTS ARE CORRECT!")
        print()
        print("No fixes needed. Your profiles are properly configured.")
        return
    
    # Ask for confirmation
    if dry_run:
        print("Dry run complete. Run without --dry-run to apply fixes.")
        return
    
    print("=" * 70)
    response = input(f"Fix {len(fixes_needed)} shortcuts? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("Cancelled.")
        return
    
    # Apply fixes
    print()
    print("Applying fixes...")
    print()
    
    fixed = 0
    failed = 0
    
    for fix in fixes_needed:
        try:
            shortcut = shell.CreateShortCut(str(fix["lnk_path"]))
            
            # Replace port in arguments
            new_arguments = re.sub(
                r'--remote-debugging-port[=\s]+\d+',
                f'--remote-debugging-port={fix["expected_port"]}',
                fix["arguments"]
            )
            
            shortcut.Arguments = new_arguments
            shortcut.Save()
            
            fixed += 1
            print(f"✓ Profile {fix['profile_id']:2d} ({fix['folder']:20s}): "
                  f"Port {fix['current_port']} → {fix['expected_port']}")
        
        except Exception as e:
            failed += 1
            print(f"✗ Profile {fix['profile_id']:2d}: Failed - {e}")
    
    print()
    print("=" * 70)
    print(f"COMPLETE: Fixed {fixed}/{len(fixes_needed)} shortcuts")
    if failed > 0:
        print(f"Failed: {failed}")
    print("=" * 70)
    print()
    
    print("Next steps:")
    print("1. Open your X Posting Automation app")
    print("2. Go to Setup tab")
    print("3. Click 'Reset Queue' (to redistribute tasks)")
    print("4. Click 'Launch Profiles'")
    print()
    print("All profiles should now launch successfully!")
    print()


def main():
    parser = argparse.ArgumentParser(description="Fix port numbers for all profile shortcuts")
    parser.add_argument('--profiles-folder', type=str, default='profiles', 
                       help='Path to profiles folder (default: profiles)')
    parser.add_argument('--base-port', type=int, default=9222,
                       help='Base port number (default: 9222)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without making changes')
    
    args = parser.parse_args()
    
    fix_all_ports(
        profiles_root=args.profiles_folder,
        base_port=args.base_port,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
