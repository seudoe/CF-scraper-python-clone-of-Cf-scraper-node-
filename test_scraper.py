"""Test script to verify scraper functionality"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json

# Add the script directory to Python path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

from lib.scraper import scrape_problem

# Load environment from multiple possible locations
env_loaded = False
for env_file in ['.env.local', '.env', '../.env.local', '../.env']:
    env_path = script_dir / env_file
    if env_path.exists():
        load_dotenv(env_path)
        print(f'[test] Loaded {env_file} from {env_path}')
        env_loaded = True
        break

if not env_loaded:
    print('[test] No .env file found, using system environment')

# Verify MONGODB_URI is set
mongodb_uri = os.getenv('MONGODB_URI')
if mongodb_uri:
    print(f'[test] ✓ MONGODB_URI is set (length: {len(mongodb_uri)} chars)')
else:
    print('[test] ✗ WARNING: MONGODB_URI is not set!')

def test_single_problem():
    """Test scraping a single problem"""
    print('\n[test] ════════════════════════════════')
    print('[test] Testing scraper with problem 158-A')
    print('[test] ════════════════════════════════\n')
    
    try:
        result = scrape_problem(158, 'A')
        
        print('\n[test] ════════════════════════════════')
        print('[test] ✓ Scrape successful!')
        print(f'[test] Title: {result["statement"]["title"]}')
        print(f'[test] Time Limit: {result["statement"]["timeLimit"]}')
        print(f'[test] Memory Limit: {result["statement"]["memoryLimit"]}')
        print(f'[test] Examples: {len(result["statement"]["examples"])}')
        print(f'[test] Description blocks: {len(result["statement"]["description"])}')
        print(f'[test] Input blocks: {len(result["statement"]["input"])}')
        print(f'[test] Output blocks: {len(result["statement"]["output"])}')
        
        # Save to file for inspection
        with open('test_output.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print('[test] Saved output to test_output.json')
        
        print('[test] ════════════════════════════════\n')
        return True
        
    except Exception as e:
        print(f'\n[test] ✗ Test failed: {str(e)}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_single_problem()
    exit(0 if success else 1)
