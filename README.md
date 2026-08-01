# CF Scraper (Python + Selenium)

Codeforces problem scraper service built with Python, Selenium, and Flask.

Uses **Selenium WebDriver** instead of Puppeteer to reliably bypass Cloudflare bot detection. Works on Hugging Face Spaces and other Python hosting platforms.

## Features

- ✅ Scrapes Codeforces problems with Selenium (bypasses Cloudflare)
- ✅ Stores problems in MongoDB with structured Block-based format
- ✅ Downloads and caches images locally
- ✅ 10-second delay between scrapes to avoid rate limiting
- ✅ Skips already-scraped problems
- ✅ RESTful API compatible with seudoe VS Code extension

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Chrome/Chromium

Selenium requires Chrome or Chromium to be installed:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver
```

**macOS:**
```bash
brew install --cask google-chrome
brew install chromedriver
```

**Windows:**
Download and install Chrome from https://www.google.com/chrome/

### 3. Configure Environment

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local` and add your MongoDB URI:

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/cf-scraper?retryWrites=true&w=majority
PORT=3000
```

### 4. Run the Server

```bash
python app.py
```

Server will start on `http://localhost:3000`

## API Endpoints

### `GET /`
Health check - returns service status and scraped problem count

### `GET /sync` or `POST /sync`
Start background sync worker to scrape all problems from Codeforces API

### `GET /problem/:contestId/:index`
Get a cached problem (e.g., `/problem/158/A`)

### `GET /image/:filename`
Get a cached image

### `GET /index`
List all scraped problem IDs

## Deployment

### Hugging Face Spaces

1. Create a new Space with Docker SDK
2. Add `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Chrome
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860", "--timeout", "0", "--workers", "1"]
```

3. Add your `MONGODB_URI` as a Space secret
4. Push code to the Space

### Render.com

1. Create new Web Service
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 0 --workers 1`
4. Add `MONGODB_URI` environment variable
5. Deploy

## Data Structure

Problems are stored using the same Block-based structure as the TypeScript version:

```json
{
  "contestId": 158,
  "index": "A",
  "cachedAt": 1754040000,
  "version": 1,
  "statement": {
    "title": "Next Round",
    "timeLimit": "3 seconds",
    "memoryLimit": "256 megabytes",
    "description": [
      {"type": "paragraph", "html": "..."},
      {"type": "image", "src": "cf-image://158-A_img1.png"}
    ],
    "input": [...],
    "output": [...],
    "examples": [
      {"input": "...", "output": "...", "explanation": "..."}
    ],
    "note": [...]
  }
}
```

## MongoDB Collections

- `problems` - cached problem statements
- `problem_index` - list of scraped problem IDs
- `images` - binary image data

## Logging

The service logs all operations:
- `[cf-api]` - CF API calls
- `[fetch]` - HTML/image fetching
- `[parse]` - HTML parsing
- `[scraper]` - Problem scraping
- `[worker]` - Sync worker
- `[db]` - Database operations
- `[api]` - API requests
- `[server]` - Server startup

## Differences from Node.js Version

1. Uses **Selenium WebDriver** instead of Puppeteer
2. Uses **Flask** instead of Node's http module
3. Uses **threading** instead of async/await for background sync
4. Uses **BeautifulSoup** for HTML parsing
5. Otherwise maintains identical API and data structure

## License

MIT
