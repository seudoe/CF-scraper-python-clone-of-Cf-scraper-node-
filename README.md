---
title: Codeforces Problems API
emoji: 🚀
colorFrom: purple
colorTo: blue
sdk: docker
app_file: app_hf.py
pinned: false
---

# Codeforces Problems API

A read-only API server for serving cached Codeforces problem statements, built as part of the seudoe VS Code extension.

## Features

- **REST API** for fetching problem statements by contest ID and index
- **Image serving** from MongoDB cache
- **Problem indexing** with complete metadata (time limits, memory limits, examples)
- **Hugging Face Spaces** compatible deployment

## Deployment

This space serves cached problems that were previously scraped and stored in MongoDB Atlas.

### Environment Variables

Set these in your Hugging Face Spaces environment:

```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority
```

## API Endpoints

### Health Check
```bash
GET /
```

Returns JSON status and count of cached problems.

### Get Problem Statement
```bash
GET /problem/<contestId>/<index>
```

Example:
```bash
GET /problem/1/A
```

Response:
```json
{
  "contestId": 1,
  "index": "A",
  "cachedAt": 1689123456,
  "version": 1,
  "statement": {
    "title": "Theatre Square",
    "timeLimit": "2 seconds",
    "memoryLimit": "256 megabytes",
    "description": [...],
    "input": [...],
    "output": [...],
    "examples": [...],
    "note": [...]
  }
}
```

### Get Image
```bash
GET /image/<filename>
```

Example:
```bash
GET /image/1-A_diagram.png
```

Returns the image binary with appropriate `Content-Type` header.

### Problem Index
```bash
GET /index
```

Returns list of all cached problem IDs.

```json
{
  "ids": ["1-A", "1-B", "1-C", ...],
  "count": 9614
}
```

## Local Development

### Installation

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### Run Locally

```bash
# Using Flask development server
python app.py

# Or for the HF Spaces version
python app_hf.py
```

Server starts on `http://localhost:3000` (app.py) or `http://localhost:7860` (app_hf.py).

## Data Structure

Problems are stored in MongoDB with the following structure:

```javascript
{
  "_id": ObjectId(...),
  "contestId": 1,
  "index": "A",
  "cachedAt": 1689123456,
  "version": 1,
  "statement": {
    "title": "Theatre Square",
    "timeLimit": "2 seconds",
    "memoryLimit": "256 megabytes",
    "description": [
      {
        "type": "paragraph",
        "html": "raw MathJax HTML from CF",
        "text": "clean text with $latex$ markers"
      }
    ],
    "input": [...],
    "output": [...],
    "examples": [
      {
        "input": "1\n1 1 1",
        "output": "1",
        "explanation": "optional"
      }
    ]
  }
}
```

Images are stored separately:

```javascript
{
  "_id": ObjectId(...),
  "problemId": "1-A",
  "filename": "1-A_diagram.png",
  "contentType": "image/png",
  "data": Binary(...),
  "cachedAt": 1689123456
}
```

## How This Works with the seudoe Extension

The VS Code extension (`seudoe`) uses this API to fetch and display Codeforces problems in a webview:

1. Extension queries `/problem/<contestId>/<index>`
2. API returns cached statement (or 404 if not cached)
3. Extension renders problem in webview using:
   - KaTeX for math rendering from `block.text` (contains `$...$` LaTeX)
   - Problem statement blocks (description, input, output, examples)
   - Fetches images from `/image/<filename>`

## Scraping

> **Note:** Scraping is done locally using `CF-scraper-python` and requires a browser.

This Hugging Face Space is **read-only** — it only serves pre-cached problems. To scrape new problems:

1. Clone the full `CF-scraper-python` repository locally
2. Set up your MongoDB connection
3. Run the scraper to populate the database
4. Deploy this Space to serve the cached problems

For scraping details, see the main repository.

## Related Projects

- **seudoe** — VS Code extension for viewing Codeforces problems
- **CF-scraper** — Node.js scraper (legacy)
- **CF-scraper-python** — Python scraper with advanced HTML parsing
