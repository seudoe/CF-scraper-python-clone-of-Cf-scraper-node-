"""
Background worker for syncing all problems from Codeforces
"""

import time
from typing import Dict
from lib.cf_api import fetch_all_problems
from lib.scraper import scrape_problem
from lib.db import get_problems_collection, get_index_collection


SCRAPE_DELAY_SEC = 10


def sync_problems() -> Dict:
    """
    Main sync function - fetches problem list and scrapes new problems
    Returns dict with scraped/failed/total counts
    """
    print('[worker] ════════════════════════════════')
    print('[worker] Starting problem sync')
    print('[worker] ════════════════════════════════')
    
    try:
        # 1. Fetch all problems from CF API
        all_problems = fetch_all_problems()
        
        # 2. Load already-scraped IDs from MongoDB
        print('[worker] Checking MongoDB for already-scraped problems ...')
        index_col = get_index_collection()
        index_doc = index_col.find_one({})
        scraped_ids = set(index_doc.get('ids', []) if index_doc else [])
        
        print(f'[worker] Already scraped: {len(scraped_ids)} / {len(all_problems)} problems')
        
        # 3. Diff - only new problems
        new_problems = [
            p for p in all_problems
            if f"{p['contestId']}-{p['index']}" not in scraped_ids
        ]
        
        print(f'[worker] New problems to scrape: {len(new_problems)}')
        
        if len(new_problems) == 0:
            print('[worker] ✓ All problems are up to date — nothing to do')
            return {'scraped': 0, 'failed': 0, 'total': len(all_problems)}
        
        problems_col = get_problems_collection()
        scraped = 0
        failed = 0
        
        for i, p in enumerate(new_problems, 1):
            problem_id = f"{p['contestId']}-{p['index']}"
            progress = f'({i}/{len(new_problems)})'
            
            try:
                print(f'[worker] {progress} Starting: {problem_id} — "{p["name"]}"')
                
                doc = scrape_problem(p['contestId'], p['index'])
                
                # Save problem JSON to problems collection
                problems_col.insert_one(doc.to_dict())
                print(f'[worker] ✓ Saved {problem_id} to problems collection')
                
                # Update the index
                index_col.update_one(
                    {},
                    {'$addToSet': {'ids': problem_id}},
                    upsert=True
                )
                print(f'[worker] ✓ Updated problem_index with {problem_id}')
                
                scraped += 1
                print(f'[worker] {progress} Done: {problem_id} ✓  (total scraped: {scraped})')
                
            except Exception as err:
                failed += 1
                print(f'[worker] {progress} ✗ Failed: {problem_id} — {err}')
            
            # Wait before next problem (skip delay after last one)
            if i < len(new_problems):
                print(f'[worker] Waiting {SCRAPE_DELAY_SEC}s before next problem...')
                time.sleep(SCRAPE_DELAY_SEC)
        
        print('[worker] ════════════════════════════════')
        print(f'[worker] Sync complete — scraped: {scraped}, failed: {failed}, total CF: {len(all_problems)}')
        print('[worker] ════════════════════════════════')
        
        return {'scraped': scraped, 'failed': failed, 'total': len(all_problems)}
        
    except Exception as err:
        print(f'[worker] ✗ Sync crashed: {err}')
        raise
