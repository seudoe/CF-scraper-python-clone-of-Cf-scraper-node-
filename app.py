"""
Flask API server for Codeforces problem scraper
Endpoints match the Node.js version for compatibility with seudoe extension
"""

import os
import sys
import threading
from pathlib import Path
from flask import Flask, jsonify, request, Response, render_template
from dotenv import load_dotenv

# Load environment from multiple possible locations
script_dir = Path(__file__).parent.absolute()
env_loaded = False
for env_file in ['.env.local', '.env']:
    env_path = script_dir / env_file
    if env_path.exists():
        load_dotenv(env_path)
        print(f'[env] Loaded {env_file}')
        env_loaded = True
        break

if not env_loaded:
    print('[env] No .env file found, using system environment')

# Verify MONGODB_URI is set
mongodb_uri = os.getenv('MONGODB_URI')
if mongodb_uri:
    print(f'[env] [OK] MONGODB_URI is set (length: {len(mongodb_uri)} chars)')
else:
    print('[env] [X] WARNING: MONGODB_URI is not set!')

from lib.db import get_problems_collection, get_index_collection, get_images_collection
from lib.worker import sync_problems

app = Flask(__name__)


@app.route('/')
def health_check():
    """Health check endpoint or web UI - serves HTML for browsers, JSON for API calls"""
    # Check if request wants JSON (API call) or HTML (browser)
    if request.accept_mimetypes.best == 'application/json' or 'application/json' in request.accept_mimetypes:
        # Return JSON for API calls
        try:
            index_col = get_index_collection()
            doc = index_col.find_one({})
            count = len(doc.get('ids', [])) if doc else 0
            print(f'[api] Health check — scraped problems: {count}')
            return jsonify({'status': 'ok', 'service': 'cf-scraper-python', 'scraped': count})
        except Exception as e:
            print(f'[api] [X] DB connection failed: {e}')
            return jsonify({'status': 'ok', 'service': 'cf-scraper-python', 'dbError': str(e)})
    else:
        # Return HTML UI for browsers
        return render_template('index.html')


@app.route('/sync', methods=['GET', 'POST'])
def sync():
    """Start background sync worker (accepts GET for easy browser testing)"""
    print('[api] Sync requested — starting background worker ...')
    
    def run_sync():
        try:
            result = sync_problems()
            print(f'[api] Sync finished: {result}')
        except Exception as e:
            print(f'[api] Sync error: {e}')
    
    # Run sync in background thread
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    
    return jsonify({'message': 'Sync started. Check server logs for progress.'}), 202


@app.route('/problem/<int:contest_id>/<index>')
def get_problem(contest_id, index):
    """Get a cached problem by contestId and index"""
    index = index.upper()
    print(f'[api] Looking up problem {contest_id}-{index} in DB ...')
    
    try:
        problems_col = get_problems_collection()
        cached = problems_col.find_one({'contestId': contest_id, 'index': index}, {'_id': 0})
        
        if not cached:
            print(f'[api] Problem {contest_id}-{index} not found in DB')
            return jsonify({'error': f'Problem {contest_id}{index} not found. Run /sync first.'}), 404
        
        title = cached.get('statement', {}).get('title', 'Untitled')
        print(f'[api] [OK] Returning problem {contest_id}-{index}: "{title}"')
        
        return jsonify(cached)
        
    except Exception as e:
        print(f'[api] [X] Error fetching problem {contest_id}-{index}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/image/<filename>')
def get_image(filename):
    """Get a cached image by filename"""
    print(f'[api] Fetching image from DB: {filename}')
    
    try:
        images_col = get_images_collection()
        doc = images_col.find_one({'filename': filename})
        
        if not doc:
            print(f'[api] Image not found: {filename}')
            return jsonify({'error': f'Image {filename} not found'}), 404
        
        print(f'[api] [OK] Serving image: {filename} ({doc["contentType"]})')
        
        return Response(
            doc['data'],
            mimetype=doc['contentType'],
            headers={
                'Cache-Control': 'public, max-age=31536000, immutable'
            }
        )
        
    except Exception as e:
        print(f'[api] [X] Error fetching image {filename}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/index')
def get_index():
    """Get list of all scraped problem IDs"""
    print('[api] Fetching problem index ...')
    
    try:
        index_col = get_index_collection()
        doc = index_col.find_one({})
        ids = doc.get('ids', []) if doc else []
        
        print(f'[api] [OK] Index has {len(ids)} scraped problems')
        
        return jsonify({'ids': ids, 'count': len(ids)})
        
    except Exception as e:
        print(f'[api] [X] Error fetching index: {e}')
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    print(f'[api] 404 — unknown route: {request.path}')
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    
    print(f'[server] CF Scraper (Python) running on port {port}')
    print(f'[server] GET/POST /sync   — start scraping')
    print(f'[server] GET  /           — health check')
    print(f'[server] GET  /problem/:contestId/:index')
    print(f'[server] GET  /image/:filename')
    print(f'[server] GET  /index      — list scraped IDs')
    
    app.run(host='0.0.0.0', port=port, debug=False)
