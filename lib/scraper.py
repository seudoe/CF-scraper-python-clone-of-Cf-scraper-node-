"""Main scraper logic for Codeforces problems"""
import time
from typing import Dict, Any, List
from urllib.parse import urljoin, urlparse
from bson.binary import Binary
from .fetch import fetch_html, fetch_image_as_buffer
from .parse import parse_problem_page
from .db import get_images_collection
from .colors import green, yellow, magenta, cyan, success, error, warning, info

CF_BASE = 'https://codeforces.com'

def build_problem_url(contest_id: int, index: str) -> str:
    """Build URL for a problem"""
    return f'{CF_BASE}/problemset/problem/{contest_id}/{index}'

def make_filename(src: str, problem_key: str) -> str:
    """Generate a unique filename for an image"""
    # Make absolute URL
    if src.startswith('http'):
        url = src
    else:
        url = urljoin(CF_BASE, src)
    
    parsed = urlparse(url)
    path = parsed.path
    
    # Extract extension
    ext = '.png'
    if '.' in path:
        parts = path.rsplit('.', 1)
        if len(parts) == 2:
            ext = '.' + parts[1]
    
    # Extract base name
    base = path.split('/')[-1].replace('.', '_').replace('-', '_')
    if not base:
        base = 'img'
    
    # Remove extension from base if it's there
    if base.endswith(ext):
        base = base[:-len(ext)]
    
    return f'{problem_key}_{base}{ext}'

def save_image(src: str, problem_key: str) -> str:
    """Save an image to MongoDB (synchronous version)"""
    # Make absolute URL
    if src.startswith('http'):
        abs_url = src
    else:
        abs_url = urljoin(CF_BASE, src)
    
    filename = make_filename(src, problem_key)
    images_col = get_images_collection()
    
    # Check if already exists
    existing = images_col.find_one({'filename': filename})
    if existing:
        print(info(f'[scraper] Image already saved, skipping: {filename}'))
        return filename
    
    print(yellow(f'[scraper] Saving image to DB: {filename}'))
    result = fetch_image_as_buffer(abs_url)
    buffer = result['buffer']
    content_type = result['contentType']
    
    images_col.insert_one({
        'problemId': problem_key,
        'filename': filename,
        'contentType': content_type,
        'data': Binary(buffer),
        'cachedAt': int(time.time())
    })
    
    size_kb = len(buffer) / 1024
    print(success(f'[scraper] Image saved: {filename} ({content_type}, {size_kb:.1f} KB)'))
    return filename

def rewrite_images(blocks: List[Dict[str, Any]], problem_key: str):
    """Rewrite image URLs in blocks to use cf-image:// scheme"""
    image_blocks = [b for b in blocks if b.get('type') == 'image']
    
    if image_blocks:
        print(yellow(f'[scraper] Processing {len(image_blocks)} image(s) for {problem_key}'))
    
    for block in image_blocks:
        try:
            filename = save_image(block['src'], problem_key)
            block['src'] = f'cf-image://{filename}'
        except Exception as e:
            print(error(f'[scraper] Failed to save image for {problem_key}: {e}'))

def scrape_problem(contest_id: int, index: str) -> Dict[str, Any]:
    """Scrape a problem and return structured data"""
    problem_key = f'{contest_id}-{index}'
    url = build_problem_url(contest_id, index)
    
    print(cyan(f'[scraper] ── Scraping {problem_key} ──'))
    print(yellow(f'[scraper] Fetching webpage: {url}'))
    
    html = fetch_html(url)
    
    print(magenta(f'[scraper] Parsing {problem_key} ...'))
    statement = parse_problem_page(html, problem_key)
    
    if not statement:
        raise Exception(f'Could not parse problem statement for {problem_key}')
    
    # Process images in all sections
    sections = [
        statement['description'],
        statement['input'],
        statement['output']
    ]
    if 'note' in statement:
        sections.append(statement['note'])
    
    total_images = sum(1 for section in sections for b in section if b.get('type') == 'image')
    if total_images > 0:
        print(yellow(f'[scraper] Found {total_images} image(s) across all sections for {problem_key}'))
    
    for section in sections:
        rewrite_images(section, problem_key)
    
    result = {
        'contestId': contest_id,
        'index': index,
        'cachedAt': int(time.time()),
        'version': 1,
        'statement': statement
    }
    
    print(success(f'[scraper] Scrape complete for {problem_key}: "{statement["title"]}"'))
    return result
