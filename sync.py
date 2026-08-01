"""Standalone sync script - run manually to sync problems"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the script directory to Python path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

from lib.worker import sync_problems

# Load environment from multiple possible locations
env_loaded = False
for env_file in ['.env.local', '.env', '../.env.local', '../.env']:
    env_path = script_dir / env_file
    if env_path.exists():
        load_dotenv(env_path)
        print(f'[sync] Loaded {env_file} from {env_path}')
        env_loaded = True
        break

if not env_loaded:
    print('[sync] No .env file found, using system environment')

# Verify MONGODB_URI is set
mongodb_uri = os.getenv('MONGODB_URI')
if mongodb_uri:
    print(f'[sync] ✓ MONGODB_URI is set (length: {len(mongodb_uri)} chars)')
else:
    print('[sync] ✗ WARNING: MONGODB_URI is not set!')

if __name__ == '__main__':
    print('\n[sync] Starting manual sync ...\n')
    
    try:
        result = sync_problems()
        print(f'\n[sync] ✓ Sync completed successfully')
        print(f'[sync] Results: {result}')
        exit(0)
        
    except Exception as e:
        print(f'\n[sync] ✗ Sync failed: {str(e)}')
        import traceback
        traceback.print_exc()
        exit(1)
