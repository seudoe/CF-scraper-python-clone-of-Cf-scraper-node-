# Cloudflare Handling Guide

This scraper has two fetching strategies to handle Cloudflare protection:

## Strategy 1: Regular Selenium (fetch.py)
- ✅ Works on most platforms
- ✅ Easier to deploy
- ⚠️ Less reliable against Cloudflare
- ⚠️ May get blocked after many requests

**Current implementation** uses this approach with:
- Proper wait for `problem-statement` element (up to 30s)
- Cloudflare challenge detection and retry (up to 30s more)
- Detailed error messages to identify Cloudflare blocks
- Better than the old "sleep 4 seconds" approach

## Strategy 2: undetected-chromedriver (fetch_undetected.py)
- ✅ Much better Cloudflare bypass
- ✅ Can scrape 1000s of problems reliably
- ✅ Maintains browser session across requests
- ✅ Periodically visits homepage to look human
- ⚠️ May have deployment issues on some platforms
- ⚠️ Slightly slower due to extra checks

## How to Switch to Undetected Mode

### 1. Install the dependency:
```bash
pip install undetected-chromedriver
```

### 2. Update imports in scraper.py:
```python
# Change this line:
from .fetch import fetch_html, fetch_image_as_buffer

# To this:
from .fetch_undetected import fetch_html, fetch_image_as_buffer
```

### 3. (Optional) Run headless for production:
Edit `lib/fetch_undetected.py` and uncomment:
```python
options.add_argument('--headless=new')
```

## What the Improved Fetcher Does

### 1. Proper Waiting
Instead of blind `time.sleep(4)`:
```python
# Wait for actual content or Cloudflare challenge
WebDriverWait(driver, 30).until(
    lambda d: d.find_elements(By.CLASS_NAME, 'problem-statement') or
              'Just a moment' in d.title
)
```

### 2. Cloudflare Detection
Checks for multiple Cloudflare indicators:
- `"Just a moment"` in title
- `"Performing security verification"` in HTML
- `"challenge-platform"` in HTML
- `"cf-chl"` in HTML

### 3. Extended Wait for Challenges
If Cloudflare detected, waits up to 45 more seconds for resolution.

### 4. Clear Error Messages
Instead of generic "Could not parse", you get:
```
✗ Cloudflare challenge not resolved - got verification page
```

### 5. Session Persistence (undetected mode)
Keeps same browser across all requests and periodically visits homepage.

### 6. Request Counting
Logs request number in session to help debug patterns.

## Recommendations

### For Testing (Local Development)
Use **undetected-chromedriver** without headless:
- More reliable
- Can see what's happening
- Better success rate

### For Production Deployment
Try both approaches:
1. Start with **regular Selenium** (simpler deployment)
2. If you get lots of Cloudflare blocks, switch to **undetected-chromedriver**

### For Scraping All 11,000+ Problems
**Definitely use undetected-chromedriver** with:
- Session persistence ✓ (already implemented)
- Periodic homepage visits ✓ (every 50 requests)
- Retry logic ✓ (retries once on Cloudflare)
- Consider adding random delays between requests (1-3 seconds)
- Consider scraping in batches (e.g., 1000 problems per session)

## Common Cloudflare Errors

### "Just a moment..."
**Cause**: Cloudflare Turnstile challenge not resolved  
**Solution**: Wait longer, use undetected-chromedriver, or retry

### "Performing security verification"
**Cause**: Cloudflare bot detection triggered  
**Solution**: Use undetected-chromedriver, reduce request rate

### "Got HTML but no problem-statement"
**Cause**: Page loaded but wrong content (login, error, etc.)  
**Solution**: Check the saved HTML file to see what you actually got

## Testing the Fetcher

Run this to test with real problems:
```bash
python test_scraper.py
```

Or fetch fresh samples:
```bash
python fetch_random_samples.py
```

## Success Indicators

### Good Signs ✓
```
[fetch] ✓ Got problem HTML (122.2 KB) - problem-statement found
[parse] ✓ Parsed 1758-B: 1 examples, 0 images
```

### Bad Signs ✗
```
[fetch] ✗ Got Cloudflare challenge page (26.5 KB)
[parse] ✗ Could not find .problem-statement in HTML
```

Note: Cloudflare challenge pages are typically ~26KB while real problem pages are 60-150KB.
