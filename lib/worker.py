"""
Background worker for syncing all problems from Codeforces
"""

import time
from typing import Dict
from lib.cf_api import fetch_all_problems
from lib.scraper import scrape_problem
from lib.db import get_problems_collection, get_index_collection
from lib.timing import random_wait
from lib.colors import green, red, yellow, cyan, bold, success, error, warning, info


def sync_problems() -> Dict:
    """
    Main sync function - fetches problem list and scrapes new problems
    Returns dict with scraped/failed/total counts
    """
    print(cyan('[worker] ================================'))
    print(cyan('[worker] Starting problem sync'))
    print(cyan('[worker] ================================'))
    
    try:
        # 1. Fetch all problems from CF API
        all_problems = fetch_all_problems()
        
        # 2. Load already-scraped IDs from MongoDB
        print(info('[worker] Checking MongoDB for already-scraped problems ...'))
        index_col = get_index_collection()
        index_doc = index_col.find_one({})
        scraped_ids = set(index_doc.get('ids', []) if index_doc else [])
        
        print(info(f'[worker] Already scraped: {len(scraped_ids)} / {len(all_problems)} problems'))
        
        # 3. Diff - only new problems
        new_problems = [
            p for p in all_problems
            if f"{p['contestId']}-{p['index']}" not in scraped_ids
        ]
        
        print(yellow(f'[worker] New problems to scrape: {len(new_problems)}'))
        
        if len(new_problems) == 0:
            print(success('[worker] All problems are up to date — nothing to do'))
            return {'scraped': 0, 'failed': 0, 'total': len(all_problems)}
        
        problems_col = get_problems_collection()
        scraped = 0
        failed = 0
        
        for i, p in enumerate(new_problems, 1):
            problem_id = f"{p['contestId']}-{p['index']}"
            progress = f'({i}/{len(new_problems)})'
            
            try:
                print(cyan(f'[worker] {progress} Starting: {problem_id} — "{p["name"]}"'))
                
                doc = scrape_problem(p['contestId'], p['index'])
                
                # Save problem JSON to problems collection
                problems_col.insert_one(doc)
                print(green(f'[worker] [OK] Saved {problem_id} to problems collection'))
                
                # Update the index
                index_col.update_one(
                    {},
                    {'$addToSet': {'ids': problem_id}},
                    upsert=True
                )
                print(green(f'[worker] [OK] Updated problem_index with {problem_id}'))
                
                scraped += 1
                print(bold(green(f'[worker] {progress} Done: {problem_id} [OK]  (total scraped: {scraped})')))
                
            except Exception as err:
                failed += 1
                print(red(f'[worker] {progress} [X] Failed: {problem_id} — {err}'))
            
            # Wait before next problem with randomized delay (7-15 seconds)
            # This mimics human behavior and avoids Cloudflare detection
            if i < len(new_problems):
                random_wait(min_seconds=7, max_seconds=15, reason="next problem")
        
        print(cyan('[worker] ================================'))
        print(bold(green(f'[worker] Sync complete — scraped: {scraped}, failed: {failed}, total CF: {len(all_problems)}')))
        print(cyan('[worker] ================================'))
        
        return {'scraped': scraped, 'failed': failed, 'total': len(all_problems)}
        
    except Exception as err:
        print(red(f'[worker] [X] Sync crashed: {err}'))
        raise
