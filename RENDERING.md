# Problem Statement Rendering Guide

## What the scraper stores

Every paragraph block in MongoDB has two fields:

```json
{
  "type": "paragraph",
  "html": "The sum of <span class=\"MathJax_Preview\">...</span><script type=\"math/tex\">n^2</script> is given.",
  "text": "The sum of $n^2$ is given."
}
```

| Field  | Contains                              | Use for                          |
|--------|---------------------------------------|----------------------------------|
| `html` | Raw HTML with MathJax spans + scripts | Rendering in webview (with KaTeX)|
| `text` | Plain text, math as `$...$` LaTeX     | Search, tooltips, plain fallback |

Other block types have no HTML issue:

```json
{ "type": "code",  "code": "1 2 3" }
{ "type": "image", "src": "cf-image://1-A_diagram.png" }
{ "type": "list",  "ordered": false, "items": ["item1", "item2"] }
{ "type": "table", "html": "<table>...</table>" }
```

---

## Why `html` still has HTML tags

Codeforces renders math server-side using MathJax. The page HTML looks like this:

```html
<!-- MathJax Preview (visual) -->
<span class="MathJax_Preview" style="color: inherit;">
  <span class="MJXp-math">
    <span class="MJXp-mi">n</span>
  </span>
</span>

<!-- Actual LaTeX source (machine-readable) -->
<script type="math/tex" id="MathJax-Element-19">n^2</script>
```

The scraper keeps `html` as-is because:
1. It preserves inline formatting (`<em>`, `<strong>`, `<code>`)
2. The `<script type="math/tex">` tags contain the exact LaTeX source
3. Stripping it would lose the math entirely

The `text` field strips all of this down to `$n^2$` using `extract_math_and_clean()` in `lib/parse.py`.

---

## How to render in the VS Code webview

### The right approach: KaTeX (not MathJax)

Don't reuse Codeforces's MathJax output (the `MJXp-span` trees). It's bloated, depends on CF's CDN, and won't work offline. Use **KaTeX** instead — it's faster, smaller, and bundles cleanly into a VS Code extension.

### Step 1 — Extract LaTeX from `html`

The LaTeX is inside `<script type="math/tex">` tags:

```typescript
function extractLatex(html: string): string {
  // Replace <script type="math/tex">...</script> with $...$
  // Replace <script type="math/tex; mode=display">...</script> with $$...$$
  return html
    .replace(/<script type="math\/tex; mode=display"[^>]*>([\s\S]*?)<\/script>/g, ' $$$$$$1$$$$ ')
    .replace(/<script type="math\/tex"[^>]*>([\s\S]*?)<\/script>/g, ' $$$1$ ')
    // Remove MathJax preview spans (they duplicate the script content)
    .replace(/<span class="MathJax_Preview"[\s\S]*?<\/span>\s*(?=<script)/g, '')
    // Keep other inline tags (<em>, <strong>, <code>, etc)
}
```

Or simpler — just use `block.text` directly since it already has `$...$` LaTeX.

### Step 2 — Render with KaTeX

```typescript
import katex from 'katex';

function renderParagraph(text: string): string {
  // Replace $$...$$ (display math) first
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, latex) => {
    try {
      return katex.renderToString(latex, { displayMode: true, throwOnError: false });
    } catch {
      return `$$${latex}$$`;
    }
  });

  // Then replace $...$ (inline math)
  text = text.replace(/\$([^\$]+?)\$/g, (_, latex) => {
    try {
      return katex.renderToString(latex, { displayMode: false, throwOnError: false });
    } catch {
      return `$${latex}$`;
    }
  });

  return text;
}
```

### Step 3 — Inject KaTeX CSS in webview

```typescript
function getWebviewContent(panel: vscode.WebviewPanel): string {
  const katexCssUri = panel.webview.asWebviewUri(
    vscode.Uri.joinPath(context.extensionUri, 'node_modules', 'katex', 'dist', 'katex.min.css')
  );

  return `<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="${katexCssUri}">
  <style>
    .problem-statement { font-family: 'Segoe UI', sans-serif; padding: 16px; }
    .section-title { font-weight: bold; margin-top: 16px; }
    pre { background: var(--vscode-editor-background); padding: 8px; }
  </style>
</head>
<body>
  <div class="problem-statement">
    ${renderProblem(problem)}
  </div>
</body>
</html>`;
}
```

### Step 4 — Render each block

```typescript
function renderBlock(block: Block): string {
  switch (block.type) {
    case 'paragraph':
      // Use block.text (has $...$) and run KaTeX over it
      return `<p>${renderParagraph(block.text)}</p>`;

    case 'code':
      return `<pre><code>${escapeHtml(block.code)}</code></pre>`;

    case 'image':
      // block.src = "cf-image://1-A_diagram.png"
      // Serve images from your local API
      const filename = block.src.replace('cf-image://', '');
      const imgUrl = `http://localhost:3000/image/${filename}`;
      return `<img src="${imgUrl}" alt="${block.alt ?? ''}" style="max-width:100%">`;

    case 'list':
      const tag = block.ordered ? 'ol' : 'ul';
      const items = block.items.map(i => `<li>${renderParagraph(i)}</li>`).join('');
      return `<${tag}>${items}</${tag}>`;

    case 'table':
      return block.html; // tables are already clean HTML

    default:
      return '';
  }
}

function renderSection(blocks: Block[]): string {
  return blocks.map(renderBlock).join('\n');
}

function renderProblem(problem: Problem): string {
  const s = problem.statement;
  return `
    <h2>${s.title}</h2>
    <p><em>Time: ${s.timeLimit} | Memory: ${s.memoryLimit}</em></p>

    <div class="section-title">Problem</div>
    ${renderSection(s.description)}

    <div class="section-title">Input</div>
    ${renderSection(s.input)}

    <div class="section-title">Output</div>
    ${renderSection(s.output)}

    <div class="section-title">Examples</div>
    ${s.examples.map((ex, i) => `
      <div class="example">
        <div class="section-title">Input ${i + 1}</div>
        <pre>${escapeHtml(ex.input)}</pre>
        <div class="section-title">Output ${i + 1}</div>
        <pre>${escapeHtml(ex.output)}</pre>
      </div>
    `).join('')}

    ${s.note ? `<div class="section-title">Note</div>${renderSection(s.note)}` : ''}
  `;
}
```

---

## Image handling

Images are stored in MongoDB as binary and served by the local Flask API.

In the scraper, image `src` values are rewritten to `cf-image://filename.png`.

In the webview, replace that scheme with your API URL:

```typescript
const filename = block.src.replace('cf-image://', '');
const url = `http://localhost:3000/image/${filename}`;
```

The API endpoint is `GET /image/:filename` — it reads from MongoDB and returns the binary with the correct `Content-Type`.

---

## Install KaTeX in extension

```bash
cd seudoe
npm install katex
npm install --save-dev @types/katex
```

---

## Summary

```
Scraper stores:
  block.html  →  raw MathJax HTML (keep, use for reference)
  block.text  →  clean text with $latex$ markers  ← use this

Webview pipeline:
  block.text
    → renderParagraph()     replace $...$ with KaTeX HTML
    → inject katex.min.css
    → display in webview
```

No need to touch the scraper. Just use `block.text` in the extension and run KaTeX over it.
