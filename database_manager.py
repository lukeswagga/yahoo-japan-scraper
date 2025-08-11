"""
Database Manager with PostgreSQL/SQLite fallback
Works locally without PostgreSQL, uses PostgreSQL on Railway
"""

import os
import sqlite3
from contextlib import contextmanager
import re

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseManager:
    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        
        # Railway provides DATABASE_URL in Postgres 12+ format, convert if needed
        if database_url and database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            os.environ['DATABASE_URL'] = database_url
        
        self.database_url = database_url
        self.use_postgres = bool(self.database_url and POSTGRES_AVAILABLE)
        
        if self.use_postgres:
            print("✅ Using PostgreSQL for persistent storage")
            print(f"📊 Database URL format: {self.database_url[:30]}...")
        else:
            print("⚠️ Using SQLite (data will be lost on redeploy)")
            self.db_file = "auction_tracking.db"
    
    @contextmanager
    def get_connection(self):
        """Get database connection (PostgreSQL or SQLite)"""
        if self.use_postgres:
            try:
                # Add connection parameters for Railway
                conn = psycopg2.connect(
                    self.database_url,
                    sslmode='require',
                    connect_timeout=10
                )
                conn.autocommit = False
                try:
                    yield conn
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    conn.close()
            except psycopg2.OperationalError as e:
                print(f"❌ PostgreSQL connection failed: {e}")
                print("Falling back to SQLite...")
                self.use_postgres = False
                self.db_file = "auction_tracking.db"
                conn = sqlite3.connect(self.db_file)
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
        """Create PostgreSQL tables with auction end time tracking"""
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
                message_id BIGINT,
                auction_end_time TIMESTAMP,
                reminder_1h_sent BOOLEAN DEFAULT FALSE,
                reminder_5m_sent BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                auction_id VARCHAR(100),
                reaction_type VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
                preferred_sizes TEXT,
                size_alerts_enabled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_bookmarks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                auction_id VARCHAR(100),
                bookmark_message_id BIGINT,
                bookmark_channel_id BIGINT,
                auction_end_time TIMESTAMP,
                reminder_sent_1h BOOLEAN DEFAULT FALSE,
                reminder_sent_5m BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, auction_id)
            )
        ''')
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE,
                tier VARCHAR(20) DEFAULT 'free',
                upgraded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                payment_provider VARCHAR(50),
                subscription_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_listings_brand ON listings(brand)",
            "CREATE INDEX IF NOT EXISTS idx_listings_created_at ON listings(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_listings_auction_end ON listings(auction_end_time)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_user_id ON reactions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_auction_id ON reactions(auction_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user_id ON user_bookmarks(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_bookmarks_auction_id ON user_bookmarks(auction_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_bookmarks_end_time ON user_bookmarks(auction_end_time)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"Index warning: {e}")
    
    def _create_sqlite_tables(self, cursor):
        """Create SQLite tables with auction end time tracking"""
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
                message_id INTEGER,
                auction_end_time TIMESTAMP,
                reminder_1h_sent BOOLEAN DEFAULT FALSE,
                reminder_5m_sent BOOLEAN DEFAULT FALSE
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
                preferred_sizes TEXT,
                size_alerts_enabled BOOLEAN DEFAULT FALSE,
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
                auction_end_time TIMESTAMP,
                reminder_sent_1h BOOLEAN DEFAULT FALSE,
                reminder_sent_5m BOOLEAN DEFAULT FALSE,
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                tier TEXT DEFAULT 'free',
                upgraded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                payment_provider TEXT,
                subscription_id TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Execute a database query with proper parameter binding"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if self.use_postgres:
                    query = query.replace('?', '%s')
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                else:
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

db_manager = DatabaseManager()

def get_user_proxy_preference(user_id):
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
    if db_manager.use_postgres:
        db_manager.execute_query('''
            INSERT INTO user_preferences (user_id, proxy_service, setup_complete, updated_at)
            VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                proxy_service = EXCLUDED.proxy_service,
                setup_complete = TRUE,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, proxy_service))
    else:
        db_manager.execute_query('''
            INSERT OR REPLACE INTO user_preferences 
            (user_id, proxy_service, setup_complete, updated_at)
            VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
        ''', (user_id, proxy_service))

def add_listing(auction_data, message_id):
    try:
        auction_end_time = auction_data.get('auction_end_time')
        
        if db_manager.use_postgres:
            result = db_manager.execute_query('''
                INSERT INTO listings 
                (auction_id, title, brand, price_jpy, price_usd, seller_id, 
                 zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, message_id, auction_end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (auction_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    message_id = EXCLUDED.message_id,
                    auction_end_time = EXCLUDED.auction_end_time
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
                message_id,
                auction_end_time
            ))
        else:
            result = db_manager.execute_query('''
                INSERT OR REPLACE INTO listings 
                (auction_id, title, brand, price_jpy, price_usd, seller_id, 
                 zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, message_id, auction_end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                message_id,
                auction_end_time
            ))
        
        print(f"✅ Successfully added listing to database: {auction_data['auction_id']}")
        return True
        
    except Exception as e:
        print(f"❌ Error adding listing to database: {e}")
        return False

def add_reaction(user_id, auction_id, reaction_type):
    try:
        db_manager.execute_query(
            'DELETE FROM reactions WHERE user_id = ? AND auction_id = ?',
            (user_id, auction_id)
        )
        
        db_manager.execute_query('''
            INSERT INTO reactions (user_id, auction_id, reaction_type)
            VALUES (?, ?, ?)
        ''', (user_id, auction_id, reaction_type))
        
        return True
    except Exception as e:
        print(f"❌ Error adding reaction: {e}")
        return False

def add_bookmark(user_id, auction_id, bookmark_message_id, bookmark_channel_id, auction_end_time=None):
    try:
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_bookmarks (user_id, auction_id, bookmark_message_id, bookmark_channel_id, auction_end_time)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, auction_id) DO UPDATE SET
                    bookmark_message_id = EXCLUDED.bookmark_message_id,
                    bookmark_channel_id = EXCLUDED.bookmark_channel_id,
                    auction_end_time = EXCLUDED.auction_end_time,
                    created_at = CURRENT_TIMESTAMP
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id, auction_end_time))
        else:
            db_manager.execute_query('''
                INSERT OR REPLACE INTO user_bookmarks 
                (user_id, auction_id, bookmark_message_id, bookmark_channel_id, auction_end_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id, auction_end_time))
        
        return True
    except Exception as e:
        print(f"❌ Error adding bookmark: {e}")
        return False

def get_user_bookmarks(user_id, limit=10):
    return db_manager.execute_query('''
        SELECT ub.auction_id, l.title, l.brand, l.price_usd, l.zenmarket_url, ub.created_at, l.auction_end_time
        FROM user_bookmarks ub
        JOIN listings l ON ub.auction_id = l.auction_id
        WHERE ub.user_id = ?
        ORDER BY ub.created_at DESC
        LIMIT ?
    ''', (user_id, limit), fetch_all=True)

def get_pending_reminders(reminder_type='1h'):
    if reminder_type == '1h':
        if db_manager.use_postgres:
            query = '''
                SELECT DISTINCT ub.user_id, ub.auction_id, ub.bookmark_channel_id, 
                       l.title, l.zenmarket_url, l.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.reminder_sent_1h = FALSE
                AND l.auction_end_time IS NOT NULL
                AND l.auction_end_time > NOW()
                AND l.auction_end_time <= NOW() + INTERVAL '1 hour'
            '''
        else:
            query = '''
                SELECT DISTINCT ub.user_id, ub.auction_id, ub.bookmark_channel_id, 
                       l.title, l.zenmarket_url, l.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.reminder_sent_1h = 0
                AND l.auction_end_time IS NOT NULL
                AND l.auction_end_time > datetime('now')
                AND l.auction_end_time <= datetime('now', '+1 hour')
            '''
    else:
        if db_manager.use_postgres:
            query = '''
                SELECT DISTINCT ub.user_id, ub.auction_id, ub.bookmark_channel_id, 
                       l.title, l.zenmarket_url, l.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.reminder_sent_5m = FALSE
                AND l.auction_end_time IS NOT NULL
                AND l.auction_end_time > NOW()
                AND l.auction_end_time <= NOW() + INTERVAL '5 minutes'
            '''
        else:
            query = '''
                SELECT DISTINCT ub.user_id, ub.auction_id, ub.bookmark_channel_id, 
                       l.title, l.zenmarket_url, l.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.reminder_sent_5m = 0
                AND l.auction_end_time IS NOT NULL
                AND l.auction_end_time > datetime('now')
                AND l.auction_end_time <= datetime('now', '+5 minutes')
            '''
    
    return db_manager.execute_query(query, fetch_all=True)

def mark_reminder_sent(user_id, auction_id, reminder_type='1h'):
    if reminder_type == '1h':
        query = 'UPDATE user_bookmarks SET reminder_sent_1h = TRUE WHERE user_id = ? AND auction_id = ?'
    else:
        query = 'UPDATE user_bookmarks SET reminder_sent_5m = TRUE WHERE user_id = ? AND auction_id = ?'
    
    db_manager.execute_query(query, (user_id, auction_id))

def clear_user_bookmarks(user_id):
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

def get_user_size_preferences(user_id):
    result = db_manager.execute_query(
        'SELECT preferred_sizes, size_alerts_enabled FROM user_preferences WHERE user_id = ?',
        (user_id,),
        fetch_one=True
    )
    
    if result and result[0]:
        sizes = result[0].split(',') if result[0] else []
        enabled = result[1] if result[1] is not None else False
        return sizes, enabled
    return [], False

def set_user_size_preferences(user_id, sizes):
    sizes_str = ','.join(sizes) if sizes else ''
    
    if db_manager.use_postgres:
        db_manager.execute_query('''
            INSERT INTO user_preferences (user_id, preferred_sizes, size_alerts_enabled, updated_at)
            VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                preferred_sizes = EXCLUDED.preferred_sizes,
                size_alerts_enabled = TRUE,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, sizes_str))
    else:
        db_manager.execute_query('''
            INSERT OR REPLACE INTO user_preferences 
            (user_id, preferred_sizes, size_alerts_enabled, updated_at)
            VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
        ''', (user_id, sizes_str))

def init_subscription_tables():
    try:
        print("🔧 Initializing subscription tables...")
        db_manager.init_database()
        print("✅ Subscription tables initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing subscription tables: {e}")
        return False

def test_postgres_connection():
    try:
        if not db_manager.use_postgres:
            print("⚠️ Using SQLite, not PostgreSQL")
            return False
            
        result = db_manager.execute_query('SELECT version()', fetch_one=True)
        if result:
            print(f"✅ PostgreSQL connected: {result[0][:50]}...")
        
        if db_manager.use_postgres:
            tables = db_manager.execute_query('''
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            ''', fetch_all=True)
        else:
            tables = db_manager.execute_query('''
                SELECT name FROM sqlite_master WHERE type='table'
            ''', fetch_all=True)
        
        print(f"📊 Existing tables: {[table[0] for table in tables] if tables else 'None'}")
        
        for table_name, in (tables or []):
            try:
                count = db_manager.execute_query(f'SELECT COUNT(*) FROM {table_name}', fetch_one=True)
                print(f"   {table_name}: {count[0] if count else 0} rows")
            except:
                print(f"   {table_name}: Error counting rows")
        
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection test failed: {e}")
        return False