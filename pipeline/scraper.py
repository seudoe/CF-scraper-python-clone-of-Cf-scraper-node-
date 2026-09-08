"""
pipeline/scraper.py
====================
Network + RAW_HTML disk layer. Owns:

  - fetching a problem page live from Codeforces (via lib.fetch, which
    already does the Selenium + Cloudflare-wait dance correctly)
  - saving it to RAW_HTML/<range>/<id>.html the moment it's fetched
  - keeping RAW_HTML/problem_index.json (ids + pdf-problem-ids) in sync,
    one id at a time, immediately -- never batched, so a crash mid-run
    never loses track of what's already on disk
  - downloading the images a parsed statement references, into
    RAW_HTML/images/, using the SAME filename scheme the old scraper used
    (so it lines up with the ~3k images already saved on disk)

No HTML parsing happens here -- that's pipeline/parser.py's job. This
module never touches MongoDB or saved-from-reparse either -- that's
pipeline.py's job.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

_PIPELINE_DIR = Path(__file__).parent.absolute()
_ROOT_DIR = _PIPELINE_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from lib.fetch import fetch_html, fetch_image_as_buffer, close_driver, reset_driver  # noqa: E402
# Re-exported: lib.fetch.fetch_html raises this exact class, so callers of
# fetch_and_save_raw() below need to be able to catch it from this module too.
from lib.parse import PdfProblemError  # noqa: E402
from lib.colors import yellow, warning, info  # noqa: E402

CF_BASE = 'https://codeforces.com'

RAW_DIR     = _ROOT_DIR / 'RAW_HTML'
IMAGES_DIR  = RAW_DIR / 'images'
INDEX_FILE  = RAW_DIR / 'problem_index.json'

__all__ = [
    'PdfProblemError', 'close_driver', 'reset_driver',
    'RAW_DIR', 'IMAGES_DIR', 'INDEX_FILE',
    'range_dir', 'html_path_for', 'find_html',
    'load_raw_index', 'save_raw_index', 'add_raw_id', 'mark_pdf',
    'fetch_and_save_raw', 'download_images',
]

# ── RAW_HTML range-folder layout: <lo>-<hi>/<contestId>-<index>.html ────────

def range_dir(contest_id: int) -> Path:
    lo = (contest_id // 100) * 100
    hi = lo + 100
    name = f'{lo:03d}-{hi}' if lo < 100 else f'{lo}-{hi}'
    d = RAW_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def html_path_for(problem_key: str, contest_id: int) -> Path:
    return range_dir(contest_id) / f'{problem_key}.html'


def find_html(problem_key: str, contest_id: int | None = None) -> Path | None:
    """Locate an already-saved raw HTML file for problem_key, if any."""
    if contest_id is None:
        try:
            contest_id = int(problem_key.split('-', 1)[0])
        except ValueError:
            return None

    direct = html_path_for(problem_key, contest_id)
    if direct.exists():
        return direct

    # Legacy flat file at RAW_HTML root (the old scraper saved here)
    flat = RAW_DIR / f'{problem_key}.html'
    if flat.exists():
        return flat

    # Fallback: full scan, in case the id landed in an unexpected range folder
    for sub in RAW_DIR.iterdir():
        if not sub.is_dir() or sub.name == 'images':
            continue
        candidate = sub / f'{problem_key}.html'
        if candidate.exists():
            return candidate

    return None

# ── RAW_HTML/problem_index.json ──────────────────────────────────────────────

def load_raw_index() -> dict:
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
            data.setdefault('ids', [])
            data.setdefault('pdf-problem-ids', [])
            return data
        except Exception:
            pass
    return {'ids': [], 'pdf-problem-ids': []}


def save_raw_index(ids: set[str], pdf_ids: set[str]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps({'ids': sorted(ids), 'pdf-problem-ids': sorted(pdf_ids)}, indent=2),
        encoding='utf-8',
    )


def add_raw_id(problem_key: str) -> None:
    """Load-modify-save a single id. Called right after every successful
    HTML save so the index is never more than one problem behind disk."""
    idx = load_raw_index()
    ids = set(idx['ids'])
    if problem_key not in ids:
        ids.add(problem_key)
        save_raw_index(ids, set(idx['pdf-problem-ids']))


def mark_pdf(problem_key: str) -> None:
    idx = load_raw_index()
    pdf_ids = set(idx['pdf-problem-ids'])
    if problem_key not in pdf_ids:
        pdf_ids.add(problem_key)
        save_raw_index(set(idx['ids']), pdf_ids)

# ── Live fetch ────────────────────────────────────────────────────────────────

def fetch_and_save_raw(contest_id: int, index: str) -> str:
    """
    Fetch a problem page live from Codeforces and save it to RAW_HTML
    immediately (before any parsing is attempted). Updates the RAW_HTML
    index right away too, so the raw file is durable the instant this
    returns.

    Raises PdfProblemError if the problem statement is a PDF (caller
    should call mark_pdf() and move on -- not a failure).
    """
    problem_key = f'{contest_id}-{index}'
    url = f'{CF_BASE}/problemset/problem/{contest_id}/{index}'

    html = fetch_html(url)  # raises PdfProblemError / Exception on failure

    save_path = html_path_for(problem_key, contest_id)
    save_path.write_text(html, encoding='utf-8')
    add_raw_id(problem_key)

    size_kb = len(html) / 1024
    print(info(f'[scraper] Saved RAW_HTML: {save_path.relative_to(RAW_DIR)} ({size_kb:.1f} KB)'))

    return html

# ── Images ────────────────────────────────────────────────────────────────────

def _absolute_url(src: str) -> str:
    return src if src.startswith('http') else urljoin(CF_BASE, src)


def _make_filename(src: str, problem_key: str) -> str:
    """Same scheme the original scraper used - keeps new downloads
    consistent with the ~3k images already saved to disk."""
    url = _absolute_url(src)
    path = urlparse(url).path

    ext = '.png'
    if '.' in path:
        parts = path.rsplit('.', 1)
        if len(parts) == 2:
            ext = '.' + parts[1]

    base = path.split('/')[-1].replace('.', '_').replace('-', '_')
    if not base:
        base = 'img'
    if base.endswith(ext):
        base = base[:-len(ext)]

    return f'{problem_key}_{base}{ext}'


def download_images(urls: list[str], problem_key: str) -> dict[str, str]:
    """
    Download every image URL a statement references, into RAW_HTML/images/.
    Returns {original_src: local_filename} for parser.rewrite_image_srcs().
    Already-downloaded files are skipped (checked by filename, not re-fetched).
    A single image failing to download is logged and skipped -- it does not
    abort the whole problem; the block just keeps its original CF URL.
    """
    result: dict[str, str] = {}
    if not urls:
        return result

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    for src in urls:
        filename = _make_filename(src, problem_key)
        img_path = IMAGES_DIR / filename

        if not img_path.exists():
            try:
                print(yellow(f'[scraper] Downloading image: {filename}'))
                data = fetch_image_as_buffer(_absolute_url(src))
                img_path.write_bytes(data['buffer'])
            except Exception as e:
                print(warning(f'[scraper] Image download failed, leaving original URL: {src} - {e}'))
                continue

        result[src] = filename

    return result
