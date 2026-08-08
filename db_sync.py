"""
db_sync.py — MongoDB consistency fixer
=======================================
Compares problems collection and problem_index collection.
Keeps only IDs that exist in BOTH. Deletes the extras from each.

Usage:
    python db_sync.py          # dry run — shows what would be deleted
    python db_sync.py --fix    # actually deletes the mismatches
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
for env_file in ['.env.local', '.env']:
    if (Path(__file__).parent / env_file).exists():
        load_dotenv(Path(__file__).parent / env_file)
        break

from lib.db import get_problems_collection, get_index_collection
from lib.colors import green, red, yellow, cyan, bold, info, success, warning


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fix', action='store_true', help='Actually delete mismatches (default: dry run)')
    args = parser.parse_args()

    print(bold(cyan('=' * 55)))
    print(bold(cyan('  MongoDB Consistency Syncer')))
    print(bold(cyan('=' * 55)))
    print()

    problems_col = get_problems_collection()
    index_col    = get_index_collection()

    # ── Collect IDs ──────────────────────────────────────
    # IDs from problems collection — use aggregation to find duplicates too
    problem_docs = list(problems_col.find({}, {'contestId': 1, 'index': 1, '_id': 1}))
    total_problem_docs = len(problem_docs)  # real count including duplicates

    # Build a map: id -> list of _ids (to find duplicates)
    from collections import defaultdict
    id_to_oids = defaultdict(list)
    for d in problem_docs:
        pid = f"{d['contestId']}-{d['index']}"
        id_to_oids[pid].append(d['_id'])

    problems_ids = set(id_to_oids.keys())  # unique IDs only

    # Duplicates: same contestId+index appearing more than once
    duplicates = {pid: oids for pid, oids in id_to_oids.items() if len(oids) > 1}

    # IDs from problem_index collection
    index_doc  = index_col.find_one({})
    index_ids  = set(index_doc.get('ids', []) if index_doc else [])

    print(info(f'  problems collection : {total_problem_docs} docs total'))
    print(info(f'  problems unique IDs : {len(problems_ids)}'))
    print(info(f'  problem_index array : {len(index_ids)} ids'))
    if duplicates:
        print(red(f'  DUPLICATES found    : {len(duplicates)} problems have multiple docs!'))
    print()

    # ── Diff ─────────────────────────────────────────────
    # In problems but NOT in index → delete the problem doc
    extra_in_problems = problems_ids - index_ids

    # In index but NOT in problems → remove from index array
    extra_in_index = index_ids - problems_ids

    # What we keep
    keep = problems_ids & index_ids

    print(bold(f'  Keep (in both)           : {len(keep)}'))
    print(red( f'  Extra in problems        : {len(extra_in_problems)}') if extra_in_problems else
          green(f'  Extra in problems        : 0'))
    print(red( f'  Extra in index           : {len(extra_in_index)}') if extra_in_index else
          green(f'  Extra in index           : 0'))
    if duplicates:
        total_dup_docs = sum(len(v) - 1 for v in duplicates.values())
        print(red(f'  Duplicate docs to delete : {total_dup_docs}'))
    print()

    if not extra_in_problems and not extra_in_index and not duplicates:
        print(success('  Collections are already in sync. Nothing to do.'))
        return

    # ── Show detail ───────────────────────────────────────
    if duplicates:
        print(yellow('  Duplicates (will keep newest, delete rest):'))
        for pid, oids in sorted(duplicates.items()):
            print(red(f'    - {pid}: {len(oids)} docs ({len(oids)-1} extra)'))
        print()

    if extra_in_problems:
        print(yellow('  Will DELETE from problems collection:'))
        for pid in sorted(extra_in_problems):
            print(red(f'    - {pid}'))
        print()

    if extra_in_index:
        print(yellow('  Will REMOVE from problem_index array:'))
        for pid in sorted(extra_in_index):
            print(red(f'    - {pid}'))
        print()

    if not args.fix:
        print(yellow('  DRY RUN — nothing changed.'))
        print(yellow('  Run with --fix to apply deletions.'))
        return

    # ── Apply fixes ───────────────────────────────────────
    print(bold(cyan('  Applying fixes...')))

    # Delete duplicate docs (keep the first _id, delete the rest)
    deleted_dups = 0
    if duplicates:
        for pid, oids in duplicates.items():
            # keep oids[0], delete all others
            for oid in oids[1:]:
                problems_col.delete_one({'_id': oid})
                deleted_dups += 1
        print(success(f'  Deleted {deleted_dups} duplicate doc(s)'))

    # Delete extra problem docs
    if extra_in_problems:
        for pid in extra_in_problems:
            contest_id, index = pid.split('-', 1)
            problems_col.delete_many({'contestId': int(contest_id), 'index': index})
        print(success(f'  Deleted {len(extra_in_problems)} problem doc(s) not in index'))

    # Remove extra IDs from index array
    if extra_in_index:
        new_ids = sorted(keep)
        index_col.update_one({}, {'$set': {'ids': new_ids}}, upsert=True)
        print(success(f'  Removed {len(extra_in_index)} id(s) from problem_index'))

    final_count = problems_col.count_documents({})
    print()
    print(bold(green(f'  Done. problems collection now has {final_count} docs.')))


if __name__ == '__main__':
    main()
