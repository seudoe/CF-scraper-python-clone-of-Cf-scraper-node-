"""Fetch random problem HTMLs for testing the parser"""
import sys
import random
from pathlib import Path

script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

from lib.cf_api import fetch_all_problems
from lib.fetch import fetch_html, get_driver, close_driver
from lib.colors import green, yellow, cyan, success, info

# Configuration
OUTPUT_DIR = script_dir / 'example-htmls'
NUM_SAMPLES = 15

def main():
    print(cyan('[fetch-samples] ═══════════════════════════════'))
    print(cyan(f'[fetch-samples] Fetching {NUM_SAMPLES} random problem HTMLs'))
    print(cyan('[fetch-samples] ═══════════════════════════════\n'))
    
    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Get all problems from CF API
    print(info('[fetch-samples] Fetching problem list from Codeforces API...'))
    all_problems = fetch_all_problems()
    
    # Select random problems
    selected = random.sample(all_problems, min(NUM_SAMPLES, len(all_problems)))
    
    print(yellow(f'\n[fetch-samples] Selected {len(selected)} random problems:'))
    for p in selected:
        print(info(f'  - {p["contestId"]}-{p["index"]}: {p["name"]}'))
    
    print()
    
    # Fetch each problem
    success_count = 0
    fail_count = 0
    
    for i, problem in enumerate(selected, 1):
        contest_id = problem['contestId']
        index = problem['index']
        problem_id = f'{contest_id}-{index}'
        filename = OUTPUT_DIR / f'{problem_id}.html'
        
        print(yellow(f'[fetch-samples] ({i}/{len(selected)}) Fetching {problem_id}...'))
        
        try:
            # Build URL
            url = f'https://codeforces.com/problemset/problem/{contest_id}/{index}'
            
            # Fetch HTML
            html = fetch_html(url)
            
            # Save to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html)
            
            print(success(f'[fetch-samples] ✓ Saved to {filename.name}'))
            success_count += 1
            
        except Exception as e:
            print(f'[fetch-samples] ✗ Failed to fetch {problem_id}: {e}')
            fail_count += 1
    
    # Close browser
    close_driver()
    
    # Summary
    print(cyan('\n[fetch-samples] ═══════════════════════════════'))
    print(green(f'[fetch-samples] ✓ Successfully fetched: {success_count}/{NUM_SAMPLES}'))
    if fail_count > 0:
        print(f'[fetch-samples] ✗ Failed: {fail_count}/{NUM_SAMPLES}')
    print(cyan('[fetch-samples] ═══════════════════════════════'))

if __name__ == '__main__':
    main()
