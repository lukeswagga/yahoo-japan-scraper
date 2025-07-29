"""
Database Manager with PostgreSQL/SQLite fallback
Works locally without PostgreSQL, uses PostgreSQL on Railway
"""

import os
import sqlite3
from contextlib import contextmanager

# Try to import PostgreSQL
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseManager:
    def __init__(self):
        # Railway automatically provides DATABASE_URL when PostgreSQL is added
        self.database_url = os.getenv('DATABASE_URL')
        self.use_postgres = bool(self.database_url and POSTGRES_AVAILABLE)
        
        if self.use_postgres:
            print("✅ Using PostgreSQL for persistent storage")
        else:
            print("⚠️ Using SQLite (data will be lost on redeploy)")
            self.db_file = "auction_tracking.db"
    
    @contextmanager
    def get_connection(self):
        """Get database connection (PostgreSQL or SQLite)"""
        if self.use_postgres:
            conn = psycopg2.connect(self.database_url)
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_file)
            try:
                yield conn
            finally:
                conn.close()
    
    def init_database(self):
        """Initialize database tables (works for both PostgreSQL and SQLite)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if self.use_postgres:
                self._create_postgres_tables(cursor)
            else:
                self._create_sqlite_tables(cursor)
            
            conn.commit()
            print("✅ Database tables initialized")
    
    def _create_postgres_tables(self, cursor):
        """Create PostgreSQL tables"""
        # Main listings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                id SERIAL PRIMARY KEY,
                auction_id VARCHAR(100) UNIQUE,
                title TEXT,
                brand VARCHAR(100),
                price_jpy INTEGER,
                price_usd REAL,
                seller_id VARCHAR(100),
                zenmarket_url TEXT,
                yahoo_url TEXT,
                image_url TEXT,
                deal_quality REAL DEFAULT 0.5,
                priority_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_id BIGINT
            )
        ''')
        
        # Reactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                auction_id VARCHAR(100),
                reaction_type VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id BIGINT PRIMARY KEY,
                proxy_service VARCHAR(50) DEFAULT 'zenmarket',
                setup_complete BOOLEAN DEFAULT FALSE,
                notifications_enabled BOOLEAN DEFAULT TRUE,
                min_quality_threshold REAL DEFAULT 0.3,
                max_price_alert REAL DEFAULT 1000.0,
                bookmark_method VARCHAR(20) DEFAULT 'private_channel',
                auto_bookmark_likes BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User bookmarks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_bookmarks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                auction_id VARCHAR(100),
                bookmark_message_id BIGINT,
                bookmark_channel_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, auction_id)
            )
        ''')
        
        # Scraper stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_stats (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_found INTEGER DEFAULT 0,
                quality_filtered INTEGER DEFAULT 0,
                sent_to_discord INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                keywords_searched INTEGER DEFAULT 0
            )
        ''')
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_listings_brand ON listings(brand)",
            "CREATE INDEX IF NOT EXISTS idx_listings_created_at ON listings(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_user_id ON reactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_auction_id ON reactions(auction_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user_id ON user_bookmarks(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_bookmarks_auction_id ON user_bookmarks(auction_id)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"Index warning: {e}")
    
    def _create_sqlite_tables(self, cursor):
        """Create SQLite tables (your existing structure)"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id TEXT UNIQUE,
                title TEXT,
                brand TEXT,
                price_jpy INTEGER,
                price_usd REAL,
                seller_id TEXT,
                zenmarket_url TEXT,
                yahoo_url TEXT,
                image_url TEXT,
                deal_quality REAL DEFAULT 0.5,
                priority_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_id INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                auction_id TEXT,
                reaction_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                proxy_service TEXT DEFAULT 'zenmarket',
                setup_complete BOOLEAN DEFAULT FALSE,
                notifications_enabled BOOLEAN DEFAULT TRUE,
                min_quality_threshold REAL DEFAULT 0.3,
                max_price_alert REAL DEFAULT 1000.0,
                bookmark_method TEXT DEFAULT 'private_channel',
                auto_bookmark_likes BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                auction_id TEXT,
                bookmark_message_id INTEGER,
                bookmark_channel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, auction_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_found INTEGER DEFAULT 0,
                quality_filtered INTEGER DEFAULT 0,
                sent_to_discord INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                keywords_searched INTEGER DEFAULT 0
            )
        ''')
    
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Execute a database query with proper parameter binding"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.use_postgres:
                    # PostgreSQL uses %s for all parameter types
                    query = query.replace('?', '%s')
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                else:
                    # SQLite uses ?
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                else:
                    result = cursor.rowcount
                
                conn.commit()
                return result
                
        except Exception as e:
            print(f"❌ Database execute_query error: {e}")
            print(f"❌ Query: {query}")
            print(f"❌ Params: {params}")
            raise e

# Global database manager instance
db_manager = DatabaseManager()

def get_user_proxy_preference(user_id):
    """Updated to work with both PostgreSQL and SQLite"""
    result = db_manager.execute_query(
        'SELECT proxy_service, setup_complete FROM user_preferences WHERE user_id = ?',
        (user_id,),
        fetch_one=True
    )
    
    if result:
        return result[0], result[1]
    else:
        return "zenmarket", False

def set_user_proxy_preference(user_id, proxy_service):
    """Updated to work with both PostgreSQL and SQLite"""
    if db_manager.use_postgres:
        # PostgreSQL UPSERT
        db_manager.execute_query('''
            INSERT INTO user_preferences (user_id, proxy_service, setup_complete, updated_at)
            VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                proxy_service = EXCLUDED.proxy_service,
                setup_complete = TRUE,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, proxy_service))
    else:
        # SQLite UPSERT
        db_manager.execute_query('''
            INSERT OR REPLACE INTO user_preferences 
            (user_id, proxy_service, setup_complete, updated_at)
            VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
        ''', (user_id, proxy_service))

def add_listing(auction_data, message_id):
    """Updated to work with both PostgreSQL and SQLite"""
    try:
        if db_manager.use_postgres:
            # PostgreSQL UPSERT
            result = db_manager.execute_query('''
                INSERT INTO listings 
                (auction_id, title, brand, price_jpy, price_usd, seller_id, 
                 zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (auction_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    message_id = EXCLUDED.message_id
            ''', (
                auction_data['auction_id'],
                auction_data['title'],
                auction_data['brand'],
                auction_data['price_jpy'],
                auction_data['price_usd'],
                auction_data.get('seller_id', 'unknown'),
                auction_data['zenmarket_url'],
                auction_data.get('yahoo_url', ''),
                auction_data.get('image_url', ''),
                auction_data.get('deal_quality', 0.5),
                auction_data.get('priority', 0.0),
                message_id
            ))
        else:
            # SQLite (your existing code)
            result = db_manager.execute_query('''
                INSERT OR REPLACE INTO listings 
                (auction_id, title, brand, price_jpy, price_usd, seller_id, 
                 zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                auction_data['auction_id'],
                auction_data['title'],
                auction_data['brand'],
                auction_data['price_jpy'],
                auction_data['price_usd'],
                auction_data.get('seller_id', 'unknown'),
                auction_data['zenmarket_url'],
                auction_data.get('yahoo_url', ''),
                auction_data.get('image_url', ''),
                auction_data.get('deal_quality', 0.5),
                auction_data.get('priority', 0.0),
                message_id
            ))
        
        print(f"✅ Successfully added listing to database: {auction_data['auction_id']}")
        return True
        
    except Exception as e:
        print(f"❌ Error adding listing to database: {e}")
        print(f"❌ Auction data: {auction_data}")
        return False

def add_reaction(user_id, auction_id, reaction_type):
    """Updated to work with both PostgreSQL and SQLite"""
    try:
        # Delete existing reaction first
        db_manager.execute_query(
            'DELETE FROM reactions WHERE user_id = ? AND auction_id = ?',
            (user_id, auction_id)
        )
        
        # Insert new reaction
        db_manager.execute_query('''
            INSERT INTO reactions (user_id, auction_id, reaction_type)
            VALUES (?, ?, ?)
        ''', (user_id, auction_id, reaction_type))
        
        return True
    except Exception as e:
        print(f"❌ Error adding reaction: {e}")
        return False

def add_bookmark(user_id, auction_id, bookmark_message_id, bookmark_channel_id):
    """Add a bookmark for a user"""
    try:
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_bookmarks (user_id, auction_id, bookmark_message_id, bookmark_channel_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, auction_id) DO UPDATE SET
                    bookmark_message_id = EXCLUDED.bookmark_message_id,
                    bookmark_channel_id = EXCLUDED.bookmark_channel_id,
                    created_at = CURRENT_TIMESTAMP
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id))
        else:
            db_manager.execute_query('''
                INSERT OR REPLACE INTO user_bookmarks 
                (user_id, auction_id, bookmark_message_id, bookmark_channel_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id))
        
        return True
    except Exception as e:
        print(f"❌ Error adding bookmark: {e}")
        return False

def get_user_bookmarks(user_id, limit=10):
    """Get user's bookmarks"""
    return db_manager.execute_query('''
        SELECT ub.auction_id, l.title, l.brand, l.price_usd, l.zenmarket_url, ub.created_at
        FROM user_bookmarks ub
        JOIN listings l ON ub.auction_id = l.auction_id
        WHERE ub.user_id = ?
        ORDER BY ub.created_at DESC
        LIMIT ?
    ''', (user_id, limit), fetch_all=True)

def clear_user_bookmarks(user_id):
    """Clear all bookmarks for a user"""
    try:
        count_result = db_manager.execute_query(
            'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?',
            (user_id,),
            fetch_one=True
        )
        
        count = count_result[0] if count_result else 0
        
        if count > 0:
            db_manager.execute_query(
                'DELETE FROM user_bookmarks WHERE user_id = ?',
                (user_id,)
            )
        
        return count
    except Exception as e:
        print(f"❌ Error clearing bookmarks: {e}")
        return 0
