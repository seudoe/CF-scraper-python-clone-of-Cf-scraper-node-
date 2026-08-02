# Hugging Face Space Troubleshooting

## Current Status Check

**What to check in your HF Space:**

1. **Go to your Space** → Check the status badge at top
2. **Click "Logs" tab** → Look for errors
3. **Check "Settings" tab** → Verify `MONGODB_URI` secret exists

## Common Issues & Fixes

### Issue 1: "Configuration Error" or Won't Start

**Symptoms**: Space shows error about missing configuration

**Fix**: README.md needs proper header (already fixed in latest version)

Verify your README.md starts with:
```yaml
---
title: Codeforces Problem Scraper API
emoji: 🔍
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---
```

### Issue 2: "Building" Stuck Forever

**Symptoms**: Status shows "Building" for >10 minutes

**Fixes**:
1. **Check Build Logs** (Logs tab)
2. **Common causes**:
   - Missing `lib/` folder
   - Missing `templates/` folder
   - Typo in `requirements-hf.txt`
   - `.env.example` file missing

**Solution**: Factory Rebuild
- Go to Settings → Danger Zone → Factory Rebuild

### Issue 3: "Starting" Stuck or 503 Error

**Symptoms**: Built successfully but won't start

**Fixes**:
1. **Check Container Logs** (Logs tab → Container)
2. **Common causes**:
   - Missing `MONGODB_URI` secret
   - App crash on startup
   - Import error

**Solutions**:
- Add `MONGODB_URI` in Settings → Variables and secrets
- Check logs for Python errors
- Verify all files uploaded correctly

### Issue 4: 403 Quota Limit Error

**Symptoms**: "403 cpu-basic quota limit exceeded"

**This is a HF bug** - your account thinks old Spaces are still running

**Fixes**:
1. **Pause ALL other Spaces**:
   - Go to your profile → Spaces
   - Pause every Space except this one
2. **Log out and log in**:
   - Completely log out of HF
   - Clear browser cache
   - Log back in
3. **Wait 5-10 minutes** for quota to sync
4. **Try Factory Rebuild**:
   - Settings → Factory Rebuild
5. **Contact HF Support** if still stuck:
   - Go to https://huggingface.co/support
   - Explain quota not releasing

### Issue 5: "ImportError" or "ModuleNotFoundError"

**Symptoms**: Build succeeds but app crashes with import error

**Fix**: Check `lib/__init__.py` exists

Create empty file if missing:
```bash
# In your Space, add file: lib/__init__.py
# Content: (can be empty)
```

### Issue 6: MongoDB Connection Failed

**Symptoms**: App starts but APIs return database errors

**Fixes**:
1. **Verify `MONGODB_URI` secret**:
   - Settings → Variables and secrets
   - Make sure it's a **Secret** not a Variable
   - Test connection string locally first

2. **Check MongoDB Network Access**:
   - MongoDB Atlas → Network Access
   - Must allow `0.0.0.0/0` (all IPs)

3. **Check MongoDB User Permissions**:
   - User needs read/write on database

## Diagnostic Commands

If you have local git clone of Space:

```bash
# Test Dockerfile locally
docker build -t cf-scraper .
docker run -p 7860:7860 -e MONGODB_URI="your_uri" cf-scraper

# Test app_hf.py locally
PORT=7860 python app_hf.py
```

## Files Checklist

Verify these files exist in your Space:

### Required Files
- [ ] `README.md` (with proper header)
- [ ] `Dockerfile`
- [ ] `app_hf.py`
- [ ] `requirements-hf.txt`
- [ ] `.env.example` (can be empty)

### Required Folders
- [ ] `lib/` with:
  - [ ] `__init__.py`
  - [ ] `db.py`
  - [ ] `colors.py`
  - [ ] `types.py`
- [ ] `templates/` with:
  - [ ] `index.html`

### Optional but Recommended
- [ ] `spaces_config.yaml`
- [ ] `.gitignore`

## Quick Fix Sequence

Try these in order:

1. ✅ **Verify README.md** has proper header
2. ✅ **Add `MONGODB_URI` secret** in Settings
3. ✅ **Check all files uploaded** (use checklist above)
4. ✅ **Factory Rebuild**: Settings → Factory Rebuild
5. ✅ **Wait 2-3 minutes** and refresh page
6. ✅ **Check Logs tab** for errors
7. ✅ **If quota error**: Pause other Spaces, log out/in

## Still Not Working?

### Check Container Logs

1. Go to Logs tab
2. Look for these specific errors:

**"ModuleNotFoundError"**:
- Missing dependency in `requirements-hf.txt`
- Or missing `lib/__init__.py`

**"Address already in use"**:
- Port conflict (shouldn't happen on HF)
- Try Factory Rebuild

**"pymongo.errors"**:
- Missing `MONGODB_URI` secret
- Or wrong connection string

**"No module named 'lib'"**:
- `lib/` folder not uploaded
- Or missing `lib/__init__.py`

### Factory Rebuild Steps

1. Go to your Space
2. Click **Settings** tab (top)
3. Scroll to bottom → **Danger Zone**
4. Click **Factory Rebuild**
5. Confirm
6. Wait 2-5 minutes
7. Check if Space starts

## HF Space Status Meanings

| Status | Meaning | Action |
|--------|---------|--------|
| Building | Installing dependencies | Wait 2-5 min, check Build Logs |
| Starting | Running your app | Wait 30-60s, check Container Logs |
| Running | ✅ App is live | Test your endpoints! |
| Paused | Manually paused | Click "Unpause" button |
| Failed | Build or runtime error | Check Logs, fix, push update |
| Sleeping | Inactive for 48+ hours | Click to wake up |

## Test Your Space

Once "Running", test these:

```bash
# Replace YOUR_SPACE_URL with actual URL

# 1. Health check (browser or curl)
curl https://YOUR_SPACE_URL/

# Expected: {"status": "ok", "service": "cf-scraper-python-hf", ...}

# 2. Get index
curl https://YOUR_SPACE_URL/index

# Expected: {"ids": [...], "count": ...}

# 3. Open in browser
# Should see nice web UI
```

## Environment Variables

Your Space needs this secret:

| Name | Type | Value |
|------|------|-------|
| `MONGODB_URI` | Secret | `mongodb+srv://user:pass@cluster.mongodb.net/` |

**How to add**:
1. Settings tab
2. Scroll to "Variables and secrets"
3. Click "New secret"
4. Name: `MONGODB_URI`
5. Value: Your connection string
6. Save

## Contact Support

If nothing works:

1. **HF Discord**: https://discord.gg/huggingface
2. **HF Forum**: https://discuss.huggingface.co/
3. **Support**: https://huggingface.co/support

Include:
- Your Space URL
- Error message from Logs
- What you've tried

## Common Deployment Mistakes

❌ **Don't do**:
- Upload `chrome-profile/` folder (too large, binary files)
- Upload `example-htmls/` folder (not needed)
- Forget `MONGODB_URI` secret
- Use wrong SDK in README (must be `sdk: docker`)
- Point to wrong app file (must be `app_hf.py`)

✅ **Do**:
- Follow the files checklist above
- Add `MONGODB_URI` as Secret (not Variable)
- Test Docker build locally first
- Check Logs if any issues
- Use Factory Rebuild to force refresh
