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
        print(info('[fetch] Waiting for page to load...'))

        # PDF detection — Chrome's built-in PDF viewer produces a tiny page (~159 bytes)
        # with a chrome-extension://...pdf_embedder.css link and empty title.
        # Check within 3s (it loads almost instantly).
        try:
            WebDriverWait(driver, 3).until(lambda d: d.title != '' or len(d.page_source) > 300)
        except Exception:
            pass

        _src_peek = driver.page_source
        _is_pdf = (
            'pdf_embedder' in _src_peek or
            driver.title.lower().endswith('.pdf') or
            (len(_src_peek) < 500 and 'chrome-extension://' in _src_peek)
        )
        if _is_pdf:
            print(yellow(f'[fetch] [PDF] Chrome PDF viewer detected for {url} — skipping'))
            try:
                driver.get('about:blank')
            except Exception:
                pass
            from .parse import PdfProblemError
            raise PdfProblemError(f'Problem has PDF statement')

        # Phase 1: wait for problem-statement OR Cloudflare page (max 30s)
        try:
            WebDriverWait(driver, 30).until(
                lambda d: (
                    d.find_elements(By.CLASS_NAME, 'problem-statement') or
                    'Just a moment' in d.title or
                    'Performing security verification' in d.page_source
                )
            )
        except Exception:
            pass  # timed out — fall through and check what we got

        # Phase 2: if CF challenge appeared, give Turnstile up to 60s to auto-resolve
        if 'Just a moment' in driver.title or 'Performing security verification' in driver.page_source:
            print(warning('[fetch] Cloudflare challenge detected, waiting up to 60s...'))
            try:
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'problem-statement'))
                )
                print(success('[fetch] Cloudflare challenge resolved'))
            except Exception:
                # Don't sit here stuck — navigate away cleanly to keep session alive
                print(error('[fetch] Cloudflare did not resolve, moving on...'))
                try:
                    driver.get('about:blank')  # navigate away to release any held resources
                except Exception:
                    pass
                raise Exception('Cloudflare challenge not resolved')

        # Read final page
        try:
            html = driver.page_source
        except Exception as e:
            print(error(f'[fetch] Could not read page source: {e}'))
            # Don't reset — CF may have just temporarily blocked us
            # The browser is still alive for the next request
            raise Exception(f'Could not read page after navigating to {url}')

        size_kb = len(html) / 1024

        if 'problem-statement' in html:
            print(green(f'[fetch] [OK] Got HTML ({size_kb:.1f} KB) - problem-statement found'))
            return html
        elif 'Just a moment' in html or 'Performing security verification' in html:
            print(red(f'[fetch] [X] Still on Cloudflare page ({size_kb:.1f} KB)'))
            raise Exception('Cloudflare challenge not resolved')
        else:
            print(warning(f'[fetch] Got HTML ({size_kb:.1f} KB) but no problem-statement'))
            raise Exception('Problem statement not found in page')

    except Exception as e:
        err_str = str(e).lower()
        if 'invalid session' in err_str or 'session not created' in err_str:
            # Browser actually died — safe to reset
            print(error('[fetch] Session lost, resetting driver...'))
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
