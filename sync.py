"""Standalone sync script - run manually to sync problems"""
import os
from dotenv import load_dotenv
from lib.worker import sync_problems

# Load environment
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f'[sync] Loaded {env_file}')
else:
    print('[sync] No .env file found, using system environment')

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
