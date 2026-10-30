"""
pipeline/pipeline.py
=====================
The one command that keeps RAW_HTML, saved-from-reparse (local JSON) and
MongoDB fully synchronized, then scrapes whatever's new on Codeforces.

RAW_HTML is the source of truth. Everything else can always be rebuilt
from it without touching the network - that's the whole point: a parser
bug should only ever cost a re-parse, never a re-scrape of 11k+ problems.

Phase 1 - index vs actual data, per store (cheap, no cross-store logic):
    a. RAW_HTML files on disk         vs RAW_HTML/problem_index.json
    b. saved-from-reparse/*.json      vs saved-from-reparse/problem_index.json
    c. MongoDB `problems` collection  vs MongoDB `problem_index` collection
   Untracked files/docs get added to their index; stale index entries
   (pointing at nothing) get dropped. Each store becomes internally
   consistent (index == actual) before we compare stores to each other.

Phase 2 - index vs index, cross-store:
    a. RAW_HTML ids   vs local JSON ids
    b. local JSON ids vs MongoDB ids
   Whichever side is missing a problem gets fixed:
     - if RAW_HTML has it but the other side doesn't -> (re)parse from
       RAW_HTML (no network).
     - if RAW_HTML does NOT have it -> scrape it live, THEN parse.
   After phase 2, raw_ids == local_ids == mongo_ids. No exceptions.

Phase 3 - the actual update: fetch the full problem list from the CF API,
   diff it against the (now-authoritative) RAW_HTML index, and scrape +
   parse + save every problem CF has that we don't. One problem at a
   time: fetch -> save raw HTML + update RAW_HTML index -> parse -> save
   local JSON + update local index -> upsert Mongo + update Mongo index
   -> only then move to the next problem.

Usage:
    python pipeline/pipeline.py                 # full run: sync-repair, then scrape new
    python pipeline/pipeline.py --sync-only      # phases 1-2 only, no new scraping
    python pipeline/pipeline.py --skip-sync      # skip repair, go straight to phase 3
    python pipeline/pipeline.py --dry-run        # report only, write nothing
    python pipeline/pipeline.py --limit 50       # cap phase 3 to 50 new problems this run
    python pipeline/pipeline.py --id 1-A         # (re)process exactly one problem, ignore phases 1-3

Run pipeline/chrome-cookies-checker.py first (and whenever scraping starts
failing with Cloudflare challenges) - Codeforces has heavy bot detection
and a stale/missing cookie jar will fail every single live fetch.
"""

import os
import sys
import json
import time
import mimetypes
import argparse
from pathlib import Path

_PIPELINE_DIR = Path(__file__).parent.absolute()
_ROOT_DIR = _PIPELINE_DIR.parent
for _p in (str(_ROOT_DIR), str(_PIPELINE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv  # noqa: E402
for _env in ['.env.local', '.env']:
    _env_path = _ROOT_DIR / _env
    if _env_path.exists():
        load_dotenv(_env_path)
        break

if os.getenv('MONGODB_URI'):
    print(f'[env] [OK] MONGODB_URI is set')
else:
    print(f'[env] [X] WARNING: MONGODB_URI is not set!')

import scraper as cf_scraper  # noqa: E402
import parser as cf_parser  # noqa: E402
from bson.binary import Binary  # noqa: E402

from lib.db import get_problems_collection, get_index_collection, get_images_collection  # noqa: E402
from lib.cf_api import fetch_all_problems  # noqa: E402
from lib.timing import random_wait  # noqa: E402
from lib.colors import cyan, yellow, red, green, bold, success, error, info, warning  # noqa: E402

LOCAL_DIR         = _ROOT_DIR / 'saved-from-reparse'
LOCAL_INDEX_FILE  = LOCAL_DIR / 'problem_index.json'
FAILURES_FILE     = LOCAL_DIR / 'pipeline_failures.json'
RESERVED_STEMS    = {'problem_index', 'missing_ids', 'missing_db_ids', 'latex_catalog',
                      'pipeline_failures', 'anomalies'}

DOC_VERSION = 3  # docs produced by this pipeline (v1 = old live scraper, v2 = extract_dataset*.py)

_failures: list[dict] = []


def _record_failure(problem_key: str, stage: str, reason) -> None:
    _failures.append({'id': problem_key, 'stage': stage, 'reason': str(reason)})
    print(red(f'    [X] {problem_key} - {stage}: {reason}'))

# ── local JSON index (saved-from-reparse/problem_index.json) ────────────────

def load_local_index() -> set[str]:
    if LOCAL_INDEX_FILE.exists():
        try:
            return set(json.loads(LOCAL_INDEX_FILE.read_text(encoding='utf-8')).get('ids', []))
        except Exception:
            pass
    return set()


def save_local_index(ids: set[str]) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_INDEX_FILE.write_text(json.dumps({'ids': sorted(ids)}, indent=2), encoding='utf-8')


def add_local_id(problem_key: str) -> None:
    ids = load_local_index()
    if problem_key not in ids:
        ids.add(problem_key)
        save_local_index(ids)

# ── local JSON file layout: saved-from-reparse/<range>/<id>.json ────────────

def local_range_dir(contest_id: int) -> Path:
    lo = (contest_id // 100) * 100
    hi = lo + 100
    name = f'{lo:03d}-{hi}' if lo < 100 else f'{lo}-{hi}'
    d = LOCAL_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def local_json_path(problem_key: str, contest_id: int) -> Path:
    return local_range_dir(contest_id) / f'{problem_key}.json'


def find_local_json(problem_key: str) -> Path | None:
    try:
        contest_id = int(problem_key.split('-', 1)[0])
    except ValueError:
        return None
    p = local_json_path(problem_key, contest_id)
    return p if p.exists() else None

# ── scanning actual data (not indexes) ───────────────────────────────────────

def scan_raw_html_ids() -> set[str]:
    ids = {p.stem for p in cf_scraper.RAW_DIR.glob('*/*.html')}
    ids |= {p.stem for p in cf_scraper.RAW_DIR.glob('*.html')}  # legacy flat files
    return ids


def scan_local_json_ids() -> set[str]:
    return {p.stem for p in LOCAL_DIR.glob('*/*.json') if p.stem not in RESERVED_STEMS}


def scan_mongo_ids(problems_col) -> set[str]:
    ids = set()
    for d in problems_col.find({}, {'contestId': 1, 'index': 1}):
        cid, idx = d.get('contestId'), d.get('index')
        if cid is not None and idx:
            ids.add(f'{cid}-{idx}')
    return ids

# ── image upload to Mongo (given cf-image:// srcs already on disk) ──────────

def upload_images_to_mongo(problem_key: str, statement: dict, images_col) -> int:
    filenames: list[str] = []
    for sec in ('description', 'input', 'output', 'note'):
        for b in statement.get(sec, []) or []:
            if b.get('type') == 'image' and b.get('src', '').startswith('cf-image://'):
                filenames.append(b['src'].replace('cf-image://', ''))
    filenames = list(dict.fromkeys(filenames))

    uploaded = 0
    for fn in filenames:
        if images_col.find_one({'filename': fn}, {'_id': 1}):
            continue
        p = cf_scraper.IMAGES_DIR / fn
        if not p.exists():
            print(warning(f'    [img] Missing on disk, cannot upload: {fn}'))
            continue
        ct = mimetypes.guess_type(fn)[0] or 'image/png'
        images_col.insert_one({
            'problemId':   problem_key,
            'filename':    fn,
            'contentType': ct,
            'data':        Binary(p.read_bytes()),
            'cachedAt':    int(time.time()),
        })
        uploaded += 1
    return uploaded

# ── the shared "finish" step: parsed statement -> images + local json + mongo

def save_and_sync(contest_id: int, index: str, statement: dict,
                   problems_col, images_col, index_col) -> dict:
    problem_key = f'{contest_id}-{index}'

    urls = cf_parser.collect_image_urls(statement)
    url_map = cf_scraper.download_images(urls, problem_key)
    cf_parser.rewrite_image_srcs(statement, url_map)

    doc = {
        'id':        problem_key,
        'contestId': contest_id,
        'index':     index,
        'version':   DOC_VERSION,
        'cachedAt':  int(time.time()),
        'statement': statement,
    }

    local_json_path(problem_key, contest_id).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    add_local_id(problem_key)

    problems_col.update_one({'contestId': contest_id, 'index': index}, {'$set': doc}, upsert=True)
    index_col.update_one({}, {'$addToSet': {'ids': problem_key}}, upsert=True)
    upload_images_to_mongo(problem_key, statement, images_col)

    return doc

# ── processing primitives ─────────────────────────────────────────────────────

def process_from_raw(problem_key: str, problems_col, images_col, index_col) -> str:
    """RAW_HTML already has this file - (re)parse it, no network involved."""
    contest_id = int(problem_key.split('-', 1)[0])
    index = problem_key.split('-', 1)[1].upper()

    html_path = cf_scraper.find_html(problem_key, contest_id)
    if not html_path:
        _record_failure(problem_key, 'find_html', 'RAW_HTML file vanished between scan and processing')
        return 'error'

    try:
        html = html_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        _record_failure(problem_key, 'read_html', e)
        return 'error'

    statement = cf_parser.parse_statement(html, problem_key)
    if not statement:
        _record_failure(problem_key, 'parse', 'no .problem-statement found in saved HTML')
        return 'error'

    try:
        save_and_sync(contest_id, index, statement, problems_col, images_col, index_col)
    except Exception as e:
        _record_failure(problem_key, 'save', e)
        return 'error'

    return 'ok'


def process_new(problem_key: str, problems_col, images_col, index_col) -> str:
    """RAW_HTML does NOT have this file - scrape it live, then parse."""
    contest_id = int(problem_key.split('-', 1)[0])
    index = problem_key.split('-', 1)[1].upper()

    try:
        html = cf_scraper.fetch_and_save_raw(contest_id, index)
    except cf_scraper.PdfProblemError:
        cf_scraper.mark_pdf(problem_key)
        print(yellow(f'  [PDF] {problem_key} - skipped (statement is a PDF)'))
        return 'pdf'
    except Exception as e:
        _record_failure(problem_key, 'fetch', e)
        return 'error'

    # Raw HTML is safely on disk + indexed at this point no matter what happens next.

    statement = cf_parser.parse_statement(html, problem_key)
    if not statement:
        _record_failure(problem_key, 'parse', 'no .problem-statement found in freshly scraped HTML')
        return 'error'

    try:
        save_and_sync(contest_id, index, statement, problems_col, images_col, index_col)
    except Exception as e:
        _record_failure(problem_key, 'save', e)
        return 'error'

    print(success(f'  [OK] {problem_key} scraped + parsed + saved'))
    return 'ok'


def push_local_to_mongo(problem_key: str, problems_col, images_col, index_col) -> str:
    """Local JSON already exists and is trusted - push as-is, no reparse."""
    json_path = find_local_json(problem_key)
    if not json_path:
        _record_failure(problem_key, 'find_local_json', 'local JSON vanished between scan and processing')
        return 'error'

    try:
        doc = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception as e:
        _record_failure(problem_key, 'read_local_json', e)
        return 'error'

    try:
        problems_col.update_one(
            {'contestId': doc['contestId'], 'index': doc['index']}, {'$set': doc}, upsert=True
        )
        index_col.update_one({}, {'$addToSet': {'ids': problem_key}}, upsert=True)
        upload_images_to_mongo(problem_key, doc.get('statement', {}), images_col)
    except Exception as e:
        _record_failure(problem_key, 'mongo_push', e)
        return 'error'

    return 'ok'


def pull_mongo_to_local(problem_key: str, problems_col, images_col) -> str:
    """Problem exists in Mongo but missing in saved-from-reparse: download JSON and images from Mongo."""
    try:
        contest_id = int(problem_key.split('-', 1)[0])
        index = problem_key.split('-', 1)[1].upper()
    except ValueError:
        _record_failure(problem_key, 'parse_key', 'Invalid problem key format')
        return 'error'

    try:
        doc = problems_col.find_one({'contestId': contest_id, 'index': index}, {'_id': 0})
        if not doc:
            _record_failure(problem_key, 'mongo_find', 'Document missing in MongoDB')
            return 'error'

        doc['id'] = problem_key
        p = local_json_path(problem_key, contest_id)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
        add_local_id(problem_key)

        # Download any referenced images from Mongo if missing on disk
        statement = doc.get('statement', {})
        for sec in ('description', 'input', 'output', 'note'):
            for b in statement.get(sec, []) or []:
                if b.get('type') == 'image' and b.get('src', '').startswith('cf-image://'):
                    fn = b['src'].replace('cf-image://', '')
                    img_path = cf_scraper.IMAGES_DIR / fn
                    if not img_path.exists():
                        img_doc = images_col.find_one({'filename': fn})
                        if img_doc and 'data' in img_doc:
                            cf_scraper.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                            img_path.write_bytes(img_doc['data'])
                            print(info(f'    [img] Downloaded {fn} from Mongo'))

        return 'ok'
    except Exception as e:
        _record_failure(problem_key, 'mongo_pull', e)
        return 'error'

# ── Phase 1 - index vs actual data, per store ─────────────────────────────────

def repair_raw_index(dry_run: bool) -> set[str]:
    actual = scan_raw_html_ids()
    idx = cf_scraper.load_raw_index()
    indexed = set(idx['ids'])
    pdf_ids = set(idx['pdf-problem-ids'])

    untracked, stale = actual - indexed, indexed - actual
    note = f'  (+{len(untracked)} untracked, -{len(stale)} stale)' if (untracked or stale) else '  (in sync)'
    print(info(f'  RAW_HTML           : {len(actual):>6} files on disk, {len(indexed):>6} indexed{note}'))

    if (untracked or stale) and not dry_run:
        cf_scraper.save_raw_index(actual, pdf_ids)
    return actual


def repair_local_index(dry_run: bool) -> set[str]:
    actual = scan_local_json_ids()
    indexed = load_local_index()

    untracked, stale = actual - indexed, indexed - actual
    note = f'  (+{len(untracked)} untracked, -{len(stale)} stale)' if (untracked or stale) else '  (in sync)'
    print(info(f'  saved-from-reparse : {len(actual):>6} files on disk, {len(indexed):>6} indexed{note}'))

    if (untracked or stale) and not dry_run:
        save_local_index(actual)
    return actual


def repair_mongo_index(problems_col, index_col, dry_run: bool) -> set[str]:
    actual = scan_mongo_ids(problems_col)
    doc = index_col.find_one({})
    indexed = set(doc.get('ids', [])) if doc else set()

    untracked, stale = actual - indexed, indexed - actual
    note = f'  (+{len(untracked)} untracked, -{len(stale)} stale)' if (untracked or stale) else '  (in sync)'
    print(info(f'  MongoDB            : {len(actual):>6} docs, {len(indexed):>6} indexed{note}'))

    if (untracked or stale) and not dry_run:
        index_col.update_one({}, {'$set': {'ids': sorted(actual)}}, upsert=True)
    return actual

# ── Phase 2a - RAW_HTML <-> local JSON ────────────────────────────────────────

def phase_2a(raw_ids: set[str], local_ids: set[str],
             problems_col, images_col, index_col, dry_run: bool) -> tuple[set[str], set[str]]:
    to_parse  = sorted(raw_ids - local_ids)    # RAW_HTML has it, local doesn't -> reparse (cheap)
    to_scrape = sorted(local_ids - raw_ids)    # local has it, RAW_HTML doesn't -> must re-scrape live

    if not to_parse and not to_scrape:
        print(success('  RAW_HTML <-> local JSON already match.'))
        return raw_ids, local_ids

    print(cyan(f'  RAW_HTML -> local JSON : {len(to_parse):>6} to (re)parse from disk (no network)'))
    print(cyan(f'  local JSON -> RAW_HTML : {len(to_scrape):>6} missing raw HTML - will re-scrape live'))
    if dry_run:
        return raw_ids, local_ids

    for i, pid in enumerate(to_parse, 1):
        print(cyan(f'  ({i}/{len(to_parse)}) parse {pid}'), end=' ', flush=True)
        if process_from_raw(pid, problems_col, images_col, index_col) == 'ok':
            local_ids.add(pid)
            print(success('ok'))

    for i, pid in enumerate(to_scrape, 1):
        print(cyan(f'\n  ({i}/{len(to_scrape)}) re-scrape {pid} (missing from RAW_HTML)'))
        status = process_new(pid, problems_col, images_col, index_col)
        if status == 'ok':
            raw_ids.add(pid)
            local_ids.add(pid)
        elif status == 'pdf':
            local_ids.discard(pid)  # was a phantom entry pointing at a PDF-only problem
        if i < len(to_scrape):
            random_wait(reason=f'next repair scrape ({i + 1}/{len(to_scrape)})')

    return raw_ids, local_ids

# ── Phase 2b - local JSON <-> MongoDB ────────────────────────────────────────

def phase_2b(local_ids: set[str], mongo_ids: set[str],
             problems_col, images_col, index_col, dry_run: bool) -> tuple[set[str], set[str]]:
    to_push = sorted(local_ids - mongo_ids)    # local JSON exists -> just push, no reparse
    to_pull = sorted(mongo_ids - local_ids)    # only Mongo has it -> source is gone, re-scrape live

    if not to_push and not to_pull:
        print(success('  local JSON <-> MongoDB already match.'))
        return local_ids, mongo_ids

    print(cyan(f'  local JSON -> MongoDB : {len(to_push):>6} to push (already parsed, no reparse)'))
    print(cyan(f'  MongoDB -> local JSON : {len(to_pull):>6} to pull (download from Mongo)'))
    if dry_run:
        return local_ids, mongo_ids

    for i, pid in enumerate(to_push, 1):
        print(cyan(f'  ({i}/{len(to_push)}) push {pid}'), end=' ', flush=True)
        if push_local_to_mongo(pid, problems_col, images_col, index_col) == 'ok':
            mongo_ids.add(pid)
            print(success('ok'))

    for i, pid in enumerate(to_pull, 1):
        print(cyan(f'  ({i}/{len(to_pull)}) pull {pid} from Mongo'), end=' ', flush=True)
        if pull_mongo_to_local(pid, problems_col, images_col) == 'ok':
            local_ids.add(pid)
            print(success('ok'))

    return local_ids, mongo_ids

# ── Phase 3 - fetch new problems from CF API, scrape the ones we're missing ──

def phase_3(raw_ids: set[str], problems_col, images_col, index_col,
            limit: int, dry_run: bool) -> dict:
    all_problems = fetch_all_problems()
    idx = cf_scraper.load_raw_index()
    pdf_ids = set(idx['pdf-problem-ids'])
    cf_ids = {f"{p['contestId']}-{p['index'].upper()}" for p in all_problems}

    todo = sorted(cf_ids - raw_ids - pdf_ids)
    if limit > 0:
        todo = todo[:limit]

    print(info(f'  CF API problems total : {len(all_problems):>6}'))
    print(info(f'  Already in RAW_HTML    : {len(cf_ids & raw_ids):>6}'))
    print(info(f'  Known PDF (skipped)    : {len(cf_ids & pdf_ids):>6}'))
    print(info(f'  New to scrape this run : {len(todo):>6}'))

    if not todo:
        print(success('\n  Nothing new - RAW_HTML already covers every CF problem.'))
        return {'scraped': 0, 'pdf': 0, 'failed': 0, 'total': 0}

    if dry_run:
        print(yellow(f'\n  DRY RUN - first 20: {todo[:20]}'))
        return {'scraped': 0, 'pdf': 0, 'failed': 0, 'total': len(todo)}

    scraped = pdf = failed = 0
    for i, pid in enumerate(todo, 1):
        print(cyan(f'\n  ({i}/{len(todo)}) {pid}'))
        contest_id, index = pid.split('-', 1)
        status = process_new(f'{contest_id}-{index}', problems_col, images_col, index_col)
        if status == 'ok':
            scraped += 1
            raw_ids.add(pid)
        elif status == 'pdf':
            pdf += 1
        else:
            failed += 1

        if i < len(todo):
            random_wait(reason=f'next problem ({i + 1}/{len(todo)})')

    return {'scraped': scraped, 'pdf': pdf, 'failed': failed, 'total': len(todo)}

# ── Entry point ───────────────────────────────────────────────────────────────

def _dump_failures() -> None:
    if _failures:
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        FAILURES_FILE.write_text(json.dumps(_failures, indent=2), encoding='utf-8')
        print(red(f'\n[pipeline] {len(_failures)} failure(s) logged to {FAILURES_FILE}'))


def run_pipeline(sync_only: bool = False, skip_sync: bool = False, limit: int = 0,
                  dry_run: bool = False, single_id: str = '', close_browser: bool = True) -> dict:
    """
    Programmatic entry point -- everything main() does, minus argument
    parsing, so app.py / app_hf.py can call this directly from a route
    instead of shelling out. Always returns a summary dict; never raises
    for per-problem failures (those land in _failures / FAILURES_FILE).

    close_browser=False lets a caller that's about to make more pipeline
    calls back-to-back skip the quit()/relaunch cycle in between.
    """
    _failures.clear()

    problems_col = get_problems_collection()
    images_col   = get_images_collection()
    index_col    = get_index_collection()

    summary: dict = {'mode': 'id' if single_id else ('sync' if sync_only else 'full')}

    try:
        if single_id:
            pid = single_id.strip()
            contest_id = int(pid.split('-', 1)[0])
            html_path = cf_scraper.find_html(pid, contest_id)

            if dry_run:
                action = 'reparse from RAW_HTML (no network)' if html_path else 'scrape live'
                print(yellow(f'[pipeline] DRY RUN - would {action} for {pid}'))
                summary.update(id=pid, would=action)
                return summary

            if html_path:
                print(cyan(f'[pipeline] {pid}: RAW_HTML found, reparsing (no network)...'))
                status = process_from_raw(pid, problems_col, images_col, index_col)
            else:
                print(cyan(f'[pipeline] {pid}: no RAW_HTML, scraping live...'))
                status = process_new(pid, problems_col, images_col, index_col)
            (print(success(f'[pipeline] {pid}: {status}')) if status == 'ok'
             else print(red(f'[pipeline] {pid}: {status}')))
            summary.update(id=pid, status=status)
            return summary

        raw_ids = scan_raw_html_ids()

        if not skip_sync:
            print(bold(cyan('=' * 62)))
            print(bold(cyan('  Phase 1 - index vs actual data (per store)')))
            print(bold(cyan('=' * 62)))
            raw_ids   = repair_raw_index(dry_run)
            local_ids = repair_local_index(dry_run)
            mongo_ids = repair_mongo_index(problems_col, index_col, dry_run)

            print(bold(cyan('\n' + '=' * 62)))
            print(bold(cyan('  Phase 2a - RAW_HTML <-> local JSON')))
            print(bold(cyan('=' * 62)))
            raw_ids, local_ids = phase_2a(raw_ids, local_ids, problems_col, images_col, index_col, dry_run)

            print(bold(cyan('\n' + '=' * 62)))
            print(bold(cyan('  Phase 2b - local JSON <-> MongoDB')))
            print(bold(cyan('=' * 62)))
            local_ids, mongo_ids = phase_2b(local_ids, mongo_ids, problems_col, images_col, index_col, dry_run)

            summary['synced'] = (raw_ids == local_ids == mongo_ids)
            summary['counts'] = {'raw': len(raw_ids), 'local': len(local_ids), 'mongo': len(mongo_ids)}

            if not dry_run:
                if summary['synced']:
                    print(success(f'\n  All three indexes are fully synchronized: {len(raw_ids)} problems.'))
                else:
                    print(warning(
                        f'\n  Still out of sync after repair - '
                        f'raw={len(raw_ids)} local={len(local_ids)} mongo={len(mongo_ids)}'
                    ))
                    print(warning(f'  Check {FAILURES_FILE} for anything that failed to repair.'))

        if not sync_only:
            print(bold(cyan('\n' + '=' * 62)))
            print(bold(cyan('  Phase 3 - fetch new problems from Codeforces')))
            print(bold(cyan('=' * 62)))
            result = phase_3(raw_ids, problems_col, images_col, index_col, limit, dry_run)
            summary.update(result)

            print(bold(cyan('\n' + '=' * 62)))
            print(bold(cyan('  Summary')))
            print(bold(cyan('=' * 62)))
            print(success(f'  Scraped : {result["scraped"]}'))
            if result['pdf']:
                print(yellow(f'  PDF skip: {result["pdf"]}'))
            if result['failed']:
                print(red(f'  Failed  : {result["failed"]}'))

        summary['failures'] = len(_failures)
        return summary

    finally:
        if close_browser:
            cf_scraper.close_driver()
        _dump_failures()


def main() -> None:
    ap = argparse.ArgumentParser(description='Sync-check + scrape/parse pipeline for CF problems.')
    ap.add_argument('--sync-only', action='store_true', help='Only run phases 1-2 (repair), skip fetching new problems')
    ap.add_argument('--skip-sync', action='store_true', help='Skip phases 1-2, jump straight to phase 3')
    ap.add_argument('--limit', type=int, default=0, help='Max NEW problems to scrape in phase 3 (0 = all)')
    ap.add_argument('--dry-run', action='store_true', help='Report only, write nothing')
    ap.add_argument('--id', type=str, default='', help='(Re)process a single problem key e.g. 1-A, bypassing phases 1-3')
    args = ap.parse_args()

    run_pipeline(
        sync_only=args.sync_only, skip_sync=args.skip_sync,
        limit=args.limit, dry_run=args.dry_run, single_id=args.id,
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(yellow('\n[pipeline] Interrupted - closing browser...'))
        cf_scraper.close_driver()
        _dump_failures()
        sys.exit(1)
