"""
extract-dataset-v2.py
======================
Three things only:

  1. Compare RAW_HTML index vs local index vs MongoDB index.
     Print what's missing where.

  2. Sync: if local has problems missing from DB (or vice versa),
     re-extract those specific ones and write to whichever is behind.
     Both stay in sync after this step.

  3. Parse all remaining (in RAW_HTML but not yet in local/DB),
     save JSON locally, upsert to MongoDB, upload images.

Pre-condition structure:
  RAW_HTML/
    problem_index.json          { "ids": [...] }
    000-100/1-A.html  ...
    images/1000-C_<hash>.png ...

  saved-from-reparse/
    problem_index.json          { "ids": [...] }   ← maintained here
    000-100/1-A.json  ...

MongoDB (new DB):
  problems       — one doc per problem
  images         — binary image files
  problem_index  — single doc { ids: [...] }

Usage:
  python extract-dataset-v2.py            # compare + sync + parse remaining
  python extract-dataset-v2.py --compare  # compare only, no writes
  python extract-dataset-v2.py --limit 50 # parse at most 50 new problems
"""

import re
import sys
import json
import time
import argparse
import mimetypes
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup, Tag, NavigableString
from dotenv import load_dotenv

for _env in ['.env.local', '.env']:
    _p = Path(__file__).parent / _env
    if _p.exists():
        load_dotenv(_p)
        break

from lib.db import get_problems_collection, get_images_collection, get_index_collection
from lib.colors import green, yellow, cyan, red, success, error, info, warning

# ── Paths ─────────────────────────────────────────────────────────────────────

RAW_DIR        = Path(__file__).parent / 'RAW_HTML'
RAW_INDEX      = RAW_DIR / 'problem_index.json'
IMAGES_DIR     = RAW_DIR / 'images'
OUT_DIR        = Path(__file__).parent / 'saved-from-reparse'
LOCAL_INDEX    = OUT_DIR / 'problem_index.json'
OUT_DIR.mkdir(exist_ok=True)

# ── Index helpers ─────────────────────────────────────────────────────────────

def load_json_ids(path: Path) -> set[str]:
    if path.exists():
        try:
            return set(json.loads(path.read_text('utf-8')).get('ids', []))
        except Exception:
            pass
    return set()

def save_local_index(ids: set[str]) -> None:
    LOCAL_INDEX.write_text(
        json.dumps({'ids': sorted(ids)}, indent=2), 'utf-8'
    )

def load_db_ids() -> set[str]:
    doc = get_index_collection().find_one({})
    return set(doc.get('ids', [])) if doc else set()

def add_to_db_index(problem_key: str) -> None:
    get_index_collection().update_one(
        {}, {'$addToSet': {'ids': problem_key}}, upsert=True
    )

# ── HTML file finder ──────────────────────────────────────────────────────────

def find_html(problem_key: str) -> Path | None:
    direct = RAW_DIR / f'{problem_key}.html'
    if direct.exists():
        return direct
    parts = problem_key.split('-', 1)
    try:
        cid = int(parts[0])
    except ValueError:
        return None
    for sub in RAW_DIR.iterdir():
        if not sub.is_dir() or sub.name == 'images':
            continue
        c = sub / f'{problem_key}.html'
        if c.exists():
            return c
    return None

def out_path_for(problem_key: str, contest_id: int) -> Path:
    lo = (contest_id // 100) * 100
    hi = lo + 100
    folder = f'{lo:03d}-{hi}' if lo < 100 else f'{lo}-{hi}'
    d = OUT_DIR / folder
    d.mkdir(exist_ok=True)
    return d / f'{problem_key}.json'

# ── Pre text extraction — handles all three CF eras ──────────────────────────
#
#  Era 1 (000-1100ish): <pre>...<br/>...<br/>...</pre>
#  Era 2 (1100-1700ish): <pre>plain text with real \n</pre>
#  Era 3 (1700+): <pre><div class="test-example-line">...</div>...</pre>
#
def extract_pre_text(pre: Tag) -> str:
    # Era 3: test-example-line divs
    divs = pre.find_all(
        'div',
        class_=lambda c: c and 'test-example-line' in (c if isinstance(c, list) else c.split())
    )
    if divs:
        return '\n'.join(d.get_text() for d in divs).strip()

    # Era 1: <br> tags as line separators
    for br in pre.find_all('br'):
        br.replace_with('\n')

    # Era 2: plain text (or Era 1 after br-replacement)
    return pre.get_text(separator='').strip()

# ── Strip tags (preserving newlines) ─────────────────────────────────────────

def strip_tags(html_str: str) -> str:
    soup = BeautifulSoup(html_str, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    text = soup.get_text(separator='')
    lines = [' '.join(line.split()) for line in text.split('\n')]
    return '\n'.join(lines).strip()

# ── Math extraction ───────────────────────────────────────────────────────────

def extract_math_text(html_str: str) -> str:
    """
    Convert paragraph HTML to plain text with $...$ LaTeX markers.
    Handles both eras:
      - mathjax era: extracts LaTeX from <script type="math/tex"> tags
      - tex-span era: keeps the inner HTML (already formatted)
    """
    soup = BeautifulSoup(html_str, 'html.parser')

    # Mathjax era: replace script tags with $...$
    for script in soup.find_all('script', type=lambda t: t and 'math/tex' in t):
        latex = (script.string or '').strip()
        if 'display' in (script.get('type') or ''):
            script.replace_with(f' $${latex}$$ ')
        else:
            script.replace_with(f' ${latex}$ ')

    # Remove MathJax preview spans (duplicate of script content)
    for span in soup.find_all('span', class_='MathJax_Preview'):
        span.decompose()
    for span in soup.find_all('span', class_=lambda c: c and any(
        'MJXp' in x for x in (c if isinstance(c, list) else [c])
    )):
        span.decompose()

    text = soup.get_text(separator=' ')
    return ' '.join(text.split())

# ── Block walker ─────────────────────────────────────────────────────────────

def walk(node: Any) -> list[dict]:
    blocks: list[dict] = []

    if isinstance(node, (str, NavigableString)):
        t = str(node).strip()
        if t:
            blocks.append({'type': 'paragraph', 'html': t, 'text': t})
        return blocks

    if not isinstance(node, Tag):
        return blocks

    name = node.name

    if name == 'img':
        src = node.get('src', '')
        if isinstance(src, list): src = src[0] if src else ''
        if src:
            b: dict[str, Any] = {'type': 'image', 'src': str(src)}
            if node.get('alt'): b['alt'] = str(node.get('alt'))
            blocks.append(b)
        return blocks

    if name == 'pre':
        blocks.append({'type': 'code', 'code': strip_tags(str(node))})
        return blocks

    if name == 'table':
        blocks.append({'type': 'table', 'html': str(node)})
        return blocks

    if name in ('ul', 'ol'):
        items = [strip_tags(str(li)) for li in node.find_all('li', recursive=False)]
        blocks.append({'type': 'list', 'ordered': name == 'ol', 'items': items})
        return blocks

    if name == 'p':
        img = node.find('img')
        if img and len(list(node.children)) == 1:
            return walk(img)
        html_content = ''.join(str(c) for c in node.children).strip()
        if html_content:
            blocks.append({
                'type': 'paragraph',
                'html': html_content,
                'text': extract_math_text(html_content),
            })
        return blocks

    if name in ('div', 'section'):
        for child in node.children:
            blocks.extend(walk(child))
        return blocks

    if name == 'br':
        return blocks

    if name in ('span', 'a', 'strong', 'em', 'b', 'i', 'u', 'code', 'sub', 'sup'):
        html = str(node).strip()
        if html:
            blocks.append({
                'type': 'paragraph',
                'html': html,
                'text': extract_math_text(html),
            })
        return blocks

    for child in node.children:
        blocks.extend(walk(child))
    return blocks

# ── Example extraction ────────────────────────────────────────────────────────

def extract_examples(soup: BeautifulSoup) -> list[dict]:
    examples: list[dict] = []

    sample_tests = soup.find(
        'div',
        class_=lambda c: c and 'sample-tests' in (c if isinstance(c, list) else c.split())
    )
    if not sample_tests:
        return examples

    for sample in sample_tests.find_all(
        'div',
        class_=lambda c: c and 'sample-test' in (c if isinstance(c, list) else c.split())
    ):
        def get_io(side: str) -> str:
            div = sample.find(
                'div',
                class_=lambda c: c and side in (c if isinstance(c, list) else c.split())
            )
            if not div:
                return ''
            pre = div.find('pre')
            return extract_pre_text(pre) if pre else ''

        ex: dict[str, Any] = {
            'input':  get_io('input'),
            'output': get_io('output'),
        }

        # Per-example explanation (some problems have it inside sample-test)
        note = sample.find(
            'div',
            class_=lambda c: c and 'note' in (c if isinstance(c, list) else c.split())
        )
        if note:
            txt = strip_tags(str(note)).strip()
            if txt:
                ex['explanation'] = txt

        examples.append(ex)

    return examples

# ── Full page parser ──────────────────────────────────────────────────────────

def parse_page(html: str, problem_key: str) -> dict | None:
    soup = BeautifulSoup(html, 'html.parser')

    ps = soup.find(
        'div',
        class_=lambda c: c and 'problem-statement' in (c if isinstance(c, list) else c.split())
    )
    if not ps or not isinstance(ps, Tag):
        return None

    # ── Header ───────────────────────────────────────────────────────────────
    header = ps.find('div', class_='header')
    title = time_limit = memory_limit = ''
    input_mode = output_mode = 'stdio'

    if header and isinstance(header, Tag):
        t = header.find('div', class_=lambda c: c and 'title' in (c if isinstance(c, list) else c.split()))
        if t: title = strip_tags(str(t))

        tl = header.find('div', class_=lambda c: c and 'time-limit' in (c if isinstance(c, list) else c.split()))
        if tl: time_limit = strip_tags(str(tl)).replace('time limit per test', '').strip()

        ml = header.find('div', class_=lambda c: c and 'memory-limit' in (c if isinstance(c, list) else c.split()))
        if ml: memory_limit = strip_tags(str(ml)).replace('memory limit per test', '').strip()

        inp_f = header.find('div', class_=lambda c: c and 'input-file' in (c if isinstance(c, list) else c.split()))
        if inp_f:
            pt = inp_f.find('div', class_='property-title')
            if pt: pt.decompose()
            v = inp_f.get_text().strip()
            if v: input_mode = v

        out_f = header.find('div', class_=lambda c: c and 'output-file' in (c if isinstance(c, list) else c.split()))
        if out_f:
            pt = out_f.find('div', class_='property-title')
            if pt: pt.decompose()
            v = out_f.get_text().strip()
            if v: output_mode = v

    # ── Sections ─────────────────────────────────────────────────────────────
    sections: dict[str, list] = {'description': [], 'input': [], 'output': [], 'note': []}
    examples: list[dict] = []

    for child in ps.children:
        if not isinstance(child, Tag):
            continue
        classes = child.get('class', [])
        if not isinstance(classes, list):
            classes = str(classes).split()

        def sec_blocks(tag: Tag, skip_title: bool = True) -> list:
            blks = []
            for c in tag.children:
                if not isinstance(c, Tag): continue
                cc = c.get('class', [])
                if not isinstance(cc, list): cc = str(cc).split()
                if skip_title and 'section-title' in cc: continue
                blks.extend(walk(c))
            return blks

        if 'header' in classes:
            continue
        elif 'input-specification' in classes:
            sections['input'] = sec_blocks(child)
        elif 'output-specification' in classes:
            sections['output'] = sec_blocks(child)
        elif 'sample-tests' in classes or 'sample-test' in classes:
            examples = extract_examples(soup)
        elif 'note' in classes and 'sample-test' not in ' '.join(classes):
            sections['note'] = sec_blocks(child)
        else:
            sections['description'].extend(walk(child))

    # ── Detect flags ─────────────────────────────────────────────────────────
    full_text = ps.get_text(' ').lower()
    is_interactive = any(k in full_text for k in ['interactive', 'interactor', 'fflush', 'flush'])
    has_multiple_tc = bool(re.search(r't\s*test\s*cases?|for\s+each\s+test\s+case', full_text))

    result: dict[str, Any] = {
        'title':          title,
        'timeLimit':      time_limit,
        'memoryLimit':    memory_limit,
        'inputMode':      input_mode,
        'outputMode':     output_mode,
        'isInteractive':  is_interactive,
        'multipleTC':     has_multiple_tc,
        'description':    sections['description'],
        'input':          sections['input'],
        'output':         sections['output'],
        'examples':       examples,
    }
    if sections['note']:
        result['note'] = sections['note']

    return result

# ── Image upload ──────────────────────────────────────────────────────────────

def upload_images(problem_key: str, statement: dict, images_col) -> int:
    from bson.binary import Binary

    def collect(blocks: list) -> list[str]:
        return [
            b['src'].replace('cf-image://', '')
            for b in (blocks or [])
            if b.get('type') == 'image' and b.get('src', '').startswith('cf-image://')
        ]

    filenames: list[str] = []
    for sec in ['description', 'input', 'output', 'note']:
        filenames.extend(collect(statement.get(sec, [])))
    filenames = list(dict.fromkeys(filenames))

    uploaded = 0
    for fn in filenames:
        if images_col.find_one({'filename': fn}, {'_id': 1}):
            continue
        p = IMAGES_DIR / fn
        if not p.exists():
            continue
        try:
            ct = mimetypes.guess_type(fn)[0] or 'image/png'
            images_col.insert_one({
                'problemId':   problem_key,
                'filename':    fn,
                'contentType': ct,
                'data':        Binary(p.read_bytes()),
                'cachedAt':    int(time.time()),
            })
            uploaded += 1
        except Exception as e:
            print(warning(f'  [img] {fn}: {e}'))
    return uploaded

def rewrite_img_srcs(statement: dict, problem_key: str) -> None:
    """Replace raw CF image URLs with cf-image://filename using local files."""
    local: dict[str, str] = {}
    for img_path in IMAGES_DIR.glob(f'{problem_key}_*'):
        stem = img_path.stem[len(problem_key) + 1:]
        url_hash = stem.rsplit('_png', 1)[0] if '_png' in stem else stem
        local[url_hash] = img_path.name

    def rewrite(blocks: list) -> None:
        for b in (blocks or []):
            if b.get('type') == 'image':
                src = b.get('src', '')
                url_hash = Path(src.split('?')[0]).stem
                if url_hash in local:
                    b['src'] = f'cf-image://{local[url_hash]}'

    for sec in ['description', 'input', 'output', 'note']:
        rewrite(statement.get(sec, []))

# ── Extract one problem from HTML ─────────────────────────────────────────────

def extract_one(html_path: Path) -> dict | None:
    problem_key = html_path.stem
    parts = problem_key.split('-', 1)
    try:
        contest_id = int(parts[0])
    except ValueError:
        return None
    index = parts[1].upper()

    try:
        html = html_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    statement = parse_page(html, problem_key)
    if not statement:
        return None

    rewrite_img_srcs(statement, problem_key)

    return {
        'id':        problem_key,
        'contestId': contest_id,
        'index':     index,
        'version':   2,
        'cachedAt':  int(time.time()),
        'statement': statement,
    }

# ── DB upsert ─────────────────────────────────────────────────────────────────

def upsert_to_db(doc: dict, problems_col, images_col) -> int:
    contest_id  = doc['contestId']
    index       = doc['index']
    problem_key = doc['id']

    problems_col.update_one(
        {'contestId': contest_id, 'index': index},
        {'$set': doc},
        upsert=True
    )
    add_to_db_index(problem_key)
    return upload_images(problem_key, doc['statement'], images_col)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--compare', action='store_true', help='Compare indexes only, no writes')
    parser.add_argument('--limit',   type=int, default=0, help='Max new problems to parse (0=all)')
    args = parser.parse_args()

    problems_col = get_problems_collection()
    images_col   = get_images_collection()

    # ── Step 1: Load all three indexes ───────────────────────────────────────
    raw_ids   = load_json_ids(RAW_INDEX)
    local_ids = load_json_ids(LOCAL_INDEX)
    db_ids    = load_db_ids()

    print(cyan('=' * 58))
    print(cyan('  Index comparison'))
    print(cyan('=' * 58))
    print(info(f'  RAW_HTML (source) : {len(raw_ids):>6}'))
    print(info(f'  Local JSON        : {len(local_ids):>6}'))
    print(info(f'  MongoDB           : {len(db_ids):>6}'))

    missing_local = raw_ids - local_ids
    missing_db    = raw_ids - db_ids
    local_not_db  = local_ids - db_ids   # extracted locally but not yet in DB
    db_not_local  = db_ids - local_ids   # in DB but not locally (shouldn't happen)

    print()
    if missing_local:
        print(yellow(f'  Not in local JSON : {len(missing_local):>6}'))
    else:
        print(success(f'  Local JSON        : up to date ✓'))
    if missing_db:
        print(yellow(f'  Not in MongoDB    : {len(missing_db):>6}'))
    else:
        print(success(f'  MongoDB           : up to date ✓'))
    if local_not_db:
        print(yellow(f'  Local ahead of DB : {len(local_not_db):>6}  (will push to DB)'))
    if db_not_local:
        print(yellow(f'  DB ahead of local : {len(db_not_local):>6}  (will save locally)'))
    print(cyan('=' * 58))

    if args.compare:
        return

    # ── Step 2: Sync local-ahead-of-DB (push existing JSONs to DB) ───────────
    if local_not_db:
        print(info(f'\n[sync] Pushing {len(local_not_db)} local-only problems to MongoDB ...'))
        for i, pid in enumerate(sorted(local_not_db), 1):
            parts = pid.split('-', 1)
            try: cid = int(parts[0])
            except ValueError: continue
            jpath = out_path_for(pid, cid)
            if not jpath.exists():
                # JSON missing locally too — treat as missing, will be re-parsed
                local_ids.discard(pid)
                continue
            try:
                doc = json.loads(jpath.read_text('utf-8'))
                imgs = upsert_to_db(doc, problems_col, images_col)
                db_ids.add(pid)
                img_s = f' +{imgs}i' if imgs else ''
                print(success(f'  ({i}/{len(local_not_db)}) {pid} → db{img_s}'))
            except Exception as e:
                print(red(f'  ({i}/{len(local_not_db)}) {pid} → error: {e}'))

    # ── Step 3: Sync DB-ahead-of-local (save DB docs as JSON locally) ────────
    if db_not_local:
        print(info(f'\n[sync] Pulling {len(db_not_local)} DB-only problems to local JSON ...'))
        for i, pid in enumerate(sorted(db_not_local), 1):
            parts = pid.split('-', 1)
            try: cid = int(parts[0])
            except ValueError: continue
            doc = problems_col.find_one(
                {'contestId': cid, 'index': parts[1].upper()},
                {'_id': 0}
            )
            if not doc:
                continue
            jpath = out_path_for(pid, cid)
            jpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), 'utf-8')
            local_ids.add(pid)
            print(success(f'  ({i}/{len(db_not_local)}) {pid} → local'))
        save_local_index(local_ids)

    # ── Step 4: Parse remaining (in RAW but not in local+DB) ─────────────────
    # After sync, both local and DB should agree — use local as reference
    still_missing = raw_ids - local_ids
    if not still_missing:
        print(success('\nAll problems are already parsed. Nothing to do.'))
        return

    todo = sorted(still_missing)
    if args.limit > 0:
        todo = todo[:args.limit]

    print(info(f'\n[parse] {len(still_missing)} problems remaining. Parsing {len(todo)} ...'))

    done = failed = total_imgs = 0

    for i, pid in enumerate(todo, 1):
        parts = pid.split('-', 1)
        try: cid = int(parts[0])
        except ValueError: continue

        html_path = find_html(pid)
        if not html_path:
            print(yellow(f'  ({i}/{len(todo)}) {pid} → HTML not found, skip'))
            failed += 1
            continue

        print(cyan(f'  ({i}/{len(todo)}) {pid}'), end=' ', flush=True)

        doc = extract_one(html_path)
        if not doc:
            print(yellow('→ parse failed, skip'))
            failed += 1
            continue

        # Save JSON locally
        jpath = out_path_for(pid, cid)
        jpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), 'utf-8')

        # Update local index
        local_ids.add(pid)
        save_local_index(local_ids)

        # Upsert to DB + upload images
        try:
            imgs = upsert_to_db(doc, problems_col, images_col)
            db_ids.add(pid)
            total_imgs += imgs
            ex   = len(doc['statement'].get('examples', []))
            img_s = f' +{imgs}i' if imgs else ''
            print(success(f'→ ok ({ex} ex){img_s}'))
        except Exception as e:
            # JSON is saved locally — DB push failed, will be retried next run
            print(red(f'→ saved locally, DB error: {e}'))

        done += 1

    print()
    print(cyan('=' * 58))
    print(success('[done]'))
    print(info(f'  Parsed    : {done}'))
    print(info(f'  Failed    : {failed}'))
    print(info(f'  Images up : {total_imgs}'))


if __name__ == '__main__':
    main()
