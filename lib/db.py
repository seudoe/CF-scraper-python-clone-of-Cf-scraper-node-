"""
MongoDB connection and collection management
"""

import os
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

_client: MongoClient = None
_db: Database = None


def connect():
    """Connect to MongoDB using MONGODB_URI env var"""
    global _client, _db
    
    if _db is not None:
        return _db
    
    uri = os.getenv('MONGODB_URI')
    if not uri:
        raise ValueError('MONGODB_URI environment variable not set')
    
    print('[db] Connecting to MongoDB ...')
    _client = MongoClient(uri)
    _db = _client.get_database()
    print('[db] ✓ Connected to MongoDB')
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
        print('[db] Connection closed')
