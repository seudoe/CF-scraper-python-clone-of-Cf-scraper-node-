"""
pipeline/chrome-cookies-checker.py
===================================
Codeforces has heavy Cloudflare bot detection. Selenium alone gets walled.
This script:

  1. Copies the Cookies DB from your real Chrome profile into the
     scraper's dedicated profile (chrome-profile/Default), so Selenium
     inherits your real cf_clearance / Cloudflare trust.
  2. Launches the scraper's browser and does a LIVE fetch of a real
     problem page to confirm Cloudflare actually lets it through --
     not just that cookies were copied.

Run this before pipeline.py, and any time scraping starts failing with
Cloudflare challenges (cookies expire).

IMPORTANT: Close Chrome completely before running the copy step --
its Cookies file is locked while Chrome is open.

Usage:
    python pipeline/chrome-cookies-checker.py                  # copy + verify
    python pipeline/chrome-cookies-checker.py --verify-only    # skip copy, just test current profile
    python pipeline/chrome-cookies-checker.py --copy-only      # skip the live verification fetch
"""

import sys
import shutil
import sqlite3
import argparse
import subprocess
from pathlib import Path

_PIPELINE_DIR = Path(__file__).parent.absolute()
_ROOT_DIR = _PIPELINE_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))

from lib.browser_config import PROFILE_DIR  # noqa: E402
from lib.colors import cyan, yellow, green, red, success, info, warning, error  # noqa: E402

REAL_PROFILE    = Path(r'C:\Users\4dmin\AppData\Local\Google\Chrome\User Data\Default')
SCRAPER_PROFILE = PROFILE_DIR / 'Default'
VERIFY_URL      = 'https://codeforces.com/problemset/problem/1/A'


def check_chrome_running() -> bool:
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
        capture_output=True, text=True
    )
    return 'chrome.exe' in result.stdout.lower()


def copy_cookies() -> bool:
    src = REAL_PROFILE / 'Network' / 'Cookies'
    if not src.exists():
        src = REAL_PROFILE / 'Cookies'  # older Chrome versions

    if not src.exists():
        print(error(f'[cookies] Could not find Cookies file at: {src}'))
        return False

    dst_dir = SCRAPER_PROFILE / 'Network'
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / 'Cookies'

    try:
        shutil.copy2(src, dst)
        print(success(f'[cookies] Copied: {src} -> {dst}'))
        return True
    except PermissionError:
        print(error('[cookies] Permission denied - Chrome is still holding the file. Close it fully and retry.'))
        return False
    except Exception as e:
        print(error(f'[cookies] Copy failed: {e}'))
        return False


def count_cf_cookies(cookie_db: Path) -> list[tuple[str, str]]:
    try:
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
        print(warning(f'[cookies] Could not inspect cookies: {e}'))
        return []


def verify_live() -> bool:
    """Launch the scraper's browser and fetch a real problem page."""
    from lib.fetch import fetch_html, close_driver
    from lib.parse import PdfProblemError

    print(cyan(f'\n[verify] Fetching {VERIFY_URL} through the scraper browser...'))
    try:
        html = fetch_html(VERIFY_URL)
    except PdfProblemError:
        # Extremely unlikely for problem 1-A, but not a Cloudflare failure either way
        print(warning('[verify] Got a PDF response - inconclusive, but Cloudflare did not block us.'))
        close_driver()
        return True
    except Exception as e:
        print(error(f'[verify] Live fetch failed: {e}'))
        close_driver()
        return False

    close_driver()

    if 'problem-statement' in html:
        print(success('[verify] Cloudflare accepted the session - problem-statement loaded cleanly.'))
        return True

    print(error('[verify] Page loaded but no problem-statement found - Cloudflare is likely still blocking.'))
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-only', action='store_true', help='Skip copying cookies, just run the live check')
    ap.add_argument('--copy-only',   action='store_true', help='Skip the live verification fetch')
    args = ap.parse_args()

    print(cyan('=' * 55))
    print(cyan('  Chrome Cookie Checker for CF Scraper Pipeline'))
    print(cyan('=' * 55))

    if not args.verify_only:
        if check_chrome_running():
            print(warning('\n[!] Chrome is still running - its Cookies file will be locked.'))
            answer = input('    Continue anyway? (y/N): ').strip().lower()
            if answer != 'y':
                sys.exit(1)

        print(info('\n[1] Copying Cookies file...'))
        if not copy_cookies():
            sys.exit(1)

        print(info('\n[2] Checking Codeforces cookies in copied file...'))
        dst = SCRAPER_PROFILE / 'Network' / 'Cookies'
        cf_cookies = count_cf_cookies(dst)
        if cf_cookies:
            print(success(f'[cookies] Found {len(cf_cookies)} Codeforces/Cloudflare cookie(s):'))
            for name, host in cf_cookies:
                print(info(f'    {name:30s}  {host}'))
        else:
            print(warning('[cookies] No Codeforces cookies found in your real profile.'))
            print(warning('          Visit https://codeforces.com in Chrome first, then re-run this.'))

    if args.copy_only:
        print(success('\n[OK] Cookies copied. Skipped live verification (--copy-only).'))
        return

    ok = verify_live()

    print(cyan('\n' + '=' * 55))
    if ok:
        print(success('  READY - pipeline.py should be able to scrape.'))
    else:
        print(error('  NOT READY - Cloudflare is blocking this browser session.'))
        print(yellow('  Try: visit codeforces.com manually in Chrome (solve any challenge),'))
        print(yellow('        then re-run this script.'))
    print(cyan('=' * 55))

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
