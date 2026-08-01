"""
HTML and image fetching using undetected-chromedriver (better Cloudflare bypass)
This is an alternative to fetch.py with better Cloudflare handling
"""

import time
from typing import Dict
import requests
try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False
    print('[fetch] Warning: undetected-chromedriver not installed, falling back to regular selenium')

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .colors import yellow, green, cyan, warning, success, info, red, error

_driver = None
_request_count = 0

def get_driver():
    """Gets or creates an undetected Chrome driver"""
    global _driver, _request_count
    
    if _driver is not None:
        return _driver
    
    print(yellow('[fetch] Launching undetected Chrome (better Cloudflare bypass)...'))
    
    if not UNDETECTED_AVAILABLE:
        raise Exception('undetected-chromedriver not installed. Run: pip install undetected-chromedriver')
    
    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    
    # For production, add headless mode (less reliable but necessary)
    # options.add_argument('--headless=new')
    
    try:
        # Let undetected_chromedriver auto-download the matching version
        _driver = uc.Chrome(options=options, driver_executable_path=None, use_subprocess=True)
        _request_count = 0
        print(success('[fetch] Undetected Chrome launched'))
        return _driver
    except Exception as e:
        print(error(f'[fetch] Failed to create undetected Chrome: {e}'))
        raise

def fetch_html(url: str, retry_on_cloudflare: bool = True) -> str:
    """
    Fetches HTML from a URL using undetected-chromedriver.
    Much better at bypassing Cloudflare than regular Selenium.
    """
    global _request_count
    _request_count += 1
    
    print(yellow(f'[fetch] Fetching HTML: {url}'))
    print(info(f'[fetch] Request #{_request_count} in this session'))
    
    driver = get_driver()
    
    # Occasionally visit homepage to look more human
    if _request_count % 50 == 1 and _request_count > 1:
        print(info('[fetch] Visiting Codeforces homepage to maintain session...'))
        driver.get('https://codeforces.com')
        time.sleep(2)
    
    driver.get(url)
    
    # Wait for either problem-statement to appear OR Cloudflare challenge
    print(info('[fetch] Waiting for page to load...'))
    
    max_wait = 45  # Increased timeout for Cloudflare
    start_time = time.time()
    
    try:
        # Wait for either:
        # 1. The problem-statement to appear (success)
        # 2. Cloudflare challenge indicators
        WebDriverWait(driver, max_wait).until(
            lambda d: (
                d.find_elements(By.CLASS_NAME, 'problem-statement') or
                'Just a moment' in d.title or
                'Performing security verification' in d.page_source or
                'challenge-platform' in d.page_source
            )
        )
        
        elapsed = time.time() - start_time
        
        # Check if we got Cloudflare challenge
        page_source = driver.page_source
        
        if ('Just a moment' in driver.title or 
            'Performing security verification' in page_source or
            'challenge-platform' in page_source):
            
            print(warning(f'[fetch] Cloudflare challenge detected after {elapsed:.1f}s'))
            print(info('[fetch] Waiting for Turnstile/challenge to resolve...'))
            
            # Wait for Cloudflare to resolve (up to 45 more seconds)
            challenge_start = time.time()
            try:
                WebDriverWait(driver, 45).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'problem-statement'))
                )
                challenge_time = time.time() - challenge_start
                print(success(f'[fetch] Cloudflare challenge resolved in {challenge_time:.1f}s'))
            except Exception as e:
                challenge_time = time.time() - challenge_start
                print(error(f'[fetch] Cloudflare challenge did not resolve after {challenge_time:.1f}s'))
                
                if retry_on_cloudflare:
                    print(warning('[fetch] Retrying with longer wait...'))
                    time.sleep(5)
                    return fetch_html(url, retry_on_cloudflare=False)  # Retry once
                else:
                    raise Exception('Cloudflare challenge not resolved after retry')
        else:
            print(success(f'[fetch] Page loaded in {elapsed:.1f}s'))
    
    except Exception as e:
        elapsed = time.time() - start_time
        print(warning(f'[fetch] Wait timeout after {elapsed:.1f}s: {e}'))
    
    # Get the final HTML
    html = driver.page_source
    size_kb = len(html) / 1024
    
    # Detailed checks for what we got
    if '.problem-statement' in html or 'problem-statement' in html:
        print(green(f'[fetch] [OK] Got problem HTML ({size_kb:.1f} KB) - problem-statement found'))
    elif 'Just a moment' in html:
        print(red(f'[fetch] [X] Still on Cloudflare "Just a moment" page ({size_kb:.1f} KB)'))
        raise Exception('Cloudflare challenge not resolved - got "Just a moment" page')
    elif 'Performing security verification' in html:
        print(red(f'[fetch] [X] Still on Cloudflare verification page ({size_kb:.1f} KB)'))
        raise Exception('Cloudflare challenge not resolved - got verification page')
    elif 'challenge-platform' in html or 'cf-chl' in html:
        print(red(f'[fetch] [X] Still on Cloudflare challenge page ({size_kb:.1f} KB)'))
        raise Exception('Cloudflare challenge not resolved - still showing challenge')
    else:
        print(warning(f'[fetch] Got HTML ({size_kb:.1f} KB) but no problem-statement detected'))
        # Don't raise - might be other issue
    
    return html

def fetch_image_as_buffer(url: str) -> Dict[str, any]:
    """
    Fetches an image and returns {'buffer': bytes, 'contentType': str}
    Uses requests (not Selenium) since images don't need JS execution
    """
    print(yellow(f'[fetch] Fetching image: {url}'))
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://codeforces.com/',
        'Accept': 'image/*,*/*;q=0.8'
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    
    content_type = response.headers.get('content-type', 'image/png')
    buffer = response.content
    
    size_kb = len(buffer) / 1024
    print(green(f'[fetch] [OK] Got image ({content_type}, {size_kb:.1f} KB)'))
    
    return {'buffer': buffer, 'contentType': content_type}

def close_driver():
    """Closes the undetected Chrome driver"""
    global _driver, _request_count
    if _driver:
        _driver.quit()
        _driver = None
        _request_count = 0
        print(info('[fetch] Browser closed'))
