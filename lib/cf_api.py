"""
Codeforces API client - fetches problem list
"""

import requests
from typing import List, Dict


CF_API_URL = 'https://codeforces.com/api/problemset.problems'


def fetch_all_problems() -> List[Dict]:
    """
    Fetches all problems from Codeforces API
    Returns list of dicts with contestId, index, name keys
    """
    print(f'[cf-api] Fetching problem list from {CF_API_URL} ...')
    
    response = requests.get(CF_API_URL, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    if data.get('status') != 'OK':
        raise Exception(f'CF API error: {data}')
    
    problems = data.get('result', {}).get('problems', [])
    
    # Filter out problems without contestId (from gym, etc)
    valid_problems = [
        {
            'contestId': p['contestId'],
            'index': p['index'],
            'name': p.get('name', 'Untitled')
        }
        for p in problems
        if 'contestId' in p and 'index' in p
    ]
    
    print(f'[cf-api] ✓ Fetched {len(valid_problems)} problems from CF API')
    return valid_problems
