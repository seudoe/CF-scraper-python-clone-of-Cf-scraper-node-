"""
Browser profile management utility.
Use this to inspect or clear the persistent Chrome profile.
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

from lib.browser_config import get_profile_info, clear_profile, PROFILE_DIR
from lib.colors import cyan, yellow, green, info, success

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'clear':
        print(yellow('[profile] Clearing browser profile...'))
        clear_profile()
        print(success('[profile] Profile cleared! Next run will start fresh.'))
        return
    
    # Show profile info
    print(cyan('[profile] ================================'))
    print(cyan('[profile] Browser Profile Information'))
    print(cyan('[profile] ================================\n'))
    
    profile_info = get_profile_info()
    
    if profile_info['exists']:
        print(success(f'[profile] Profile exists: {profile_info["path"]}'))
        print(info(f'[profile] Size: {profile_info["size_mb"]} MB'))
        print()
        print(info('[profile] This profile contains:'))
        print(info('  - Cookies (including cf_clearance)'))
        print(info('  - Browser cache'))
        print(info('  - Local storage'))
        print(info('  - IndexedDB'))
        print(info('  - Session data'))
        print(info('  - Browser preferences'))
        print()
        print(yellow('[profile] To clear profile: python manage_profile.py clear'))
    else:
        print(yellow('[profile] No profile exists yet'))
        print(info(f'[profile] Profile will be created at: {profile_info["path"]}'))
        print(info('[profile] Run any script to create the profile'))
    
    print(cyan('\n[profile] ================================'))

if __name__ == '__main__':
    main()
