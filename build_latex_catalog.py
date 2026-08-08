"""
build_latex_catalog.py
======================
Scans all saved-from-reparse/**/*.json and builds a comprehensive catalog of:
  - Every LaTeX command found and how many problems use it
  - CF formatting tag classes and their frequency
  - Math era distribution (mathjax / tex-span / image / none)
  - tex-span rendered text samples (old-era problems)
  - Example LaTeX strings for each command

Output: saved-from-reparse/latex_catalog.md  (human-readable reference)
        saved-from-reparse/latex_catalog.json (machine-readable)

Usage:
    python build_latex_catalog.py
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter

OUTPUT_DIR   = Path(__file__).parent / 'saved-from-reparse'
CATALOG_MD   = OUTPUT_DIR / 'latex_catalog.md'
CATALOG_JSON = OUTPUT_DIR / 'latex_catalog.json'

# ── What each LaTeX command means for rendering ───────────────────────────────

COMMAND_DESCRIPTIONS = {
    r'\sum':          ('Summation',              'display: Σ with limits above/below'),
    r'\int':          ('Integral',               'display: ∫ with limits'),
    r'\frac':         ('Fraction',               '\\frac{num}{den} → num/den stacked'),
    r'\sqrt':         ('Square root',            '\\sqrt{x} or \\sqrt[n]{x}'),
    r'\prod':         ('Product',                'Π with limits, like \\sum'),
    r'\lim':          ('Limit',                  '\\lim_{x→∞}'),
    r'\min':          ('Minimum',                '\\min or \\min_{i} — use \\operatorname'),
    r'\max':          ('Maximum',                '\\max or \\max_{i}'),
    r'\binom':        ('Binomial coefficient',   '\\binom{n}{k} → C(n,k)'),
    r'\left':         ('Left delimiter',         'scales bracket: \\left( ... \\right)'),
    r'\right':        ('Right delimiter',        'scales bracket: \\left( ... \\right)'),
    r'\cdot':         ('Centered dot',           'multiplication: a \\cdot b'),
    r'\times':        ('Times / cross product',  'a \\times b'),
    r'\leq':          ('Less or equal',          '≤ — also \\le'),
    r'\geq':          ('Greater or equal',       '≥ — also \\ge'),
    r'\neq':          ('Not equal',              '≠'),
    r'\infty':        ('Infinity',               '∞'),
    r'\log':          ('Logarithm',              '\\log or \\log_2'),
    r'\lceil':        ('Left ceiling',           '⌈ — pair with \\rceil'),
    r'\lfloor':       ('Left floor',             '⌊ — pair with \\rfloor'),
    r'\rceil':        ('Right ceiling',          '⌉'),
    r'\rfloor':       ('Right floor',            '⌋'),
    r'\pmod':         ('Modulo (paren)',          'a \\pmod{m} → a (mod m)'),
    r'\mod':          ('Modulo',                 'a \\mod m'),
    r'\oplus':        ('XOR / direct sum',       '⊕'),
    r'\cup':          ('Union',                  '∪'),
    r'\cap':          ('Intersection',           '∩'),
    r'\forall':       ('For all',                '∀'),
    r'\exists':       ('There exists',           '∃'),
    r'\substack':     ('Stacked subscript',      '\\sum_{\\substack{i≥1\\\\j≥1}} — multi-line limits'),
    r'\text':         ('Text in math',           '\\text{word} — renders as normal text inside math'),
    r'\mathbb':       ('Blackboard bold',        '\\mathbb{Z}, \\mathbb{R}, \\mathbb{N}'),
    r'\mathcal':      ('Calligraphic',           '\\mathcal{O} — big-O notation'),
    r'\operatorname': ('Custom operator',        '\\operatorname{lcm}, \\operatorname{gcd}'),
    r'\begin':        ('Environment start',      '\\begin{cases}, \\begin{matrix}, \\begin{align}'),
    r'\end':          ('Environment end',        'paired with \\begin'),
    r'\vec':          ('Vector arrow',           '\\vec{v} → v with arrow above'),
    r'\overline':     ('Overline',               '\\overline{AB} — line above'),
    r'\underline':    ('Underline',              '\\underline{x}'),
}

CF_TAG_DESCRIPTIONS = {
    'tex-font-style-bf': ('Bold text',           'font-weight: bold',                   'b'),
    'tex-font-style-it': ('Italic text',         'font-style: italic',                  'i'),
    'tex-font-style-tt': ('Monospace / code',    'font-family: monospace',              'code'),
    'tex-font-style-sl': ('Slanted text',        'font-style: oblique',                 'i'),
    'tex-font-style-sc': ('Small caps',          'font-variant: small-caps',            'span'),
    'tex-span':          ('Legacy inline math',  'old-era: inner HTML, not raw LaTeX',  'span'),
    'upper-index':       ('Superscript',         'render as <sup>',                     'sup'),
    'lower-index':       ('Subscript',           'render as <sub>',                     'sub'),
    'tex-math':          ('Math block wrapper',  'wraps display math in newer problems', 'div'),
}

# ── Aggregate across all JSONs ────────────────────────────────────────────────

def aggregate() -> dict:
    json_files = sorted(OUTPUT_DIR.rglob('*.json'))
    # Exclude index files
    json_files = [f for f in json_files if f.stem not in ('problem_index', 'missing_ids', 'missing_db_ids', 'latex_catalog')]

    total_problems  = 0
    era_counts      = Counter()
    cmd_problems    = defaultdict(int)   # command → how many problems contain it
    cmd_total       = defaultdict(int)   # command → total occurrences across all problems
    cmd_examples    = defaultdict(list)  # command → sample LaTeX strings containing it
    cf_tag_counts   = defaultdict(int)   # tag → total across all problems
    cf_tag_problems = defaultdict(int)   # tag → how many problems have it > 0
    tex_span_samples: list[str] = []     # sample tex-span rendered texts (old era)

    print(f'Scanning {len(json_files)} JSON files ...')

    for jpath in json_files:
        try:
            data = json.loads(jpath.read_text(encoding='utf-8'))
        except Exception:
            continue

        total_problems += 1
        math = data.get('math', {})
        era  = math.get('era', 'none')
        era_counts[era] += 1

        # LaTeX commands
        for cmd, count in math.get('latexCommands', {}).items():
            cmd_problems[cmd] += 1
            cmd_total[cmd]    += count

        # Collect example LaTeX strings per command (up to 3 per command)
        for latex_str in math.get('allLatex', []):
            for cmd in math.get('latexCommands', {}).keys():
                if cmd in latex_str and len(cmd_examples[cmd]) < 3:
                    clean = latex_str.strip()
                    if clean not in cmd_examples[cmd]:
                        cmd_examples[cmd].append(clean[:120])  # truncate long ones

        # CF tags
        for tag, count in data.get('cfTags', {}).items():
            cf_tag_counts[tag]   += count
            if count > 0:
                cf_tag_problems[tag] += 1

        # tex-span samples (old era)
        if era == 'tex-span':
            for sample in math.get('texSpanRendered', [])[:2]:
                if sample and len(tex_span_samples) < 20:
                    tex_span_samples.append(sample)

    return {
        'total_problems': total_problems,
        'era_counts':     dict(era_counts),
        'latex_commands': {
            cmd: {
                'problems':  cmd_problems[cmd],
                'total_occurrences': cmd_total[cmd],
                'examples':  cmd_examples.get(cmd, []),
            }
            for cmd in sorted(cmd_problems, key=lambda c: -cmd_problems[c])
        },
        'cf_tags': {
            tag: {
                'total':    cf_tag_counts[tag],
                'problems': cf_tag_problems[tag],
            }
            for tag in cf_tag_counts
        },
        'tex_span_samples': list(dict.fromkeys(tex_span_samples)),
    }


# ── Write markdown catalog ────────────────────────────────────────────────────

def write_markdown(data: dict) -> None:
    lines = []
    a = lines.append

    a('# Codeforces LaTeX & Formatting Catalog')
    a('')
    a('> Auto-generated from all local problem JSONs in `saved-from-reparse/`.')
    a('> Use this as the reference for how to treat each tag/command in the renderer.')
    a('')
    a(f'**Problems scanned:** {data["total_problems"]}')
    a('')

    # ── Math era breakdown ────────────────────────────────────────────────────
    a('---')
    a('')
    a('## Math Era Distribution')
    a('')
    a('CF changed how it renders math over time. The `math.era` field tells you which path to use.')
    a('')
    a('| Era | Problems | Math style | Renderer action |')
    a('|-----|----------|------------|-----------------|')
    era_info = {
        'mathjax':  ('~contest 1100+', '`<script type="math/tex">` tags', 'Extract LaTeX from script tags → KaTeX'),
        'tex-span': ('~contest 000–1099', '`<span class="tex-span">` with rendered HTML inside', 'Render inner HTML as-is (already formatted)'),
        'image':    ('Very old', '`<img>` pointing to formula service', 'Show original CF image URL as fallback'),
        'none':     ('Any era', 'No math expressions', 'Plain text only'),
    }
    for era, count in sorted(data['era_counts'].items(), key=lambda x: -x[1]):
        contest_range, style, action = era_info.get(era, ('?', '?', '?'))
        a(f'| `{era}` | {count} | {style} | {action} |')
    a('')

    # ── CF HTML formatting tags ───────────────────────────────────────────────
    a('---')
    a('')
    a('## CF HTML Formatting Tags')
    a('')
    a('These are the undocumented CSS class names Codeforces uses in problem statements.')
    a('The scraper stores counts in `cfTags` per problem.')
    a('')
    a('| Class name | Meaning | CSS to apply | HTML element | Problems | Total uses |')
    a('|------------|---------|--------------|--------------|----------|------------|')
    for tag, info in CF_TAG_DESCRIPTIONS.items():
        meaning, css, element = info
        stats = data['cf_tags'].get(tag, {})
        problems = stats.get('problems', 0)
        total    = stats.get('total', 0)
        a(f'| `{tag}` | {meaning} | `{css}` | `<{element}>` | {problems} | {total} |')
    a('')
    a('### tex-span era (old problems) — rendered HTML samples')
    a('')
    a('Old problems use `<span class="tex-span">` with rendered HTML inside, not raw LaTeX.')
    a('Inner content looks like: `<i>n</i>`, `10<sup class="upper-index">5</sup>`')
    a('**Renderer action:** render the inner HTML as-is — it is already formatted.')
    a('')
    if data['tex_span_samples']:
        a('Sample inner texts found:')
        a('```')
        for s in data['tex_span_samples'][:15]:
            a(s)
        a('```')
    a('')

    # ── LaTeX commands ────────────────────────────────────────────────────────
    a('---')
    a('')
    a('## LaTeX Commands (MathJax era)')
    a('')
    a('All commands found in `math.allLatex` across scraped problems, sorted by frequency.')
    a('KaTeX supports all of these — no special handling needed unless noted.')
    a('')
    a('| Command | Meaning | Renderer note | Problems | Total uses |')
    a('|---------|---------|---------------|----------|------------|')

    for cmd, stats in data['latex_commands'].items():
        desc = COMMAND_DESCRIPTIONS.get(cmd, ('', ''))
        meaning   = desc[0] if desc[0] else cmd.replace('\\', '')
        note      = desc[1] if len(desc) > 1 else 'Standard KaTeX'
        problems  = stats['problems']
        total     = stats['total_occurrences']
        a(f'| `{cmd}` | {meaning} | {note} | {problems} | {total} |')

    a('')

    # ── Commands with examples ────────────────────────────────────────────────
    a('---')
    a('')
    a('## LaTeX Command Examples')
    a('')
    a('Real LaTeX strings from CF problems for each command.')
    a('')
    for cmd, stats in data['latex_commands'].items():
        examples = stats.get('examples', [])
        if not examples:
            continue
        a(f'### `{cmd}`')
        desc = COMMAND_DESCRIPTIONS.get(cmd, ('', ''))
        if desc[0]:
            a(f'*{desc[0]}* — {desc[1]}')
        a('')
        a('```latex')
        for ex in examples:
            a(ex)
        a('```')
        a('')

    # ── Renderer summary ──────────────────────────────────────────────────────
    a('---')
    a('')
    a('## Renderer Decision Table')
    a('')
    a('Quick reference for implementing the VS Code webview renderer.')
    a('')
    a('| Condition | Action |')
    a('|-----------|--------|')
    a('| `math.era == "mathjax"` | Extract LaTeX from `<script type="math/tex">` → run KaTeX auto-render on `block.text` |')
    a('| `math.era == "tex-span"` | Render `block.html` as-is — inner HTML is already formatted |')
    a('| `math.era == "image"` | Show original CF image URL as `<img>` fallback |')
    a('| `cfTags["tex-font-style-bf"] > 0` | Apply `font-weight: bold` to `<span class="tex-font-style-bf">` |')
    a('| `cfTags["tex-font-style-it"] > 0` | Apply `font-style: italic` to `<span class="tex-font-style-it">` |')
    a('| `cfTags["tex-font-style-tt"] > 0` | Apply `font-family: monospace` to `<span class="tex-font-style-tt">` |')
    a('| `cfTags["upper-index"] > 0` | Render `<sup class="upper-index">` as `<sup>` |')
    a('| `cfTags["lower-index"] > 0` | Render `<sub class="lower-index">` as `<sub>` |')
    a('| `\\substack` in allLatex | Multi-line sum limits — KaTeX handles natively |')
    a('| `\\text` in allLatex | Text inside math — KaTeX handles natively |')
    a('| `\\mathbb` in allLatex | Blackboard bold (ℝ, ℤ, ℕ) — KaTeX handles natively |')
    a('| `\\operatorname` in allLatex | Custom operator names — KaTeX handles natively |')
    a('')

    CATALOG_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(f'Written: {CATALOG_MD}')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    data = aggregate()

    # Save JSON catalog
    CATALOG_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Written: {CATALOG_JSON}')

    # Save markdown catalog
    write_markdown(data)

    print()
    print(f'Era breakdown:')
    for era, count in sorted(data['era_counts'].items(), key=lambda x: -x[1]):
        print(f'  {era:10s}: {count}')
    print(f'Unique LaTeX commands found: {len(data["latex_commands"])}')
    print(f'CF tag classes found:        {len(data["cf_tags"])}')


if __name__ == '__main__':
    main()
