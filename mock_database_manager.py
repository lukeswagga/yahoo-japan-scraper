"""
Mock database manager for testing the notification tier system
"""

import os
from datetime import datetime, timezone

class MockDatabaseManager:
    """Mock database manager for testing"""
    
    def __init__(self):
        self.use_postgres = False
        self.database_url = None
        self.db_path = 'test_auction_tracking.db'
        print("🗄️ Using mock SQLite database for testing")
    
    def init_database(self):
        """Mock database initialization"""
        print("✅ Mock database initialized")
    
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Mock query execution"""
        # Return mock data for testing
        if 'SELECT tier FROM user_subscriptions' in query:
            return {'tier': 'free'} if fetch_one else [{'tier': 'free'}]
        elif 'SELECT daily_count, last_reset FROM user_subscriptions' in query:
            return {'daily_count': 0, 'last_reset': datetime.now(timezone.utc)} if fetch_one else [{'daily_count': 0, 'last_reset': datetime.now(timezone.utc)}]
        elif 'SELECT user_id FROM user_subscriptions' in query:
            return [{'user_id': 123456789}] if fetch_all else None
        elif 'SELECT * FROM daily_digest_queue' in query:
            return [] if fetch_all else None
        elif 'INSERT' in query or 'UPDATE' in query or 'DELETE' in query:
            return True
        else:
            return None

# Mock the database manager
db_manager = MockDatabaseManager()

# Mock functions that might be imported
def get_user_proxy_preference(user_id):
    return 'zenmarket'

def set_user_proxy_preference(user_id, preference):
    return True

def add_listing(auction_data, message_id):
    return True

def add_user_bookmark(user_id, auction_id, bookmark_message_id, bookmark_channel_id):
    return True

def clear_user_bookmarks(user_id):
    return True

def init_subscription_tables():
    return True

def test_postgres_connection():
    return False

def get_user_size_preferences(user_id):
    return []

def set_user_size_preferences(user_id, sizes):
    return True

def mark_reminder_sent(user_id, auction_id, reminder_type):
    return True
