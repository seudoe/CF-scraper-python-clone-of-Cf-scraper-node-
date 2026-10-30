"""
pipeline/chrome-cookies-checker.py
===================================
Codeforces has heavy Cloudflare bot detection. Selenium alone gets walled.
This script:

  1. Copies the Cookies DB from your real Brave / Chrome profile into the
     scraper's dedicated profile (chrome-profile/Default), so Selenium
     inherits your real cf_clearance / Cloudflare trust.
  2. Launches the scraper's browser (Brave or Chrome) and does a LIVE fetch
     of a real problem page to confirm Cloudflare lets it through.

Run this before pipeline.py, and any time scraping starts failing with
Cloudflare challenges (cookies expire).

IMPORTANT: Close Brave / Chrome completely before running the copy step --
Chromium locks its Cookies file while the browser is open.

Usage:
    uv run python pipeline/chrome-cookies-checker.py                    # auto-detect (Brave/Chrome) + copy + verify
    uv run python pipeline/chrome-cookies-checker.py --path "C:\path"   # custom profile or Cookies file path
    uv run python pipeline/chrome-cookies-checker.py --verify-only      # test current scraper profile without copying
    uv run python pipeline/chrome-cookies-checker.py --copy-only        # copy cookies without running live verification
"""

import sys
import os
import shutil
import sqlite3
import argparse
import subprocess
from pathlib import Path

_PIPELINE_DIR = Path(__file__).parent.absolute()
_ROOT_DIR = _PIPELINE_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))

from lib.browser_config import PROFILE_DIR, find_browser_binary  # noqa: E402
from lib.colors import cyan, yellow, green, red, success, info, warning, error  # noqa: E402

SCRAPER_PROFILE = PROFILE_DIR / 'Default'
VERIFY_URL      = 'https://codeforces.com/problemset/problem/1/A'

STANDARD_PROFILES = [
    ("Brave",  Path(os.path.expandvars(r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default'))),
    ("Chrome", Path(os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default'))),
    ("Edge",   Path(os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\User Data\Default'))),
]


def resolve_cookies_path(custom_path: str | None) -> tuple[str, Path | None]:
    """
    Finds the Cookies file from a custom path or by auto-detecting standard browsers.
    Returns (browser_name, cookies_file_path).
    """
    if custom_path:
        p = Path(custom_path.strip().strip('"').strip("'"))
        if p.is_file():
            return ("Custom", p)
        # Check standard subpaths if a directory was given
        candidates = [
            p / 'Network' / 'Cookies',
            p / 'Cookies',
            p / 'Default' / 'Network' / 'Cookies',
            p / 'Default' / 'Cookies',
        ]
        for c in candidates:
            if c.is_file():
                return ("Custom", c)
        return ("Custom", None)

    for name, prof_dir in STANDARD_PROFILES:
        candidates = [
            prof_dir / 'Network' / 'Cookies',
            prof_dir / 'Cookies',
        ]
        for c in candidates:
            if c.is_file():
                return (name, c)

    return ("None", None)


def check_browser_running(browser_name: str) -> str | None:
    """Checks if the relevant browser process is running."""
    proc_map = {
        "brave": "brave.exe",
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
    }
    targets = [proc_map[browser_name.lower()]] if browser_name.lower() in proc_map else ["brave.exe", "chrome.exe", "msedge.exe"]
    
    for proc in targets:
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {proc}'],
            capture_output=True, text=True
        )
        if proc in result.stdout.lower():
            return proc
    return None


def copy_cookies(src: Path) -> bool:
    """
    Safely copies Cookies from src to scraper profile without deleting existing data.
    Preserves a backup of existing scraper cookies as Cookies.bak.
    """
    dst_dir = SCRAPER_PROFILE / 'Network'
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / 'Cookies'
    backup = dst_dir / 'Cookies.bak'

    if dst.exists():
        try:
            shutil.copy2(dst, backup)
            print(info(f'[cookies] Existing scraper cookies backed up to: {backup.name}'))
        except Exception as e:
            print(warning(f'[cookies] Could not create backup of existing cookies: {e}'))

    try:
        shutil.copy2(src, dst)
        print(success(f'[cookies] Successfully copied:\n  From: {src}\n  To:   {dst}'))
        return True
    except PermissionError:
        print(error(f'[cookies] Permission denied - browser is still holding {src}. Close it fully and retry.'))
        return False
    except Exception as e:
        print(error(f'[cookies] Copy failed: {e}'))
        return False


def count_cf_cookies(cookie_db: Path) -> list[tuple[str, str]]:
    if not cookie_db.exists():
        return []
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
    ap = argparse.ArgumentParser(description="Copy Brave/Chrome cookies to scraper profile and verify Cloudflare access.")
    ap.add_argument('--path', '--profile-path', dest='custom_path', type=str, default=None,
                    help='Custom path to browser profile directory or direct Cookies SQLite file')
    ap.add_argument('--verify-only', action='store_true', help='Skip copying cookies, just run the live check')
    ap.add_argument('--copy-only',   action='store_true', help='Skip the live verification fetch')
    args = ap.parse_args()

    print(cyan('=' * 58))
    print(cyan('  Brave / Chrome Cookie Copier & Cloudflare Checker'))
    print(cyan('=' * 58))

    browser_bin = find_browser_binary()
    if browser_bin:
        print(info(f'[browser] Scraper executable: {browser_bin}'))

    if not args.verify_only:
        browser_name, src_cookies = resolve_cookies_path(args.custom_path)

        if not src_cookies or not src_cookies.exists():
            print(error('\n[cookies] Could not locate Cookies file!'))
            if args.custom_path:
                print(error(f'  Specified path not found: {args.custom_path}'))
            else:
                print(warning('  Checked standard Brave, Chrome, and Edge locations.'))
                print(warning('  Use --path <profile_or_cookies_path> to specify manually.'))
            sys.exit(1)

        print(info(f'\n[1] Source: {browser_name} ({src_cookies})'))

        running_proc = check_browser_running(browser_name)
        if running_proc:
            print(warning(f'\n[!] {running_proc} is currently running.'))
            print(warning('    Chromium exclusively locks its Cookies database while open.'))
            answer = input('    Have you closed it, or continue anyway? (y/N): ').strip().lower()
            if answer != 'y':
                print(yellow('[cookies] Cancelled. Existing scraper cookies remain untouched.'))
                sys.exit(1)

        print(info('\n[2] Copying Cookies file (preserving existing cookies)...'))
        if not copy_cookies(src_cookies):
            print(warning('[cookies] Copy failed. Existing scraper cookies remain untouched.'))
            sys.exit(1)

        print(info('\n[3] Checking Codeforces cookies in scraper profile...'))
        dst = SCRAPER_PROFILE / 'Network' / 'Cookies'
        cf_cookies = count_cf_cookies(dst)
        if cf_cookies:
            print(success(f'[cookies] Found {len(cf_cookies)} Codeforces/Cloudflare cookie(s):'))
            for name, host in cf_cookies:
                print(info(f'    {name:30s}  {host}'))
        else:
            print(warning(f'[cookies] No Codeforces cookies found in your {browser_name} profile.'))
            print(warning('          Visit https://codeforces.com in your browser first to get cookies.'))

    if args.copy_only:
        print(success('\n[OK] Cookies copied safely. Skipped live verification (--copy-only).'))
        return

    ok = verify_live()

    print(cyan('\n' + '=' * 58))
    if ok:
        print(success('  READY - pipeline.py can scrape with this session.'))
    else:
        print(error('  NOT READY - Cloudflare is blocking this browser session.'))
        print(yellow('  Try: visit codeforces.com manually in Brave (solve any challenge),'))
        print(yellow('        close Brave, then re-run this script.'))
    print(cyan('=' * 58))

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
