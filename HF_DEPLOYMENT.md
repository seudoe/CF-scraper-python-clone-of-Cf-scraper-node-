# Hugging Face Spaces Deployment Guide

## Overview

This guide explains how to deploy the Codeforces scraper API to Hugging Face Spaces.

**Important**: The HF Space serves **read-only** access to cached problems. The actual scraping must be done locally and problems uploaded to MongoDB.

## Architecture

```
Local Machine                    HF Space (Read-Only)              MongoDB Atlas
─────────────                    ───────────────────              ─────────────
[Scraper]                        [Flask API]                      [Problems DB]
  ↓                                    ↑                                ↑
  ↓ Scrapes problems                   │ Reads problems                 │
  ↓                                    │                                │
  └──────────────────→ MongoDB ←───────┴────────────────────────────────┘
     Writes problems              Shared Database
```

### Why Read-Only on HF?

1. **Browser Limitations**: HF Spaces can't run Chrome/Selenium reliably
2. **Cloudflare Challenges**: Would fail without persistent profile
3. **Resource Intensive**: Scraping requires significant CPU/memory
4. **Better Separation**: Scrape locally, serve globally

## Prerequisites

1. **MongoDB Atlas Account** (free tier works)
2. **Hugging Face Account**
3. **Local scraper running** to populate MongoDB

## Step 1: Set Up MongoDB Atlas

### Create Cluster

1. Go to https://www.mongodb.com/cloud/atlas
2. Create free cluster
3. Go to Security → Database Access
4. Create database user with read/write permissions
5. Go to Security → Network Access
6. Add IP: `0.0.0.0/0` (allow from anywhere - for HF Spaces)

### Get Connection String

1. Go to Database → Connect
2. Choose "Connect your application"
3. Copy connection string:
   ```
   mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```

### Create Database and Collections

The scraper will create these automatically, but you can pre-create:

- Database: `codeforces`
- Collections:
  - `problems` - Problem data
  - `problem_index` - List of scraped IDs
  - `images` - Image cache

## Step 2: Configure Local Scraper

### Set MongoDB URI

Edit `.env` file:

```bash
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### Run Initial Scrape

```bash
# Scrape a few problems to test
python fetch_random_samples.py

# Or scrape specific problems
python test_scraper.py

# Or run full sync (will take hours/days)
python sync.py
```

### Verify Data in MongoDB

1. Go to MongoDB Atlas → Browse Collections
2. You should see:
   - `problems` collection with problem documents
   - `problem_index` with list of IDs
   - `images` with cached images

## Step 3: Create Hugging Face Space

### Create New Space

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Fill in:
   - **Owner**: Your username
   - **Space name**: `codeforces-scraper` (or your choice)
   - **License**: MIT
   - **SDK**: Docker
   - **Visibility**: Public or Private

### Configure Space Files

Your Space needs these files (already created):

```
Space Root/
├── Dockerfile              # Docker configuration
├── app_hf.py              # HF-optimized Flask app (read-only)
├── requirements-hf.txt    # Minimal dependencies (no Selenium)
├── spaces_config.yaml     # HF Space metadata
├── README.md              # Documentation
└── lib/                   # Support modules
    ├── db.py
    ├── colors.py
    └── types.py
```

### Upload Files to Space

**Option A: Git CLI**

```bash
# Clone your Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME

# Copy necessary files
cp /path/to/CF-scraper-python/Dockerfile .
cp /path/to/CF-scraper-python/app_hf.py .
cp /path/to/CF-scraper-python/requirements-hf.txt .
cp /path/to/CF-scraper-python/spaces_config.yaml .
cp /path/to/CF-scraper-python/README.md .
cp -r /path/to/CF-scraper-python/lib .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

**Option B: Web UI**

1. Go to your Space → Files
2. Click "Add file"
3. Upload each file manually

### Set Environment Variables (Secrets)

1. Go to Space → Settings → Variables and secrets
2. Add secret:
   - **Name**: `MONGODB_URI`
   - **Value**: Your MongoDB connection string
   - **Type**: Secret (hidden)

## Step 4: Deploy and Test

### Wait for Build

HF will automatically:
1. Build Docker image
2. Install dependencies
3. Start Flask app on port 7860

Watch the build logs in the Space.

### Test Endpoints

Once running, test your API:

```bash
# Health check
curl https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/

# Get problem index
curl https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/index

# Get specific problem
curl https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/problem/1/A

# Get image
curl https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space/image/1-A_diagram.png
```

## Step 5: Maintain Data

### Update Problems

To add new problems:

```bash
# On your local machine
python sync.py

# Problems automatically appear in HF Space
# (HF Space reads from same MongoDB)
```

### Monitor Usage

1. HF Spaces have generous free tier
2. Monitor in Space → Analytics
3. If needed, upgrade to paid tier for more resources

## Troubleshooting

### "Database connection failed"

- Check `MONGODB_URI` secret is set correctly
- Verify MongoDB Network Access allows `0.0.0.0/0`
- Check database user has correct permissions

### "Problem not found"

- Verify problem was scraped locally
- Check MongoDB collections have data
- Confirm `MONGODB_URI` points to correct cluster/database

### Space Build Failed

- Check Dockerfile syntax
- Verify all files were uploaded
- Check build logs for specific errors

### Slow Response

- MongoDB free tier can be slow
- Consider upgrading to paid tier
- Add indexes to MongoDB collections:
  ```javascript
  db.problems.createIndex({ "contestId": 1, "index": 1 })
  db.images.createIndex({ "filename": 1 })
  ```

## API Documentation for HF Space

### GET /

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "cf-scraper-python-hf",
  "scraped": 1234
}
```

### GET /problem/:contestId/:index

Get problem data.

**Example:** `/problem/1/A`

**Response:**
```json
{
  "contestId": 1,
  "index": "A",
  "statement": {
    "title": "Theatre Square",
    "description": [...],
    "input": [...],
    "output": [...],
    "examples": [...]
  }
}
```

### GET /image/:filename

Get cached image.

**Example:** `/image/1-A_diagram.png`

**Response:** Image binary with appropriate `Content-Type`

### GET /index

Get all scraped problem IDs.

**Response:**
```json
{
  "ids": ["1-A", "1-B", "2-A", ...],
  "count": 1234
}
```

### POST /sync

**Not available in HF Space** (read-only deployment).

Returns 403 error with message to scrape locally.

## Costs

### Free Tier Includes

- **HF Spaces**: Generous free tier for Docker apps
- **MongoDB Atlas**: 512 MB storage free
- **Bandwidth**: Reasonable for API usage

### If You Need More

- **HF Spaces Pro**: ~$9/month for more CPU/RAM
- **MongoDB**: ~$9/month for 2GB storage
- Consider:
  - Caching layer (Redis)
  - CDN for images
  - Database indexes for speed

## Security Notes

### What's Safe to Share

- HF Space URL (public API)
- MongoDB read-only connection string (if needed)

### Keep Secret

- MongoDB write connection string
- Database admin credentials
- Local scraper setup

### Recommendations

1. Use separate MongoDB users for:
   - Local scraper (read/write)
   - HF Space (read-only recommended)

2. Enable MongoDB audit logging

3. Monitor API usage for abuse

## Next Steps

1. ✅ Deploy to HF Spaces
2. ✅ Test all endpoints
3. 📝 Update README with Space URL
4. 🔄 Run periodic local syncs to add new problems
5. 📊 Monitor usage and performance
6. 🎨 (Optional) Add web UI to Space

## Workflow Summary

```
You (Local) ──┐
              ├──> Scrape Problems ──> MongoDB Atlas
              │                            │
              └──────────────────────────────┤
                                             │
HF Space (Public) ──> Read Problems ◄───────┘
                                             │
Users (API) ──> Request Problems ◄───────────┘
```

This architecture gives you:
- ✅ Reliable scraping (local with persistent profile)
- ✅ Public API (HF Space with global access)
- ✅ Shared storage (MongoDB Atlas)
- ✅ No browser issues on HF
- ✅ Easy updates (scrape locally → automatically in API)
