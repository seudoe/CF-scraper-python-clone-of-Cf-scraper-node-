"""
sync_db_rawlocal.py
====================
Compares MongoDB problems_index with RAW_HTML/problem_index.json.
Fetches and saves HTML for any problems in MongoDB that are missing locally.

Usage:
    python sync_db_rawlocal.py            # show diff only
    python sync_db_rawlocal.py --fetch    # fetch missing HTMLs from CF
    python sync_db_rawlocal.py --fetch --limit 50   # fetch at most 50 this run
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
for env_file in ['.env.local', '.env']:
    if (Path(__file__).parent / env_file).exists():
        load_dotenv(Path(__file__).parent / env_file)
        break

from lib.db import get_index_collection
from lib.fetch import fetch_html, close_driver
from lib.scraper import _save_raw_html, _RAW_DIR, _INDEX_FILE
from lib.timing import random_wait
from lib.parse import PdfProblemError
from lib.colors import green, red, yellow, cyan, bold, info, success, warning, error, gray

CF_BASE = 'https://codeforces.com'


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_raw_index() -> dict:
    if _INDEX_FILE.exists():
        try:
            return json.loads(_INDEX_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'ids': [], 'pdf-problem-ids': []}


def save_raw_index(index: dict):
    _RAW_DIR.mkdir(exist_ok=True)
    _INDEX_FILE.write_text(json.dumps(index, indent=2), encoding='utf-8')


def add_to_raw_index(problem_id: str):
    idx = load_raw_index()
    if problem_id not in idx['ids']:
        idx['ids'].append(problem_id)
        idx['ids'].sort()
        save_raw_index(idx)


def add_pdf_to_raw_index(problem_id: str):
    idx = load_raw_index()
    idx.setdefault('pdf-problem-ids', [])
    if problem_id not in idx['pdf-problem-ids']:
        idx['pdf-problem-ids'].append(problem_id)
        idx['pdf-problem-ids'].sort()
        save_raw_index(idx)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true',
                        help='Actually fetch missing HTMLs from CF')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max number of missing problems to fetch this run')
    args = parser.parse_args()

    print(bold(cyan('=' * 55)))
    print(bold(cyan('  DB ↔ RAW_HTML Sync')))
    print(bold(cyan('=' * 55)))
    print()

    # ── Step 1: get IDs from both sources ────────────────
    index_col = get_index_collection()
    index_doc = index_col.find_one({})
    db_ids = set(index_doc.get('ids', []) if index_doc else [])

    raw_index = load_raw_index()
    local_ids = set(raw_index.get('ids', []))
    pdf_ids   = set(raw_index.get('pdf-problem-ids', []))

    print(info(f'  MongoDB problems_index : {len(db_ids)} ids'))
    print(info(f'  RAW_HTML local files   : {len(local_ids)} ids'))
    print(info(f'  Known PDF problems     : {len(pdf_ids)} (will skip)'))
    print()

    # ── Step 2: diff ──────────────────────────────────────
    # Missing locally = in DB but not in local AND not a known PDF
    missing = sorted(db_ids - local_ids - pdf_ids)
    # Extra locally = in local but not in DB (orphaned files)
    orphaned = sorted(local_ids - db_ids)

    print(bold(f'  Missing locally (need fetch) : {len(missing)}'))
    if orphaned:
        print(yellow(f'  Orphaned local files        : {len(orphaned)} (in RAW_HTML but not in DB)'))
    print()

    if not missing and not orphaned:
        print(success('  Already in sync. Nothing to do.'))
        return

    if orphaned:
        print(yellow('  Orphaned (local only, no DB entry):'))
        for pid in orphaned[:20]:
            print(gray(f'    - {pid}'))
        if len(orphaned) > 20:
            print(gray(f'    ... and {len(orphaned) - 20} more'))
        print()

    if not missing:
        print(success('  No missing HTMLs to fetch.'))
        return

    if not args.fetch:
        print(yellow(f'  DRY RUN — {len(missing)} HTMLs to fetch.'))
        print(yellow('  First 20:'))
        for pid in missing[:20]:
            print(gray(f'    - {pid}'))
        if len(missing) > 20:
            print(gray(f'    ... and {len(missing) - 20} more'))
        print()
        print(yellow('  Run with --fetch to download them.'))
        print(yellow('  Add --limit N to fetch at most N this run.'))
        return

    # ── Step 3: fetch missing HTMLs ───────────────────────
    to_fetch = missing[:args.limit] if args.limit else missing

    print(bold(cyan(f'  Fetching {len(to_fetch)} missing HTML(s)...')))
    if args.limit and len(missing) > args.limit:
        print(yellow(f'  (limited to {args.limit} this run, {len(missing) - args.limit} remaining after)'))
    print()

    ok = 0
    failed = 0
    pdfs = 0

    for i, problem_id in enumerate(to_fetch, 1):
        parts = problem_id.split('-', 1)
        contest_id, index = parts[0], parts[1]
        url = f'{CF_BASE}/problemset/problem/{contest_id}/{index}'
        progress = f'({i}/{len(to_fetch)})'

        print(cyan(f'  {progress} Fetching {problem_id}...'))

        try:
            html = fetch_html(url)
            _save_raw_html(problem_id, html)
            add_to_raw_index(problem_id)
            ok += 1
            print(success(f'  {progress} Saved {problem_id}.html'))

        except PdfProblemError:
            pdfs += 1
            add_pdf_to_raw_index(problem_id)
            print(yellow(f'  {progress} [PDF] Skipped {problem_id}'))

        except Exception as e:
            failed += 1
            print(error(f'  {progress} [X] Failed {problem_id}: {e}'))

        # Wait between requests (keep existing timing)
        if i < len(to_fetch):
            random_wait(reason=f'next problem ({i+1}/{len(to_fetch)})')

    # ── Summary ───────────────────────────────────────────
    close_driver()
    print()
    print(bold(cyan('=' * 55)))
    print(bold(cyan('  Summary')))
    print(bold(cyan('=' * 55)))
    print(success(f'  Saved    : {ok}'))
    if pdfs:
        print(yellow(f'  PDF skip : {pdfs}'))
    if failed:
        print(red(f'  Failed   : {failed}'))

    remaining = len(missing) - len(to_fetch)
    if remaining > 0:
        print(yellow(f'  Remaining: {remaining} (run again to continue)'))
    else:
        print(success('  All missing HTMLs fetched!'))
    print()


if __name__ == '__main__':
    main()
