# Quick Start Guide

## Local Development

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your MongoDB URI
# MONGODB_URI=mongodb://localhost:27017/codeforces
# or
# MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
```

### 3. Run the API Server

```bash
python app.py
```

Server starts on http://localhost:3000

**Open in browser**: You'll see a nice web UI!

**Or use as API**:
```bash
# Health check
curl http://localhost:3000/

# Start scraping
curl -X POST http://localhost:3000/sync

# Get problem
curl http://localhost:3000/problem/1/A

# List all problems
curl http://localhost:3000/index
```

### 4. Scrape Problems

**Option A: Background Sync**
```bash
# Trigger from API (runs in background)
curl -X POST http://localhost:3000/sync
```

**Option B: Command Line**
```bash
# Full sync (takes hours/days for all problems)
python sync.py

# Test with random samples
python fetch_random_samples.py

# Test single problem
python test_scraper.py
```

## Deploy to Hugging Face

### 1. Prepare MongoDB

- Create MongoDB Atlas account (free)
- Create cluster
- Get connection string
- Add to HF Space secrets

### 2. Create HF Space

1. Go to https://huggingface.co/spaces
2. Create new Space with Docker SDK
3. Upload these files:
   - `Dockerfile`
   - `app_hf.py`
   - `requirements-hf.txt`
   - `spaces_config.yaml`
   - `README.md`
   - `lib/` folder
   - `templates/` folder

### 3. Configure Secrets

In Space Settings → Variables and secrets:
- Add `MONGODB_URI` = your connection string

### 4. Deploy

Push files and HF builds automatically!

See `HF_DEPLOYMENT.md` for detailed instructions.

## Key Differences

### app.py vs app_hf.py

| Feature | app.py (Local) | app_hf.py (HF Space) |
|---------|----------------|----------------------|
| Scraping | ✅ Full access | ❌ Read-only |
| `/sync` endpoint | ✅ Works | ❌ Disabled |
| Browser required | ✅ Yes (Selenium) | ❌ No |
| Dependencies | Full (with Selenium) | Minimal (no browser) |
| Port | 3000 (customizable) | 7860 (HF standard) |
| Web UI | ✅ Yes | ✅ Yes |

### Workflow

```
Local (app.py)          HF Space (app_hf.py)
──────────────          ────────────────────
Scrape problems    →    Read-only API
Write to MongoDB   ←──→ Shared MongoDB
Full features           Serve cached data
```

## Architecture

```
┌─────────────────┐
│  Local Machine  │
│   (app.py)      │
│                 │
│ • Scrapes       │
│ • Parses        │
│ • Writes DB     │
│ • Serves API    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  MongoDB Atlas  │
│  (Shared DB)    │
│                 │
│ • Problems      │
│ • Images        │
│ • Index         │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   HF Space      │
│  (app_hf.py)    │
│                 │
│ • Read-only     │
│ • Serves API    │
│ • Web UI        │
└─────────────────┘
```

## Common Commands

```bash
# Check profile status
python manage_profile.py

# Clear profile (start fresh)
python manage_profile.py clear

# Test parser with example HTMLs
python test_parser.py

# Fetch 15 random problems
python fetch_random_samples.py

# Full sync
python sync.py

# Start local API server
python app.py

# Start with custom port
PORT=8000 python app.py
```

## Troubleshooting

### "Module not found"
```bash
# Make sure you're in the right directory
cd CF-scraper-python

# Install dependencies
pip install -r requirements.txt
```

### "MongoDB connection failed"
```bash
# Check .env file exists
cat .env

# Verify MONGODB_URI is set
echo $MONGODB_URI  # Linux/Mac
echo %MONGODB_URI%  # Windows
```

### "Cloudflare blocking requests"
```bash
# Check profile exists
python manage_profile.py

# Clear and recreate
python manage_profile.py clear

# Disable headless mode in lib/browser_config.py
# Comment out: chrome_options.add_argument('--headless=new')
```

### "Browser crashes"
```bash
# Kill any stuck Chrome processes
# Windows: taskkill /F /IM chrome.exe
# Linux/Mac: killall chrome

# Clear profile
python manage_profile.py clear
```

## Next Steps

1. ✅ Run locally with `python app.py`
2. ✅ Scrape some problems
3. ✅ Test the API
4. ✅ Deploy to HF Space (optional)
5. ✅ Integrate with seudoe extension

## Resources

- Full documentation: `README.md`
- HF deployment: `HF_DEPLOYMENT.md`
- Deployment checklist: `HF_CHECKLIST.md`
- Status report: `STATUS.md`
- Persistent profiles: `PERSISTENT_PROFILE_GUIDE.md`
