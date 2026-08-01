"""
Browser configuration with persistent profile for better Cloudflare bypass.
Based on cloudflareDetection.md - maintains cookies, cache, and browser state across sessions.
"""

import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from .colors import yellow, success, info

# Profile directory - will persist cookies, cache, local storage, etc.
PROFILE_DIR = Path(__file__).parent.parent / 'chrome-profile'

def create_persistent_browser_options() -> Options:
    """
    Creates Chrome options with persistent profile and anti-detection settings.
    
    This maintains across sessions:
    - Cookies (cf_clearance, session cookies) ⭐⭐⭐⭐⭐
    - Cache (makes you look like returning visitor) ⭐⭐⭐
    - Local Storage ⭐⭐
    - IndexedDB ⭐⭐
    - Login sessions ⭐⭐⭐⭐
    - Browser preferences ⭐⭐
    """
    chrome_options = Options()
    
    # MOST IMPORTANT: Persistent profile directory
    # This stores cookies, cache, local storage, IndexedDB, etc.
    profile_path = str(PROFILE_DIR.absolute())
    chrome_options.add_argument(f'--user-data-dir={profile_path}')
    
    print(info(f'[browser] Using persistent profile: {profile_path}'))
    
    # Consistent browser fingerprint
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
    
    # Anti-detection settings
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Performance and stability
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    
    # Suppress WebRTC/STUN errors
    chrome_options.add_argument('--disable-webrtc')
    chrome_options.add_argument('--log-level=3')
    
    # For production deployment, enable headless mode
    # chrome_options.add_argument('--headless=new')
    # Note: Headless mode is more likely to be detected by Cloudflare
    # For local development, leave commented out to run with visible browser
    
    # Set language preferences (consistency matters)
    chrome_options.add_argument('--lang=en-US')
    chrome_options.add_experimental_option('prefs', {
        'intl.accept_languages': 'en-US,en',
        'profile.default_content_setting_values.notifications': 2,  # Disable notifications
    })
    
    return chrome_options


def create_persistent_driver():
    """
    Creates a Selenium WebDriver with persistent profile.
    
    Returns:
        webdriver.Chrome: Configured Chrome driver with persistent state
    """
    print(yellow('[browser] Initializing Chrome with persistent profile...'))
    
    # Ensure profile directory exists
    PROFILE_DIR.mkdir(exist_ok=True)
    
    options = create_persistent_browser_options()
    
    driver = webdriver.Chrome(options=options)
    
    # Execute CDP commands to further mask automation
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Make chrome object look more legitimate
            window.chrome = {
                runtime: {}
            };
            
            // Consistent navigator properties
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        '''
    })
    
    print(success('[browser] Chrome initialized with persistent profile'))
    print(info('[browser] Profile maintains: cookies, cache, local storage, sessions'))
    
    return driver


def warm_up_browser(driver):
    """
    Optional: Visit homepage to establish initial session and cookies.
    This makes subsequent problem visits look more natural.
    
    Args:
        driver: Selenium WebDriver instance
    """
    try:
        print(yellow('[browser] Warming up: visiting Codeforces homepage...'))
        driver.get('https://codeforces.com')
        
        # Wait a moment for page to fully load and cookies to be set
        import time
        time.sleep(3)
        
        print(success('[browser] Homepage visit complete, cookies established'))
    except Exception as e:
        print(f'[browser] Warning: Homepage warm-up failed: {e}')
        # Non-critical, continue anyway


def get_profile_info():
    """
    Get information about the persistent profile.
    
    Returns:
        dict: Profile statistics
    """
    if not PROFILE_DIR.exists():
        return {
            'exists': False,
            'path': str(PROFILE_DIR),
            'size_mb': 0
        }
    
    # Calculate profile size
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(PROFILE_DIR):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except:
                pass
    
    size_mb = total_size / (1024 * 1024)
    
    return {
        'exists': True,
        'path': str(PROFILE_DIR),
        'size_mb': round(size_mb, 2)
    }


def clear_profile():
    """
    Clears the persistent browser profile.
    Use this if you need to start fresh or if the profile becomes corrupted.
    """
    import shutil
    
    if PROFILE_DIR.exists():
        print(yellow(f'[browser] Clearing profile: {PROFILE_DIR}'))
        shutil.rmtree(PROFILE_DIR)
        print(success('[browser] Profile cleared'))
    else:
        print(info('[browser] No profile to clear'))
