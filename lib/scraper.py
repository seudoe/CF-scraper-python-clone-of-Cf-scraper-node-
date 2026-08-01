"""
Problem scraper - fetches, parses, and caches Codeforces problems
"""

import time
from urllib.parse import urljoin
from bson.binary import Binary
from lib.fetch import fetch_html, fetch_image_as_buffer
from lib.parse import parse_problem_page
from lib.db import get_images_collection
from lib.types import CachedProblem, ImageBlock


CF_BASE = 'https://codeforces.com'


def build_problem_url(contest_id: int, index: str) -> str:
    """Build URL for a problem page"""
    return f'{CF_BASE}/problemset/problem/{contest_id}/{index}'


def make_filename(src: str, problem_key: str) -> str:
    """Generate a unique filename for an image"""
    if src.startswith('http'):
        url = src
    else:
        url = urljoin(CF_BASE, src)
    
    # Extract extension and base name
    parts = url.split('/')
    last_part = parts[-1] if parts else 'img'
    
    # Clean filename
    clean_name = ''.join(c if c.isalnum() or c in '._-' else '_' for c in last_part)
    
    # Add extension if missing
    if '.' not in clean_name:
        clean_name += '.png'
    
    return f'{problem_key}_{clean_name}'


async def save_image(src: str, problem_key: str) -> str:
    """Download and save an image to MongoDB, returns cf-image:// URL"""
    abs_url = src if src.startswith('http') else urljoin(CF_BASE, src)
    filename = make_filename(src, problem_key)
    
    images_col = get_images_collection()
    
    # Check if already saved
    existing = images_col.find_one({'filename': filename})
    if existing:
        print(f'[scraper] Image already saved, skipping: {filename}')
        return filename
    
    print(f'[scraper] Saving image to DB: {filename}')
    
    buffer, content_type = fetch_image_as_buffer(abs_url)
    
    images_col.insert_one({
        'problemId': problem_key,
        'filename': filename,
        'contentType': content_type,
        'data': Binary(buffer),
        'cachedAt': int(time.time())
    })
    
    size_kb = len(buffer) / 1024
    print(f'[scraper] ✓ Image saved: {filename} ({content_type}, {size_kb:.1f} KB)')
    
    return filename


def rewrite_images(blocks, problem_key: str):
    """Rewrite image src URLs to cf-image:// format after downloading"""
    image_blocks = [b for b in blocks if isinstance(b, ImageBlock)]
    
    if image_blocks:
        print(f'[scraper] Processing {len(image_blocks)} image(s) for {problem_key}')
    
    for block in image_blocks:
        try:
            filename = save_image(block.src, problem_key)
            block.src = f'cf-image://{filename}'
        except Exception as e:
            print(f'[scraper] ✗ Failed to save image for {problem_key}: {e}')


def save_image(src: str, problem_key: str) -> str:
    """Download and save an image to MongoDB (synchronous version)"""
    abs_url = src if src.startswith('http') else urljoin(CF_BASE, src)
    filename = make_filename(src, problem_key)
    
    images_col = get_images_collection()
    
    # Check if already saved
    existing = images_col.find_one({'filename': filename})
    if existing:
        print(f'[scraper] Image already saved, skipping: {filename}')
        return filename
    
    print(f'[scraper] Saving image to DB: {filename}')
    
    buffer, content_type = fetch_image_as_buffer(abs_url)
    
    images_col.insert_one({
        'problemId': problem_key,
        'filename': filename,
        'contentType': content_type,
        'data': Binary(buffer),
        'cachedAt': int(time.time())
    })
    
    size_kb = len(buffer) / 1024
    print(f'[scraper] ✓ Image saved: {filename} ({content_type}, {size_kb:.1f} KB)')
    
    return filename


def scrape_problem(contest_id: int, index: str) -> CachedProblem:
    """
    Scrape a single problem from Codeforces
    Returns a CachedProblem object ready for MongoDB storage
    """
    problem_key = f'{contest_id}-{index}'
    url = build_problem_url(contest_id, index)
    
    print(f'[scraper] ── Scraping {problem_key} ──')
    print(f'[scraper] Fetching webpage: {url}')
    
    html = fetch_html(url)
    
    print(f'[scraper] Parsing {problem_key} ...')
    statement = parse_problem_page(html, problem_key)
    
    if not statement:
        raise Exception(f'Could not parse problem statement for {problem_key}')
    
    # Process images in all sections
    sections = [
        statement.description,
        statement.input,
        statement.output
    ]
    if statement.note:
        sections.append(statement.note)
    
    total_images = sum(
        1 for section in sections
        for b in section
        if isinstance(b, ImageBlock)
    )
    
    if total_images > 0:
        print(f'[scraper] Found {total_images} image(s) across all sections for {problem_key}')
    
    for section in sections:
        rewrite_images(section, problem_key)
    
    result = CachedProblem(
        contestId=contest_id,
        index=index,
        cachedAt=int(time.time()),
        version=1,
        statement=statement
    )
    
    print(f'[scraper] ✓ Scrape complete for {problem_key}: "{statement.title}"')
    
    return result
