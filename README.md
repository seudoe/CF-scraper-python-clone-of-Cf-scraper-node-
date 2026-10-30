---
title: Codeforces Problems API
emoji: 🚀
colorFrom: purple
colorTo: blue
sdk: docker
app_file: app_hf.py
pinned: false
---
# Codeforces Problems Scraper & API Engine

A high-performance pipeline and REST API server for scraping, parsing, synchronizing, and serving Codeforces problem statements. This repository is the backend engine powering the **seudoe** VS Code extension.

---

## 🏛️ Architecture & The 3-Store Model

The system uses three layers of data storage to ensure that parser bugs or network failures never require re-scraping the 11,000+ problems from Codeforces:

```
[ Codeforces Web ]  <─── (Selenium + Persistent Chrome Cookies)
       │
       ▼
 [ RAW_HTML/ ]      <─── Ground truth (raw HTML files + problem_index.json)
       │
       ▼ (Parser: MathJax to LaTeX, images, sample tests)
 [ saved-from-reparse/ ] <─── High-fidelity JSON files (local disk cache)
       │
       ▲▼ (Bidirectional Sync)
 [ MongoDB Atlas ]  <─── Cloud database (problems, images, problem_index)
       ▲
       │
 [ REST API Server ] <─── Serves seudoe extension (Flask / Gunicorn via uv)
```

1. **`RAW_HTML/` (The Source of Truth)**

   * Stores unmodified HTML pages fetched from Codeforces in range buckets (e.g. `RAW_HTML/2200-2300/2261-A.html`).
   * Tracked by [`RAW_HTML/problem_index.json`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/RAW_HTML/problem_index.json).
   * Once saved, any parsing logic improvement can be tested and applied locally with **zero network requests**.
2. **`saved-from-reparse/` (Local Structured JSON)**

   * Clean, parsed problem statements in range buckets (e.g. `saved-from-reparse/2200-2300/2261-A.json`).
   * LaTeX formulas converted from MathJax to standard `$math$` markers for KaTeX rendering.
   * Diagram images rewritten to local `cf-image://` URI identifiers.
3. **`MongoDB` (Production Serving Layer)**

   * **`problems`**: Structured problem documents.
   * **`images`**: Binary image buffers (PNG/JPEG/GIF) stored with mime types.
   * **`problem_index`**: Array of all available problem IDs for quick cataloging.

---

## ⚙️ How the Pipeline Works

When you run the pipeline ([`pipeline/pipeline.py`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/pipeline/pipeline.py)), it executes the following phases in sequence:

### Phase 1: Internal Index Verification (Per Store)

* Scans `RAW_HTML/` on disk vs `RAW_HTML/problem_index.json`.
* Scans `saved-from-reparse/` on disk vs `saved-from-reparse/problem_index.json`.
* Scans MongoDB `problems` collection vs MongoDB `problem_index`.
* Automatically prunes stale entries and adds untracked files to maintain index integrity.

### Phase 2: Cross-Store Synchronization

* **Phase 2a (`RAW_HTML` ⟷ `saved-from-reparse`)**:
  * If `RAW_HTML` has a problem that `saved-from-reparse` is missing: immediately (re)parses it from disk with **no network calls**.
  * If local JSON exists but `RAW_HTML` is missing: re-scrapes the raw page live.
* **Phase 2b (`saved-from-reparse` ⟷ `MongoDB`)**:
  * **Upload**: If local JSON exists but MongoDB is missing it, pushes the JSON statement and binary images to MongoDB.
  * **Download**: If MongoDB has a problem that local disk is missing, downloads the document and missing images directly from MongoDB without scraping.

### Phase 3 & 4: Live Scraping & Ingestion (New Problems)

1. **Fetches CF API**: Queries `https://codeforces.com/api/problemset.problems` to get the master list of all problems on Codeforces.
2. **Diffs against Index**: Identifies which problems exist on Codeforces but are missing from `RAW_HTML` (excluding known PDF-only problems).
3. **Live Web Scrape**: Uses Selenium with stealth scripts and real Chrome cookies to bypass Cloudflare Turnstile protection.
4. **Immediate Persistence**: Saves RAW HTML, parses statement, downloads images, writes local JSON, and upserts to MongoDB **one problem at a time** (no bulk batching, so interruptions never lose progress).

---

## 🚀 Setup & Installation (using `uv`)

This project uses [**`uv`**](https://github.com/astral-sh/uv) for fast, deterministic Python environment and dependency management.

### 1. Install Dependencies

* **For Full Scraper & Pipeline (Local Machine)**:

  ```powershell
  uv sync --extra scraper
  ```

  *(Installs Flask, PyMongo, Gunicorn, Requests, plus Selenium, Undetected-Chromedriver, and BeautifulSoup4).*
* **For Read-Only API Server (Lightweight / Docker)**:

  ```powershell
  uv sync
  ```

### 2. Configure Environment

Create a `.env` file in the root directory:

```ini
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/codeforces?retryWrites=true&w=majority
PORT=3000
```

---

## 🛠️ CLI Commands: Scraping & Synchronization

All commands are run using `uv run` (no manual virtual environment activation needed).

### Step 1: Verify / Copy Brave or Chrome Cookies (Bypass Cloudflare)

Codeforces uses Cloudflare Turnstile bot detection. To ensure the scraper is trusted, copy cookies from your local Brave (or Chrome) profile into the dedicated scraper profile:

1. Close Brave (or Chrome) completely so Windows releases the lock on the Cookies database.
2. Run the cookie checker:
   ```powershell
   # Auto-detects Brave or Chrome and copies safely (preserves existing cookies)
   uv run python pipeline/chrome-cookies-checker.py

   # Or specify a custom profile / Cookies file path:
   uv run python pipeline/chrome-cookies-checker.py --path "C:\Users\<user>\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default"
   ```
3. The script creates a backup (`Cookies.bak`), copies the session cookies, and runs a live verification check against `https://codeforces.com/problemset/problem/1/A`.
4. *Flags:*
   * `--path <path>`: Custom path to a browser profile directory or direct `Cookies` file.
   * `--verify-only`: Skip copying, test the existing scraper cookies directly.
   * `--copy-only`: Copy cookies without launching the verification browser.

---

### Step 2: Run the Pipeline

#### 1. Dry Run (Inspect without making changes)

Check what the pipeline would repair and which new problems are ready to be scraped:

```powershell
uv run python pipeline/pipeline.py --dry-run
```

#### 2. Full Run (Sync + Scrape all new problems)

Syncs all three stores and scrapes every new problem from Codeforces:

```powershell
uv run python pipeline/pipeline.py
```

#### 3. Scrape a Capped Batch of New Problems (Recommended)

Cap the number of new problems scraped in this run (e.g. scrape the first 10 new problems):

```powershell
uv run python pipeline/pipeline.py --limit 10
```

#### 4. Sync Only (No Live Scraping)

Run Phases 1, 2a, and 2b to ensure `RAW_HTML`, `saved-from-reparse`, and `MongoDB` are 100% in sync without scraping anything new:

```powershell
uv run python pipeline/pipeline.py --sync-only
```

#### 5. Skip Sync (Jump straight to Scraping New Problems)

Skip the internal store consistency check and immediately scrape new problems from CF API:

```powershell
uv run python pipeline/pipeline.py --skip-sync
```

#### 6. Scrape or Reparse a Single Problem

Target a single problem key (e.g. `2261-A` or `1-A`). If RAW HTML exists, it reparses locally; if not, it scrapes live:

```powershell
uv run python pipeline/pipeline.py --id 2261-A
```

---

## 🌐 Running the Web API Server

### 1. Full API Server (`app.py`)

Includes problem lookup, image streaming, and the `/sync` background pipeline trigger endpoint:

```powershell
# Development
uv run python app.py

# Production with Gunicorn
uv run gunicorn -w 1 -b 0.0.0.0:3000 app:app --timeout 300
```

### 2. Read-Only HF Spaces Server (`app_hf.py`)

Lightweight server that queries MongoDB directly (no browser / scraping dependencies):

```powershell
uv run python app_hf.py
```

---

## 📡 API Endpoints

| Method       | Endpoint                         | Description                                                                                                                                                                                                    |
| :----------- | :------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`      | `/`                            | Health check. Returns JSON status for API requests, or web UI for browsers.                                                                                                                                    |
| `GET`      | `/problem/<contestId>/<index>` | Returns parsed JSON statement with LaTeX text, example tests, and metadata.                                                                                                                                    |
| `GET`      | `/image/<filename>`            | Streams cached problem diagram binary from MongoDB with proper `Content-Type`.                                                                                                                               |
| `GET`      | `/index`                       | Returns list of all scraped problem IDs and total count.                                                                                                                                                       |
| `GET/POST` | `/sync`                        | Triggers [`pipeline.py`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/pipeline/pipeline.py) in the background. Optional params: `limit=10`, `sync_only=1`, `dry_run=1`, `id=1-A`. |

---

## 🐳 Deployment

### Hugging Face Spaces

Configured via [`Dockerfile`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/Dockerfile) and [`spaces_config.yaml`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/spaces_config.yaml). The Dockerfile copies `uv` directly from the official image, runs `uv sync --frozen --no-dev` to install only core dependencies, and starts Gunicorn on port `7860`.

### Render

Configured via [`render.yaml`](file:///c:/Users/4dmin/Downloads/HackWo/seudoe/CF-scraper-python/render.yaml). Builds with `pip install uv && uv sync --extra scraper` and installs Chromium for live background scraping.
