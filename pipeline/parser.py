"""
pipeline/parser.py
===================
Pure HTML -> statement parser. No network calls, no disk I/O beyond the
html string it's handed. Safe to unit-test against any saved HTML file.

This is the "good" parser (originally proven out in extract-dataset-v2.py),
rewritten as the canonical parser for the pipeline. It is era-aware:

  Era 1 (contest ~000-1099): <pre>...<br/>...<br/>...</pre>, math as
                              <span class="tex-span"> with rendered inner HTML
  Era 2 (contest ~1100-1700): <pre>plain text with real \\n</pre>
  Era 3 (contest ~1700+):     <pre><div class="test-example-line">...</div></pre>,
                              math as <script type="math/tex">...</script>

Getting sample I/O, math and images right matters more than anything else
here -- a parser bug means every problem has to be re-scraped from scratch.
"""

import re
from typing import Any
from bs4 import BeautifulSoup, Tag, NavigableString

# ── pre/code text extraction - handles all three CF eras ────────────────────

def extract_pre_text(pre: Tag) -> str:
    divs = pre.find_all(
        'div',
        class_=lambda c: c and 'test-example-line' in (c if isinstance(c, list) else c.split())
    )
    if divs:
        return '\n'.join(d.get_text() for d in divs).strip()

    for br in pre.find_all('br'):
        br.replace_with('\n')

    return pre.get_text(separator='').strip()


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
    Convert paragraph HTML to plain text with $...$ / $$...$$ LaTeX markers.
    mathjax era: pulls LaTeX out of <script type="math/tex"> tags.
    tex-span era: left as rendered inner HTML (handled by caller, not here).
    """
    soup = BeautifulSoup(html_str, 'html.parser')

    for script in soup.find_all('script', type=lambda t: t and 'math/tex' in t):
        latex = (script.string or '').strip()
        if 'display' in (script.get('type') or ''):
            script.replace_with(f' $${latex}$$ ')
        else:
            script.replace_with(f' ${latex}$ ')

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
        if isinstance(src, list):
            src = src[0] if src else ''
        if src:
            b: dict[str, Any] = {'type': 'image', 'src': str(src)}
            if node.get('alt'):
                b['alt'] = str(node.get('alt'))
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
            'input': get_io('input'),
            'output': get_io('output'),
        }

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

def parse_statement(html: str, problem_key: str = '?') -> dict | None:
    """
    Parse a Codeforces problem page into a structured statement dict:

      {
        title, timeLimit, memoryLimit, inputMode, outputMode,
        isInteractive, multipleTC,
        description: [Block], input: [Block], output: [Block],
        examples: [{input, output, explanation?}],
        note?: [Block],
      }

    Returns None if no .problem-statement div is found (bad/incomplete HTML).
    """
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
        if t:
            title = strip_tags(str(t))

        tl = header.find('div', class_=lambda c: c and 'time-limit' in (c if isinstance(c, list) else c.split()))
        if tl:
            time_limit = strip_tags(str(tl)).replace('time limit per test', '').strip()

        ml = header.find('div', class_=lambda c: c and 'memory-limit' in (c if isinstance(c, list) else c.split()))
        if ml:
            memory_limit = strip_tags(str(ml)).replace('memory limit per test', '').strip()

        inp_f = header.find('div', class_=lambda c: c and 'input-file' in (c if isinstance(c, list) else c.split()))
        if inp_f:
            pt = inp_f.find('div', class_='property-title')
            if pt:
                pt.decompose()
            v = inp_f.get_text().strip()
            if v:
                input_mode = v

        out_f = header.find('div', class_=lambda c: c and 'output-file' in (c if isinstance(c, list) else c.split()))
        if out_f:
            pt = out_f.find('div', class_='property-title')
            if pt:
                pt.decompose()
            v = out_f.get_text().strip()
            if v:
                output_mode = v

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
                if not isinstance(c, Tag):
                    continue
                cc = c.get('class', [])
                if not isinstance(cc, list):
                    cc = str(cc).split()
                if skip_title and 'section-title' in cc:
                    continue
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
        'title':         title,
        'timeLimit':     time_limit,
        'memoryLimit':   memory_limit,
        'inputMode':     input_mode,
        'outputMode':    output_mode,
        'isInteractive': is_interactive,
        'multipleTC':    has_multiple_tc,
        'description':   sections['description'],
        'input':         sections['input'],
        'output':        sections['output'],
        'examples':      examples,
    }
    if sections['note']:
        result['note'] = sections['note']

    return result

# ── Image handling (pure - no network, no disk) ──────────────────────────────

def collect_image_urls(statement: dict) -> list[str]:
    """Every raw (http/relative) image src referenced by this statement, deduped."""
    urls: list[str] = []
    for sec in ('description', 'input', 'output', 'note'):
        for b in statement.get(sec, []) or []:
            if b.get('type') == 'image':
                src = b.get('src', '')
                if src and not src.startswith('cf-image://'):
                    urls.append(src)
    return list(dict.fromkeys(urls))


def rewrite_image_srcs(statement: dict, url_to_filename: dict[str, str]) -> None:
    """Mutate statement in place: raw image URLs -> cf-image://<local filename>."""
    for sec in ('description', 'input', 'output', 'note'):
        for b in statement.get(sec, []) or []:
            if b.get('type') == 'image':
                src = b.get('src', '')
                if src in url_to_filename:
                    b['src'] = f'cf-image://{url_to_filename[src]}'
