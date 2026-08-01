"""
MongoDB connection and collection management
"""

import os
from typing import Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from .colors import blue, green, gray, success, info

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def connect():
    """Connect to MongoDB using MONGODB_URI env var"""
    global _client, _db
    
    if _db is not None:
        return _db
    
    uri = os.getenv('MONGODB_URI')
    if not uri:
        raise ValueError('MONGODB_URI environment variable not set')
    
    print(blue('[db] Connecting to MongoDB ...'))
    _client = MongoClient(uri)
    _db = _client['codeforces']  # Explicitly specify the database name
    print(success('[db] Connected to MongoDB (database: codeforces)'))
    return _db


def get_problems_collection() -> Collection:
    """Returns the 'problems' collection"""
    db = connect()
    return db['problems']


def get_index_collection() -> Collection:
    """Returns the 'problem_index' collection"""
    db = connect()
    return db['problem_index']


def get_images_collection() -> Collection:
    """Returns the 'images' collection"""
    db = connect()
    return db['images']


def close():
    """Close MongoDB connection"""
    global _client
    if _client:
        _client.close()
        print(info('[db] Connection closed'))
