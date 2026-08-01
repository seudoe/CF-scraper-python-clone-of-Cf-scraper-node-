"""
Hugging Face Spaces entry point.
Simplified version that doesn't require browser for serving cached problems.
"""

import os
from flask import Flask, jsonify, request, Response, render_template
from lib.db import get_problems_collection, get_index_collection, get_images_collection

app = Flask(__name__)

# Get port from environment (HF Spaces uses 7860)
PORT = int(os.getenv('PORT', 7860))

print('[hf-app] Starting Codeforces Scraper API (read-only mode)')

# Test MongoDB connection
mongodb_uri = os.getenv('MONGODB_URI')
if mongodb_uri:
    print(f'[hf-app] [OK] MONGODB_URI is set')
else:
    print('[hf-app] [!] WARNING: MONGODB_URI not set - using default')


@app.route('/')
def index():
    """Serve HTML UI or JSON based on Accept header"""
    # Check if request wants JSON (API call) or HTML (browser)
    if request.accept_mimetypes.best == 'application/json' or 'application/json' in request.accept_mimetypes:
        # Return JSON for API calls
        try:
            problems_col = get_problems_collection()
            count = problems_col.count_documents({})
            return jsonify({'status': 'ok', 'service': 'cf-scraper-python-hf', 'scraped': count})
        except Exception as e:
            print(f'[hf-app] [X] DB connection failed: {e}')
            return jsonify({'status': 'ok', 'service': 'cf-scraper-python-hf', 'dbError': str(e)})
    else:
        # Return HTML UI for browsers
        return render_template('index.html')


@app.route('/problem/<int:contest_id>/<string:index>')
def get_problem(contest_id, index):
    """Get a specific problem by contestId and index"""
    try:
        problem_id = f'{contest_id}-{index}'
        problems_col = get_problems_collection()
        
        cached = problems_col.find_one({'contestId': contest_id, 'index': index})
        
        if not cached:
            return jsonify({'error': f'Problem {problem_id} not found'}), 404
        
        # Remove MongoDB _id field
        if '_id' in cached:
            del cached['_id']
        
        title = cached.get('statement', {}).get('title', 'Untitled')
        print(f'[hf-app] [OK] Returning problem {contest_id}-{index}: "{title}"')
        
        return jsonify(cached)
        
    except Exception as e:
        print(f'[hf-app] [X] Error fetching problem {contest_id}-{index}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/image/<string:filename>')
def get_image(filename):
    """Get a cached image by filename"""
    try:
        images_col = get_images_collection()
        
        doc = images_col.find_one({'filename': filename})
        
        if not doc:
            return jsonify({'error': f'Image {filename} not found'}), 404
        
        print(f'[hf-app] [OK] Serving image: {filename} ({doc["contentType"]})')
        
        return Response(
            doc['data'],
            mimetype=doc['contentType'],
            headers={'Cache-Control': 'public, max-age=31536000'}  # Cache for 1 year
        )
        
    except Exception as e:
        print(f'[hf-app] [X] Error fetching image {filename}: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/index')
def get_index():
    """Get list of all scraped problem IDs"""
    try:
        index_col = get_index_collection()
        doc = index_col.find_one({})
        
        ids = doc.get('ids', []) if doc else []
        
        print(f'[hf-app] [OK] Index has {len(ids)} scraped problems')
        
        return jsonify({'ids': ids, 'count': len(ids)})
        
    except Exception as e:
        print(f'[hf-app] [X] Error fetching index: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/sync', methods=['POST'])
def sync():
    """Sync endpoint - disabled in HF Spaces (read-only)"""
    return jsonify({
        'error': 'Sync disabled in Hugging Face Spaces',
        'message': 'This is a read-only deployment. Scraping should be done locally.'
    }), 403


if __name__ == '__main__':
    print(f'[hf-app] Starting Flask server on port {PORT}')
    print(f'[hf-app] Read-only mode - serving cached problems from MongoDB')
    app.run(host='0.0.0.0', port=PORT, debug=False)
