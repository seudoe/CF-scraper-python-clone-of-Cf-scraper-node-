"""
compare_indexes.py
==================
Compares the three problem indexes:
  1. RAW_HTML/problem_index.json          — source of truth (all scraped HTMLs)
  2. saved-from-reparse/problem_index.json — locally extracted dataset JSONs
  3. MongoDB problem_index collection      — new DB

Shows what's missing from each and saves:
  saved-from-reparse/missing_ids.json     — missing from local JSON
  saved-from-reparse/missing_db_ids.json  — missing from MongoDB

Usage:
    python compare_indexes.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
for env_file in ['.env.local', '.env']:
    p = Path(__file__).parent / env_file
    if p.exists():
        load_dotenv(p)
        break

from lib.db import get_index_collection
from lib.colors import cyan, green, yellow, red, info, success, warning

RAW_INDEX    = Path(__file__).parent / 'RAW_HTML' / 'problem_index.json'
LOCAL_INDEX  = Path(__file__).parent / 'saved-from-reparse' / 'problem_index.json'
MISSING_LOCAL = Path(__file__).parent / 'saved-from-reparse' / 'missing_ids.json'
MISSING_DB    = Path(__file__).parent / 'saved-from-reparse' / 'missing_db_ids.json'

# ── Load all three ────────────────────────────────────────────────────────────

raw_ids = set(json.loads(RAW_INDEX.read_text(encoding='utf-8')).get('ids', []))

local_ids: set[str] = set()
if LOCAL_INDEX.exists():
    local_ids = set(json.loads(LOCAL_INDEX.read_text(encoding='utf-8')).get('ids', []))

doc = get_index_collection().find_one({})
db_ids: set[str] = set(doc.get('ids', [])) if doc else set()

# ── Diff ──────────────────────────────────────────────────────────────────────

missing_local = sorted(raw_ids - local_ids)
missing_db    = sorted(raw_ids - db_ids)
extra_local   = sorted(local_ids - raw_ids)
extra_db      = sorted(db_ids - raw_ids)

# In local but not yet in DB (local ahead of DB)
local_not_db  = sorted(local_ids - db_ids)

# ── Report ────────────────────────────────────────────────────────────────────

print(cyan('=' * 56))
print(cyan('  Index comparison'))
print(cyan('=' * 56))
print(info(f'  RAW_HTML (source of truth) : {len(raw_ids):>6}'))
print(info(f'  Local JSON index           : {len(local_ids):>6}'))
print(info(f'  MongoDB index              : {len(db_ids):>6}'))
print()

if missing_local:
    print(yellow(f'  Missing from local JSON    : {len(missing_local):>6}  ← run: python extract_dataset.py --missing --full-insert'))
else:
    print(success(f'  Missing from local JSON    :      0  ✓'))

if missing_db:
    print(yellow(f'  Missing from MongoDB       : {len(missing_db):>6}  ← run: python extract_dataset.py --missing-db --full-insert'))
else:
    print(success(f'  Missing from MongoDB       :      0  ✓'))

if local_not_db:
    print(yellow(f'  Local JSON not yet in DB   : {len(local_not_db):>6}  (extracted but not pushed)'))
else:
    print(success(f'  Local JSON not yet in DB   :      0  ✓ (in sync)'))

if extra_local:
    print(warning(f'  Extra in local (not in RAW): {len(extra_local):>6}'))
if extra_db:
    print(warning(f'  Extra in DB    (not in RAW): {len(extra_db):>6}'))

print(cyan('=' * 56))

# ── Save missing lists ────────────────────────────────────────────────────────

if missing_local:
    MISSING_LOCAL.write_text(json.dumps({'ids': missing_local}, indent=2), encoding='utf-8')
    print(info(f'\n  Saved {len(missing_local)} missing-local IDs → {MISSING_LOCAL.name}'))

if missing_db:
    MISSING_DB.write_text(json.dumps({'ids': missing_db}, indent=2), encoding='utf-8')
    print(info(f'  Saved {len(missing_db)} missing-db IDs    → {MISSING_DB.name}'))

if not missing_local and not missing_db:
    print(success('\n  All three indexes are in sync!'))
