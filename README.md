# Codeforces Problem Scraper

A Python-based web scraper for Codeforces problems with intelligent Cloudflare bypass using persistent browser profiles.

## Features

- ✅ **Persistent Browser Profile** - Maintains cookies and cache across sessions for better Cloudflare bypass
- ✅ **Intelligent Parsing** - Handles arbitrary HTML nesting with recursive DOM walker
- ✅ **MongoDB Storage** - Stores problems and images in MongoDB
- ✅ **REST API** - Flask API for accessing scraped problems
- ✅ **Randomized Timing** - Human-like request patterns (7-15s delays)
- ✅ **Colored Logging** - Clear, semantic terminal output
- ✅ **Image Caching** - Stores images with `cf-image://` URLs

## API Endpoints

### `GET /`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "cf-scraper-python",
  "scraped": 1234
}
```

### `GET /problem/:contestId/:index`
Get a specific problem.

**Example:** `/problem/1/A`

**Response:**
```json
{
  "contestId": 1,
  "index": "A",
  "statement": {
    "title": "Theatre Square",
    "timeLimit": "1 second",
    "memoryLimit": "256 megabytes",
    "description": [...],
    "input": [...],
    "output": [...],
    "examples": [...]
  }
}
```

### `GET /image/:filename`
Get a cached image.

**Example:** `/image/1-A_diagram.png`

### `GET /index`
Get list of all scraped problem IDs.

**Response:**
```json
{
  "ids": ["1-A", "1-B", "2-A", ...],
  "count": 1234
}
```

### `POST /sync`
Trigger background sync of new problems.

**Response:**
```json
{
  "status": "started",
  "message": "Sync started in background"
}
```

## Environment Variables

- `MONGODB_URI` - MongoDB connection string (required)
- `PORT` - Server port (default: 5000)

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your MongoDB URI

# Run the server
python app.py

# Or run a full sync
python sync.py

# Test the parser
python test_parser.py
```

## Profile Management

```bash
# Check profile status
python manage_profile.py

# Clear profile (start fresh)
python manage_profile.py clear
```

## Architecture

- **Persistent Profile**: Stores cookies, cache, local storage in `chrome-profile/`
- **Randomized Delays**: 7-15 second waits between requests
- **Intelligent Waiting**: Detects and waits for Cloudflare challenges
- **Recursive Parser**: Handles any HTML structure

## Success Rate

- **First Run**: ~10-20% (building trust)
- **Second Run**: ~40-60% (has cookies)
- **Third+ Runs**: ~60-80% (trusted profile)

## Documentation

- `STATUS.md` - Current status and completed fixes
- `PERSISTENT_PROFILE_GUIDE.md` - Detailed guide on persistent profiles
- `cloudflareDetection.md` - Cloudflare signals research
- `parserCorrection.md` - Parser design documentation

## Tech Stack

- **Python 3.9+**
- **Selenium** - Browser automation with persistent profiles
- **Flask** - REST API
- **MongoDB** - Data storage
- **BeautifulSoup4** - HTML parsing
- **Colorama** - Terminal colors

## License

MIT
