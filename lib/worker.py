"""
Background worker for syncing all problems from Codeforces
"""

import json
import time
from pathlib import Path
from typing import Dict
from lib.cf_api import fetch_all_problems
from lib.scraper import scrape_problem
from lib.db import get_problems_collection, get_index_collection
from lib.timing import random_wait
from lib.parse import PdfProblemError
from lib.colors import green, red, yellow, cyan, bold, success, error, warning, info

MAX_WAIT = 7
MIN_WAIT = 3

# RAW_HTML index file (same as scraper.py uses)
_RAW_INDEX = Path(__file__).parent.parent / 'RAW_HTML' / 'problem_index.json'


def _load_raw_index() -> dict:
    """Load RAW_HTML/problem_index.json, return empty structure if missing."""
    if _RAW_INDEX.exists():
        try:
            return json.loads(_RAW_INDEX.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'ids': [], 'pdf-problem-ids': []}


def _save_pdf_id(problem_id: str):
    """Append problem_id to pdf-problem-ids in RAW_HTML/problem_index.json."""
    try:
        index = _load_raw_index()
        index.setdefault('pdf-problem-ids', [])
        if problem_id not in index['pdf-problem-ids']:
            index['pdf-problem-ids'].append(problem_id)
            index['pdf-problem-ids'].sort()
            _RAW_INDEX.parent.mkdir(exist_ok=True)
            _RAW_INDEX.write_text(json.dumps(index, indent=2), encoding='utf-8')
    except Exception as e:
        print(warning(f'[worker] Could not save PDF id to index: {e}'))


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

        # Also load known PDF ids from RAW_HTML index — no point scraping them again
        raw_index = _load_raw_index()
        pdf_ids = set(raw_index.get('pdf-problem-ids', []))

        print(info(f'[worker] Already scraped : {len(scraped_ids)} / {len(all_problems)}'))
        if pdf_ids:
            print(info(f'[worker] Known PDF problems: {len(pdf_ids)} (will skip)'))

        # 3. Diff — skip already scraped AND known PDFs
        new_problems = [
            p for p in all_problems
            if f"{p['contestId']}-{p['index']}" not in scraped_ids
            and f"{p['contestId']}-{p['index']}" not in pdf_ids
        ]
        
        print(yellow(f'[worker] New problems to scrape: {len(new_problems)}'))
        
        if len(new_problems) == 0:
            print(success('[worker] All problems are up to date — nothing to do'))
            return {'scraped': 0, 'failed': 0, 'total': len(all_problems)}
        
        problems_col = get_problems_collection()
        scraped = 0
        failed = 0
        skipped_pdf = 0
        
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
                
            except PdfProblemError as pdf_err:
                # PDF problems are expected — record the id, skip, no failure count
                skipped_pdf += 1
                _save_pdf_id(problem_id)
                print(yellow(f'[worker] {progress} [PDF] Skipped: {problem_id} — {pdf_err}'))

            except Exception as err:
                failed += 1
                print(red(f'[worker] {progress} [X] Failed: {problem_id} — {err}'))
            
            # Wait before next problem with randomized delay (7-15 seconds)
            # This mimics human behavior and avoids Cloudflare detection
            if i < len(new_problems):
                random_wait(min_seconds=MIN_WAIT, max_seconds=MAX_WAIT, reason="next problem")
        
        print(cyan('[worker] ================================'))
        print(bold(green(f'[worker] Sync complete — scraped: {scraped}, failed: {failed}, pdf_skipped: {skipped_pdf}, total CF: {len(all_problems)}')))
        print(cyan('[worker] ================================'))
        
        return {'scraped': scraped, 'failed': failed, 'skipped_pdf': skipped_pdf, 'total': len(all_problems)}
        
    except Exception as err:
        print(red(f'[worker] [X] Sync crashed: {err}'))
        raise
