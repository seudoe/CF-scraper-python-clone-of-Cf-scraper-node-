"""
HTML and image fetching using Selenium (bypasses Cloudflare bot detection)
"""

import time
from typing import Dict, Tuple
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from .colors import yellow, green, cyan, warning, success, info


_driver = None


def get_driver():
    """Gets or creates a Selenium WebDriver instance"""
    global _driver
    
    if _driver is not None:
        return _driver
    
    print(yellow('[fetch] Launching headless Chrome...'))
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Suppress WebRTC/STUN errors
    chrome_options.add_argument('--disable-webrtc')
    chrome_options.add_argument('--log-level=3')
    
    # User agent to avoid bot detection
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
    
    _driver = webdriver.Chrome(options=chrome_options)
    
    # Override navigator.webdriver flag
    _driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    
    print(success('[fetch] Browser launched'))
    return _driver


def fetch_html(url: str) -> str:
    """Fetches HTML from a URL using Selenium WebDriver"""
    print(yellow(f'[fetch] Fetching HTML: {url}'))
    
    driver = get_driver()
    driver.get(url)
    
    # Wait longer for page to load - give JS time to execute
    # Some CF pages load content dynamically
    print(info('[fetch] Waiting for page to fully load...'))
    time.sleep(4)
    
    html = driver.page_source
    size_kb = len(html) / 1024
    print(green(f'[fetch] ✓ Got HTML for {url} ({size_kb:.1f} KB)'))
    
    # Quick check if we got actual content
    if '.problem-statement' not in html and 'problem-statement' not in html:
        print(warning(f'[fetch] ⚠ Warning: HTML may not contain problem statement'))
    
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
    print(green(f'[fetch] ✓ Got image ({content_type}, {size_kb:.1f} KB)'))
    
    return {'buffer': buffer, 'contentType': content_type}


def close_driver():
    """Closes the Selenium WebDriver"""
    global _driver
    if _driver:
        _driver.quit()
        _driver = None
        print('[fetch] Browser closed')
