"""
Timing utilities for human-like behavior patterns.
Helps bypass Cloudflare by avoiding robotic timing patterns.
"""

import time
import random
from .colors import cyan, info

# Randomized wait range (in seconds)
MIN_WAIT = 7
MAX_WAIT = 15


def random_wait(min_seconds=MIN_WAIT, max_seconds=MAX_WAIT, reason="next request"):
    """
    Wait a random amount of time to mimic human behavior.
    
    Cloudflare detects robotic timing patterns. By randomizing delays,
    we appear more like a human browsing the site.
    
    Args:
        min_seconds: Minimum wait time in seconds
        max_seconds: Maximum wait time in seconds
        reason: Description of what we're waiting for (for logging)
    """
    wait_time = random.uniform(min_seconds, max_seconds)
    print(cyan(f'[timing] Waiting {wait_time:.1f}s before {reason}...'))
    time.sleep(wait_time)


def random_page_delay():
    """
    Short random delay simulating human reading/processing time.
    Use this after page loads before taking action.
    """
    delay = random.uniform(0.5, 2.0)
    time.sleep(delay)


def progressive_backoff(attempt, base_delay=5, max_delay=60):
    """
    Progressive backoff for retries. Increases wait time with each attempt.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        
    Returns:
        float: Delay time in seconds
    """
    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 3), max_delay)
    return delay
