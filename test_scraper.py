"""Test script to verify scraper functionality"""
import os
from dotenv import load_dotenv
from lib.scraper import scrape_problem
import json

# Load environment
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f'[test] Loaded {env_file}')

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
