"""
Browser configuration using the real Chrome user profile.
This gives Cloudflare the highest possible trust — real browsing history,
real cookies, real cf_clearance, real TLS fingerprint.
"""

import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from .colors import yellow, success, info, warning

# Real Chrome profile — has existing Cloudflare trust, cookies, history
REAL_CHROME_PROFILE = r'C:\Users\4dmin\AppData\Local\Google\Chrome\User Data'

# Fallback profile (used if real profile is locked by a running Chrome)
PROFILE_DIR = Path(__file__).parent.parent / 'chrome-profile'


def create_persistent_browser_options(use_real_profile: bool = True) -> Options:
    chrome_options = Options()

    if use_real_profile:
        chrome_options.add_argument(f'--user-data-dir={REAL_CHROME_PROFILE}')
        chrome_options.add_argument('--profile-directory=Default')
        print(info('[browser] Using REAL Chrome profile (max Cloudflare trust)'))
    else:
        profile_path = str(PROFILE_DIR.absolute())
        PROFILE_DIR.mkdir(exist_ok=True)
        chrome_options.add_argument(f'--user-data-dir={profile_path}')
        print(info(f'[browser] Using fallback profile: {profile_path}'))

    # --- Anti-detection (applied before driver launch) ---
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # --- Stability ---
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    # --- Suppress log spam ---
    chrome_options.add_argument('--disable-webrtc')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')

    # --- Realistic viewport (Turnstile checks this) ---
    chrome_options.add_argument('--window-size=1280,800')
    chrome_options.add_argument('--start-maximized')

    # --- Language / locale ---
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_experimental_option('prefs', {
        'intl.accept_languages': 'en-US,en',
        'profile.default_content_setting_values.notifications': 2,
    })

    return chrome_options


def _apply_stealth_script(driver):
    """
    Inject stealth patches into EVERY frame including Turnstile's sandbox iframe.
    Page.addScriptToEvaluateOnNewDocument applies before any frame JS runs.
    """
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': """
            // 1. Remove webdriver — Turnstile checks this inside its iframe
            try {
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            } catch(e) {}

            // 2. Full chrome runtime — missing runtime = instant bot flag
            if (!window.chrome) {
                window.chrome = {
                    app: { isInstalled: false },
                    runtime: {
                        connect: function(){},
                        sendMessage: function(){},
                        onMessage: { addListener: function(){} }
                    },
                    loadTimes: function() {},
                    csi: function() {},
                    webstore: {}
                };
            }

            // 3. Realistic plugin list — empty = headless signal
            try {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const arr = [
                            { name: 'Chrome PDF Plugin',  filename: 'internal-pdf-viewer' },
                            { name: 'Chrome PDF Viewer',  filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                            { name: 'Native Client',      filename: 'internal-nacl-plugin' }
                        ];
                        arr.item = i => arr[i];
                        arr.namedItem = n => arr.find(p => p.name === n) || null;
                        arr.refresh = () => {};
                        Object.setPrototypeOf(arr, PluginArray.prototype);
                        return arr;
                    }
                });
            } catch(e) {}

            // 4. Languages
            try {
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            } catch(e) {}

            // 5. Realistic hardware
            try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(e) {}
            try { Object.defineProperty(navigator, 'deviceMemory',         { get: () => 8 }); } catch(e) {}

            // 6. Permissions API — headless returns denied for notifications by default
            try {
                const origQuery = window.navigator.permissions.query.bind(navigator.permissions);
                window.navigator.permissions.query = (p) =>
                    p.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : origQuery(p);
            } catch(e) {}

            // 7. Remove chromedriver artifact
            try { delete window.$cdc_asdjflasutopfhvcZLmcfl_;  } catch(e) {}
            try { delete document.$cdc_asdjflasutopfhvcZLmcfl_; } catch(e) {}
        """
    })


def create_persistent_driver():
    """
    Creates a Chrome driver using the scraper profile.
    The scraper profile should have real cookies copied into it via copy_cookies.py.
    Does NOT use the real Chrome profile directly (avoids the "wrong window" conflict).
    """
    print(yellow('[browser] Launching Chrome with scraper profile...'))
    options = create_persistent_browser_options(use_real_profile=False)
    driver = webdriver.Chrome(options=options)
    _apply_stealth_script(driver)
    print(success('[browser] Chrome launched'))
    return driver


def warm_up_browser(driver):
    """Visit homepage to refresh CF cookies before scraping."""
    try:
        print(yellow('[browser] Warming up on Codeforces homepage...'))
        driver.get('https://codeforces.com')
        time.sleep(3)
        print(success('[browser] Warm-up done — cookies refreshed'))
    except Exception as e:
        print(f'[browser] Warm-up failed (non-critical): {e}')


def get_profile_info():
    return {
        'real_profile': REAL_CHROME_PROFILE,
        'fallback_profile': str(PROFILE_DIR),
    }


def clear_profile():
    """Clears only the fallback profile. Never touches your real Chrome."""
    import shutil
    if PROFILE_DIR.exists():
        print(yellow(f'[browser] Clearing fallback profile: {PROFILE_DIR}'))
        shutil.rmtree(PROFILE_DIR)
        print(success('[browser] Fallback profile cleared'))
    else:
        print(info('[browser] No fallback profile to clear'))
