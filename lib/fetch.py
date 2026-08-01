"""
HTML and image fetching using Selenium with persistent profile (bypasses Cloudflare bot detection)
"""

import time
import random
from typing import Dict, Tuple
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .browser_config import create_persistent_driver, warm_up_browser
from .colors import yellow, green, cyan, warning, success, info, red, error


_driver = None
_warmed_up = False


def get_driver():
    """Gets or creates a Selenium WebDriver instance with persistent profile"""
    global _driver, _warmed_up
    
    if _driver is not None:
        return _driver
    
    # Create driver with persistent profile (maintains cookies, cache, etc.)
    _driver = create_persistent_driver()
    
    # Optional: Warm up browser by visiting homepage
    # This establishes initial cookies and makes subsequent visits look more natural
    if not _warmed_up:
        warm_up_browser(_driver)
        _warmed_up = True
    
    return _driver


def fetch_html(url: str) -> str:
    """
    Fetches HTML from a URL using Selenium WebDriver with persistent profile.
    Properly waits for Cloudflare challenges to complete.
    """
    print(yellow(f'[fetch] Fetching HTML: {url}'))
    
    try:
        driver = get_driver()
    except Exception as e:
        print(error(f'[fetch] Failed to get driver: {e}'))
        # Reset driver and try one more time
        reset_driver()
        driver = get_driver()
    
    try:
        driver.get(url)
        
        # Wait for either problem-statement to appear OR Cloudflare challenge
        print(info('[fetch] Waiting for page to load...'))
        
        try:
            # Wait up to 30 seconds for either:
            # 1. The problem-statement to appear (success)
            # 2. Cloudflare challenge page (need to wait longer)
            WebDriverWait(driver, 30).until(
                lambda d: (
                    d.find_elements(By.CLASS_NAME, 'problem-statement') or
                    'Just a moment' in d.title or
                    'Performing security verification' in d.page_source or
                    'Cloudflare' in d.page_source
                )
            )
            
            # Check if we got Cloudflare challenge
            if 'Just a moment' in driver.title or 'Performing security verification' in driver.page_source:
                print(warning('[fetch] Cloudflare challenge detected, waiting for resolution...'))
                
                # Wait for Cloudflare to resolve (up to 30 more seconds)
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'problem-statement'))
                    )
                    print(success('[fetch] Cloudflare challenge resolved'))
                except:
                    # Cloudflare didn't resolve - return the HTML anyway so we can detect it
                    print(error('[fetch] Cloudflare challenge did not resolve in time'))
            
        except Exception as e:
            print(warning(f'[fetch] Wait timeout: {e}'))
        
        html = driver.page_source
        size_kb = len(html) / 1024
        
        # Detailed checks for what we got
        if '.problem-statement' in html or 'problem-statement' in html:
            print(green(f'[fetch] [OK] Got HTML for {url} ({size_kb:.1f} KB) - problem-statement found'))
        elif 'Just a moment' in html or 'Performing security verification' in html:
            print(red(f'[fetch] [X] Got Cloudflare challenge page ({size_kb:.1f} KB)'))
            raise Exception('Cloudflare challenge not resolved - got verification page instead of problem')
        elif 'Cloudflare' in html:
            print(red(f'[fetch] [X] Got Cloudflare-related page ({size_kb:.1f} KB)'))
            raise Exception('Cloudflare protection triggered')
        else:
            print(warning(f'[fetch] Got HTML ({size_kb:.1f} KB) but no problem-statement detected'))
        
        return html
        
    except Exception as e:
        # If we get an invalid session error, reset the driver
        if 'invalid session' in str(e).lower():
            print(error('[fetch] Browser session invalid, resetting...'))
            reset_driver()
        raise


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
    """Closes the Selenium WebDriver"""
    global _driver, _warmed_up
    if _driver:
        try:
            _driver.quit()
        except:
            pass  # Ignore errors during cleanup
        _driver = None
        _warmed_up = False
        print('[fetch] Browser closed')


def reset_driver():
    """Resets the driver (close and recreate on next use)"""
    global _driver, _warmed_up
    close_driver()
    print(yellow('[fetch] Driver reset, will recreate on next request'))
