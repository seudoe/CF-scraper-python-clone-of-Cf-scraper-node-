# Hugging Face Deployment Checklist

## Pre-Deployment (Local Setup)

- [ ] MongoDB Atlas cluster created
- [ ] Database user created with read/write permissions
- [ ] Network access configured (allow 0.0.0.0/0)
- [ ] Connection string obtained
- [ ] `.env` file configured with `MONGODB_URI`
- [ ] Test local scraper:
  ```bash
  python fetch_random_samples.py
  ```
- [ ] Verify problems in MongoDB Atlas dashboard

## Files to Upload to HF Space

### Required Files
- [ ] `Dockerfile`
- [ ] `app_hf.py`
- [ ] `requirements-hf.txt`
- [ ] `spaces_config.yaml`
- [ ] `README.md`
- [ ] `.gitignore`

### Required Folders
- [ ] `lib/` (with these files):
  - [ ] `lib/__init__.py`
  - [ ] `lib/db.py`
  - [ ] `lib/colors.py`
  - [ ] `lib/types.py`
- [ ] `templates/`
  - [ ] `templates/index.html`

### Optional Files
- [ ] `HF_DEPLOYMENT.md` (documentation)
- [ ] `LICENSE` (if you want)

## HF Space Configuration

- [ ] Create new Space on huggingface.co
- [ ] Set SDK to "Docker"
- [ ] Set Space name (e.g., `codeforces-scraper`)
- [ ] Set visibility (Public or Private)
- [ ] Upload all files
- [ ] Go to Settings → Variables and secrets
- [ ] Add secret: `MONGODB_URI` = your connection string
- [ ] Save and wait for build

## Testing

Once deployed, test these endpoints:

- [ ] Open Space URL in browser → Should see web UI
- [ ] `curl https://YOUR_SPACE.hf.space/` → JSON health check
- [ ] `curl https://YOUR_SPACE.hf.space/index` → Problem IDs list
- [ ] `curl https://YOUR_SPACE.hf.space/problem/1/A` → Problem data
- [ ] (If images exist) `curl https://YOUR_SPACE.hf.space/image/FILENAME`

## Troubleshooting

If build fails:
- [ ] Check build logs in HF Space
- [ ] Verify all files uploaded correctly
- [ ] Check Dockerfile syntax

If database errors:
- [ ] Verify `MONGODB_URI` secret is set
- [ ] Check MongoDB network access (0.0.0.0/0)
- [ ] Test connection string locally first

If no problems showing:
- [ ] Confirm scraper ran locally
- [ ] Check MongoDB has data
- [ ] Verify connection string points to correct database

## Post-Deployment

- [ ] Update README with Space URL
- [ ] Add Space badge to README:
  ```markdown
  [![Open in Spaces](https://huggingface.co/datasets/huggingface/badges/resolve/main/open-in-hf-spaces-md.svg)](https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE)
  ```
- [ ] Test all endpoints
- [ ] Monitor Space logs for errors
- [ ] Set up regular local syncs to add new problems

## Maintenance

### Adding New Problems
```bash
# On local machine
python sync.py

# Problems automatically appear in HF Space
```

### Updating Space
```bash
# Make changes locally
git add .
git commit -m "Update message"
git push

# HF automatically rebuilds
```

### Monitoring
- [ ] Check Space analytics regularly
- [ ] Monitor MongoDB storage usage
- [ ] Watch for API errors in Space logs

## Quick Deploy Commands

```bash
# Clone Space repo
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME

# Copy files
cp -r /path/to/CF-scraper-python/lib .
cp -r /path/to/CF-scraper-python/templates .
cp /path/to/CF-scraper-python/Dockerfile .
cp /path/to/CF-scraper-python/app_hf.py .
cp /path/to/CF-scraper-python/requirements-hf.txt .
cp /path/to/CF-scraper-python/spaces_config.yaml .
cp /path/to/CF-scraper-python/README.md .
cp /path/to/CF-scraper-python/.gitignore .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

## Common Issues

### Issue: Port binding error
**Solution**: HF Spaces use port 7860 by default. The Dockerfile is already configured for this.

### Issue: Module not found
**Solution**: Ensure `lib/__init__.py` exists (can be empty file).

### Issue: Template not found
**Solution**: Verify `templates/` folder uploaded with `index.html` inside.

### Issue: CORS errors
**Solution**: Add Flask-CORS if needed:
```python
from flask_cors import CORS
CORS(app)
```

### Issue: Slow responses
**Solution**: 
- Upgrade to HF Pro
- Add MongoDB indexes
- Consider caching layer

## Resources

- [HF Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [MongoDB Atlas Free Tier](https://www.mongodb.com/cloud/atlas)
- [Docker Documentation](https://docs.docker.com/)
- Project docs: `HF_DEPLOYMENT.md`
