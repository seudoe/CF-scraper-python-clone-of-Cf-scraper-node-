"""
HTML and image fetching using Selenium (bypasses Cloudflare bot detection)
"""

import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


_driver = None


def get_driver():
    """Gets or creates a Selenium WebDriver instance"""
    global _driver
    
    if _driver is not None:
        return _driver
    
    print('[fetch] Launching headless Chrome...')
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
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
    
    print('[fetch] ✓ Browser launched')
    return _driver


def fetch_html(url: str) -> str:
    """Fetches HTML from a URL using Selenium WebDriver"""
    print(f'[fetch] Fetching HTML: {url}')
    
    driver = get_driver()
    driver.get(url)
    
    # Wait for page to load (wait for .problem-statement to appear)
    time.sleep(2)
    
    html = driver.page_source
    size_kb = len(html) / 1024
    print(f'[fetch] ✓ Got HTML for {url} ({size_kb:.1f} KB)')
    
    return html


def fetch_image_as_buffer(url: str) -> tuple:
    """
    Fetches an image and returns (buffer, content_type)
    Uses requests (not Selenium) since images don't need JS execution
    """
    print(f'[fetch] Fetching image: {url}')
    
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
    print(f'[fetch] ✓ Got image ({content_type}, {size_kb:.1f} KB)')
    
    return buffer, content_type


def close_driver():
    """Closes the Selenium WebDriver"""
    global _driver
    if _driver:
        _driver.quit()
        _driver = None
        print('[fetch] Browser closed')
