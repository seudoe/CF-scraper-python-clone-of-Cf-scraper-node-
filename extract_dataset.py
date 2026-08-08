"""
extract_dataset.py
===================
Extracts a rich dataset from local RAW HTML files and saves one JSON per
problem into  saved-from-reparse/<contestId>-<index>.json

Covers everything in save-from-reparsing.md:

  1.  CF HTML formatting tags catalogue  (the undocumented map)
  2.  Math / LaTeX metrics
  3.  Problem structure flags
  4.  Constraints parsed from text
  5.  Algorithmic keyword presence
  6.  Statement length / readability metrics
  7.  Examples analysis
  8.  Input / output mode (stdin/file)
  9.  Fixed examples (newlines preserved)
  10. tex-font-style-* tag inventory

Output schema (saved-from-reparse/<id>.json):
{
  "id":            "1-A",
  "contestId":     1,
  "index":         "A",
  "title":         "Theatre Square",
  "timeLimit":     "1 second",
  "memoryLimit":   "256 megabytes",
  "inputMode":     "stdin" | "<filename>",
  "outputMode":    "stdout" | "<filename>",

  -- Fixed examples (newlines preserved) --
  "examples": [
    { "input": "...", "output": "...", "explanation": "..." }
  ],

  -- Math metrics --
  "math": {
    "inlineCount":    12,
    "displayCount":   3,
    "imageFormulas":  0,       // old-style img instead of MathJax
    "texSpanCount":   5,       // legacy <span class="tex-span">
    "latexCommands":  {        // which \\commands appear and how many times
      "\\sum": 2,
      "\\frac": 1,
      ...
    },
    "formulaComplexityScore": 14,   // weighted sum: display*3 + image*2 + inline*1
    "allLatex": ["n^2", "\\sum_{i=1}^n a_i", ...]   // every unique LaTeX string
  },

  -- CF formatting tag catalogue (THE undocumented map) --
  "cfTags": {
    "tex-font-style-bf":  3,    // bold
    "tex-font-style-it":  7,    // italic
    "tex-font-style-tt":  2,    // monospace / code variable
    "tex-font-style-sl":  0,    // slanted
    "tex-font-style-sc":  0,    // small caps
    "tex-span":           5,    // legacy inline math wrapper (pre-MathJax)
    "upper-index":        2,    // superscript
    "lower-index":        1,    // subscript
    "tex-math":           0     // math block wrapper
  },

  -- Structure flags --
  "structure": {
    "hasNote":          true,
    "isInteractive":    false,
    "hasSubtasks":      false,
    "hasMultipleTests": true,     // "t test cases" pattern in input spec
    "imageCount":       0,        // <img> tags in statement
    "sectionCount": {
      "description": 4,           // block count per section
      "input":       2,
      "output":      1,
      "note":        3
    },
    "exampleCount":     2
  },

  -- Constraints --
  "constraints": [
    { "variable": "n", "operator": "<=", "value": 100000, "raw": "n ≤ 10^5" },
    { "variable": "m", "operator": "<=", "value": 1000,   "raw": "m ≤ 1000" }
  ],

  -- Algorithmic keywords (presence in full statement text) --
  "keywords": {
    "greedy":         false,
    "dp":             false,
    "dynamic":        false,
    "binary search":  false,
    "graph":          false,
    "tree":           false,
    "dfs":            false,
    "bfs":            false,
    "modulo":         false,
    "flow":           false,
    "geometry":       false,
    "probability":    false,
    "prime":          false,
    "matrix":         false,
    "sort":           true,
    "construct":      false,
    "permutation":    false,
    "prefix":         false,
    "suffix":         false,
    "segment tree":   false,
    "fenwick":        false,
    "bitset":         false,
    "two pointers":   false,
    "sliding window": false,
    "number theory":  false,
    "interactive":    false
  },

  -- Length / readability --
  "readability": {
    "statementWordCount":    210,
    "statementCharCount":    1340,
    "noteWordCount":         88,
    "mathDensity":           0.12,   // math chars / total chars
    "uniqueWordCount":       134
  }
}

Usage:
    python extract_dataset.py                    # process all HTML files
    python extract_dataset.py --limit 100        # first 100
    python extract_dataset.py --id 1-A           # single problem
    python extract_dataset.py --overwrite        # re-extract even if JSON exists
"""

import re
import sys
import json
import argparse
import math as pymath
from pathlib import Path
from typing import Any
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from bs4 import BeautifulSoup, Tag, NavigableString
from lib.colors import green, yellow, cyan, red, success, error, info, warning

# ── Paths ─────────────────────────────────────────────────────────────────────
RAW_DIR    = Path(__file__).parent / 'RAW_HTML'
OUTPUT_DIR = Path(__file__).parent / 'saved-from-reparse'

# Range boundaries that match RAW_HTML subfolder names (000-100, 100-200, ...)
# Used to mirror the same subfolder structure in saved-from-reparse/
RANGE_STEP = 100

def get_output_subdir(contest_id: int) -> Path:
    """Returns the matching subfolder e.g. contest 1234 → saved-from-reparse/1200-1300/"""
    lo = (contest_id // RANGE_STEP) * RANGE_STEP
    hi = lo + RANGE_STEP
    folder_name = f'{lo:03d}-{hi}' if lo < 100 else f'{lo}-{hi}'
    subdir = OUTPUT_DIR / folder_name
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir

# ── Algorithmic keywords to detect ───────────────────────────────────────────
ALGO_KEYWORDS = [
    'greedy', 'dp', 'dynamic programming', 'binary search', 'graph', 'tree',
    'dfs', 'bfs', 'modulo', 'flow', 'geometry', 'probability', 'prime',
    'matrix', 'sort', 'construct', 'permutation', 'prefix', 'suffix',
    'segment tree', 'fenwick', 'bitset', 'two pointers', 'sliding window',
    'number theory', 'interactive',
]

# LaTeX commands to track frequency
LATEX_CMDS = [
    r'\sum', r'\int', r'\frac', r'\sqrt', r'\prod', r'\lim',
    r'\min', r'\max', r'\binom', r'\left', r'\right', r'\cdot',
    r'\times', r'\leq', r'\geq', r'\neq', r'\infty', r'\log',
    r'\lceil', r'\lfloor', r'\rceil', r'\rfloor', r'\pmod',
    r'\mod', r'\oplus', r'\cup', r'\cap', r'\forall', r'\exists',
    r'\substack', r'\text', r'\mathbb', r'\mathcal', r'\operatorname',
    r'\begin', r'\end', r'\vec', r'\overline', r'\underline',
]

# CF formatting tag class names → human description
CF_TAG_CLASSES = {
    'tex-font-style-bf': 'bold',
    'tex-font-style-it': 'italic',
    'tex-font-style-tt': 'monospace/code variable',
    'tex-font-style-sl': 'slanted',
    'tex-font-style-sc': 'small caps',
    'tex-span':          'legacy inline math wrapper (pre-MathJax)',
    'upper-index':       'superscript',
    'lower-index':       'subscript',
    'tex-math':          'math block wrapper',
}

# ── HTML file discovery ───────────────────────────────────────────────────────

def iter_html_files(limit: int = 0, single_id: str = '', missing_ids: set[str] | None = None) -> list[Path]:
    files: list[Path] = []

    if single_id:
        # Check root-level and all subdirs
        direct = RAW_DIR / f'{single_id}.html'
        if direct.exists():
            return [direct]
        for sub in RAW_DIR.iterdir():
            if sub.is_dir() and sub.name != 'images':
                candidate = sub / f'{single_id}.html'
                if candidate.exists():
                    return [candidate]
        print(red(f'[extract] HTML not found for {single_id}'))
        return []

    # All files: root level + subdirectories
    files.extend(RAW_DIR.glob('*.html'))
    for sub in sorted(RAW_DIR.iterdir()):
        if sub.is_dir() and sub.name != 'images':
            files.extend(sorted(sub.glob('*.html')))

    # Deduplicate (root files may be re-saved versions of older ones)
    seen: set[str] = set()
    unique: list[Path] = []
    for f in files:
        key = f.stem
        if key not in seen:
            seen.add(key)
            unique.append(f)

    # Filter to only missing IDs if provided
    if missing_ids is not None:
        unique = [f for f in unique if f.stem in missing_ids]

    if limit > 0:
        unique = unique[:limit]
    return unique

# ── strip_tags (preserving newlines) ─────────────────────────────────────────

def strip_tags(html_str: str) -> str:
    soup = BeautifulSoup(html_str, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    text = soup.get_text(separator='')
    lines = [' '.join(line.split()) for line in text.split('\n')]
    return '\n'.join(lines).strip()

# ── Example extraction (newlines preserved) ───────────────────────────────────

def extract_examples(soup: BeautifulSoup) -> list[dict]:
    examples = []
    sample_div = soup.find('div', class_=lambda c: c and 'sample-tests' in (c if isinstance(c, list) else c.split()))
    if not sample_div:
        return examples

    for sample in sample_div.find_all('div', class_=lambda c: c and 'sample-test' in (c if isinstance(c, list) else c.split())):
        inp = ''
        out = ''
        input_div = sample.find('div', class_=lambda c: c and 'input' in (c if isinstance(c, list) else c.split()))
        if input_div:
            pre = input_div.find('pre')
            if pre:
                inp = _extract_pre_text(pre)

        output_div = sample.find('div', class_=lambda c: c and 'output' in (c if isinstance(c, list) else c.split()))
        if output_div:
            pre = output_div.find('pre')
            if pre:
                out = _extract_pre_text(pre)

        ex: dict[str, Any] = {'input': inp, 'output': out}
        note_div = sample.find('div', class_=lambda c: c and 'note' in (c if isinstance(c, list) else c.split()))
        if note_div:
            note_text = strip_tags(str(note_div)).strip()
            if note_text:
                ex['explanation'] = note_text
        examples.append(ex)
    return examples

# ── Math extraction ───────────────────────────────────────────────────────────

def extract_math_metrics(ps_div: Tag) -> dict:
    # ── New era (contest ~1100+): <script type="math/tex"> ──────────────────
    inline_scripts  = ps_div.find_all('script', type='math/tex')
    display_scripts = ps_div.find_all('script', attrs={'type': re.compile(r'math/tex.*display')})

    # ── Old era (contest ~000–1099): <span class="tex-span"> ────────────────
    # Inner content is RENDERED HTML (e.g. <i>n</i>, 10<sup>5</sup>),
    # NOT raw LaTeX — so we store it separately, not mixed with allLatex.
    tex_spans = ps_div.find_all('span', class_='tex-span')

    # Old-era formula images (src contains "latex" or "formula")
    img_formulas = [
        img for img in ps_div.find_all('img')
        if 'latex' in str(img.get('src', '')).lower()
        or 'formula' in str(img.get('class', '')).lower()
    ]

    # ── Collect raw LaTeX strings (MathJax era only) ─────────────────────────
    all_latex: list[str] = []
    for sc in inline_scripts:
        latex = (sc.string or '').strip()
        if latex:
            all_latex.append(latex)
    for sc in display_scripts:
        latex = (sc.string or '').strip()
        if latex:
            all_latex.append(latex)

    # ── tex-span rendered text (old era) — stored as separate field ──────────
    tex_span_rendered: list[str] = []
    for ts in tex_spans:
        text = ts.get_text().strip()
        if text:
            tex_span_rendered.append(text)

    # Count LaTeX command frequencies (MathJax era only — tex-span has no \cmds)
    combined = ' '.join(all_latex)
    cmd_counts: dict[str, int] = {}
    for cmd in LATEX_CMDS:
        count = combined.count(cmd)
        if count > 0:
            cmd_counts[cmd] = count

    inline_count   = len(inline_scripts)
    display_count  = len(display_scripts)
    img_count      = len(img_formulas)
    tex_span_count = len(tex_spans)

    complexity_score = display_count * 3 + img_count * 2 + inline_count * 1 + tex_span_count * 1

    # Determine which era this problem belongs to
    if inline_count + display_count > 0:
        math_era = 'mathjax'
    elif tex_span_count > 0:
        math_era = 'tex-span'
    elif img_count > 0:
        math_era = 'image'
    else:
        math_era = 'none'

    return {
        'era':                   math_era,          # 'mathjax' | 'tex-span' | 'image' | 'none'
        'inlineCount':           inline_count,
        'displayCount':          display_count,
        'imageFormulas':         img_count,
        'texSpanCount':          tex_span_count,
        'texSpanRendered':       tex_span_rendered,  # old-era: rendered HTML text, NOT LaTeX
        'latexCommands':         cmd_counts,          # mathjax-era only
        'formulaComplexityScore': complexity_score,
        'allLatex':              list(dict.fromkeys(all_latex)),  # mathjax-era raw LaTeX strings
    }

# ── CF tag catalogue ──────────────────────────────────────────────────────────

def extract_cf_tags(ps_div: Tag) -> dict:
    counts: dict[str, int] = {}
    for cls_name in CF_TAG_CLASSES:
        found = ps_div.find_all(class_=lambda c, cn=cls_name: c and (cn in (c if isinstance(c, list) else c.split())))
        counts[cls_name] = len(found)
    return counts

# ── Structure flags ───────────────────────────────────────────────────────────

def extract_structure(soup: BeautifulSoup, ps_div: Tag, examples: list) -> dict:
    full_text = ps_div.get_text(' ').lower()

    has_note = bool(ps_div.find('div', class_=lambda c: c and 'note' in (c if isinstance(c, list) else c.split()) and 'sample-test' not in ' '.join(c if isinstance(c, list) else c.split())))

    is_interactive = any(kw in full_text for kw in [
        'interactive', 'interactor', 'flush', 'fflush', 'special judge'
    ])

    has_subtasks = 'subtask' in full_text

    # "t test cases" pattern — implies multiple test cases per run
    has_multiple_tests = bool(re.search(
        r'(first line.*contains.*\bt\b|t\s*test\s*cases|for\s+each\s+test\s*case)',
        full_text
    ))

    # Image count (non-formula images in problem body)
    image_count = len(ps_div.find_all('img'))

    # Block counts per section
    def count_blocks(section_class: str) -> int:
        sec = ps_div.find('div', class_=lambda c: c and section_class in (c if isinstance(c, list) else c.split()))
        if not sec:
            return 0
        return len(sec.find_all(['p', 'pre', 'ul', 'ol', 'table', 'img']))

    return {
        'hasNote':          has_note,
        'isInteractive':    is_interactive,
        'hasSubtasks':      has_subtasks,
        'hasMultipleTests': has_multiple_tests,
        'imageCount':       image_count,
        'sectionCount': {
            'description': len(list(ps_div.children)),  # rough approximation
            'input':       count_blocks('input-specification'),
            'output':      count_blocks('output-specification'),
            'note':        count_blocks('note'),
        },
        'exampleCount': len(examples),
    }

# ── Constraint extraction ─────────────────────────────────────────────────────

CONSTRAINT_PATTERN = re.compile(
    r'([a-zA-Z][a-zA-Z0-9_]*)\s*'
    r'(≤|≥|<|>|=|\\leq|\\geq|\\lt|\\gt|\\le|\\ge)\s*'
    r'([\d\^\{\}eE\+\*\·]+)',
    re.UNICODE
)
OP_MAP = {
    '≤': '<=', '\\leq': '<=', '\\le': '<=',
    '≥': '>=', '\\geq': '>=', '\\ge': '>=',
    '<':  '<', '\\lt':  '<',
    '>':  '>', '\\gt':  '>',
    '=':  '=',
}

def parse_value(raw: str) -> int | str | None:
    """
    Convert '10^5', '100000', '1e6', '10^{9}+7' etc. to int.
    Returns None if unparseable, or a string if the number is too large
    for BSON/JSON (> 10^18) — avoids crashing on display-math false positives.
    """
    raw = raw.replace('{', '').replace('}', '').strip()
    # 10^N style
    m = re.match(r'^(\d+)\^(\d+)$', raw)
    if m:
        base, exp = int(m.group(1)), int(m.group(2))
        # Anything beyond 10^18 is not a real constraint value — store as string
        if exp > 18:
            return f'{m.group(1)}^{m.group(2)}'
        return base ** exp
    # plain int
    if re.match(r'^\d+$', raw):
        val = int(raw)
        # BSON max signed 64-bit int is 2^63-1 ≈ 9.2 × 10^18
        if val > 9_223_372_036_854_775_807:
            return str(val)
        return val
    # scientific 1e6
    m = re.match(r'^(\d+)[eE](\d+)$', raw)
    if m:
        exp = int(m.group(2))
        if exp > 18:
            return f'{m.group(1)}e{m.group(2)}'
        return int(float(raw))
    return None

def extract_constraints(ps_div: Tag) -> list[dict]:
    # Get plain text from the whole statement (math scripts give raw LaTeX)
    text_parts: list[str] = []
    for sc in ps_div.find_all('script', type=re.compile(r'math/tex')):
        if sc.string:
            text_parts.append(sc.string)
    # Also plain text
    text_parts.append(ps_div.get_text(' '))
    combined = ' '.join(text_parts)

    seen: set[str] = set()
    constraints: list[dict] = []
    for m in CONSTRAINT_PATTERN.finditer(combined):
        var, op_raw, val_raw = m.group(1), m.group(2), m.group(3)
        op = OP_MAP.get(op_raw, op_raw)
        val = parse_value(val_raw)
        key = f'{var}{op}{val_raw}'
        if key not in seen:
            seen.add(key)
            entry: dict[str, Any] = {
                'variable': var,
                'operator': op,
                'raw':      m.group(0).strip(),
            }
            if val is not None:
                entry['value'] = val
            constraints.append(entry)
    return constraints

# ── Keyword detection ─────────────────────────────────────────────────────────

def extract_keywords(ps_div: Tag) -> dict:
    text = ps_div.get_text(' ').lower()
    return {kw: (kw in text) for kw in ALGO_KEYWORDS}

# ── Readability metrics ───────────────────────────────────────────────────────

def extract_readability(ps_div: Tag, math_metrics: dict) -> dict:
    # Get pure text (no math scripts)
    plain = ps_div.get_text(' ')
    # Remove script content
    for sc in ps_div.find_all('script'):
        sc.extract()
    plain_no_math = ps_div.get_text(' ')

    words = plain_no_math.split()
    chars = len(plain_no_math.replace(' ', ''))
    unique_words = len(set(w.lower().strip('.,;:()[]{}') for w in words if len(w) > 1))

    # Math density: count LaTeX chars vs total
    latex_chars = sum(len(s) for s in math_metrics.get('allLatex', []))
    math_density = round(latex_chars / max(chars + latex_chars, 1), 4)

    # Note section word count
    note_div = ps_div.find('div', class_=lambda c: c and 'note' in (c if isinstance(c, list) else c.split()) and 'sample' not in ' '.join(c if isinstance(c, list) else c.split()))
    note_words = 0
    if note_div:
        note_words = len(note_div.get_text(' ').split())

    return {
        'statementWordCount': len(words),
        'statementCharCount': chars,
        'noteWordCount':      note_words,
        'mathDensity':        math_density,
        'uniqueWordCount':    unique_words,
    }

# ── Header metadata ───────────────────────────────────────────────────────────

def extract_header(ps_div: Tag) -> dict:
    header = ps_div.find('div', class_='header')
    if not header:
        return {}

    def get_text_after_title(class_name: str) -> str:
        div = header.find('div', class_=class_name)
        if not div:
            return ''
        # Remove the property-title child text
        title_div = div.find('div', class_='property-title')
        if title_div:
            title_div.extract()
        return div.get_text().strip()

    title_div = header.find('div', class_='title')
    title = title_div.get_text().strip() if title_div else ''

    time_limit   = get_text_after_title('time-limit')
    memory_limit = get_text_after_title('memory-limit')

    input_div  = header.find('div', class_=lambda c: c and 'input-file' in (c if isinstance(c, list) else c.split()))
    output_div = header.find('div', class_=lambda c: c and 'output-file' in (c if isinstance(c, list) else c.split()))

    def io_mode(div: Tag | None) -> str:
        if not div:
            return 'stdin'
        prop = div.find('div', class_='property-title')
        if prop:
            prop.extract()
        return div.get_text().strip() or 'stdin'

    return {
        'title':       title,
        'timeLimit':   time_limit,
        'memoryLimit': memory_limit,
        'inputMode':   io_mode(input_div),
        'outputMode':  io_mode(output_div),
    }

# ── Main extraction ───────────────────────────────────────────────────────────

def extract_one(html_path: Path) -> dict | None:
    problem_key = html_path.stem
    parts = problem_key.split('-', 1)
    if len(parts) != 2:
        return None
    try:
        contest_id = int(parts[0])
    except ValueError:
        return None
    index = parts[1].upper()

    try:
        html = html_path.read_text(encoding='utf-8')
    except Exception as e:
        print(red(f'  [!] Could not read {html_path}: {e}'))
        return None

    soup = BeautifulSoup(html, 'html.parser')

    ps_div = soup.find('div', class_=lambda c: c and 'problem-statement' in (c if isinstance(c, list) else c.split()))
    if not ps_div or not isinstance(ps_div, Tag):
        return None

    header_data = extract_header(ps_div)
    examples    = extract_examples(soup)
    math_data   = extract_math_metrics(ps_div)
    cf_tags     = extract_cf_tags(ps_div)
    structure   = extract_structure(soup, ps_div, examples)
    constraints = extract_constraints(ps_div)
    keywords    = extract_keywords(ps_div)
    readability = extract_readability(ps_div, math_data)

    # Save the parsed statement blocks so extension can read from disk
    # instead of always hitting MongoDB
    from lib.parse import parse_problem_page
    statement = parse_problem_page(html, problem_key)

    # Rewrite image src URLs to cf-image://filename using locally saved files
    if statement:
        statement = rewrite_image_srcs(statement, problem_key)

    return {
        'id':          problem_key,
        'contestId':   contest_id,
        'index':       index,
        'title':       header_data.get('title', ''),
        'timeLimit':   header_data.get('timeLimit', ''),
        'memoryLimit': header_data.get('memoryLimit', ''),
        'inputMode':   header_data.get('inputMode', 'stdin'),
        'outputMode':  header_data.get('outputMode', 'stdout'),
        # Full parsed statement (description/input/output/note blocks + fixed examples)
        'statement':   statement,
        # Dataset fields
        'math':        math_data,
        'cfTags':      cf_tags,
        'structure':   structure,
        'constraints': constraints,
        'keywords':    keywords,
        'readability': readability,
    }

# ── Entry point ───────────────────────────────────────────────────────────────

# ── DB patch helpers ─────────────────────────────────────────────────────────

# ── Image upload from disk ────────────────────────────────────────────────────

IMAGES_DIR = RAW_DIR / 'images'

def _guess_content_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        '.png':  'image/png',
        '.jpg':  'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif':  'image/gif',
        '.svg':  'image/svg+xml',
        '.webp': 'image/webp',
    }.get(ext, 'image/png')


def rewrite_image_srcs(statement: dict, problem_key: str) -> dict:
    """
    After parse_problem_page(), image blocks have raw CF URLs as src.
    This rewrites them to cf-image://filename using the locally saved files
    in RAW_HTML/images/ that match the problem_key prefix.

    Matching: local files are named  {problem_key}_{hash}_png.png
    We match the URL hash against the filename hash segment.
    """
    if not statement:
        return statement

    # Build map: url_hash → local_filename
    local_imgs: dict[str, str] = {}
    for img_path in IMAGES_DIR.glob(f'{problem_key}_*.png'):
        # filename: 1000-C_b3d344391aaf...png.png
        # extract the hash part (between first _ and _png.png)
        stem = img_path.stem  # e.g. 1000-C_b3d344...png
        # Remove problem_key prefix
        rest = stem[len(problem_key) + 1:]  # b3d344...png
        # The hash is everything up to the last _png
        if '_png' in rest:
            url_hash = rest.rsplit('_png', 1)[0]
        else:
            url_hash = rest
        local_imgs[url_hash] = img_path.name

    def rewrite_blocks(blocks: list) -> list:
        for block in (blocks or []):
            if block.get('type') == 'image':
                src = block.get('src', '')
                # Extract hash from CF URL: https://espresso.codeforces.com/{hash}.png
                url_hash = Path(src.split('?')[0]).stem  # removes query params + extension
                if url_hash in local_imgs:
                    block['src'] = f'cf-image://{local_imgs[url_hash]}'
                # else: keep original URL (will be fetched live by renderer)
        return blocks

    for section in ['description', 'input', 'output', 'note']:
        if section in statement:
            statement[section] = rewrite_blocks(statement[section])

    return statement

def upload_images_for_problem(problem_key: str, statement: dict, images_col) -> int:
    """
    Find every image block in the statement, read from RAW_HTML/images/,
    and upsert into the images collection.
    Returns number of images uploaded.
    """
    from bson.binary import Binary

    def collect_image_blocks(blocks: list) -> list[str]:
        """Return list of filenames from cf-image:// src values."""
        filenames = []
        for b in (blocks or []):
            if b.get('type') == 'image':
                src = b.get('src', '')
                if src.startswith('cf-image://'):
                    filenames.append(src.replace('cf-image://', ''))
        return filenames

    filenames: list[str] = []
    if statement:
        for section in ['description', 'input', 'output', 'note']:
            filenames.extend(collect_image_blocks(statement.get(section, [])))
        # deduplicate
        filenames = list(dict.fromkeys(filenames))

    uploaded = 0
    for filename in filenames:
        # Skip if already in DB
        if images_col.find_one({'filename': filename}, {'_id': 1}):
            continue

        img_path = IMAGES_DIR / filename
        if not img_path.exists():
            print(yellow(f'    [img] Missing on disk: {filename}'))
            continue

        try:
            data = img_path.read_bytes()
            content_type = _guess_content_type(filename)
            import time as _time
            images_col.insert_one({
                'problemId':   problem_key,
                'filename':    filename,
                'contentType': content_type,
                'data':        Binary(data),
                'cachedAt':    int(_time.time()),
            })
            uploaded += 1
        except Exception as e:
            print(yellow(f'    [img] Upload failed {filename}: {e}'))

    return uploaded


# ── DB insert/patch helpers ───────────────────────────────────────────────────

def insert_or_patch_db(json_path: Path, problems_col, images_col, index_col,
                        full_insert: bool) -> tuple[str, int]:
    """
    full_insert=True  → upsert the whole document (for new DB)
    full_insert=False → update only renderer-relevant fields (for existing DB)

    Returns (status, images_uploaded).
    status: 'inserted' | 'patched' | 'not_found' | 'error:<msg>'
    """
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception as e:
        return f'error:read:{e}', 0

    contest_id = data.get('contestId')
    index      = data.get('index', '').upper()
    problem_key = data.get('id', f'{contest_id}-{index}')

    if not contest_id or not index:
        return 'error:missing_id', 0

    statement = data.get('statement')

    # ── Upload images first ───────────────────────────────────────────────────
    imgs_uploaded = 0
    if statement and images_col is not None:
        imgs_uploaded = upload_images_for_problem(problem_key, statement, images_col)

    # ── Build the document to write ───────────────────────────────────────────
    if full_insert:
        # Complete document for new DB — matches CachedProblem schema
        # that the extension expects, plus the new dataset fields
        doc = {
            'contestId':   contest_id,
            'index':       index,
            'cachedAt':    int(__import__('time').time()),
            'version':     2,            # v2 = re-parsed with fixed parser
            'inputMode':   data.get('inputMode', 'stdin'),
            'outputMode':  data.get('outputMode', 'stdout'),
            'structure':   data.get('structure', {}),
            'constraints': data.get('constraints', []),
            'math':        data.get('math', {}),
            'cfTags':      data.get('cfTags', {}),
        }
        if statement:
            doc['statement'] = statement
        else:
            # No statement available — skip
            return 'error:no_statement', 0

        problems_col.update_one(
            {'contestId': contest_id, 'index': index},
            {'$set': doc},
            upsert=True
        )

        # Update problem_index
        if index_col is not None:
            index_col.update_one(
                {},
                {'$addToSet': {'ids': problem_key}},
                upsert=True
            )

        return 'inserted', imgs_uploaded

    else:
        # Patch mode — only update renderer-relevant fields on existing doc
        update: dict = {
            'inputMode':   data.get('inputMode', 'stdin'),
            'outputMode':  data.get('outputMode', 'stdout'),
            'structure':   data.get('structure', {}),
            'constraints': data.get('constraints', []),
            'math':        data.get('math', {}),
            'cfTags':      data.get('cfTags', {}),
        }
        if statement:
            update['statement'] = statement

        result = problems_col.update_one(
            {'contestId': contest_id, 'index': index},
            {'$set': update}
        )
        if result.matched_count == 0:
            return 'not_found', 0
        return 'patched', imgs_uploaded


# ── Entry point ───────────────────────────────────────────────────────────────

# ── Local problem index ───────────────────────────────────────────────────────

LOCAL_INDEX_FILE = OUTPUT_DIR / 'problem_index.json'

def _load_local_index() -> set[str]:
    """Load the local problem_index.json, return set of ids."""
    if LOCAL_INDEX_FILE.exists():
        try:
            data = json.loads(LOCAL_INDEX_FILE.read_text(encoding='utf-8'))
            return set(data.get('ids', []))
        except Exception:
            pass
    return set()

def _append_local_index(problem_key: str, ids: set[str]) -> None:
    """Add problem_key to the in-memory set and write the index file."""
    if problem_key in ids:
        return
    ids.add(problem_key)
    LOCAL_INDEX_FILE.write_text(
        json.dumps({'ids': sorted(ids)}, indent=2),
        encoding='utf-8'
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Extract rich dataset from RAW HTML files.')
    parser.add_argument('--limit',        type=int, default=0,   help='Max files to process (0=all)')
    parser.add_argument('--id',           type=str, default='',  help='Single problem key e.g. 1-A')
    parser.add_argument('--overwrite',    action='store_true',   help='Re-extract even if JSON exists')
    parser.add_argument('--patch-db',     action='store_true',   help='Patch existing MongoDB docs with renderer fields')
    parser.add_argument('--full-insert',  action='store_true',   help='Upsert full documents into new MongoDB DB (also uploads images)')
    parser.add_argument('--missing',      action='store_true',   help='Only process IDs in saved-from-reparse/missing_ids.json (missing from local)')
    parser.add_argument('--missing-db',   action='store_true',   help='Only process IDs in saved-from-reparse/missing_db_ids.json (missing from MongoDB)')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    do_db      = args.patch_db or args.full_insert
    full_insert = args.full_insert

    # Load local index once — keep in memory, write after each new JSON
    local_ids = _load_local_index()
    print(info(f'[index] {len(local_ids)} problems already in local index'))

    # ── Connect to DB up-front if needed ─────────────────────────────────────
    problems_col = images_col = index_col = None
    if do_db:
        from dotenv import load_dotenv
        for env_file in ['.env.local', '.env']:
            p = Path(__file__).parent / env_file
            if p.exists():
                load_dotenv(p)
                break
        from lib.db import get_problems_collection, get_images_collection, get_index_collection
        problems_col = get_problems_collection()
        images_col   = get_images_collection()
        index_col    = get_index_collection() if full_insert else None
        mode_label   = 'full-insert' if full_insert else 'patch-db'
        print(info(f'[db] Connected — mode: {mode_label}'))

    # ── Main loop: extract + save JSON + push to DB in one pass ──────────────
    missing_ids: set[str] | None = None
    if args.missing:
        missing_file = OUTPUT_DIR / 'missing_ids.json'
        if not missing_file.exists():
            print(red('[missing] saved-from-reparse/missing_ids.json not found.'))
            print(yellow('  Run: python compare_indexes.py'))
            return
        missing_ids = set(json.loads(missing_file.read_text(encoding='utf-8')).get('ids', []))
        print(info(f'[missing] Targeting {len(missing_ids)} problems missing from local JSON'))
    elif args.missing_db:
        missing_file = OUTPUT_DIR / 'missing_db_ids.json'
        if not missing_file.exists():
            print(red('[missing-db] saved-from-reparse/missing_db_ids.json not found.'))
            print(yellow('  Run: python compare_indexes.py'))
            return
        missing_ids = set(json.loads(missing_file.read_text(encoding='utf-8')).get('ids', []))
        print(info(f'[missing-db] Targeting {len(missing_ids)} problems missing from MongoDB'))

    files = iter_html_files(limit=args.limit, single_id=args.id, missing_ids=missing_ids)
    total = len(files)
    print(info(f'[extract] {total} HTML files to process'))

    done = skipped = failed = 0
    db_ok = db_not_found = db_errors = total_imgs = 0

    for i, html_path in enumerate(files, 1):
        problem_key = html_path.stem
        parts = problem_key.split('-', 1)
        try:
            contest_id = int(parts[0])
        except (ValueError, IndexError):
            contest_id = 0

        out_dir  = get_output_subdir(contest_id)
        out_path = out_dir / f'{problem_key}.json'

        # ── Extract ──────────────────────────────────────────────────────────
        if out_path.exists() and not args.overwrite:
            # JSON already exists — if DB flag set, still push it
            if do_db:
                try:
                    status, imgs = insert_or_patch_db(
                        out_path, problems_col, images_col, index_col, full_insert
                    )
                except Exception as e:
                    status, imgs = f'error:{e}', 0
                total_imgs += imgs
                if status in ('inserted', 'patched'):
                    db_ok += 1
                elif status == 'not_found':
                    db_not_found += 1
                else:
                    db_errors += 1
                    print(red(f'  ({i}/{total}) {problem_key} → db error: {status}'))
                if total <= 30 or i % 500 == 0:
                    img_note = f' +{imgs}i' if imgs else ''
                    print(info(f'  ({i}/{total}) {problem_key} → skipped extract, db={status}{img_note}'))
            skipped += 1
            continue

        print(cyan(f'  ({i}/{total}) {problem_key}'), end=' ', flush=True)

        result = extract_one(html_path)
        if result is None:
            print(yellow('→ no problem-statement, skip'))
            failed += 1
            continue

        # ── Save JSON ─────────────────────────────────────────────────────────
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        done += 1

        # ── Update local index immediately ────────────────────────────────────
        _append_local_index(problem_key, local_ids)

        ex_count  = len((result.get('statement') or {}).get('examples', []))
        math_note = f'{result["math"]["inlineCount"]}i+{result["math"]["displayCount"]}d [{result["math"]["era"]}]'
        save_note = f'saved ({ex_count}ex, {math_note}, {len(result["constraints"])}c)'

        # ── Push to DB immediately ────────────────────────────────────────────
        if do_db:
            try:
                status, imgs = insert_or_patch_db(
                    out_path, problems_col, images_col, index_col, full_insert
                )
            except Exception as e:
                status, imgs = f'error:{e}', 0
            total_imgs += imgs
            if status in ('inserted', 'patched'):
                db_ok += 1
                img_note = f' +{imgs}i' if imgs else ''
                print(success(f'→ {save_note} | db={status}{img_note}'))
            elif status == 'not_found':
                db_not_found += 1
                print(yellow(f'→ {save_note} | db=not_found'))
            else:
                db_errors += 1
                print(red(f'→ {save_note} | db={status}'))
        else:
            print(success(f'→ {save_note}'))

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print(cyan('=' * 60))
    print(success('[extract] Complete'))
    print(info(f'  Extracted  : {done}'))
    print(info(f'  Skipped    : {skipped}  (JSON existed, use --overwrite to redo)'))
    print(info(f'  Failed     : {failed}'))
    if do_db:
        print(info(f'  DB OK      : {db_ok}'))
        if not full_insert:
            print(info(f'  Not in DB  : {db_not_found}'))
        print(info(f'  DB errors  : {db_errors}'))
        print(info(f'  Images up  : {total_imgs}'))
    if not do_db:
        print(yellow('\n  Tip: add --full-insert to also push to MongoDB.'))


if __name__ == '__main__':
    main()
