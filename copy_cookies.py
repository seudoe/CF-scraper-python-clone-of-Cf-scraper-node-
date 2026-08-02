"""
Copies cookies from your real Chrome profile into the scraper profile.
Run this once before scraping to give Selenium your real Cloudflare trust.

IMPORTANT: Close Chrome completely before running this.
"""

import sys
import shutil
import sqlite3
import os
from pathlib import Path

REAL_PROFILE  = Path(r'C:\Users\4dmin\AppData\Local\Google\Chrome\User Data\Default')
SCRAPER_PROFILE = Path(__file__).parent / 'chrome-profile' / 'Default'

def check_chrome_running():
    """Warn if Chrome is still open (profile will be locked)."""
    import subprocess
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
        capture_output=True, text=True
    )
    if 'chrome.exe' in result.stdout.lower():
        print('[!] Chrome is still running!')
        print('[!] Close Chrome completely before copying cookies.')
        print('[!] Otherwise the Cookies file will be locked and the copy will fail.')
        return True
    return False


def copy_cookies():
    src = REAL_PROFILE / 'Network' / 'Cookies'
    if not src.exists():
        # Older Chrome versions store Cookies directly in Default/
        src = REAL_PROFILE / 'Cookies'

    if not src.exists():
        print(f'[X] Could not find Cookies file at:\n    {src}')
        return False

    # Create destination folder structure
    dst_dir = SCRAPER_PROFILE / 'Network'
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / 'Cookies'

    # Copy
    try:
        shutil.copy2(src, dst)
        print(f'[OK] Cookies copied: {src}')
        print(f'     -> {dst}')
        return True
    except PermissionError:
        print(f'[X] Permission denied — Chrome is still holding the file.')
        print(f'    Close Chrome completely and try again.')
        return False
    except Exception as e:
        print(f'[X] Copy failed: {e}')
        return False


def count_cf_cookies(cookie_db: Path):
    """Count Cloudflare-related cookies in the database."""
    try:
        # Must copy to temp first since SQLite file may be WAL-locked
        tmp = cookie_db.parent / 'Cookies_tmp'
        shutil.copy2(cookie_db, tmp)
        conn = sqlite3.connect(tmp)
        cur = conn.cursor()
        cur.execute(
            "SELECT name, host_key FROM cookies WHERE host_key LIKE '%codeforces%' OR name LIKE '%cf_%'"
        )
        rows = cur.fetchall()
        conn.close()
        tmp.unlink(missing_ok=True)
        return rows
    except Exception as e:
        print(f'[!] Could not inspect cookies: {e}')
        return []


def main():
    print('=' * 50)
    print('  Chrome Cookie Copier for CF Scraper')
    print('=' * 50)
    print()

    # Check Chrome isn't running
    if check_chrome_running():
        answer = input('\nContinue anyway? (y/N): ').strip().lower()
        if answer != 'y':
            sys.exit(1)

    # Copy cookies
    print('\n[1] Copying Cookies file...')
    ok = copy_cookies()
    if not ok:
        sys.exit(1)

    # Inspect what we got
    dst = SCRAPER_PROFILE / 'Network' / 'Cookies'
    print('\n[2] Checking Codeforces cookies in copied file...')
    cf_cookies = count_cf_cookies(dst)

    if cf_cookies:
        print(f'\n[OK] Found {len(cf_cookies)} Codeforces/Cloudflare cookie(s):')
        for name, host in cf_cookies:
            print(f'     {name:30s}  {host}')
    else:
        print('\n[!] No Codeforces cookies found.')
        print('    This means you have never visited codeforces.com in this Chrome profile,')
        print('    OR the cookies expired.')
        print('    Visit https://codeforces.com in Chrome, then re-run this script.')

    print()
    print('[OK] Done! Now run:  python fetch_random_samples.py')
    print('     (The scraper will use the fallback profile with your real cookies)')


if __name__ == '__main__':
    main()
