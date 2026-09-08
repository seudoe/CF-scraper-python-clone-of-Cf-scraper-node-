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

        '''
so take the new one and all of its associated files
and make new - that does this 

  1. checks syncronization between index and data :
  a. RAW_HTML and index
  b. local_json and index
  c. mongo_json and its index

  2. checks syncronization between indexes
  a. between RAW_HTML-index and local_json-index
  b. local_json-index and mongo_json-index

  2A. FETCHES/SCRAPES IF RAW_HTML is missing 
  and parses from RAW_HTML if other two are missing

  SO all lists become syncronized no exceptions in here

  THEN comes the actual updation part (scraping new problems)
  3. Fetches the problems list from cf/api 
  and compares with RAW_HTML-index 
  and scrapes the remaining problems (not present in raw-html-index)
  and parses them -> saves into local-json @saved-from-reparse -> saves into mongo-json

SCRAPE AND PARSES intructions
  1. PROPERLY (maths-latex, question-paras, images, input-output
  examples)  (heavy importance) scrapes the problem statements from
  website
  2. save the scraped html into RAW_HTML/100-range and updates the
  index
  3. PROPERLY (again all things mentioned above) parses into json
  4. all three saving must be done one problem after another (no bulking of problems)

Im saying properly because one mistake in last parser caused me to re-scrape all 11 thousand problems
thats why the name 'reparse' 

make a new folder named pipeline/
make chrome-cookies-checker.py (this pastes cookies from my chrome to selenium, because of heavy bot-detection on the site)
scraper.py
parser.py
pipeline.py (uses others and does the work and saves the problem)
        '''