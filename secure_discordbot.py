import discord
from discord.ext import commands
import re
from datetime import datetime, timezone, timedelta
import asyncio
from flask import Flask, request, jsonify
import threading
import os
import logging
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import hmac
import hashlib
import random
from webhook_security import secure_webhook_required

# Optional Stripe imports
try:
    from stripe_integration import StripeManager
    from subscription_commands import SubscriptionCommands
    STRIPE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Stripe not available: {e}")
    StripeManager = None
    SubscriptionCommands = None
    STRIPE_AVAILABLE = False
from database_manager import (
    db_manager, get_user_proxy_preference, set_user_proxy_preference, 
    add_listing, add_user_bookmark, clear_user_bookmarks,
    init_subscription_tables, test_postgres_connection,
    get_user_size_preferences, set_user_size_preferences, mark_reminder_sent
)

# Tier system imports
try:
    from tier_manager import TierManager
    from priority_calculator import PriorityCalculator
    from channel_router import ChannelRouter
    from digest_manager import DigestManager
    TIER_SYSTEM_AVAILABLE = True
    print("✅ Tier system modules imported successfully")
except ImportError as e:
    print(f"⚠️ Tier system modules not available: {e}")
    TierManager = None
    PriorityCalculator = None
    ChannelRouter = None
    DigestManager = None
    TIER_SYSTEM_AVAILABLE = False
# Optional imports for advanced features
try:
    from notification_tiers import tier_manager
    from daily_scheduler import daily_scheduler
    ADVANCED_FEATURES_AVAILABLE = True
    print("✅ Advanced features (notification tiers, daily scheduler) loaded successfully")
except ImportError as e:
    print(f"⚠️ Advanced features not available: {e}")
    print("📝 Bot will run with basic functionality only")
    tier_manager = None
    daily_scheduler = None
    ADVANCED_FEATURES_AVAILABLE = False

# Set up secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Input validation and sanitization
class InputValidator:
    @staticmethod
    def sanitize_username(username: str) -> str:
        """Sanitize username for safe use in channel names"""
        if not username:
            return "user"
        # Remove dangerous characters, limit length
        safe_username = re.sub(r'[^a-zA-Z0-9\-_]', '', username)
        return safe_username[:20] or "user"
    
    @staticmethod
    def validate_auction_id(auction_id: str) -> bool:
        """Validate auction ID format"""
        if not auction_id or len(auction_id) > 50:
            return False
        # Yahoo auction IDs are typically alphanumeric with specific patterns
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', auction_id))
    
    @staticmethod
    def validate_sizes(sizes: list) -> bool:
        """Validate size input"""
        if not isinstance(sizes, list):
            return False
        
        if len(sizes) > 20:  # Limit number of sizes
            return False
        
        valid_size_patterns = [
            r'^[XxSsMmLl]+$',  # XS, S, M, L, XL, etc.
            r'^\d{1,2}(?:\.\d)?$',  # Numeric sizes like 30, 30.5
            r'^\d{1,2}(?:\.\d)?\s*(?:US|EU|UK)$',  # 30 US, 30.5 EU
        ]
        
        for size in sizes:
            if not isinstance(size, str) or len(size) > 10:
                return False
            
            size_valid = any(re.match(pattern, size, re.IGNORECASE) for pattern in valid_size_patterns)
            if not size_valid:
                return False
        
        return True
    
    @staticmethod
    def sanitize_command_input(text: str) -> str:
        """Sanitize user input for commands"""
        if not text:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', text)
        return sanitized[:1000]  # Limit length
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        if not url or len(url) > 500:
            return False
        
        # Check for valid URL patterns
        valid_domains = [
            'zenmarket.jp', 'buyee.jp', 'page.auctions.yahoo.co.jp',
            'jp.mercari.com', 'ebay.com', 'grailed.com'
        ]
        
        url_lower = url.lower()
        return any(domain in url_lower for domain in valid_domains)
    
    @staticmethod
    def sanitize_channel_name(name: str) -> str:
        """Sanitize channel name for safe creation"""
        if not name:
            return "channel"
        
        # Remove dangerous characters, limit length
        safe_name = re.sub(r'[^a-zA-Z0-9\-_#]', '', name)
        return safe_name[:32] or "channel"  # Discord limit is 32 chars

# Initialize input validator
input_validator = InputValidator()

def get_user_size_preferences(user_id):
    """Get user's size preferences and alert status"""
    try:
        result = db_manager.execute_query(
            'SELECT sizes, size_alerts_enabled FROM user_preferences WHERE user_id = %s' if db_manager.use_postgres else 'SELECT sizes, size_alerts_enabled FROM user_preferences WHERE user_id = ?',
            (user_id,),
            fetch_one=True
        )
        
        if result:
            sizes = result[0] if isinstance(result, (list, tuple)) else result['sizes']
            enabled = result[1] if isinstance(result, (list, tuple)) else result['size_alerts_enabled']
            
            if sizes:
                size_list = sizes.split(',') if isinstance(sizes, str) else sizes
                return [s.strip() for s in size_list], bool(enabled)
            
        return [], False
        
    except Exception as e:
        logger.error(f"Error getting size preferences for user {user_id}: {str(e)}")
        return [], False

def set_user_size_preferences(user_id, sizes):
    """Set user's size preferences"""
    try:
        sizes_str = ','.join(sizes) if sizes else ''
        
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_preferences (user_id, sizes, size_alerts_enabled)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (user_id) DO UPDATE SET
                    sizes = EXCLUDED.sizes,
                    size_alerts_enabled = TRUE
            ''', (user_id, sizes_str))
        else:
            db_manager.execute_query('''
                INSERT OR REPLACE INTO user_preferences 
                (user_id, sizes, size_alerts_enabled)
                VALUES (?, ?, 1)
            ''', (user_id, sizes_str))
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting size preferences for user {user_id}: {str(e)}")
        return False

def add_user_bookmark(user_id, auction_id, bookmark_message_id, bookmark_channel_id):
    """Add a user bookmark to the database"""
    try:
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_bookmarks (user_id, auction_id, bookmark_message_id, bookmark_channel_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, auction_id) DO UPDATE SET
                    bookmark_message_id = EXCLUDED.bookmark_message_id,
                    bookmark_channel_id = EXCLUDED.bookmark_channel_id
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id))
        else:
            db_manager.execute_query('''
                INSERT OR REPLACE INTO user_bookmarks 
                (user_id, auction_id, bookmark_message_id, bookmark_channel_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, auction_id, bookmark_message_id, bookmark_channel_id))
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding bookmark for user {user_id}, auction {auction_id}: {str(e)}")
        return False





class SizeAlertSystem:
    def __init__(self, bot):
        self.bot = bot
        self.size_mappings = {
            's': ['s', 'small', '44', '46', 'サイズs'],
            'm': ['m', 'medium', '48', '50', 'サイズm'],
            'l': ['l', 'large', '52', 'サイズl'],
            'xl': ['xl', 'x-large', '54', 'サイズxl'],
            'xxl': ['xxl', 'xx-large', '56', 'サイズxxl']
        }
    
    def normalize_size(self, size_str):
        """Normalize size string to standard format"""
        size_lower = size_str.lower().strip()
        
        for standard_size, variations in self.size_mappings.items():
            if size_lower in variations:
                return standard_size
        
        return size_lower
    
    async def check_user_size_match(self, user_id, sizes_found):
        """Check if listing matches user's preferred sizes"""
        if not sizes_found:
            return False
        
        user_sizes, enabled = get_user_size_preferences(user_id)
        
        if not enabled or not user_sizes:
            return False
        
        normalized_found = [self.normalize_size(s) for s in sizes_found]
        normalized_user = [self.normalize_size(s) for s in user_sizes]
        
        return any(size in normalized_user for size in normalized_found)
    
    async def send_size_alert(self, user_id, listing_data):
        """Send size-specific alert to user"""
        try:
            user = self.bot.get_user(user_id)
            if not user:
                user = await self.bot.fetch_user(user_id)
            
            size_channel = discord.utils.get(guild.text_channels, name="🔔-size-alerts")
            if not size_channel:
                return
            
            sizes_str = ", ".join(listing_data.get('sizes', []))
            
            embed = discord.Embed(
                title=f"🔔 Size Alert: {sizes_str}",
                description=f"Found an item in your size!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📦 Item",
                value=listing_data['title'][:200],
                inline=False
            )
            
            embed.add_field(
                name="🏷️ Brand",
                value=listing_data['brand'],
                inline=True
            )
            
            embed.add_field(
                name="💰 Price",
                value=f"¥{listing_data['price_jpy']:,} (${listing_data['price_usd']:.2f})",
                inline=True
            )
            
            embed.add_field(
                name="📏 Sizes Available",
                value=sizes_str,
                inline=True
            )
            
            embed.add_field(
                name="🛒 Links",
                value=f"[ZenMarket]({listing_data['zenmarket_url']})",
                inline=False
            )
            
            if listing_data.get('image_url'):
                embed.set_thumbnail(url=listing_data['image_url'])
            
            embed.set_footer(text=f"ID: {listing_data['auction_id']} | Set sizes with !set_sizes")
            
            await size_channel.send(f"{user.mention} - Size match found!", embed=embed)
            print(f"🔔 Sent size alert to {user.name} for sizes: {sizes_str}")
            
        except Exception as e:
            print(f"❌ Error sending size alert: {e}")

# Simple health server for Railway
class SimpleHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/health', '/ping', '/']:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "discord-bot",
                "uptime_seconds": int(time.time() - start_time),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

app = Flask(__name__)
start_time = time.time()

@app.route('/health', methods=['GET'])
def health():
    try:
        # Check if Discord bot is connected
        bot_status = "connected" if bot.is_ready() else "connecting"
        
        # Check if advanced features are available
        advanced_status = "available" if ADVANCED_FEATURES_AVAILABLE else "limited"
        
        return jsonify({
            "status": "healthy",
            "service": "discord-bot",
            "bot_status": bot_status,
            "advanced_features": advanced_status,
            "uptime_seconds": int(time.time() - start_time),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "service": "discord-bot", 
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "Archive Collective Discord Bot", 
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint for Railway healthchecks"""
    return jsonify({
        "status": "ok",
        "message": "pong",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }), 200

def load_secure_config():
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    guild_id = os.getenv('GUILD_ID')
    
    if not bot_token:
        print("❌ SECURITY ERROR: DISCORD_BOT_TOKEN environment variable not set!")
        exit(1)
    
    if not guild_id:
        print("❌ SECURITY ERROR: GUILD_ID environment variable not set!")
        exit(1)
    
    if len(bot_token) < 50 or not bot_token.startswith(('M', 'N', 'O')):
        logger.error("SECURITY ERROR: Invalid Discord bot token format detected!")
        exit(1)
    
    logger.info("SECURITY: Secure configuration loaded from environment variables")
    logger.info(f"Bot token validated successfully (length: {len(bot_token)} characters)")
    
    return {
        'bot_token': bot_token,
        'guild_id': int(guild_id)
    }

try:
    config = load_secure_config()
    BOT_TOKEN = config['bot_token']
    GUILD_ID = config['guild_id']
except Exception as e:
    print(f"❌ SECURITY FAILURE: Could not load secure config: {e}")
    exit(1)

AUCTION_CATEGORY_NAME = "🎯 AUCTION SNIPES"
AUCTION_CHANNEL_NAME = "🎯-auction-alerts"

batch_buffer = []
BATCH_SIZE = 10  # Increase from 4 to 10
BATCH_TIMEOUT = 60  # Increase from 30 to 60 seconds
last_batch_time = None

SUPPORTED_PROXIES = {
    "zenmarket": {
        "name": "ZenMarket",
        "emoji": "🛒",
        "url_template": "https://zenmarket.jp/en/auction.aspx?itemCode={auction_id}",
        "description": "Popular proxy service with English support"
    },
    "buyee": {
        "name": "Buyee", 
        "emoji": "📦",
        "url_template": "https://buyee.jp/item/yahoo/auction/{auction_id}",
        "description": "Official partner of Yahoo Auctions"
    },
    "yahoo_japan": {
        "name": "Yahoo Japan Direct",
        "emoji": "🇯🇵", 
        "url_template": "https://page.auctions.yahoo.co.jp/jp/auction/{auction_id}",
        "description": "Direct access (requires Japanese address)"
    }
}

BRAND_CHANNEL_MAP = {
    "Vetements": "vetements",
    "Alyx": "alyx", 
    "Anonymous Club": "anonymous-club",
    "Balenciaga": "balenciaga",
    "Bottega Veneta": "bottega-veneta",
    "Celine": "celine",
    "Chrome Hearts": "chrome-hearts",
    "Comme Des Garcons": "comme-des-garcons",
    "Gosha Rubchinskiy": "gosha-rubchinskiy",
    "Helmut Lang": "helmut-lang",
    "Hood By Air": "hood-by-air",
    "Miu Miu": "miu-miu",
    "Hysteric Glamour": "hysteric-glamour",
    "Junya Watanabe": "junya-watanabe",
    "Kiko Kostadinov": "kiko-kostadinov",
    "Maison Margiela": "maison-margiela",
    "Martine Rose": "martine-rose",
    "Prada": "prada",
    "Raf Simons": "raf-simons",
    "Rick Owens": "rick-owens",
    "Undercover": "undercover",
    "Jean Paul Gaultier": "jean-paul-gaultier",
    "Yohji Yamamoto": "yohji_yamamoto",
    "Issey Miyake": "issey-miyake"  # NEW: Added Issey Miyake
}

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Stripe manager
stripe_manager = None
if STRIPE_AVAILABLE:
    try:
        stripe_manager = StripeManager()
        print("✅ Stripe manager initialized")
    except Exception as e:
        print(f"⚠️ Stripe initialization failed: {e}")
        stripe_manager = None
else:
    print("⚠️ Stripe not available - install stripe package")

guild = None
auction_channel = None
brand_channels_cache = {}
reminder_system = None
size_alert_system = None

class UserPreferenceLearner:
    def __init__(self):
        self.init_learning_tables()
    
    def init_learning_tables(self):
        try:
            db_manager.execute_query('''
                CREATE TABLE IF NOT EXISTS user_seller_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    seller_id VARCHAR(100),
                    likes INTEGER DEFAULT 0,
                    dislikes INTEGER DEFAULT 0,
                    trust_score REAL DEFAULT 0.5,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, seller_id)
                )
            ''' if db_manager.use_postgres else '''
                CREATE TABLE IF NOT EXISTS user_seller_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    seller_id TEXT,
                    likes INTEGER DEFAULT 0,
                    dislikes INTEGER DEFAULT 0,
                    trust_score REAL DEFAULT 0.5,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, seller_id)
                )
            ''')
            
            db_manager.execute_query('''
                CREATE TABLE IF NOT EXISTS user_brand_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    brand VARCHAR(100),
                    likes INTEGER DEFAULT 0,
                    dislikes INTEGER DEFAULT 0,
                    preference_score REAL DEFAULT 0.5,
                    avg_liked_price REAL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, brand)
                )
            ''' if db_manager.use_postgres else '''
                CREATE TABLE IF NOT EXISTS user_brand_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    brand TEXT,
                    likes INTEGER DEFAULT 0,
                    dislikes INTEGER DEFAULT 0,
                    preference_score REAL DEFAULT 0.5,
                    avg_liked_price REAL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, brand)
                )
            ''')
            
            db_manager.execute_query('''
                CREATE TABLE IF NOT EXISTS user_item_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    item_category VARCHAR(100),
                    size_preference VARCHAR(50),
                    max_price_usd REAL,
                    min_quality_score REAL DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            ''' if db_manager.use_postgres else '''
                CREATE TABLE IF NOT EXISTS user_item_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    item_category TEXT,
                    size_preference TEXT,
                    max_price_usd REAL,
                    min_quality_score REAL DEFAULT 0.3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            ''')
            
            print("✅ User preference learning tables initialized")
            
        except Exception as e:
            print(f"❌ Error initializing learning tables: {e}")
    
    def learn_from_reaction(self, user_id, auction_data, reaction_type):
        try:
            is_positive = (reaction_type == "thumbs_up")
            
            self._update_seller_preference(user_id, auction_data, is_positive)
            self._update_brand_preference(user_id, auction_data, is_positive)
            self._update_item_preferences(user_id, auction_data, is_positive)
            
            print(f"🧠 Updated preferences for user {user_id} based on {reaction_type}")
            
        except Exception as e:
            print(f"❌ Error learning from reaction: {e}")
    
    def _update_seller_preference(self, user_id, auction_data, is_positive):
        seller_id = auction_data.get('seller_id', 'unknown')
        
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_seller_preferences (user_id, seller_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, seller_id) DO NOTHING
            ''', (user_id, seller_id))
        else:
            db_manager.execute_query('''
                INSERT OR IGNORE INTO user_seller_preferences (user_id, seller_id)
                VALUES (?, ?)
            ''', (user_id, seller_id))
        
        if is_positive:
            db_manager.execute_query('''
                UPDATE user_seller_preferences 
                SET likes = likes + 1, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND seller_id = ?
            ''', (user_id, seller_id))
        else:
            db_manager.execute_query('''
                UPDATE user_seller_preferences 
                SET dislikes = dislikes + 1, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND seller_id = ?
            ''', (user_id, seller_id))
        
        result = db_manager.execute_query('''
            SELECT likes, dislikes FROM user_seller_preferences 
            WHERE user_id = ? AND seller_id = ?
        ''', (user_id, seller_id), fetch_one=True)
        
        if result:
            likes, dislikes = result
            total_reactions = likes + dislikes
            trust_score = likes / total_reactions if total_reactions > 0 else 0.5
            
            db_manager.execute_query('''
                UPDATE user_seller_preferences 
                SET trust_score = ? WHERE user_id = ? AND seller_id = ?
            ''', (trust_score, user_id, seller_id))
    
    def _update_brand_preference(self, user_id, auction_data, is_positive):
        brand = auction_data.get('brand', '')
        
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_brand_preferences (user_id, brand)
                VALUES (%s, %s)
                ON CONFLICT (user_id, brand) DO NOTHING
            ''', (user_id, brand))
        else:
            db_manager.execute_query('''
                INSERT OR IGNORE INTO user_brand_preferences (user_id, brand)
                VALUES (?, ?)
            ''', (user_id, brand))
        
        if is_positive:
            db_manager.execute_query('''
                UPDATE user_brand_preferences 
                SET likes = likes + 1, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND brand = ?
            ''', (user_id, brand))
            
            result = db_manager.execute_query('''
                SELECT avg_liked_price, likes FROM user_brand_preferences 
                WHERE user_id = ? AND brand = ?
            ''', (user_id, brand), fetch_one=True)
            
            if result:
                current_avg, likes = result
                new_price = auction_data.get('price_usd', 0)
                new_avg = ((current_avg * (likes - 1)) + new_price) / likes if likes > 0 else new_price
                
                db_manager.execute_query('''
                    UPDATE user_brand_preferences 
                    SET avg_liked_price = ? WHERE user_id = ? AND brand = ?
                ''', (new_avg, user_id, brand))
        else:
            db_manager.execute_query('''
                UPDATE user_brand_preferences 
                SET dislikes = dislikes + 1, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND brand = ?
            ''', (user_id, brand))
        
        result = db_manager.execute_query('''
            SELECT likes, dislikes FROM user_brand_preferences 
            WHERE user_id = ? AND brand = ?
        ''', (user_id, brand), fetch_one=True)
        
        if result:
            likes, dislikes = result
            total_reactions = likes + dislikes
            preference_score = likes / total_reactions if total_reactions > 0 else 0.5
            
            db_manager.execute_query('''
                UPDATE user_brand_preferences 
                SET preference_score = ? WHERE user_id = ? AND brand = ?
            ''', (preference_score, user_id, brand))
    
    def _update_item_preferences(self, user_id, auction_data, is_positive):
        if is_positive:
            price_usd = auction_data.get('price_usd', 0)
            quality_score = auction_data.get('deal_quality', 0.5)
            
            if db_manager.use_postgres:
                db_manager.execute_query('''
                    INSERT INTO user_item_preferences (user_id, max_price_usd, min_quality_score)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        max_price_usd = GREATEST(user_item_preferences.max_price_usd, EXCLUDED.max_price_usd),
                        min_quality_score = LEAST(user_item_preferences.min_quality_score, EXCLUDED.min_quality_score)
                ''', (user_id, price_usd, quality_score))
            else:
                db_manager.execute_query('''
                    INSERT OR REPLACE INTO user_item_preferences 
                    (user_id, max_price_usd, min_quality_score)
                    VALUES (?, 
                        COALESCE((SELECT MAX(max_price_usd, ?) FROM user_item_preferences WHERE user_id = ?), ?),
                        COALESCE((SELECT MIN(min_quality_score, ?) FROM user_item_preferences WHERE user_id = ?), ?)
                    )
                ''', (user_id, price_usd, user_id, price_usd, quality_score, user_id, quality_score))

    def is_likely_spam(self, title, brand):
        title_lower = title.lower()
        
        LUXURY_SPAM_PATTERNS = {
            "Celine": [
                "レディース", "women", "femme", "ladies",
                "wallet", "財布", "purse", "bag", "バッグ", "ポーチ", "pouch",
                "earring", "pierce", "ピアス", "イヤリング", "ring", "指輪",
                "necklace", "ネックレス", "bracelet", "ブレスレット",
                "perfume", "香水", "fragrance", "cologne", "cosmetic", "化粧品",
                "keychain", "キーホルダー", "sticker", "ステッカー"
            ],
            "Bottega Veneta": [
                "wallet", "財布", "purse", "clutch", "クラッチ",
                "bag", "バッグ", "handbag", "ハンドバッグ", "tote", "トート",
                "pouch", "ポーチ", "case", "ケース",
                "earring", "pierce", "ピアス", "イヤリング", "ring", "指輪",
                "necklace", "ネックレス", "bracelet", "ブレスレット",
                "heel", "ヒール", "pump", "パンプ", "sandal", "サンダル",
                "dress", "ドレス", "skirt", "スカート",
                "perfume", "香水", "fragrance"
            ],
            "Undercover": [
                "cb400sf", "cb1000sf", "cb1300sf", "cb400sb", "cbx400f", "cb750f",
                "vtr250", "ジェイド", "ホーネット", "undercowl", "アンダーカウル",
                "mr2", "bmw", "エンジン", "motorcycle", "engine", "5upj",
                "アンダーカバー", "under cover", "フロント", "リア"
            ],
            "Rick Owens": [
                "ifsixwasnine", "share spirit", "kmrii", "14th addiction", "goa",
                "civarize", "fuga", "tornado mart", "l.g.b", "midas", "ekam"
            ],
            "Chrome Hearts": [
                "luxe", "luxe/r", "luxe r", "ラグジュ", "LUXE/R", "doll bear"
            ]
        }
        
        if brand in LUXURY_SPAM_PATTERNS:
            for pattern in LUXURY_SPAM_PATTERNS[brand]:
                if pattern.lower() in title_lower:
                    print(f"🚫 {brand} spam detected: {pattern}")
                    return True
        
        ARCHIVE_KEYWORDS = [
            "archive", "アーカイブ", "vintage", "ヴィンテージ", "rare", "レア",
            "runway", "ランウェイ", "collection", "コレクション", "fw", "ss",
            "mainline", "メインライン", "homme", "オム"
        ]
        
        for keyword in ARCHIVE_KEYWORDS:
            if keyword.lower() in title_lower:
                print(f"✅ Archive item detected: {keyword} - allowing through")
                return False
        
        generic_spam = ["motorcycle", "engine", "server", "perfume", "香水"]
        
        for pattern in generic_spam:
            if pattern in title_lower:
                return True
        
        return False

def final_spam_check(listing_data):
    """Final spam check before Discord sending with enhanced filtering"""
    title = listing_data.get('title', '')
    brand = listing_data.get('brand', '')
    title_lower = title.lower()
    
    # NEW HIGH PRIORITY EXCLUSIONS (same as in core_scraper_base.py)
    new_excluded_keywords = {
        "LEGO", "レゴ",  # LEGO blocks
        "Water Tank", "ウォータータンク", "水タンク",  # Water tanks
        "BMW Touring E91", "BMW E91", "E91",  # BMW car parts
        "Mazda", "マツダ",  # Mazda car parts
        "Band of Outsiders", "バンドオブアウトサイダーズ"  # Unwanted brand
    }
    
    for excluded in new_excluded_keywords:
        if excluded.lower() in title_lower:
            print(f"🚫 FINAL SPAM CHECK - NEW EXCLUSION BLOCKED: {excluded}")
            return True
    
    # STRICT JDirectItems FILTERING
    if "jdirectitems" in title_lower:
        import re
        pattern = r'jdirectitems auction.*?→\s*([^,\n]+)'
        match = re.search(pattern, title_lower)
        if match:
            category = match.group(1).strip().lower()
            
            # Only allow fashion-related categories
            allowed_categories = {
                "fashion", "clothing", "apparel", 
                "ファッション", "衣類", "服", "洋服"
            }
            
            if not any(allowed in category for allowed in allowed_categories):
                print(f"🚫 FINAL SPAM CHECK - JDirectItems NON-FASHION BLOCKED: {category}")
                return True
            else:
                print(f"✅ FINAL SPAM CHECK - JDirectItems FASHION ALLOWED: {category}")
    
    # Use existing spam detection
    if preference_learner and preference_learner.is_likely_spam(title, brand):
        print(f"🚫 FINAL SPAM CHECK - Existing spam patterns detected")
        return True
    
    print(f"✅ FINAL SPAM CHECK - Listing passed all filters")
    return False

def create_enhanced_listing_embed(listing_data):
    """Create enhanced embed with scraper-specific styling"""
    title = listing_data.get('title', '')
    brand = listing_data.get('brand', '')
    price_jpy = listing_data.get('price_jpy', 0)
    price_usd = listing_data.get('price_usd', 0)
    deal_quality = listing_data.get('deal_quality', 0.5)
    priority = listing_data.get('priority', 0.0)
    seller_id = listing_data.get('seller_id', 'unknown')
    zenmarket_url = listing_data.get('zenmarket_url', '')
    image_url = listing_data.get('image_url', '')
    auction_id = listing_data.get('auction_id', '')
    auction_end_time = listing_data.get('auction_end_time', None)
    sizes = listing_data.get('sizes', [])
    scraper_source = listing_data.get('scraper_source', 'unknown')
    
    # Scraper-specific colors and emojis
    scraper_config = {
        'ending_soon_scraper': {'color': 0xff6b6b, 'emoji': '⏰', 'name': 'Ending Soon'},
        'budget_steals_scraper': {'color': 0x4ecdc4, 'emoji': '💰', 'name': 'Budget Steal'},
        'new_listings_scraper': {'color': 0x45b7d1, 'emoji': '🆕', 'name': 'New Listing'},
        'buy_it_now_scraper': {'color': 0x96ceb4, 'emoji': '🛒', 'name': 'Buy It Now'}
    }
    
    # Get scraper-specific styling
    config = scraper_config.get(scraper_source, {'color': 0xff4444, 'emoji': '📦', 'name': 'Auction'})
    
    # Quality-based color override
    if deal_quality >= 0.8 or priority >= 100:
        config['color'] = 0x00ff00
        quality_emoji = "🔥"
    elif deal_quality >= 0.6 or priority >= 70:
        config['color'] = 0xffa500
        quality_emoji = "🌟"
    else:
        quality_emoji = "⭐"
    
    display_title = title
    if len(display_title) > 100:
        display_title = display_title[:97] + "..."
    
    # Enhanced description with scraper info
    description = f"{config['emoji']} **{config['name']}**\n"
    description += f"💴 **¥{price_jpy:,}** (~${price_usd:.2f})\n"
    description += f"🏷️ **{brand.replace('_', ' ').title()}**\n"
    description += f"{quality_emoji} **Quality: {deal_quality:.1%}** | **Priority: {priority:.0f}**\n"
    description += f"👤 **Seller:** {seller_id}\n"

    if sizes:
        description += f"📏 **Sizes:** {', '.join(sizes)}\n"
    
    # Add scraper-specific metadata
    if listing_data.get('is_ending_soon'):
        description += f"⏰ **Ending Soon**\n"
    if listing_data.get('is_budget_steal'):
        description += f"💰 **Budget Steal**\n"
    if listing_data.get('is_new_listing'):
        description += f"🆕 **New Listing**\n"
    if listing_data.get('is_buy_it_now'):
        description += f"🛒 **Buy It Now**\n"
    
    # Add time remaining if available
    if auction_end_time:
        try:
            end_dt = datetime.fromisoformat(auction_end_time.replace('Z', '+00:00'))
            time_remaining = end_dt - datetime.now(timezone.utc)
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                description += f"⏰ **Time Remaining:** {hours}h {minutes}m\n"
        except:
            pass
    
    auction_id_clean = auction_id.replace('yahoo_', '')
    link_section = "\n**🛒 Proxy Links:**\n"
    for key, proxy_info in SUPPORTED_PROXIES.items():
        proxy_url = generate_proxy_url(auction_id_clean, key)
        link_section += f"{proxy_info['emoji']} [{proxy_info['name']}]({proxy_url})\n"
    
    description += link_section
    
    embed = discord.Embed(
        title=display_title,
        url=zenmarket_url,
        description=description,
        color=config['color'],
        timestamp=datetime.now(timezone.utc)
    )
    
    if image_url:
        embed.set_thumbnail(url=image_url)
    
    embed.set_footer(text=f"ID: {auction_id} | Source: {config['name']} | !setup for proxy config | React 👍/👎 to train")
    
    return embed

preference_learner = None

def generate_proxy_url(auction_id, proxy_service):
    if proxy_service not in SUPPORTED_PROXIES:
        proxy_service = "zenmarket"
    
    clean_auction_id = auction_id.replace("yahoo_", "")
    template = SUPPORTED_PROXIES[proxy_service]["url_template"]
    return template.format(auction_id=clean_auction_id)

async def get_or_create_auction_channel():
    global guild, auction_channel
    
    if not guild:
        return None
    
    if auction_channel and auction_channel.guild:
        return auction_channel
    
    for channel in guild.text_channels:
        if channel.name == AUCTION_CHANNEL_NAME:
            auction_channel = channel
            return auction_channel
    
    try:
        category = None
        for cat in guild.categories:
            if cat.name == AUCTION_CATEGORY_NAME:
                category = cat
                break
        
        if not category:
            category = await guild.create_category(AUCTION_CATEGORY_NAME)
        
        auction_channel = await guild.create_text_channel(
            AUCTION_CHANNEL_NAME,
            category=category,
            topic="All auction listings - React with 👍/👎 to help the bot learn!"
        )
        
        return auction_channel
        
    except Exception as e:
        print(f"❌ Error creating auction channel: {e}")
        return None

async def get_or_create_brand_channel(brand_name):
    global guild, brand_channels_cache
    
    if not guild:
        print(f"❌ No guild available for brand channel creation")
        return None
        
    if brand_name not in BRAND_CHANNEL_MAP:
        print(f"❌ Brand '{brand_name}' not in channel map")
        return None
    
    channel_name = BRAND_CHANNEL_MAP[brand_name]
    full_channel_name = f"🏷️-{channel_name}"
    
    print(f"🔍 Looking for channel: {full_channel_name}")
    
    if full_channel_name in brand_channels_cache:
        channel = brand_channels_cache[full_channel_name]
        if channel and channel.guild:
            print(f"✅ Found cached channel: {full_channel_name}")
            return channel
    
    for channel in guild.text_channels:
        print(f"🔍 Checking existing channel: '{channel.name}' vs target: '{full_channel_name}'")
        if channel.name == full_channel_name:
            brand_channels_cache[full_channel_name] = channel
            print(f"✅ Found existing channel: {full_channel_name}")
            
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        send_messages=False,
                        add_reactions=True,
                        read_messages=True,
                        use_slash_commands=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        send_messages=True,
                        manage_messages=True,
                        add_reactions=True,
                        read_messages=True
                    )
                }
                await channel.edit(overwrites=overwrites)
                print(f"✅ Updated permissions for {full_channel_name} - now read-only for users")
            except Exception as e:
                print(f"⚠️ Could not update permissions for {full_channel_name}: {e}")
            
            return channel
    
    print(f"⚠️ Channel {full_channel_name} doesn't exist, falling back to main channel")
    return None

async def create_bookmark_for_user_enhanced(user_id, auction_data, original_message):
    try:
        user = bot.get_user(user_id)
        if not user:
            try:
                user = await bot.fetch_user(user_id)
            except:
                print(f"❌ Could not fetch user {user_id}")
                return False
        
        print(f"📚 Creating enhanced bookmark for user: {user.name} ({user_id})")
        
        bookmark_channel = await get_or_create_user_bookmark_channel(user)
        if not bookmark_channel:
            print(f"❌ Could not create bookmark channel for {user.name}")
            return False
        
        if original_message.embeds:
            original_embed = original_message.embeds[0]
            
            embed = discord.Embed(
                title=original_embed.title,
                url=original_embed.url,
                description=original_embed.description,
                color=original_embed.color,
                timestamp=datetime.now(timezone.utc)
            )
            
            if original_embed.thumbnail:
                embed.set_thumbnail(url=original_embed.thumbnail.url)
            
            # Add end time information if available
            if auction_data.get('auction_end_time'):
                try:
                    end_dt = datetime.fromisoformat(auction_data['auction_end_time'].replace('Z', '+00:00'))
                    time_remaining = end_dt - datetime.now(timezone.utc)
                    
                    if time_remaining.total_seconds() > 0:
                        hours = int(time_remaining.total_seconds() // 3600)
                        minutes = int((time_remaining.total_seconds() % 3600) // 60)
                        
                        embed.add_field(
                            name="⏰ Time Remaining",
                            value=f"{hours}h {minutes}m",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="🔔 Reminders",
                            value="You'll be notified at:\n• 1 hour before end\n• 5 minutes before end",
                            inline=True
                        )
                except:
                    pass
            
            embed.set_footer(text=f"📚 Bookmarked from ID: {auction_data['auction_id']} | {datetime.now(timezone.utc).strftime('%Y-%m-%d at %H:%M UTC')}")
            
        else:
            print(f"❌ No embeds found in original message")
            return False
        
        try:
            bookmark_message = await bookmark_channel.send(embed=embed)
            print(f"✅ Successfully sent bookmark to #{bookmark_channel.name}")
        except discord.HTTPException as e:
            print(f"❌ Failed to send bookmark message: {e}")
            return False
        
        # Store bookmark (reminder functionality temporarily disabled)
        success = add_user_bookmark(
            user_id, 
            auction_data['auction_id'], 
            bookmark_message.id, 
            bookmark_channel.id
        )
        
        if success:
            print(f"📚 Successfully created enhanced bookmark for {user.name}")
            return True
        else:
            print(f"❌ Failed to store bookmark in database for {user.name}")
            return False
        
    except Exception as e:
        print(f"❌ Unexpected error creating bookmark for user {user_id}: {e}")
        return False

async def get_or_create_user_bookmark_channel(user):
    try:
        if not guild:
            print("❌ No guild available for bookmark channel creation")
            return None
        
        safe_username = re.sub(r'[^a-zA-Z0-9]', '', user.name.lower())[:20]
        channel_name = f"bookmarks-{safe_username}"
        
        print(f"🔍 Looking for existing bookmark channel: #{channel_name}")
        
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            user_permissions = existing_channel.permissions_for(user)
            if user_permissions.read_messages:
                print(f"✅ Found existing bookmark channel: #{channel_name}")
                return existing_channel
            else:
                print(f"⚠️ Found channel #{channel_name} but user doesn't have access")
        
        print(f"📚 Creating new bookmark channel: #{channel_name}")
        
        category = None
        for cat in guild.categories:
            if cat.name == "📚 USER BOOKMARKS":
                category = cat
                break
        
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            }
            category = await guild.create_category("📚 USER BOOKMARKS", overwrites=overwrites)
            print("✅ Created bookmark category")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=False, add_reactions=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }
        
        bookmark_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Private bookmark channel for {user.name} - Your liked auction listings will appear here!"
        )
        
        welcome_embed = discord.Embed(
            title="📚 Welcome to Your Personal Bookmark Channel!",
            description=f"Hi {user.mention}! This is your private bookmark channel.\n\nWhenever you react 👍 to auction listings, they'll be automatically saved here for easy reference.",
            color=0x0099ff
        )
        welcome_embed.add_field(
            name="🎯 How it works:",
            value="• React 👍 to any auction listing\n• It gets bookmarked here instantly\n• Use `!bookmarks` to see a summary\n• Use `!clear_bookmarks` to clean up",
            inline=False
        )
        
        await bookmark_channel.send(embed=welcome_embed)
        
        print(f"✅ Created new bookmark channel: #{channel_name} for {user.name}")
        return bookmark_channel
        
    except Exception as e:
        print(f"❌ Error creating bookmark channel for {user.name}: {e}")
        return None

async def process_batch_buffer():
    global batch_buffer, last_batch_time
    
    while True:
        await asyncio.sleep(1)
        
        if not batch_buffer:
            continue
            
        current_time = datetime.now(timezone.utc)
        buffer_size = len(batch_buffer)
        
        # Add this logging back
        if buffer_size > 0:
            print(f"📦 Buffer status: {buffer_size} items waiting")
        
        time_since_batch = 0
        if last_batch_time:
            time_since_batch = (current_time - last_batch_time).total_seconds()
        
        should_send = (
            buffer_size >= BATCH_SIZE or 
            time_since_batch >= BATCH_TIMEOUT
        )
        
        if should_send:
            items_to_send = batch_buffer[:BATCH_SIZE]
            batch_buffer = batch_buffer[BATCH_SIZE:]
            
            last_batch_time = current_time
            
            print(f"📤 Processing {len(items_to_send)} items from buffer (remaining: {len(batch_buffer)})...")
            await send_individual_listings_with_rate_limit(items_to_send)

# Trimlist configuration
TRIMLIST_BRANDS = {
    "Comme des Garcons",
    "Rick Owens", 
    "Junya Watanabe"
}

TRIMLIST_MAX_PRICE = 60.0  # $60 limit for trimlist

def determine_target_channel(price_usd, brand, deal_quality, title, scraper_source=None):
    """Enhanced channel routing with scraper-specific channels and trimlist support"""
    channels = []
    
    # Always send to main auction alerts
    channels.append("🎯-auction-alerts")
    
    # SCRAPER-SPECIFIC CHANNELS (Priority routing)
    if scraper_source:
        scraper_source_lower = scraper_source.lower()
        
        # Buy It Now Scraper -> 🛒-buy-it-now
        if "buy_it_now" in scraper_source_lower:
            channels.append("🛒-buy-it-now")
            print(f"🛒 Buy It Now listing from {scraper_source} -> buy-it-now channel")
        
        # New Listings Scraper -> 🆕-new-listings  
        elif "new_listings" in scraper_source_lower:
            channels.append("🆕-new-listings")
            print(f"🆕 New listing from {scraper_source} -> new-listings channel")
        
        # Budget Steals Scraper -> 💰-budget-steals
        elif "budget_steals" in scraper_source_lower:
            channels.append("💰-budget-steals")
            print(f"💰 Budget steal from {scraper_source} -> budget-steals channel")
        
        # Ending Soon Scraper -> ⏰-ending-soon
        elif "ending_soon" in scraper_source_lower:
            channels.append("⏰-ending-soon")
            print(f"⏰ Ending soon from {scraper_source} -> ending-soon channel")
    
    # TRIMLIST - Specific brands under $60 (but not if already routed by scraper)
    if brand in TRIMLIST_BRANDS and price_usd <= TRIMLIST_MAX_PRICE:
        if "🏆-trimlist" not in channels:  # Don't duplicate if scraper already routed
            channels.append("🏆-trimlist")
            print(f"🏆 TRIMLIST HIT: {brand} at ${price_usd:.2f} -> trimlist")
    
    # Budget steals - STRICT $100 limit (but not if already in trimlist or scraper-routed)
    elif price_usd <= 100.0:
        if "💰-budget-steals" not in channels:  # Don't duplicate if scraper already routed
            channels.append("💰-budget-steals")
            print(f"💰 Budget steal: ${price_usd:.2f} -> budget-steals")
    
    # High-value pieces
    if price_usd >= 500.0 and deal_quality >= 0.3:
        channels.append("💎-investment-pieces")
    
    # Trending pieces (good deals)
    if deal_quality >= 0.4:
        channels.append("🎯-trending-pieces")
    
    # Brand channel if applicable (ALWAYS send to brand channel too)
    if brand and brand in BRAND_CHANNEL_MAP:
        brand_channel = f"🏷️-{BRAND_CHANNEL_MAP[brand]}"
        channels.append(brand_channel)
    
    return channels

def is_trimlist_eligible(brand, price_usd):
    """Check if item qualifies for trimlist channel"""
    return (
        brand in TRIMLIST_BRANDS and 
        price_usd <= TRIMLIST_MAX_PRICE and
        price_usd > 0  # Sanity check
    )

# Enhanced brand detection for trimlist
def detect_trimlist_brand(title):
    """Enhanced brand detection specifically for trimlist brands"""
    title_lower = title.lower()
    
    # Comme des Garcons variants
    cdg_variants = [
        "comme des garcons", "cdg", "comme des garçons", 
        "コムデギャルソン", "rei kawakubo"
    ]
    
    # Rick Owens variants  
    rick_variants = [
        "rick owens", "rick", "drkshdw", "dark shadow",
        "リックオウエンス"
    ]
    
    # Junya Watanabe variants
    junya_variants = [
        "junya watanabe", "junya", "ジュンヤワタナベ",
        "watanabe junya"
    ]
    
    for variant in cdg_variants:
        if variant in title_lower:
            return "Comme des Garcons"
    
    for variant in rick_variants:
        if variant in title_lower:
            return "Rick Owens"
            
    for variant in junya_variants:
        if variant in title_lower:
            return "Junya Watanabe"
    
    return None

# Update the main brand detection to include trimlist brands
def detect_brand_in_title_enhanced(title):
    """Enhanced brand detection including trimlist priority"""
    
    # First check trimlist brands with enhanced detection
    trimlist_brand = detect_trimlist_brand(title)
    if trimlist_brand:
        return trimlist_brand
    
    # Then fall back to regular brand detection
    title_lower = title.lower()
    
    for brand, details in BRAND_DATA.items():
        for variant in details["variants"]:
            if variant.lower() in title_lower:
                return brand
    
    return "Unknown"

async def send_single_listing_enhanced(auction_data):
    """Enhanced listing sender with intelligent channel routing"""
    try:
        title = auction_data.get('title', 'Unknown Item')[:100]
        brand = auction_data.get('brand', 'Unknown')
        price_usd = auction_data.get('price_usd', 0)
        deal_quality = auction_data.get('deal_quality', 0.0)
        sizes = extract_sizes_from_title(title) if title else []
        
        # Check for duplicates first
        existing = db_manager.execute_query(
            'SELECT id FROM listings WHERE auction_id = %s' if db_manager.use_postgres else 'SELECT id FROM listings WHERE auction_id = ?', 
            (auction_data['auction_id'],), 
            fetch_one=True
        )
        
        if existing:
            print(f"⚠️ Duplicate found, skipping: {auction_data['auction_id']}")
            return False
        
        # Determine target channels based on price, quality, and scraper source
        scraper_source = auction_data.get('scraper_source', '')
        target_channels = determine_target_channel(price_usd, brand, deal_quality, title, scraper_source)
        
        embed = create_enhanced_listing_embed(auction_data)
        main_message = None
        sent_count = 0
        
        # Send to each target channel
        for channel_name in target_channels:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                try:
                    message = await channel.send(embed=embed)
                    sent_count += 1
                    
                    # Track main message for database
                    if channel_name == "🎯-auction-alerts":
                        main_message = message
                    
                    print(f"📤 Sent to {channel_name}: {title[:30]}...")
                    
                    # Rate limiting between channels
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"❌ Failed to send to {channel_name}: {e}")
            else:
                print(f"⚠️ Channel not found: {channel_name}")
        
        # Add to database if we sent to main channel
        if main_message:
            success = add_listing(auction_data, main_message.id)
            if not success:
                print(f"❌ Failed to add listing to database: {auction_data['auction_id']}")
        
        return sent_count > 0
        
    except Exception as e:
        print(f"❌ Error in send_single_listing_enhanced: {e}")
        import traceback
        traceback.print_exc()
        return False

async def send_to_premium_channels_immediately(listing_data):
    """Send listing immediately to Pro/Elite tier channels"""
    try:
        brand = listing_data.get('brand', 'Unknown')
        
        # Determine target channel based on brand
        brand_channel_name = f"🏷️-{brand.lower().replace(' ', '-')}"
        channel = discord.utils.get(guild.text_channels, name=brand_channel_name)
        
        if not channel:
            # Fallback to general auction alerts
            channel = discord.utils.get(guild.text_channels, name='🎯-auction-alerts')
        
        if channel:
            embed = create_enhanced_listing_embed(listing_data)
            embed.set_footer(text=f"Pro/Elite Real-time Alert | ID: {listing_data['auction_id']}")
            
            # Check channel permissions - only Pro/Elite should see this
            await channel.send(embed=embed)
            print(f"⚡ Sent real-time alert to #{channel.name}")
        
        # Also add to database for tracking
        add_listing(listing_data, channel.id if channel else None)
        
    except Exception as e:
        print(f"❌ Error sending to premium channels: {e}")

async def send_individual_listings_with_rate_limit(batch_data):
    try:
        for i, auction_data in enumerate(batch_data, 1):
            success = await send_single_listing_enhanced(auction_data)
            if success:
                print(f"✅ Sent {i}/{len(batch_data)}")
            else:
                print(f"⚠️ Skipped {i}/{len(batch_data)}")
            
            if i < len(batch_data):
                await asyncio.sleep(1.5)  # Reduced from 3 to 1.5 seconds
        
    except Exception as e:
        print(f"❌ Error in rate-limited sending: {e}")

@bot.event
async def on_ready():
    global guild, auction_channel, preference_learner, tier_manager, delayed_manager, reminder_system, size_alert_system
    global priority_calculator, channel_router, digest_manager, brand_data, tier_manager_new
    print(f'✅ Bot connected as {bot.user}!')
    guild = bot.get_guild(GUILD_ID)
    
    if guild:
        print(f'🎯 Connected to server: {guild.name}')
        auction_channel = await get_or_create_auction_channel()
        
        # Initialize existing systems
        preference_learner = UserPreferenceLearner()
        delayed_manager = DelayedListingManager()
        
        # Initialize new tier system if available
        if TIER_SYSTEM_AVAILABLE:
            print("🔄 Initializing tier system...")
            brand_data = load_brand_data()
            
            # Initialize tier system components
            tier_manager_new = TierManager()
            await tier_manager_new.init_database()
            
            priority_calculator = PriorityCalculator(brand_data)
            channel_router = ChannelRouter(bot, tier_manager_new)
            digest_manager = DigestManager(bot, tier_manager_new)
            
            # Start background tasks
            bot.loop.create_task(reset_counters(tier_manager_new))
            bot.loop.create_task(post_digest())
            bot.loop.create_task(post_standard_feed_hourly())
            
        print("🎯 Tier system initialized")
        print("📊 Priority calculator initialized")
        print("🛣️ Channel router initialized")
        print("📰 Digest manager initialized")
        
        # Subscription commands are loaded manually (see below)
        print("💳 Subscription commands loaded manually")
        
        # Initialize notification tier system - if available
        if ADVANCED_FEATURES_AVAILABLE and tier_manager:
            tier_manager.set_bot(bot)
        
        # Find daily digest channel (only if tier system is available)
        if TIER_SYSTEM_AVAILABLE and tier_manager_new:
            daily_digest_channel = discord.utils.get(guild.channels, name='daily-digest')
            if daily_digest_channel:
                print(f"📰 Daily digest channel found: #{daily_digest_channel.name}")
            else:
                print("⚠️ Daily digest channel not found - please create #daily-digest channel")
        
        # Start background tasks
        bot.loop.create_task(process_batch_buffer())
        bot.loop.create_task(delayed_manager.process_delayed_queue())
        
        # Start daily scheduler - if available
        if ADVANCED_FEATURES_AVAILABLE and daily_scheduler:
            daily_scheduler.start()
        
        print("⏰ Started batch buffer processor")
        print("🧠 User preference learning system initialized")
        print("💎 Notification tier system initialized")
        print("⏳ Delayed listing manager started")
        print("📅 Daily scheduler started")
    else:
        print(f'❌ Could not find server with ID: {GUILD_ID}')

async def reset_counters(tier_mgr):
    """Reset standard tier counters at midnight UTC"""
    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.hour == 0 and now.minute == 0:  # Midnight UTC
                if tier_mgr:
                    await tier_mgr.reset_daily_counters()
                    print("✅ Reset daily counters for standard tier users")
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            print(f"❌ Error in reset_counters: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

async def post_digest():
    """Post daily digest at 9 AM UTC"""
    while True:
        try:
            # Check every hour if it's 9 AM UTC
            now = datetime.now(timezone.utc)
            print(f"🕘 Current UTC time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if now.hour == 9 and now.minute < 10:  # 9:00-9:09 AM window
                print("🔄 It's 9 AM UTC - generating daily digest...")
                
                if digest_manager:
                    success = await digest_manager.generate_daily_digest()
                    if success:
                        print("✅ Daily digest posted successfully")
                    else:
                        print("❌ Failed to post daily digest")
                else:
                    print("⚠️ Digest manager not available")
                
                # Wait 10 minutes to avoid duplicate posts
                await asyncio.sleep(600)
            else:
                # Wait 1 hour before checking again
                await asyncio.sleep(3600)
                
        except Exception as e:
            print(f"❌ Digest task error: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            await asyncio.sleep(3600)  # Wait 1 hour before retrying

async def post_standard_feed_hourly():
    """Post top 5 listings to standard-feed every hour"""
    while True:
        try:
            # Wait until the top of the next hour
            now = datetime.now(timezone.utc)
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            wait_seconds = (next_hour - now).total_seconds()
            
            print(f"⏰ Standard-feed hourly posting scheduled in {wait_seconds/60:.1f} minutes")
            await asyncio.sleep(wait_seconds)
            
            # Post top 5 listings
            if tier_manager_new:
                await post_top_standard_feed_listings()
            else:
                print("⚠️ Tier manager not available for standard-feed posting")
                
        except Exception as e:
            print(f"❌ Standard-feed hourly task error: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            await asyncio.sleep(3600)  # Wait 1 hour before retrying

async def post_top_standard_feed_listings():
    """Post top 5 listings to standard-feed"""
    try:
        print("📦 Posting top 5 listings to standard-feed...")
        
        # Get top 5 listings
        listings = await tier_manager_new.get_top_standard_feed_listings(limit=5)
        
        if not listings:
            print("📭 No listings queued for standard-feed")
            return
        
        print(f"📊 Found {len(listings)} listings for standard-feed")
        
        # Find standard-feed channel
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print("❌ Guild not found")
            return
        
        channel = discord.utils.get(guild.channels, name='standard-feed')
        if not channel:
            channel = discord.utils.get(guild.channels, name='📦-standard-feed')
        
        if not channel:
            print("❌ Standard-feed channel not found")
            return
        
        # Check permissions
        if not channel.permissions_for(guild.me).send_messages:
            print(f"❌ No permission to send messages in #{channel.name}")
            return
        
        # Post each listing
        posted_auction_ids = []
        for i, (listing_data, priority_score) in enumerate(listings, 1):
            try:
                embed = create_listing_embed(listing_data)
                await channel.send(embed=embed)
                posted_auction_ids.append(listing_data.get('auction_id'))
                print(f"✅ Posted listing {i}/5 to #{channel.name} (priority: {priority_score:.2f})")
                
                # Small delay between posts
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"❌ Failed to post listing {i}: {e}")
                continue
        
        # Mark listings as posted
        if posted_auction_ids:
            await tier_manager_new.mark_standard_feed_posted(posted_auction_ids)
            print(f"✅ Marked {len(posted_auction_ids)} listings as posted to standard-feed")
        
    except Exception as e:
        print(f"❌ Failed to post standard-feed listings: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
    # SETUP REACTION DETECTION - Must be FIRST
    if reaction.message.embeds and len(reaction.message.embeds) > 0:
        embed = reaction.message.embeds[0]
        # Check if this is a setup message
        if embed.title and ("Setup" in embed.title or "Auction Sniper Setup" in embed.title):
            print(f"🔧 Setup reaction detected from {user.name}: {reaction.emoji}")
            await handle_setup_reaction(reaction, user)
            return
    
    # Regular reaction handling continues below...
    if str(reaction.emoji) not in ["👍", "👎"]:
        return
    
    # Setup check (existing code)
    result = db_manager.execute_query(
        'SELECT setup_complete FROM user_preferences WHERE user_id = %s' if db_manager.use_postgres else 'SELECT setup_complete FROM user_preferences WHERE user_id = ?',
        (user.id,),
        fetch_one=True
    )

    setup_complete = False
    if result:
        if isinstance(result, dict):
            setup_complete = result.get('setup_complete', False)
        elif isinstance(result, (list, tuple)) and len(result) > 0:
            setup_complete = bool(result[0])

    if not setup_complete:
        try:
            await user.send("⚠️ Please complete your setup first using `!setup`!")
        except:
            pass
        return
    
    # Extract auction ID
    if not reaction.message.embeds:
        return
    
    embed = reaction.message.embeds[0]
    footer_text = embed.footer.text if embed.footer else ""
    
    auction_id_match = re.search(r'ID: (\w+)', footer_text)
    if not auction_id_match:
        return
    
    auction_id = auction_id_match.group(1)
    reaction_type = "thumbs_up" if str(reaction.emoji) == "👍" else "thumbs_down"
    
    # Save reaction to database
    try:
        db_manager.execute_query('''
            INSERT INTO reactions (user_id, auction_id, reaction_type)
            VALUES (%s, %s, %s)
        ''' if db_manager.use_postgres else '''
            INSERT INTO reactions (user_id, auction_id, reaction_type)
            VALUES (?, ?, ?)
        ''', (user.id, auction_id, reaction_type))
        print(f"✅ Saved {reaction_type} reaction for {user.name}")
    except Exception as e:
        print(f"❌ Error saving reaction: {e}")
    
    # For thumbs up, create bookmark channel
    if str(reaction.emoji) == "👍":
        try:
            print(f"🔍 Looking up auction: {auction_id}")
            
            result = db_manager.execute_query('''
                SELECT title, brand, price_jpy, price_usd, seller_id, zenmarket_url, deal_quality
                FROM listings WHERE auction_id = %s
            ''' if db_manager.use_postgres else '''
                SELECT title, brand, price_jpy, price_usd, seller_id, zenmarket_url, deal_quality
                FROM listings WHERE auction_id = ?
            ''', (auction_id,), fetch_one=True)
            
            if result:
                # Get the original embed from the message
                if reaction.message.embeds:
                    original_embed = reaction.message.embeds[0]
                    
                    # Create EXACT copy of the original embed
                    bookmark_embed = discord.Embed(
                        title=original_embed.title,
                        url=original_embed.url,
                        description=original_embed.description,
                        color=0x00ff00,  # Change color to green for bookmarks
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    # Copy the thumbnail exactly
                    if original_embed.thumbnail:
                        bookmark_embed.set_thumbnail(url=original_embed.thumbnail.url)
                    
                    # Copy all fields exactly
                    for field in original_embed.fields:
                        bookmark_embed.add_field(
                            name=field.name,
                            value=field.value,
                            inline=field.inline
                        )
                    
                    # Just change the footer to show it's bookmarked
                    bookmark_embed.set_footer(text=f"📌 Bookmarked • {original_embed.footer.text}")
                    
                    # Create/get bookmark channel
                    bookmark_channel = await get_or_create_bookmark_channel(user)
                    
                    if bookmark_channel:
                        # Send the EXACT copy
                        await bookmark_channel.send(embed=bookmark_embed)
                        await reaction.message.add_reaction("✅")
                        print(f"✅ Created exact bookmark copy for {user.name}")
                    else:
                        await reaction.message.add_reaction("⚠️")
                        print(f"⚠️ Could not create bookmark channel for {user.name}")
                else:
                    print(f"❌ No embeds found in original message")
                    await reaction.message.add_reaction("❓")
            else:
                print(f"❌ No listing found for auction ID: {auction_id}")
                await reaction.message.add_reaction("❓")
                
        except Exception as e:
            print(f"❌ Error in thumbs up handler: {str(e)}")
            import traceback
            traceback.print_exc()
            await reaction.message.add_reaction("⚠️")


async def get_or_create_bookmark_channel(user):
    """Get or create bookmark channel for user"""
    try:
        # Sanitize username for safe channel creation
        safe_username = input_validator.sanitize_username(user.name)
        channel_name = f"bookmarks-{safe_username}"
        
        # Check if channel exists
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            return existing_channel
        
        # Find or create category
        bookmarks_category = discord.utils.get(guild.categories, name="📚 USER BOOKMARKS")
        if not bookmarks_category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            bookmarks_category = await guild.create_category("📚 USER BOOKMARKS", overwrites=overwrites)
        
        # Create channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        bookmark_channel = await guild.create_text_channel(
            channel_name,
            category=bookmarks_category,
            overwrites=overwrites,
            topic=f"Private bookmark channel for {user.display_name}"
        )
        
        return bookmark_channel
        
    except Exception as e:
        print(f"❌ Error creating bookmark channel: {e}")
        return None


@bot.command(name='setup')
async def setup_command(ctx):
    user_id = ctx.author.id
    print(f"🔧 Setup command called by user {user_id}")
    
    try:
        proxy_service, setup_complete = get_user_proxy_preference(user_id)
        print(f"🔧 get_user_proxy_preference returned: proxy={proxy_service}, complete={setup_complete}")
        
        if setup_complete:
            print(f"🔧 User {user_id} is already setup, showing current config")
            
            try:
                current_proxy = SUPPORTED_PROXIES[proxy_service]
                print(f"🔧 Found proxy info: {current_proxy}")
                
                embed = discord.Embed(
                    title="⚙️ Your Current Setup",
                    description=f"You're already set up! Your current proxy service is **{current_proxy['name']}** {current_proxy['emoji']}",
                    color=0x00ff00
                )
                print(f"🔧 Created embed successfully")
                
                try:
                    bookmark_count = db_manager.execute_query(
                        'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = %s' if db_manager.use_postgres else 'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?',
                        (user_id,),
                        fetch_one=True
                    )
                    print(f"🔧 Bookmark count query result: {bookmark_count}")
                    
                    if bookmark_count:
                        embed.add_field(
                            name="📚 Your Bookmarks",
                            value=f"You have **{bookmark_count[0]}** bookmarked items",
                            inline=False
                        )
                        print(f"🔧 Added bookmark field to embed")
                except Exception as e:
                    print(f"🔧 Error getting bookmark count: {e}")
                    # Continue without bookmark count
                
                print(f"🔧 About to send embed to channel {ctx.channel.id}")
                await ctx.send(embed=embed)
                print(f"🔧 Successfully sent setup message to user {user_id}")
                return
                
            except KeyError as e:
                print(f"🔧 KeyError with proxy service '{proxy_service}': {e}")
                await ctx.send(f"❌ Error: Unknown proxy service '{proxy_service}'. Please run setup again.")
                return
            except Exception as e:
                print(f"🔧 Error creating/sending embed: {e}")
                await ctx.send(f"❌ Error showing your current setup: {str(e)}")
                return
        
        print(f"🔧 User {user_id} needs to complete setup, showing setup flow")
        
        # Original setup flow for new users
        embed = discord.Embed(
            title="🎯 Welcome to Auction Sniper Setup!",
            description="Let's get you set up to receive auction listings. First, I need to know which proxy service you use to buy from Yahoo Auctions Japan.",
            color=0x0099ff
        )
        
        proxy_options = ""
        for key, proxy in SUPPORTED_PROXIES.items():
            proxy_options += f"{proxy['emoji']} **{proxy['name']}**\n{proxy['description']}\n\n"
        
        embed.add_field(
            name="📋 Available Proxy Services",
            value=proxy_options,
            inline=False
        )
        
        embed.add_field(
            name="🎮 How to choose:",
            value="React with the emoji below that matches your proxy service!",
            inline=False
        )
        
        embed.add_field(
            name="📚 Auto-Bookmarking",
            value="After setup, any listing you react 👍 to will be automatically bookmarked in your own private channel!",
            inline=False
        )
        
        message = await ctx.send(embed=embed)
        
        for proxy in SUPPORTED_PROXIES.values():
            await message.add_reaction(proxy['emoji'])
            
        print(f"🔧 Sent setup flow to user {user_id}")
        
    except Exception as e:
        logger.error(f"Fatal error in setup command for user {user_id}: {str(e)}")
        await ctx.send("❌ An error occurred during setup. Please try again later.")

async def handle_setup_reaction(reaction, user):
    print(f"🔧 handle_setup_reaction called: user={user.name}, emoji={reaction.emoji}")
    
    emoji = str(reaction.emoji)
    
    selected_proxy = None
    for key, proxy in SUPPORTED_PROXIES.items():
        if proxy['emoji'] == emoji:
            selected_proxy = key
            print(f"🔧 Proxy selected: {selected_proxy}")
            break
    
    if not selected_proxy:
        print(f"🔧 No proxy found for emoji: {emoji}")
        return
    
    # Save proxy preference
    print(f"🔧 Calling set_user_proxy_preference({user.id}, {selected_proxy})")
    success = set_user_proxy_preference(user.id, selected_proxy)
    print(f"🔧 set_user_proxy_preference returned: {success}")
    
    if not success:
        await reaction.message.channel.send(f"❌ {user.mention} - Error saving setup. Please try again.")
        return
    
    proxy_info = SUPPORTED_PROXIES[selected_proxy]
    
    # Send completion message in the SAME CHANNEL as the setup command
    embed = discord.Embed(
        title="✅ Setup Complete!",
        description=f"Great choice! {user.mention} has selected **{proxy_info['name']}** {proxy_info['emoji']}",
        color=0x00ff00
    )
    
    embed.add_field(
        name="🎯 What happens now?",
        value="You can start reacting to listings with 👍/👎 to auto-bookmark items!",
        inline=False
    )
    
    await reaction.message.channel.send(embed=embed)
    print(f"✅ Setup completed for {user.name}")















@bot.command(name='check_bookmarks_table')
async def check_bookmarks_table(ctx):
    try:
        schema = db_manager.execute_query('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_bookmarks'
            ORDER BY ordinal_position
        ''' if db_manager.use_postgres else '''
            PRAGMA table_info(user_bookmarks)
        ''', fetch_all=True)
        
        if db_manager.use_postgres:
            columns = [col['column_name'] for col in schema]
        else:
            columns = [col[1] for col in schema]  # SQLite returns tuples
            
        await ctx.send(f"user_bookmarks columns: {columns}")
        
    except Exception as e:
        await ctx.send(f"Error: {e}")

@bot.command(name='set_sizes')
async def set_sizes_command(ctx, *sizes):
    """Set preferred sizes for alerts"""
    user_id = ctx.author.id
    
    # Validate sizes input
    if not sizes:
        embed = discord.Embed(
            title="📏 Set Your Preferred Sizes",
            description="Configure size alerts to get notified when items in your size are found!",
            color=0x0099ff
        )
        
        embed.add_field(
            name="Usage",
            value="`!set_sizes S M L` or `!set_sizes 48 50` or `!set_sizes XL XXL`",
            inline=False
        )
        
        embed.add_field(
            name="Supported Formats",
            value="• Letter sizes: XS, S, M, L, XL, XXL\n• European sizes: 44, 46, 48, 50, 52, 54, 56\n• Words: small, medium, large",
            inline=False
        )
        
        current_sizes, enabled = get_user_size_preferences(ctx.author.id)
        if current_sizes:
            embed.add_field(
                name="Your Current Sizes",
                value=", ".join(current_sizes) if current_sizes else "None set",
                inline=False
            )
        
        await ctx.send(embed=embed)
        return
    
    # Validate sizes
    sizes_list = list(sizes)
    if not input_validator.validate_sizes(sizes_list):
        await ctx.send("❌ Invalid size format. Please use standard sizes like: S, M, L, XL, 30, 30.5, etc.")
        return
    
    normalized_sizes = []
    size_alert_system = SizeAlertSystem(bot)
    
    for size in sizes:
        normalized = size_alert_system.normalize_size(size)
        normalized_sizes.append(normalized.upper())
    
    set_user_size_preferences(ctx.author.id, normalized_sizes)
    
    embed = discord.Embed(
        title="✅ Size Preferences Updated",
        description=f"You'll now receive alerts for items in sizes: **{', '.join(normalized_sizes)}**",
        color=0x00ff00
    )
    
    embed.add_field(
        name="📱 Where to find alerts",
        value="Size-specific alerts will appear in #🔔-size-alerts",
        inline=False
    )
    
    embed.add_field(
        name="🔕 To disable",
        value="Use `!clear_sizes` to stop receiving size alerts",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='clear_sizes')
async def clear_sizes_command(ctx):
    """Clear size preferences"""
    set_user_size_preferences(ctx.author.id, [])
    
    embed = discord.Embed(
        title="🔕 Size Alerts Disabled",
        description="You will no longer receive size-specific alerts.",
        color=0xff9900
    )
    
    await ctx.send(embed=embed)

@bot.command(name='my_sizes')
async def my_sizes_command(ctx):
    """View your size preferences"""
    sizes, enabled = get_user_size_preferences(ctx.author.id)
    
    if not sizes or not enabled:
        embed = discord.Embed(
            title="📏 No Size Preferences Set",
            description="Use `!set_sizes` to configure size alerts",
            color=0x0099ff
        )
    else:
        embed = discord.Embed(
            title="📏 Your Size Preferences",
            description=f"Currently tracking sizes: **{', '.join(sizes)}**",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🔔 Alerts",
            value="Enabled - You'll receive notifications in #🔔-size-alerts",
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name='volume_debug')
@commands.has_permissions(administrator=True)
async def volume_debug_command(ctx):
    try:
        recent_listings = db_manager.execute_query('''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > datetime('now', '-1 hour')
        ''' if not db_manager.use_postgres else '''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > NOW() - INTERVAL '1 hour'
        ''', fetch_one=True)[0] or 0
        
        daily_listings = db_manager.execute_query('''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > datetime('now', '-1 day')
        ''' if not db_manager.use_postgres else '''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > NOW() - INTERVAL '1 day'
        ''', fetch_one=True)[0] or 0
        
        scraper_stats = db_manager.execute_query('''
            SELECT 
                sent_to_discord,
                keywords_searched,
                total_found,
                quality_filtered,
                timestamp
            FROM scraper_stats 
            ORDER BY timestamp DESC 
            LIMIT 5
        ''', fetch_all=True)
        
        embed = discord.Embed(
            title="📊 Listing Volume Debug",
            color=0xff9900
        )
        
        embed.add_field(
            name="📦 Recent Volume",
            value=f"Last Hour: {recent_listings}\nLast 24h: {daily_listings}\nTarget: 50+ per hour",
            inline=True
        )
        
        if scraper_stats:
            latest_cycle = scraper_stats[0]
            efficiency = latest_cycle[0] / max(1, latest_cycle[1])
            
            embed.add_field(
                name="🤖 Latest Scraper Cycle",
                value=f"Sent: {latest_cycle[0]}\nSearched: {latest_cycle[1]}\nFound: {latest_cycle[2]}\nFiltered: {latest_cycle[3]}\nEfficiency: {efficiency:.1%}",
                inline=True
            )
            
            recent_sent = [stat[0] for stat in scraper_stats]
            avg_sent = sum(recent_sent) / len(recent_sent)
            
            embed.add_field(
                name="📈 5-Cycle Average",
                value=f"Avg Sent: {avg_sent:.1f}\nTotal in 5 cycles: {sum(recent_sent)}",
                inline=True
            )
        
        main_channel = discord.utils.get(guild.text_channels, name="🎯-auction-alerts")
        main_message = None
        if main_channel:
            embed = create_enhanced_listing_embed(auction_data)
            main_message = await main_channel.send(embed=embed)
            print(f"📤 Sent to MAIN channel: {title[:30]}...")
            
            # Add to database with end time
            add_listing(auction_data, main_message.id)
            
            # Allow users to react manually without pre-added bot reactions
        
        recommendations = []
        if recent_listings < 20:
            recommendations.append("🚨 Low volume - check scraper settings")
        if daily_listings < 200:
            recommendations.append("📈 Consider lowering quality thresholds")
        
        if recommendations:
            embed.add_field(
                name="💡 Recommendations",
                value="\n".join(recommendations),
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error getting volume debug: {e}")

@bot.command(name='force_high_volume')
@commands.has_permissions(administrator=True)
async def force_high_volume_command(ctx):
    await ctx.send("""
🚨 **EMERGENCY HIGH VOLUME MODE INSTRUCTIONS:**

**Update these settings in yahoo_sniper.py:**
```python
PRICE_QUALITY_THRESHOLD = 0.05  # Much lower
MAX_LISTINGS_PER_BRAND = 100    # Much higher
MIN_PRICE_USD = 1               # Lower minimum
```

**And set all tiers to search every cycle:**
```python
'search_frequency': 1  # For ALL tiers
```

**Then redeploy the scraper immediately.**
    """)

@bot.command(name='channel_status')
@commands.has_permissions(administrator=True)
async def channel_status_command(ctx):
    required_channels = [
        "🎯-auction-alerts", "💰-budget-steals", "⏰-hourly-drops",
        "🏷️-raf-simons", "🏷️-rick-owens", "🏷️-maison-margiela",
        "🏷️-jean-paul-gaultier", "🏷️-yohji-yamamoto", "🏷️-junya-watanabe",
        "🏷️-undercover", "🏷️-vetements", "🏷️-martine-rose",
        "🏷️-balenciaga", "🏷️-alyx", "🏷️-celine",
        "🏷️-bottega-veneta", "🏷️-kiko-kostadinov", "🏷️-chrome-hearts",
        "🏷️-comme-des-garcons", "🏷️-prada", "🏷️-miu-miu", "🏷️-hysteric-glamour"
    ]
    
    existing_channels = [ch.name for ch in guild.text_channels]
    
    missing = [ch for ch in required_channels if ch not in existing_channels]
    existing = [ch for ch in required_channels if ch in existing_channels]
    
    embed = discord.Embed(title="📺 Channel Status", color=0x0099ff)
    
    if existing:
        embed.add_field(
            name=f"✅ Existing ({len(existing)})",
            value="\n".join(existing[:10]) + ("..." if len(existing) > 10 else ""),
            inline=True
        )
    
    if missing:
        embed.add_field(
            name=f"❌ Missing ({len(missing)})",
            value="\n".join(missing[:10]) + ("..." if len(missing) > 10 else ""),
            inline=True
        )
    
    embed.add_field(
        name="📊 Summary",
        value=f"Total Required: {len(required_channels)}\nExisting: {len(existing)}\nMissing: {len(missing)}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='bookmarks')
async def bookmarks_command(ctx):
    user_id = ctx.author.id
    
    bookmarks = db_manager.execute_query('''
        SELECT auction_id, title, brand, price_usd, zenmarket_url, created_at 
        FROM user_bookmarks 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 10
    ''' if db_manager.use_postgres else '''
        SELECT auction_id, title, brand, price_usd, zenmarket_url, created_at 
        FROM user_bookmarks 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (user_id,), fetch_all=True) or []
    
    if not bookmarks:
        embed = discord.Embed(
            title="📚 Your Bookmarks",
            description="You haven't bookmarked any listings yet! React 👍 to auction listings to bookmark them.",
            color=0x0099ff
        )
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"📚 Your Recent Bookmarks ({len(bookmarks)} shown)",
        color=0x0099ff
    )
    
    for auction_id, title, brand, price_usd, zenmarket_url, created_at in bookmarks:
        short_title = title[:50] + "..." if len(title) > 50 else title
        embed.add_field(
            name=f"{brand.replace('_', ' ').title()} - ${price_usd:.2f}",
            value=f"[{short_title}]({zenmarket_url})\nBookmarked: {created_at[:10]}",
            inline=False
        )
    
    embed.set_footer(text="Use !clear_bookmarks to remove all bookmarks")
    await ctx.send(embed=embed)



@bot.command(name='db_debug')
async def db_debug_command(ctx):
    try:
        await ctx.send(f"PostgreSQL available: {db_manager.use_postgres}")
        await ctx.send(f"Database URL exists: {bool(db_manager.database_url)}")
        
        result = db_manager.execute_query('SELECT COUNT(*) FROM user_preferences', fetch_one=True)
        count = result['count'] if isinstance(result, dict) and 'count' in result else result[0] if result else 0
        await ctx.send(f"User preferences count: {count}")
        
        result2 = db_manager.execute_query('SELECT COUNT(*) FROM reactions', fetch_one=True)
        count2 = result2['count'] if isinstance(result2, dict) and 'count' in result2 else result2[0] if result2 else 0
        await ctx.send(f"Reactions count: {count2}")
        
        listings_count = db_manager.execute_query('SELECT COUNT(*) FROM listings', fetch_one=True)
        count3 = listings_count['count'] if isinstance(listings_count, dict) and 'count' in listings_count else listings_count[0] if listings_count else 0
        await ctx.send(f"Total listings in DB: {count3}")
        
        recent_listings = db_manager.execute_query('''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > NOW() - INTERVAL '1 day'
        ''' if db_manager.use_postgres else '''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > datetime('now', '-1 day')
        ''', fetch_one=True)
        count4 = recent_listings['count'] if isinstance(recent_listings, dict) and 'count' in recent_listings else recent_listings[0] if recent_listings else 0
        await ctx.send(f"Recent listings (24h): {count4}")
        
        recent_ids = db_manager.execute_query('''
            SELECT auction_id, title, created_at FROM listings 
            ORDER BY created_at DESC LIMIT 5
        ''', fetch_all=True)
        
        if recent_ids:
            ids_text = "\n".join([f"{r['auction_id'][:10]}... - {r['title'][:30]}..." for r in recent_ids])
            await ctx.send(f"Recent auction IDs:\n```{ids_text}```")
        
        # FIX: Use proper parameter syntax
        user_prefs = db_manager.execute_query('''
            SELECT proxy_service, setup_complete FROM user_preferences WHERE user_id = %s
        ''' if db_manager.use_postgres else '''
            SELECT proxy_service, setup_complete FROM user_preferences WHERE user_id = ?
        ''', (ctx.author.id,), fetch_one=True)
        
        if user_prefs:
            await ctx.send(f"Your setup: {user_prefs['proxy_service']}, complete: {user_prefs['setup_complete']}")
        
    except Exception as e:
        await ctx.send(f"❌ Database debug error: {str(e)}")



@bot.command(name='clear_recent_listings')
@commands.has_permissions(administrator=True)
async def clear_recent_listings_command(ctx):
    try:
        recent_count = db_manager.execute_query('''
            SELECT COUNT(*) as count FROM listings 
            WHERE created_at > NOW() - INTERVAL '6 hours'
        ''' if db_manager.use_postgres else '''
            SELECT COUNT(*) as count FROM listings 
            WHERE created_at > datetime('now', '-6 hours')
        ''', fetch_one=True)
        
        recent_listings = recent_count['count'] if recent_count else 0
        
        if recent_listings == 0:
            await ctx.send("✅ No recent listings to clear!")
            return
        
        db_manager.execute_query('''
            DELETE FROM listings 
            WHERE created_at > NOW() - INTERVAL '6 hours'
        ''' if db_manager.use_postgres else '''
            DELETE FROM listings 
            WHERE created_at > datetime('now', '-6 hours')
        ''')
        
        db_manager.execute_query('''
            DELETE FROM reactions 
            WHERE auction_id NOT IN (SELECT auction_id FROM listings)
        ''')
        
        db_manager.execute_query('''
            DELETE FROM user_bookmarks 
            WHERE auction_id NOT IN (SELECT auction_id FROM listings)
        ''')
        
        embed = discord.Embed(
            title="🗑️ Recent Listings Cleared",
            description=f"Removed **{recent_listings}** recent listings from the last 6 hours to fix duplicate detection.\n\nNew listings should start appearing shortly!",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error clearing recent listings: {e}")

@bot.command(name='force_clear_all')
@commands.has_permissions(administrator=True)
async def force_clear_all_command(ctx):
    try:
        # Get count first
        total_result = db_manager.execute_query('SELECT COUNT(*) as count FROM listings', fetch_one=True)
        total_listings = total_result['count'] if total_result else 0
        
        if total_listings == 0:
            await ctx.send("No listings to clear.")
            return
        
        # Clear tables
        db_manager.execute_query('DELETE FROM listings')
        db_manager.execute_query('DELETE FROM reactions')
        db_manager.execute_query('DELETE FROM user_bookmarks')
        
        embed = discord.Embed(
            title="🚨 ALL LISTINGS CLEARED",
            description=f"**EMERGENCY RESET**: Removed **{total_listings}** listings and all associated data.",
            color=0xff4444
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Clear error: {str(e)}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name='send_guide')
@commands.has_permissions(administrator=True)
async def send_guide_command(ctx):
    """Send the comprehensive user guide (admin only)"""
    try:
        # Find or create the guide channel
        channel = discord.utils.get(ctx.guild.text_channels, name="📋-start-here")
        if not channel:
            try:
                channel = await ctx.guild.create_text_channel("📋-start-here")
                print(f"✅ Created guide channel: #{channel.name}")
            except Exception as e:
                await ctx.send(f"❌ Could not create guide channel: {e}")
                return
        
        await ctx.send(f"📤 Sending comprehensive guide to #{channel.name}...")
        
        # Main guide embed
        main_embed = discord.Embed(
            title="🎯 Discord Auction Bot - Complete User Guide",
            description="Welcome to the ultimate fashion auction discovery platform! This bot automatically finds rare designer pieces from Yahoo Auctions Japan and learns your personal style preferences.",
            color=0x000000
        )
        
        # Getting Started section
        setup_embed = discord.Embed(
            title="🚀 Getting Started",
            color=0x00ff00
        )
        setup_embed.add_field(
            name="Step 1: Initial Setup (Required)",
            value="```!setup```\nThis command will:\n• Show you available proxy services\n• Let you choose your preferred service\n• Create your personal bookmark system\n• Enable AI preference learning\n\n⚠️ **Important**: You cannot use reactions or bookmarks until setup is complete!",
            inline=False
        )
        setup_embed.add_field(
            name="Step 2: Start Exploring",
            value="Once setup is complete, you can:\n• Browse auction listings in brand channels\n• React to listings to train the AI\n• Use commands to manage preferences",
            inline=False
        )
        
        # Commands section
        commands_embed = discord.Embed(
            title="📋 Available Commands",
            color=0x0099ff
        )
        commands_embed.add_field(
            name="⚙️ Configuration",
            value="**`!setup`** - Complete initial setup or view current configuration\n**`!preferences`** - View your current settings",
            inline=False
        )
        commands_embed.add_field(
            name="📊 Statistics & Data",
            value="**`!stats`** - View your personal statistics\n**`!export`** - Download complete reaction history\n**`!my_tier`** - Check your membership tier",
            inline=False
        )
        commands_embed.add_field(
            name="📖 Help",
            value="**`!commands`** - Display the help menu anytime",
            inline=False
        )
        
        # Reactions section
        reactions_embed = discord.Embed(
            title="🎯 How to Use Reactions",
            color=0xff9900
        )
        reactions_embed.add_field(
            name="👍 Like (Thumbs Up)",
            value="When you react with 👍 to any auction listing:\n• **Automatically bookmarks** the item to your private channel\n• **Trains the AI** to show you more similar items\n• **Learns your preferences** for brands, sellers, and price ranges",
            inline=False
        )
        reactions_embed.add_field(
            name="👎 Dislike (Thumbs Down)",
            value="When you react with 👎 to any auction listing:\n• **Trains the AI** to avoid similar items\n• **Learns what you don't like** (sellers, styles, price points)\n• Helps improve future recommendations",
            inline=False
        )
        
        # Proxy services section
        proxy_embed = discord.Embed(
            title="🛒 Proxy Services Explained",
            description="During setup, you'll choose one of these services to buy items from Japan:",
            color=0x9932cc
        )
        proxy_embed.add_field(
            name="🛒 ZenMarket",
            value="**Best for**: Beginners and English speakers\n**Features**: Full English support, detailed guides\n**Fees**: Competitive rates with transparent pricing",
            inline=True
        )
        proxy_embed.add_field(
            name="📦 Buyee",
            value="**Best for**: Frequent buyers\n**Features**: Official Yahoo Auctions partner\n**Fees**: Often lower for multiple items",
            inline=True
        )
        proxy_embed.add_field(
            name="🇯🇵 Yahoo Japan Direct",
            value="**Best for**: Advanced users in Japan\n**Features**: No proxy fees, direct access\n**Requirements**: Japanese address and language",
            inline=True
        )
        
        # Tips section
        tips_embed = discord.Embed(
            title="💡 Pro Tips",
            color=0x00ced1
        )
        tips_embed.add_field(
            name="Getting the Most Out of the Bot",
            value="1. **React frequently** - The more you react, the better your recommendations\n2. **Use both 👍 and 👎** - Negative feedback is just as valuable\n3. **Check your bookmark channel** - Items you like get saved automatically\n4. **Explore all brand channels** - Don't miss finds in other designers\n5. **Run `!setup` properly** - Choose the right proxy service for your needs",
            inline=False
        )
        
        # FAQ section
        faq_embed = discord.Embed(
            title="❓ Frequently Asked Questions",
            color=0x8b0000
        )
        faq_embed.add_field(
            name="Common Questions",
            value="**Q: Can I change my proxy service later?**\nA: Yes, run `!setup` again to reconfigure\n\n**Q: Are my bookmarks private?**\nA: Yes, only you can see your bookmark channel\n\n**Q: How do I get better recommendations?**\nA: Keep reacting! The more you use 👍/👎, the smarter the bot becomes\n\n**Q: What brands are covered?**\nA: 19+ major designers including Raf Simons, Rick Owens, CDG, Margiela, and more",
            inline=False
        )
        
        # Final section
        final_embed = discord.Embed(
            title="🆘 Need Help?",
            description="If you encounter any issues or have questions:\n1. First try `!commands` to see all available options\n2. Ask in the general chat for community help\n3. Contact an admin for technical issues\n\n**Ready to start hunting for grails? Run `!setup` to begin your journey!** 🎯",
            color=0x8b0000
        )
        
        # Send all embeds with delays
        embeds = [
            main_embed, setup_embed, commands_embed, reactions_embed, 
            proxy_embed, tips_embed, faq_embed, final_embed
        ]
        
        messages = []
        for i, embed in enumerate(embeds):
            try:
                print(f"📤 Sending guide embed {i+1}/{len(embeds)}")
                message = await channel.send(embed=embed)
                messages.append(message)
                if i < len(embeds) - 1:  # Don't sleep after last message
                    await asyncio.sleep(2)  # Delay to avoid rate limits
            except Exception as e:
                print(f"❌ Error sending embed {i+1}: {e}")
                continue
        
        # Pin the first message
        if messages:
            try:
                await messages[0].pin()
                print("📌 Pinned the main guide message")
            except discord.errors.Forbidden:
                print("⚠️ Could not pin message - bot needs 'Manage Messages' permission")
            except discord.errors.HTTPException:
                print("⚠️ Could not pin message - channel may have too many pinned messages")
        
        await ctx.send(f"✅ Successfully sent {len(messages)} guide messages to #{channel.name}")
        
    except Exception as e:
        print(f"❌ Error in send_guide_command: {e}")
        await ctx.send(f"❌ Error sending guide: {e}")



@bot.command(name='stats')
async def stats_command(ctx):
    # Fix the parameter placeholders
    stats = db_manager.execute_query('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN reaction_type = 'thumbs_up' THEN 1 ELSE 0 END) as thumbs_up,
            SUM(CASE WHEN reaction_type = 'thumbs_down' THEN 1 ELSE 0 END) as thumbs_down
        FROM reactions 
        WHERE user_id = %s
    ''' if db_manager.use_postgres else '''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN reaction_type = 'thumbs_up' THEN 1 ELSE 0 END) as thumbs_up,
            SUM(CASE WHEN reaction_type = 'thumbs_down' THEN 1 ELSE 0 END) as thumbs_down
        FROM reactions 
        WHERE user_id = ?
    ''', (ctx.author.id,), fetch_one=True)
    
    if not stats:
        await ctx.send("❌ No stats found. React to some listings first!")
        return
    
    total = stats.get('total', 0)
    thumbs_up = stats.get('thumbs_up', 0)
    thumbs_down = stats.get('thumbs_down', 0)
    
    # Fix the other queries too
    bookmark_count = db_manager.execute_query(
        'SELECT COUNT(*) as count FROM user_bookmarks WHERE user_id = %s' if db_manager.use_postgres else 'SELECT COUNT(*) as count FROM user_bookmarks WHERE user_id = ?',
        (ctx.author.id,),
        fetch_one=True
    )
    
    embed = discord.Embed(
        title=f"📊 Stats for {ctx.author.display_name}",
        color=0x0099ff
    )
    
    embed.add_field(
        name="📈 Reaction Summary", 
        value=f"Total: {total}\n👍 Likes: {thumbs_up}\n👎 Dislikes: {thumbs_down}",
        inline=True
    )
    
    if bookmark_count:
        count = bookmark_count.get('count', 0)
        embed.add_field(
            name="📚 Bookmarks",
            value=f"Total: {count}",
            inline=True
        )
    
    if total > 0:
        positivity = thumbs_up / total * 100
        embed.add_field(
            name="🎯 Positivity Rate",
            value=f"{positivity:.1f}%",
            inline=True
        )
    
    await ctx.send(embed=embed)

async def create_bookmark_channel_for_user(user, auction_data):
    """Create private bookmark channel with proper thumbnails"""
    try:
        # Sanitize username for safe channel creation
        safe_username = input_validator.sanitize_username(user.name)
        channel_name = f"bookmarks-{safe_username}"
        
        # Check if channel already exists
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if not existing_channel:
            # Find or create the USER BOOKMARKS category
            bookmarks_category = discord.utils.get(guild.categories, name="📚 USER BOOKMARKS")
            if not bookmarks_category:
                # Create category if it doesn't exist
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                bookmarks_category = await guild.create_category("📚 USER BOOKMARKS", overwrites=overwrites)
            
            # Create private channel with proper permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            bookmark_channel = await guild.create_text_channel(
                channel_name,
                category=bookmarks_category,
                overwrites=overwrites,
                topic=f"Private bookmark channel for {user.display_name} - Your liked auction listings"
            )
            
            # Send welcome message
            welcome_embed = discord.Embed(
                title="📚 Welcome to Your Personal Bookmark Channel!",
                description=f"Hi {user.mention}! This is your private bookmark channel.\n\nWhenever you react 👍 to auction listings, they'll be automatically saved here for easy reference.",
                color=0x0099ff
            )
            welcome_embed.add_field(
                name="🎯 How it works:",
                value="• React 👍 to any auction listing\n• It gets bookmarked here instantly\n• Use `!bookmarks` to see a summary\n• Use `!clear_bookmarks` to clean up",
                inline=False
            )
            await bookmark_channel.send(embed=welcome_embed)
            
            print(f"✅ Created new bookmark channel: #{channel_name} for {user.name}")
        else:
            bookmark_channel = existing_channel
        
        # CREATE BOOKMARK EMBED WITH THUMBNAIL (this is the key fix)
        embed = discord.Embed(
            title=auction_data['title'][:100],  # Truncate long titles
            url=auction_data['zenmarket_url'],
            description=f"**Brand:** {auction_data['brand'].replace('_', ' ').title()}\n**Price:** ¥{auction_data['price_jpy']:,} (~${auction_data['price_usd']:.2f})",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        # 🔧 KEY FIX: Add thumbnail from the auction data
        if auction_data.get('image_url'):
            embed.set_thumbnail(url=auction_data['image_url'])
            print(f"✅ Added thumbnail: {auction_data['image_url']}")
        else:
            print(f"⚠️ No image_url found in auction_data for {auction_data['auction_id']}")
        
        # Add quality and deal info
        embed.add_field(
            name="📊 Deal Quality",
            value=f"{auction_data.get('deal_quality', 0):.1%}",
            inline=True
        )
        
        # Add proxy links
        auction_id_clean = auction_data['auction_id'].replace('yahoo_', '')
        proxy_links = []
        for key, proxy_info in SUPPORTED_PROXIES.items():
            proxy_url = generate_proxy_url(auction_id_clean, key)
            proxy_links.append(f"{proxy_info['emoji']} [{proxy_info['name']}]({proxy_url})")
        
        embed.add_field(
            name="🛒 Proxy Links",
            value="\n".join(proxy_links),
            inline=False
        )
        
        embed.set_footer(text=f"📌 Bookmarked • ID: {auction_data['auction_id']}")
        
        # Send to bookmark channel
        bookmark_message = await bookmark_channel.send(embed=embed)
        
        # Save to database
        success = add_user_bookmark(
            user.id,
            auction_data['auction_id'],
            bookmark_message.id,
            bookmark_channel.id
        )
        
        if success:
            print(f"✅ Created bookmark with thumbnail in #{channel_name} for {user.name}")
            return True
        else:
            print(f"❌ Failed to save bookmark to database for {user.name}")
            return False
        
    except Exception as e:
        print(f"❌ Error creating bookmark channel for {user.name}: {e}")
        import traceback
        traceback.print_exc()
        return False



@bot.command(name='preferences')
async def preferences_command(ctx):
    try:
        user_id = ctx.author.id
        
        prefs = db_manager.execute_query('''
            SELECT proxy_service, notifications_enabled, min_quality_threshold, max_price_alert 
            FROM user_preferences WHERE user_id = %s
        ''' if db_manager.use_postgres else '''
            SELECT proxy_service, notifications_enabled, min_quality_threshold, max_price_alert 
            FROM user_preferences WHERE user_id = ?
        ''', (user_id,), fetch_one=True)
        
        if not prefs:
            await ctx.send("❌ No preferences found. Run `!setup` first!")
            return
    
        # Handle dict results properly
        proxy_service = prefs['proxy_service']
        notifications = prefs['notifications_enabled'] 
        min_quality = prefs['min_quality_threshold']
        max_price = prefs['max_price_alert']
        
        proxy_info = SUPPORTED_PROXIES.get(proxy_service, {"name": "Unknown", "emoji": "❓"})
        
        embed = discord.Embed(
            title="⚙️ Your Preferences",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🛒 Proxy Service",
            value=f"{proxy_info['emoji']} {proxy_info['name']}",
            inline=True
        )
        
        embed.add_field(
            name="🔔 Notifications",
            value="✅ Enabled" if notifications else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="⭐ Min Quality",
            value=f"{min_quality:.1%}",
            inline=True
        )
        
        embed.add_field(
            name="💰 Max Price Alert",
            value=f"${max_price:.0f}",
            inline=True
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Preferences error: {str(e)}")
        await ctx.send(f"❌ Error loading preferences: {str(e)}")

@bot.command(name='export')
async def export_command(ctx):
    try:
        all_reactions = db_manager.execute_query('''
            SELECT r.reaction_type, r.created_at, l.title, l.brand, l.price_jpy, 
                   l.price_usd, l.seller_id, l.zenmarket_url, l.yahoo_url, l.auction_id,
                   l.deal_quality, l.priority_score
            FROM reactions r
            JOIN listings l ON r.auction_id = l.auction_id
            WHERE r.user_id = %s
            ORDER BY r.created_at DESC
        ''' if db_manager.use_postgres else '''
            SELECT r.reaction_type, r.created_at, l.title, l.brand, l.price_jpy, 
                   l.price_usd, l.seller_id, l.zenmarket_url, l.yahoo_url, l.auction_id,
                   l.deal_quality, l.priority_score
            FROM reactions r
            JOIN listings l ON r.auction_id = l.auction_id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
        ''', (ctx.author.id,), fetch_all=True)
        
        if not all_reactions:
            await ctx.send("❌ No reactions found!")
            return
        
        export_text = f"# {ctx.author.display_name}'s Auction Reactions Export\n"
        export_text += f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        export_text += f"# Total Reactions: {len(all_reactions)}\n\n"
        
        # Process dict results correctly
        liked_count = sum(1 for r in all_reactions if r['reaction_type'] == 'thumbs_up')
        disliked_count = len(all_reactions) - liked_count
        
        export_text += f"## Summary\n"
        export_text += f"👍 Liked: {liked_count}\n"
        export_text += f"👎 Disliked: {disliked_count}\n\n"
        
        for reaction_type in ['thumbs_up', 'thumbs_down']:
            emoji = "👍 LIKED" if reaction_type == 'thumbs_up' else "👎 DISLIKED"
            export_text += f"## {emoji} LISTINGS\n\n"
            
            filtered_reactions = [r for r in all_reactions if r['reaction_type'] == reaction_type]
            
            for i, r in enumerate(filtered_reactions, 1):
                export_text += f"{i}. **{r['title']}**\n"
                export_text += f"   Brand: {r['brand']}\n"
                export_text += f"   Price: ¥{r['price_jpy']:,} (~${r['price_usd']:.2f})\n"
                export_text += f"   Seller: {r['seller_id']}\n"
                export_text += f"   Date: {r['created_at']}\n"
                export_text += f"   ZenMarket: {r['zenmarket_url']}\n\n"
        
        # Send as message (simplified)
        if len(export_text) < 2000:
            await ctx.send(f"```{export_text}```")
        else:
            # Send first part
            await ctx.send(f"```{export_text[:1900]}```")
            await ctx.send("... (truncated)")
            
    except Exception as e:
        print(f"❌ Export error: {str(e)}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Export error: {str(e)}")

@bot.command(name='scraper_stats')
async def scraper_stats_command(ctx):
    try:
        recent_stats = db_manager.execute_query('''
            SELECT timestamp, total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched
            FROM scraper_stats 
            ORDER BY timestamp DESC 
            LIMIT 5
        ''', fetch_all=True)
        
        if not recent_stats:
            await ctx.send("❌ No scraper statistics found! The scraper hasn't logged stats yet.")
            return
        
        embed = discord.Embed(
            title="🤖 Recent Scraper Statistics",
            color=0x0099ff
        )
        
        for i, stat in enumerate(recent_stats, 1):
            if isinstance(stat, dict):
                timestamp = stat['timestamp']
                total_found = stat['total_found']
                quality_filtered = stat['quality_filtered'] 
                sent_to_discord = stat['sent_to_discord']
                errors_count = stat['errors_count']
                keywords_searched = stat['keywords_searched']
            else:
                timestamp, total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched = stat
            
            success_rate = (sent_to_discord / total_found * 100) if total_found > 0 else 0
            
            embed.add_field(
                name=f"Run #{i} - {timestamp}",
                value=f"🔍 Keywords: {keywords_searched}\n📊 Found: {total_found}\n✅ Quality: {quality_filtered}\n📤 Sent: {sent_to_discord}\n❌ Errors: {errors_count}\n📈 Success: {success_rate:.1f}%",
                inline=True
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Scraper stats error: {e}")
        await ctx.send(f"❌ Error getting scraper stats: {e}")

@bot.command(name='commands')
async def commands_command(ctx):
    embed = discord.Embed(
        title="🤖 Auction Bot Commands",
        description="All available commands for the auction tracking bot",
        color=0x0099ff
    )
    
    embed.add_field(
        name="⚙️ Setup & Configuration",
        value="**!setup** - Initial setup or view current configuration\n**!preferences** - View your current preferences",
        inline=False
    )
    
    embed.add_field(
        name="📚 Bookmarks",
        value="**!bookmarks** - View your bookmarked listings\n**!clear_bookmarks** - Remove all bookmarks",
        inline=False
    )
    
    embed.add_field(
        name="📊 Statistics & Data",
        value="**!stats** - Your reaction statistics\n**!scraper_stats** - Recent scraper performance\n**!export** - Export your reaction data",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Admin Commands",
        value="**!commands** - Show this help menu\n**!send_guide** - Send comprehensive user guide (admin only)\n**!db_debug** - Database diagnostics (admin only)",
        inline=False
    )
    
    embed.set_footer(text="New users: Start with !setup | React with 👍/👎 to auction listings to train the bot!")
    
    await ctx.send(embed=embed)

@app.route('/webhook', methods=['POST'])
def webhook():
    global batch_buffer, last_batch_time
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400
        
        required_fields = ['auction_id', 'title', 'brand', 'price_jpy', 'price_usd', 'zenmarket_url']
        if not all(field in data for field in required_fields):
            missing = [field for field in required_fields if field not in data]
            print(f"❌ Missing required fields: {missing}")
            return jsonify({"error": f"Missing required fields: {missing}"}), 400
        
        # Add to batch buffer
        batch_buffer.append(data)
        
        if len(batch_buffer) == 1:
            last_batch_time = datetime.now(timezone.utc)
        
        print(f"📥 Added to buffer: {data['title'][:30]}... (Buffer: {len(batch_buffer)}/{BATCH_SIZE})")
        
        return jsonify({
            "status": "queued",
            "buffer_size": len(batch_buffer),
            "auction_id": data['auction_id']
        }), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events for subscription management"""
    try:
        if not stripe_manager:
            return jsonify({"error": "Stripe not configured"}), 503
        
        # Get webhook data
        payload = request.data
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            return jsonify({"error": "Missing signature"}), 400
        
        # Process webhook with Stripe manager
        event_data = asyncio.run(stripe_manager.handle_webhook(payload, signature))
        
        # Handle the event (this would update user tiers, assign roles, etc.)
        print(f"📧 Stripe webhook processed: {event_data}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Stripe webhook error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/check_duplicate/<auction_id>', methods=['GET'])
def check_duplicate(auction_id):
    try:
        # FIXED: Use proper placeholder for PostgreSQL
        if db_manager.use_postgres:
            existing = db_manager.execute_query(
                'SELECT auction_id FROM listings WHERE auction_id = %s',
                (auction_id,),
                fetch_one=True
            )
        else:
            existing = db_manager.execute_query(
                'SELECT auction_id FROM listings WHERE auction_id = ?',
                (auction_id,),
                fetch_one=True
            )
        
        return jsonify({
            'exists': existing is not None,
            'auction_id': auction_id
        }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'exists': False
        }), 500

@app.route('/stats', methods=['GET'])
def stats():
    total_listings = db_manager.execute_query('SELECT COUNT(*) FROM listings', fetch_one=True)
    total_reactions = db_manager.execute_query('SELECT COUNT(*) FROM reactions', fetch_one=True)
    active_users = db_manager.execute_query('SELECT COUNT(DISTINCT user_id) FROM user_preferences WHERE setup_complete = TRUE', fetch_one=True)
    
    # Enhanced buffer monitoring
    buffer_info = {
        "current_size": len(batch_buffer),
        "max_size": 100,  # Maximum buffer size
        "scraper_sources": list(set([item.get('scraper_source', 'unknown') for item in batch_buffer[:10]]))  # First 10 sources
    }
    
    return jsonify({
        "total_listings": total_listings[0] if total_listings else 0,
        "total_reactions": total_reactions[0] if total_reactions else 0,
        "active_users": active_users[0] if active_users else 0,
        "buffer": buffer_info
    }), 200

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        if not STRIPE_AVAILABLE or not stripe_manager:
            return jsonify({"error": "Stripe not available"}), 500
            
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            print("❌ Missing Stripe signature")
            return jsonify({"error": "Missing signature"}), 400
        
        # Verify webhook signature
        event = stripe_manager.verify_webhook_signature(payload, sig_header)
        if not event:
            print("❌ Invalid Stripe signature")
            return jsonify({"error": "Invalid signature"}), 400
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            discord_id = session['metadata'].get('discord_id')
            tier = session['metadata'].get('tier')
            
            if discord_id and tier and tier_manager_new:
                # Assign tier to user (schedule for async execution)
                def assign_tier():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(tier_manager_new.set_user_tier(discord_id, tier))
                    loop.close()
                
                threading.Thread(target=assign_tier).start()
                print(f"✅ User {discord_id} upgraded to {tier} tier via Stripe")
                
                # Try to send confirmation DM
                def send_confirmation():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        user = bot.get_user(int(discord_id))
                        if user:
                            embed = discord.Embed(
                                title="🎉 Subscription Successful!",
                                description=f"Welcome to the {tier.title()} tier! You now have access to premium channels.",
                                color=discord.Color.green()
                            )
                            loop.run_until_complete(user.send(embed=embed))
                        loop.close()
                    except Exception as e:
                        print(f"❌ Could not send confirmation DM: {e}")
                
                threading.Thread(target=send_confirmation).start()
        
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            discord_id = subscription['metadata'].get('discord_id')
            
            if discord_id and tier_manager_new:
                # Downgrade to free tier (schedule for async execution)
                def downgrade_tier():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(tier_manager_new.set_user_tier(discord_id, 'free'))
                    loop.close()
                
                threading.Thread(target=downgrade_tier).start()
                print(f"✅ User {discord_id} downgraded to free tier (subscription cancelled)")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Stripe webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/stripe-success', methods=['GET'])
def stripe_success():
    """Handle successful Stripe checkout"""
    session_id = request.args.get('session_id')
    if session_id:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1 style="color: green;">✅ Payment Successful!</h1>
            <p>Your subscription has been activated. Check Discord for your new role!</p>
            <p>You can close this window and return to Discord.</p>
        </body>
        </html>
        """
    return "Payment successful! Check Discord for your new role."

@app.route('/stripe-cancel', methods=['GET'])
def stripe_cancel():
    """Handle cancelled Stripe checkout"""
    return """
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: orange;">❌ Payment Cancelled</h1>
        <p>Your payment was cancelled. You can try again anytime.</p>
        <p>You can close this window and return to Discord.</p>
    </body>
    </html>
    """

@app.route('/webhook/listing', methods=['POST'])
# @secure_webhook_required(os.getenv('WEBHOOK_SECRET_KEY', 'your-secret-key-here'))  # Temporarily disabled
def webhook_listing():
    """Receive listing from multiple scrapers with rate limiting buffer"""
    try:
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        listing_data = request.get_json()
        
        if not listing_data or 'auction_id' not in listing_data:
            return jsonify({"status": "error", "message": "Invalid listing data"}), 400
        
        # Add scraper source info for debugging
        scraper_source = listing_data.get('scraper_source', 'unknown')
        print(f"📥 Received listing from {scraper_source}: {listing_data.get('title', 'Unknown')[:50]}...")
        
        # FINAL SPAM CHECK before processing
        if final_spam_check(listing_data):
            print(f"🚫 Final spam check blocked listing from {scraper_source}")
            return jsonify({
                "status": "blocked", 
                "message": "Listing blocked by final spam check", 
                "scraper_source": scraper_source
            }), 200
        
        # Process with tier system if available
        if bot.is_ready() and priority_calculator and channel_router:
            try:
                # Calculate priority score
                priority_score = priority_calculator.calculate_priority(listing_data)
                listing_data['priority_score'] = priority_score
                
                # Route to appropriate channels using bot's event loop
                if bot.loop and not bot.loop.is_closed():
                    bot.loop.create_task(channel_router.route_listing(listing_data))
                
                print(f"🎯 Routed listing with priority {priority_score:.2f} from {scraper_source}")
                
                return jsonify({
                    "status": "success", 
                    "message": "Listing routed to tier system", 
                    "priority_score": priority_score,
                    "scraper_source": scraper_source
                }), 200
                
            except Exception as e:
                print(f"❌ Tier system routing failed: {e}")
                # Fall through to old system
        else:
            print(f"⚠️ Tier system not available - bot_ready: {bot.is_ready()}, priority_calc: {priority_calculator is not None}, channel_router: {channel_router is not None}")
        
        # Fallback to old system
        batch_buffer.append(listing_data)
        buffer_size = len(batch_buffer)
        
        print(f"📦 Added to buffer (size: {buffer_size}) from {scraper_source}")
        print(f"💡 Note: Discord bot should be running separately to process these listings")
        
        # Return success immediately to prevent scraper timeouts
        return jsonify({
            "status": "success", 
            "message": "Listing buffered - Discord bot should process separately", 
            "buffer_size": buffer_size,
            "scraper_source": scraper_source
        }), 200
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook/listing_with_delay', methods=['POST'])
def webhook_listing_with_delay():
    """Handle listings that should be delayed for free users"""
    try:
        listing_data = request.get_json()
        
        if not listing_data:
            return jsonify({"error": "No data received"}), 400
        
        if not bot.is_ready():
            return jsonify({"error": "Bot not ready"}), 503
        
        delay_hours = listing_data.get('delay_hours', 2.0)
        delay_seconds = delay_hours * 3600
        
        # Queue for delayed delivery to free users
        if delayed_manager:
            asyncio.run_coroutine_threadsafe(
                delayed_manager.queue_for_free_users(listing_data, delay_seconds), 
                bot.loop
            )
            print(f"⏳ Queued listing for delayed delivery in {delay_hours} hours")
        
        # Send immediately to Pro/Elite users in real-time channels
        asyncio.run_coroutine_threadsafe(
            send_to_premium_channels_immediately(listing_data), 
            bot.loop
        )
        
        return jsonify({"status": "success", "delayed_hours": delay_hours}), 200
        
    except Exception as e:
        print(f"❌ Webhook delay error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/stats', methods=['POST'])
def webhook_stats():
    """Log scraper statistics"""
    try:
        stats_data = request.get_json()
        
        db_manager.execute_query('''
            INSERT INTO scraper_stats (total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched)
            VALUES (%s, %s, %s, %s, %s)
        ''' if db_manager.use_postgres else '''
            INSERT INTO scraper_stats (total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched)
        ''', (
            stats_data['total_found'],
            stats_data['quality_filtered'], 
            stats_data['sent_to_discord'],
            stats_data['errors_count'],
            stats_data['keywords_searched']
        ))
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook/process_buffer', methods=['POST'])
def process_buffer_webhook():
    """Process buffered listings with rate limiting"""
    try:
        if not bot.is_ready():
            return jsonify({"status": "error", "message": "Bot not ready"}), 503
        
        # Process buffer in batches to avoid rate limiting
        if batch_buffer:
            # Take up to 5 listings at a time
            batch_size = min(5, len(batch_buffer))
            batch_to_process = batch_buffer[:batch_size]
            
            # Remove processed items from buffer
            batch_buffer[:batch_size] = []
            
            print(f"🔄 Processing buffer batch: {batch_size} listings")
            
            # Process each listing with rate limiting
            for i, listing_data in enumerate(batch_to_process):
                try:
                    asyncio.run_coroutine_threadsafe(
                        send_single_listing_enhanced(listing_data), 
                        bot.loop
                    )
                    print(f"✅ Processed {i+1}/{batch_size} from buffer")
                    
                    # Rate limiting: wait 2 seconds between each listing
                    if i < batch_size - 1:  # Don't wait after the last one
                        time.sleep(2)
                        
                except Exception as e:
                    print(f"❌ Error processing buffered listing: {e}")
                    continue
            
            return jsonify({
                "status": "success", 
                "message": f"Processed {batch_size} listings",
                "remaining_buffer": len(batch_buffer)
            }), 200
        else:
            return jsonify({
                "status": "success", 
                "message": "Buffer empty",
                "remaining_buffer": 0
            }), 200
            
    except Exception as e:
        print(f"❌ Buffer processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

class PremiumTierManager:
    def __init__(self, bot):
        self.bot = bot
        self.tier_roles = {
            'free': 'Free User',
            'pro': 'Pro User',
            'elite': 'Elite User'
        }
        
        # Updated to match your EXACT channel structure
        self.tier_channels = {
            'free': [
                # Welcome & Community (accessible to all)
                '🎭-introductions',
                '🎯-daily-discussion', 
                '💬-general-chat',
                '📋-start-here',
                '📸-fit-pics',
                '🗳️-community-votes',
                '💡-style-advice',
                '🔄-buy-sell-trade',
                '🤝-legit-checks',
                # Free tier alerts (delayed)
                '🌅-daily-digest',
                '🎯-auction-alerts',  # Main delayed feed for free users
                '💰-budget-steals'
            ],
            'pro': [
                # Pro tier gets immediate access to Find Alerts
                '⏰-hourly-drops',
                '🎯-trending-pieces', 
                '🔔-size-alerts',
                # All brand channels (immediate access)
                '🏷️-alyx', '🏷️-balenciaga', '🏷️-bottega-veneta', '🏷️-celine',
                '🏷️-chrome-hearts', '🏷️-comme-des-garcons', '🏷️-gosha-rubchinskiy',
                '🏷️-helmut-lang', '🏷️-hysteric-glamour', '🏷️-jean-paul-gaultier',
                '🏷️-junya-watanabe', '🏷️-kiko-kostadinov', '🏷️-maison-margiela',
                '🏷️-martine-rose', '🏷️-miu-miu', '🏷️-prada', '🏷️-raf-simons',
                '🏷️-rick-owens', '🏷️-undercover', '🏷️-vetements', '🏷️-yohji_yamamoto',
                # Market analytics
                '📈-market-analytics'
            ],
            'elite': [
                # Premium vault - Elite exclusive
                '⚡-instant-alerts',     # The fastest feed
                '🎯-personal-alerts',
                '🏆-vip-lounge',
                '💎-investment-pieces',
                '💹-investment-tracking',
                '📈-trend-analysis', 
                '📊-market-intelligence',
                '🔥-grail-hunter',
                '🛡️-verified-sellers'
            ]
        }
        
        # Update tier features with your preferences
        self.tier_features = {
            'free': {
                'delay_multiplier': 2.0,  # 2+ hour delays
                'daily_limit': 100,       # 100 listings per day
                'bookmark_limit': None,   # Unlimited bookmarks
                'ai_personalized': False,
                'priority_support': False,
                'channels': ['📦-daily-digest', '💰-budget-steals', '🗳️-community-votes', '💬-general-chat']
            },
            'pro': {
                'delay_multiplier': 0.0,  # Real-time
                'daily_limit': None,      # Unlimited
                'bookmark_limit': None,   # Unlimited
                'ai_personalized': True,
                'priority_support': False,
                'channels': ['all_brand_channels', '⏰-hourly-drops', '🔔-size-alerts']
            },
            'elite': {
                'delay_multiplier': 0.0,  # Real-time
                'daily_limit': None,      # Unlimited  
                'bookmark_limit': None,   # Unlimited
                'ai_personalized': True,
                'priority_support': True,
                'early_access': True,
                'channels': ['everything', '⚡-instant-alerts', '🔥-grail-hunter', '💎-investment-pieces']
            }
        }
    
    async def setup_tier_roles(self, guild):
        for tier, role_name in self.tier_roles.items():
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if not existing_role:
                try:
                    color = {
                        'free': 0x808080,
                        'pro': 0x3498db,
                        'elite': 0xf1c40f
                    }[tier]
                    
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color(color),
                        mentionable=False,
                        reason="Premium tier role"
                    )
                    print(f"✅ Created role: {role_name}")
                except Exception as e:
                    print(f"❌ Error creating role {role_name}: {e}")
    
    async def setup_channel_permissions(self, guild):
        print("🔧 Setting up channel permissions...")
        
        existing_channels = [channel.name for channel in guild.text_channels]
        print(f"📋 Found {len(existing_channels)} existing channels")
        
        for tier, channels in self.tier_channels.items():
            role = discord.utils.get(guild.roles, name=self.tier_roles[tier])
            if not role:
                print(f"⚠️ Role {self.tier_roles[tier]} not found, skipping")
                continue
            
            accessible_channels = []
            if tier == 'free':
                accessible_channels = self.tier_channels['free']
            elif tier == 'pro':
                accessible_channels = self.tier_channels['free'] + self.tier_channels['pro']
            elif tier == 'elite':
                accessible_channels = (self.tier_channels['free'] + 
                                     self.tier_channels['pro'] + 
                                     self.tier_channels['elite'])
            
            existing_accessible_channels = [ch for ch in accessible_channels if ch in existing_channels]
            missing_channels = [ch for ch in accessible_channels if ch not in existing_channels]
            
            if missing_channels:
                print(f"⚠️ Missing channels for {tier} tier: {missing_channels}")
            
            for channel_name in existing_accessible_channels:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    try:
                        await channel.set_permissions(role, read_messages=True, add_reactions=True)
                        print(f"✅ Set {tier} access to #{channel_name}")
                    except Exception as e:
                        print(f"❌ Error setting permissions for #{channel_name}: {e}")
        
        free_role = discord.utils.get(guild.roles, name=self.tier_roles['free'])
        if free_role:
            premium_channels = self.tier_channels['pro'] + self.tier_channels['elite']
            existing_premium_channels = [ch for ch in premium_channels if ch in existing_channels]
            
            for channel_name in existing_premium_channels:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    try:
                        await channel.set_permissions(free_role, read_messages=False)
                        print(f"🚫 Denied free user access to #{channel_name}")
                    except Exception as e:
                        print(f"❌ Error denying access to #{channel_name}: {e}")
        
        print("✅ Channel permissions setup complete!")
    
    def get_user_tier(self, member):
        user_roles = [role.name for role in member.roles]
        
        if self.tier_roles['elite'] in user_roles:
            return 'elite'
        elif self.tier_roles['pro'] in user_roles:
            return 'pro'
        else:
            return 'free'
    
    async def upgrade_user(self, member, new_tier):
        guild = member.guild
        
        for tier_role_name in self.tier_roles.values():
            role = discord.utils.get(guild.roles, name=tier_role_name)
            if role in member.roles:
                await member.remove_roles(role)
        
        new_role = discord.utils.get(guild.roles, name=self.tier_roles[new_tier])
        if new_role:
            await member.add_roles(new_role)
            
            if db_manager.use_postgres:
                db_manager.execute_query('''
                    INSERT INTO user_subscriptions 
                    (user_id, tier, upgraded_at, expires_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        tier = EXCLUDED.tier,
                        upgraded_at = EXCLUDED.upgraded_at,
                        expires_at = EXCLUDED.expires_at
                ''', (
                    member.id, 
                    new_tier, 
                    datetime.now().isoformat(),
                    (datetime.now() + timedelta(days=30)).isoformat()
                ))
            else:
                db_manager.execute_query('''
                    INSERT OR REPLACE INTO user_subscriptions 
                    (user_id, tier, upgraded_at, expires_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    member.id, 
                    new_tier, 
                    datetime.now().isoformat(),
                    (datetime.now() + timedelta(days=30)).isoformat()
                ))
            
            return True
        return False
    
    def should_delay_listing(self, user_tier, listing_priority):
        if user_tier in ['pro', 'elite']:
            return False
        
        features = self.tier_features['free']
        delay_hours = features['delay_multiplier']
        
        if listing_priority >= 100:
            delay_hours *= 0.5
        elif listing_priority >= 70:
            delay_hours *= 0.75
        
        return delay_hours * 3600

# Enhanced DelayedListingManager with better queue processing
class DelayedListingManager:
    def __init__(self):
        self.delayed_queue = []
        self.running = False
        self.daily_counts = {}  # Track daily limits per user
    
    async def queue_for_free_users(self, listing_data, delay_seconds):
        delivery_time = datetime.now() + timedelta(seconds=delay_seconds)
        
        self.delayed_queue.append({
            'listing': listing_data,
            'delivery_time': delivery_time,
            'target_channels': ['📦-daily-digest', '💰-budget-steals'],
            'priority': listing_data.get('priority', 0)
        })
        
        # Sort by priority first, then delivery time
        self.delayed_queue.sort(key=lambda x: (-x['priority'], x['delivery_time']))
    
    async def process_delayed_queue(self):
        self.running = True
        while self.running:
            try:
                now = datetime.now()
                ready_items = []
                
                for item in self.delayed_queue[:]:
                    if item['delivery_time'] <= now:
                        ready_items.append(item)
                        self.delayed_queue.remove(item)
                
                # Process ready items (prioritize higher quality items)
                ready_items.sort(key=lambda x: -x['priority'])
                
                for item in ready_items[:100]:  # Max 100 listings per day for free users
                    await self.deliver_to_free_channels(item)
                    await asyncio.sleep(2)  # Small delay between deliveries
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"❌ Delayed queue error: {e}")
                await asyncio.sleep(300)
    
    async def deliver_to_free_channels(self, queued_item):
        listing = queued_item['listing']
        
        for channel_name in queued_item['target_channels']:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                try:
                    embed = create_enhanced_listing_embed(listing)
                    
                    # Add free tier messaging
                    delay_hours = (datetime.now() - (queued_item['delivery_time'] - timedelta(seconds=7200))).total_seconds() / 3600
                    embed.set_footer(text=f"Free Tier - Delivered {delay_hours:.1f}h after discovery • Upgrade for real-time alerts | ID: {listing['auction_id']}")
                    
                    await channel.send(embed=embed)
                    print(f"📤 Delivered delayed listing to #{channel_name}")
                    break  # Only send to first available channel
                    
                except Exception as e:
                    print(f"❌ Error delivering to #{channel_name}: {e}")

tier_manager = None  # Old premium tier system
tier_manager_new = None  # New tier system (TierManager)
delayed_manager = None
reminder_system = None
size_alert_system = None

def load_brand_data():
    """Load brand data from brands.json file"""
    try:
        if os.path.exists("brands.json"):
            with open("brands.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.warning("⚠️ brands.json not found, using default brand data")
            return get_default_brand_data()
    except Exception as e:
        logger.error(f"❌ Failed to load brand data: {e}")
        return get_default_brand_data()

def get_default_brand_data():
    """Get default brand data with tier information"""
    return {
        "Raf Simons": {"variants": ["raf simons", "raf", "ラフシモンズ"], "tier": 1},
        "Rick Owens": {"variants": ["rick owens", "rick", "リックオウエンス"], "tier": 1},
        "Maison Margiela": {"variants": ["margiela", "maison margiela", "メゾンマルジェラ"], "tier": 1},
        "Jean Paul Gaultier": {"variants": ["jean paul gaultier", "gaultier", "jpg", "ジャンポールゴルチエ"], "tier": 1},
        "Yohji Yamamoto": {"variants": ["yohji yamamoto", "yohji", "ヨウジヤマモト"], "tier": 2},
        "Junya Watanabe": {"variants": ["junya watanabe", "junya", "ジュンヤワタナベ"], "tier": 2},
        "Undercover": {"variants": ["undercover", "アンダーカバー"], "tier": 2},
        "Vetements": {"variants": ["vetements", "ヴェトモン"], "tier": 2},
        "Comme des Garçons": {"variants": ["comme des garcons", "cdg", "コムデギャルソン"], "tier": 3},
        "Martine Rose": {"variants": ["martine rose", "martine"], "tier": 3},
        "Balenciaga": {"variants": ["balenciaga", "バレンシアガ"], "tier": 3},
        "Alyx": {"variants": ["alyx", "1017 alyx 9sm"], "tier": 3},
        "Celine": {"variants": ["celine", "セリーヌ"], "tier": 4},
        "Bottega Veneta": {"variants": ["bottega veneta", "bottega"], "tier": 4},
        "Kiko Kostadinov": {"variants": ["kiko kostadinov", "kiko"], "tier": 4},
        "Prada": {"variants": ["prada", "プラダ"], "tier": 4},
        "Miu Miu": {"variants": ["miu miu", "ミュウミュウ"], "tier": 4},
        "Chrome Hearts": {"variants": ["chrome hearts", "chrome"], "tier": 5}
    }

def extract_sizes_from_title(title):
    """Extract size information from auction title"""
    if not title:
        return []
    
    title_lower = title.lower()
    sizes = []
    
    # Common size patterns
    size_patterns = [
        r'\b(xs|s|m|l|xl|xxl)\b',
        r'\b(44|46|48|50|52|54|56)\b',
        r'\b(small|medium|large)\b',
        r'サイズ[smxl]',
        r'[smxl]サイズ'
    ]
    
    for pattern in size_patterns:
        matches = re.findall(pattern, title_lower)
        sizes.extend(matches)
    
    return list(set(sizes))  # Remove duplicates

def create_listing_embed(listing_data):
    """Create a standardized embed for listings"""
    title = listing_data.get('title', '')
    brand = listing_data.get('brand', '')
    price_jpy = listing_data.get('price_jpy', 0)
    price_usd = listing_data.get('price_usd', 0)
    deal_quality = listing_data.get('deal_quality', 0.5)
    priority = listing_data.get('priority', 0.0)
    seller_id = listing_data.get('seller_id', 'unknown')
    zenmarket_url = listing_data.get('zenmarket_url', '')
    image_url = listing_data.get('image_url', '')
    auction_id = listing_data.get('auction_id', '')
    auction_end_time = listing_data.get('auction_end_time', None)
    sizes = listing_data.get('sizes', [])
    
    if deal_quality >= 0.8 or priority >= 100:
        color = 0x00ff00
        quality_emoji = "🔥"
    elif deal_quality >= 0.6 or priority >= 70:
        color = 0xffa500
        quality_emoji = "🌟"
    else:
        color = 0xff4444
        quality_emoji = "⭐"
    
    display_title = title
    if len(display_title) > 100:
        display_title = display_title[:97] + "..."
    
    description = f"💴 **¥{price_jpy:,}** (~${price_usd:.2f})\n"
    description += f"🏷️ **{brand.replace('_', ' ').title()}**\n"
    description += f"{quality_emoji} **Quality: {deal_quality:.1%}** | **Priority: {priority:.0f}**\n"
    description += f"👤 **Seller:** {seller_id}\n"

    if sizes:
        description += f"📏 **Sizes:** {', '.join(sizes)}\n"
    
    # Add time remaining if available
    if auction_end_time:
        try:
            end_dt = datetime.fromisoformat(auction_end_time.replace('Z', '+00:00'))
            time_remaining = end_dt - datetime.now(timezone.utc)
            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                description += f"⏰ **Time Remaining:** {hours}h {minutes}m\n"
        except:
            pass
    
    auction_id_clean = auction_id.replace('yahoo_', '')
    link_section = "\n**🛒 Proxy Links:**\n"
    for key, proxy_info in SUPPORTED_PROXIES.items():
        proxy_url = generate_proxy_url(auction_id_clean, key)
        link_section += f"{proxy_info['emoji']} [{proxy_info['name']}]({proxy_url})\n"
    
    description += link_section
    
    embed = discord.Embed(
        title=display_title,
        url=zenmarket_url,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    
    if image_url:
        embed.set_thumbnail(url=image_url)
    
    embed.set_footer(text=f"ID: {auction_id} | !setup for proxy config | React 👍/👎 to train")
    
    return embed

@bot.command(name='setup_tiers')
@commands.has_permissions(administrator=True)
async def setup_tiers_command(ctx):
    print(f"🔧 setup_tiers called by {ctx.author.name}")
    
    if not ADVANCED_FEATURES_AVAILABLE:
        await ctx.send("❌ Advanced features (notification tiers) are not available. Please ensure all required modules are deployed.")
        return
    
    try:
        global tier_manager
        print(f"🔧 Creating PremiumTierManager")
        tier_manager = PremiumTierManager(bot)
        print(f"🔧 PremiumTierManager created successfully")
        
        print(f"🔧 Setting up tier roles...")
        await tier_manager.setup_tier_roles(ctx.guild)
        print(f"🔧 Tier roles setup complete")
        
        print(f"🔧 Setting up channel permissions...")
        await tier_manager.setup_channel_permissions(ctx.guild)
        print(f"🔧 Channel permissions setup complete")
        
        print(f"🔧 Sending success message...")
        await ctx.send("✅ Tier system setup complete!")
        print(f"🔧 Success message sent!")
        
    except Exception as e:
        print(f"🔧 Error in setup_tiers: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Error setting up tiers: {str(e)}")

@bot.command(name='upgrade_user')
@commands.has_permissions(administrator=True)
async def upgrade_user_command(ctx, member: discord.Member, tier: str):
    print(f"🔧 upgrade_user called: {member.name} to {tier}")
    
    if tier not in ['free', 'pro', 'elite']:
        await ctx.send("❌ Invalid tier. Use: free, pro, or elite")
        return
    
    if not tier_manager:
        await ctx.send("❌ Tier system not initialized. Run `!setup_tiers` first")
        return
    
    try:
        print(f"🔧 Calling tier_manager.upgrade_user")
        success = await tier_manager.upgrade_user(member, tier)
        print(f"🔧 upgrade_user returned: {success}")
        
        if success:
            embed = discord.Embed(
                title="🎯 User Upgraded",
                description=f"{member.mention} has been upgraded to **{tier.title()} Tier**",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to upgrade user - check bot role permissions")
    except discord.Forbidden:
        await ctx.send("❌ **Permission Error**: Bot role must be higher than tier roles in server settings")
    except Exception as e:
        print(f"🔧 Error in upgrade_user: {e}")
        await ctx.send(f"❌ Error upgrading user: {str(e)}")

@bot.command(name='my_tier')
async def my_tier_command(ctx):
    if not tier_manager:
        await ctx.send("❌ Tier system not initialized")
        return
    
    user_tier = tier_manager.get_user_tier(ctx.author)
    features = tier_manager.tier_features[user_tier]
    
    embed = discord.Embed(
        title=f"🎯 Your Tier: {user_tier.title()}",
        color={
            'free': 0x808080,
            'pro': 0x3498db, 
            'elite': 0xf1c40f
        }[user_tier]
    )
    
    if user_tier == 'free':
        embed.add_field(
            name="Current Benefits",
            value=f"• {features['daily_limit']} listings per day\n• {features['bookmark_limit']} bookmark limit\n• Community features\n• 2+ hour delays",
            inline=False
        )
        embed.add_field(
            name="🚀 Upgrade to Pro ($20/month)",
            value="• Real-time alerts\n• All brand channels\n• Unlimited bookmarks\n• AI personalization\n• Price tracking",
            inline=False
        )
    elif user_tier == 'pro':
        embed.add_field(
            name="Your Benefits",
            value="• Real-time alerts\n• All brand channels\n• Unlimited bookmarks\n• AI personalization\n• Price tracking",
            inline=False
        )
        embed.add_field(
            name="🔥 Upgrade to Elite ($50/month)",
            value="• Grail hunter alerts\n• Market intelligence\n• Investment tracking\n• Priority support\n• VIP lounge access",
            inline=False
        )
    else:
        embed.add_field(
            name="Elite Benefits",
            value="• All Pro features\n• Grail hunter alerts\n• Market intelligence\n• Investment tracking\n• Priority support\n• VIP lounge access",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='bookmark')
async def bookmark_item(ctx, *, auction_url_or_id=None):
    # Validate input
    if auction_url_or_id and len(auction_url_or_id) > 500:
        await ctx.send("❌ Invalid auction URL or ID provided.")
        return
    
    # Sanitize input if provided
    if auction_url_or_id:
        sanitized_input = input_validator.sanitize_command_input(auction_url_or_id)
        if not sanitized_input:
            await ctx.send("❌ Invalid input provided.")
            return
    """Bookmark an auction with fixed database handling"""
    try:
        user_id = ctx.author.id
        
        if not auction_url_or_id:
            await ctx.send("❌ Please provide an auction URL or ID. Example: `!bookmark w1234567890`")
            return
        
        # Extract auction ID from URL or use directly
        auction_id = auction_url_or_id
        if 'yahoo.co.jp' in auction_url_or_id or 'zenmarket.jp' in auction_url_or_id:
            import re
            match = re.search(r'[wab]\d{10}', auction_url_or_id)
            if match:
                auction_id = match.group()
            else:
                await ctx.send("❌ Could not extract auction ID from URL")
                return
        
        # Validate auction ID
        if not input_validator.validate_auction_id(auction_id):
            await ctx.send("❌ Invalid auction ID format. Please provide a valid Yahoo auction URL or ID.")
            return
        
        # Check if listing exists in database with fixed query
        listing = db_manager.execute_query(
            'SELECT * FROM listings WHERE auction_id = %s' if db_manager.use_postgres else 'SELECT * FROM listings WHERE auction_id = ?',
            (auction_id,),
            fetch_one=True
        )
        
        if not listing:
            await ctx.send(f"❌ Auction {auction_id} not found in our database. Make sure it was posted by the bot recently.")
            return
        
        # Check if already bookmarked with fixed query
        existing_bookmark = db_manager.execute_query(
            'SELECT id FROM user_bookmarks WHERE user_id = %s AND auction_id = %s' if db_manager.use_postgres else 'SELECT id FROM user_bookmarks WHERE user_id = ? AND auction_id = ?',
            (user_id, auction_id),
            fetch_one=True
        )
        
        if existing_bookmark:
            await ctx.send(f"📌 You already have this auction bookmarked: {auction_id}")
            return
        
        # Get user's bookmark method preference
        bookmark_method, _ = get_user_proxy_preference(user_id)
        
        if bookmark_method == 'private_channel':
            # Create private bookmark channel
            channel_name = f"bookmark-{ctx.author.name}-{auction_id}"
            
            # Check if channel already exists
            existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if existing_channel:
                bookmark_channel = existing_channel
            else:
                # Create new private channel
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                
                bookmark_channel = await guild.create_text_channel(
                    channel_name,
                    overwrites=overwrites,
                    category=discord.utils.get(guild.categories, name="📌 Bookmarks")
                )
            
            # Send bookmark embed to private channel
            embed = create_listing_embed({
                'auction_id': auction_id,
                'title': listing['title'] if isinstance(listing, dict) else listing[2],
                'brand': listing['brand'] if isinstance(listing, dict) else listing[3],
                'price_jpy': listing['price_jpy'] if isinstance(listing, dict) else listing[4],
                'price_usd': listing['price_usd'] if isinstance(listing, dict) else listing[5],
                'zenmarket_url': listing['zenmarket_url'] if isinstance(listing, dict) else listing[7],
                'yahoo_url': listing['yahoo_url'] if isinstance(listing, dict) else listing[8],
                'image_url': listing['image_url'] if isinstance(listing, dict) else listing[9],
                'deal_quality': listing['deal_quality'] if isinstance(listing, dict) else listing[10],
                'auction_end_time': listing['auction_end_time'] if isinstance(listing, dict) else listing[14]
            })
            
            embed.title = f"📌 BOOKMARKED: {embed.title}"
            embed.color = 0x00ff00
            
            bookmark_message = await bookmark_channel.send(embed=embed)
            
            # Add bookmark to database with fixed function call
            auction_end_time = listing['auction_end_time'] if isinstance(listing, dict) else listing[14]
            success = add_user_bookmark(
                user_id, 
                auction_id, 
                bookmark_message.id, 
                bookmark_channel.id
            )
            
            if success:
                await ctx.send(f"✅ Bookmarked! Check your private channel: {bookmark_channel.mention}")
            else:
                await ctx.send(f"❌ Failed to save bookmark to database")
        
        else:
            # DM bookmark method
            try:
                embed = create_listing_embed({
                    'auction_id': auction_id,
                    'title': listing['title'] if isinstance(listing, dict) else listing[2],
                    'brand': listing['brand'] if isinstance(listing, dict) else listing[3],
                    'price_jpy': listing['price_jpy'] if isinstance(listing, dict) else listing[4],
                    'price_usd': listing['price_usd'] if isinstance(listing, dict) else listing[5],
                'zenmarket_url': listing['zenmarket_url'] if isinstance(listing, dict) else listing[7],
                'yahoo_url': listing['yahoo_url'] if isinstance(listing, dict) else listing[8],
                'image_url': listing['image_url'] if isinstance(listing, dict) else listing[9],
                'deal_quality': listing['deal_quality'] if isinstance(listing, dict) else listing[10],
                'auction_end_time': listing['auction_end_time'] if isinstance(listing, dict) else listing[14]
                })
                
                embed.title = f"📌 BOOKMARKED: {embed.title}"
                embed.color = 0x00ff00
                
                dm_message = await ctx.author.send(embed=embed)
                
                # Add bookmark to database
                auction_end_time = listing['auction_end_time'] if isinstance(listing, dict) else listing[14]
                success = add_user_bookmark(
                    user_id, 
                    auction_id, 
                    dm_message.id, 
                    0  # 0 for DM
                )
                
                if success:
                    await ctx.send(f"✅ Bookmarked! Check your DMs.")
                else:
                    await ctx.send(f"❌ Failed to save bookmark to database")
                    
            except discord.Forbidden:
                await ctx.send("❌ Cannot send DM. Please enable DMs from server members or use `!settings bookmark_method private_channel`")
        
    except Exception as e:
        print(f"❌ Error in bookmark command: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Error creating bookmark: {str(e)}")

@bot.command(name='my_bookmarks')
async def list_bookmarks(ctx):
    """List user's bookmarks with fixed database queries"""
    try:
        user_id = ctx.author.id
        
        bookmarks = db_manager.execute_query(
            '''SELECT ub.auction_id, ub.created_at, 
                      l.title, l.brand, l.price_usd, l.zenmarket_url
               FROM user_bookmarks ub
               LEFT JOIN listings l ON ub.auction_id = l.auction_id
               WHERE ub.user_id = %s
               ORDER BY ub.created_at DESC
               LIMIT 10''' if db_manager.use_postgres else 
            '''SELECT ub.auction_id, ub.created_at, 
                      l.title, l.brand, l.price_usd, l.zenmarket_url
               FROM user_bookmarks ub
               LEFT JOIN listings l ON ub.auction_id = l.auction_id
               WHERE ub.user_id = ?
               ORDER BY ub.created_at DESC
               LIMIT 10''',
            (user_id,),
            fetch_all=True
        )
        
        if not bookmarks:
            await ctx.send("📌 You haven't bookmarked any auctions yet. Use `!bookmark <auction_id>` to save items!")
            return
        
        embed = discord.Embed(
            title=f"📌 Your Bookmarks ({len(bookmarks)})",
            color=0x3498db,
            description="Your most recent bookmarked auctions"
        )
        
        for bookmark in bookmarks:
            auction_id = bookmark[0] if isinstance(bookmark, (list, tuple)) else bookmark['auction_id']
            title = bookmark[2] if isinstance(bookmark, (list, tuple)) else bookmark['title']
            brand = bookmark[3] if isinstance(bookmark, (list, tuple)) else bookmark['brand']
            price_usd = bookmark[4] if isinstance(bookmark, (list, tuple)) else bookmark['price_usd']
            zenmarket_url = bookmark[5] if isinstance(bookmark, (list, tuple)) else bookmark['zenmarket_url']
            
            if title:
                display_title = f"{brand} - {title[:50]}..." if len(title) > 50 else f"{brand} - {title}"
                embed.add_field(
                    name=f"🎯 {display_title}",
                    value=f"💰 ${price_usd:.2f} | [View on Zenmarket]({zenmarket_url})\n`{auction_id}`",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"🎯 {auction_id}",
                    value="Listing details not available",
                    inline=False
                )
        
        embed.set_footer(text="Use !clear_bookmarks to remove all bookmarks")
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"❌ Error listing bookmarks: {e}")
        await ctx.send("❌ Error retrieving your bookmarks. Please try again later.")

@bot.command(name='clear_bookmarks')
async def clear_bookmarks_command(ctx):
    """Clear all user bookmarks with confirmation"""
    try:
        user_id = ctx.author.id
        
        count = clear_user_bookmarks(user_id)
        
        if count > 0:
            await ctx.send(f"✅ Cleared {count} bookmarks.")
        else:
            await ctx.send("📌 You don't have any bookmarks to clear.")
            
    except Exception as e:
        print(f"❌ Error clearing bookmarks: {e}")
        await ctx.send("❌ Error clearing bookmarks. Please try again later.")

@bot.command(name='size_alerts')
async def set_size_alerts(ctx, *, sizes=None):
    """Set size preferences for alerts with fixed database handling"""
    try:
        user_id = ctx.author.id
        
        if not sizes:
            # Show current preferences
            user_sizes, alerts_enabled = get_user_size_preferences(user_id)
            
            embed = discord.Embed(
                title="📏 Your Size Alert Settings",
                color=0x3498db
            )
            
            if user_sizes:
                embed.add_field(
                    name="Current Sizes",
                    value=", ".join(user_sizes),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Current Sizes",
                    value="None set",
                    inline=False
                )
            
            embed.add_field(
                name="Alerts Enabled",
                value="✅ Yes" if alerts_enabled else "❌ No",
                inline=False
            )
            
            embed.add_field(
                name="Usage",
                value="Use `!size_alerts S, M, L` to set your preferred sizes",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        # Parse and clean sizes
        size_list = [size.strip().upper() for size in sizes.split(',')]
        valid_sizes = []
        
        for size in size_list:
            if size in ['XS', 'S', 'M', 'L', 'XL', 'XXL', '0', '1', '2', '3', '4', '5'] or size.isdigit():
                valid_sizes.append(size)
        
        if not valid_sizes:
            await ctx.send("❌ Please provide valid sizes. Examples: S, M, L, XL or 0, 1, 2, 3")
            return
        
        # Save to database with fixed function call
        success = set_user_size_preferences(user_id, valid_sizes)
        
        if success:
            embed = discord.Embed(
                title="✅ Size Alerts Updated",
                color=0x00ff00,
                description=f"You'll now receive DM alerts for items in sizes: **{', '.join(valid_sizes)}**"
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Error saving size preferences. Please try again later.")
            
    except Exception as e:
        print(f"❌ Error setting size alerts: {e}")
        await ctx.send("❌ Error setting size preferences. Please try again later.")

@bot.command(name='update_channels')
@commands.has_permissions(administrator=True)
async def update_channels_command(ctx):
    if not tier_manager:
        await ctx.send("❌ Tier system not initialized. Run `!setup_tiers` first")
        return
    
    await ctx.send("🔄 Updating channel permissions for new channels...")
    await tier_manager.setup_channel_permissions(ctx.guild)
    await ctx.send("✅ Channel permissions updated!")

@bot.command(name='list_channels')
@commands.has_permissions(administrator=True)
async def list_channels_command(ctx):
    if not tier_manager:
        await ctx.send("❌ Tier system not initialized")
        return
    
    embed = discord.Embed(title="📋 Channel Tier Assignments", color=0x3498db)
    
    existing_channels = [channel.name for channel in ctx.guild.text_channels]
    
    for tier, channels in tier_manager.tier_channels.items():
        existing_tier_channels = [ch for ch in channels if ch in existing_channels]
        missing_tier_channels = [ch for ch in channels if ch not in existing_channels]
        
        if existing_tier_channels:
            embed.add_field(
                name=f"✅ {tier.title()} Tier (Existing)",
                value="\n".join([f"• #{ch}" for ch in existing_tier_channels]),
                inline=True
            )
        
        if missing_tier_channels:
            embed.add_field(
                name=f"❌ {tier.title()} Tier (Missing)",
                value="\n".join([f"• #{ch}" for ch in missing_tier_channels]),
                inline=True
            )
    
    await ctx.send(embed=embed)

@bot.command(name='show_all_channels')
async def show_all_channels(ctx):
    """Show all text channels organized by category"""
    
    guild = ctx.guild
    output = []
    
    # Group channels by category
    categories = {}
    no_category = []
    
    for channel in guild.text_channels:
        if channel.category:
            cat_name = channel.category.name
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(channel.name)
        else:
            no_category.append(channel.name)
    
    # Format output
    output.append("📋 **COMPLETE CHANNEL STRUCTURE**\n")
    
    # Channels with categories
    for category_name, channels in categories.items():
        output.append(f"📁 **{category_name.upper()}**")
        for channel in sorted(channels):
            output.append(f"  #{channel}")
        output.append("")  # Empty line
    
    # Channels without category
    if no_category:
        output.append("📁 **NO CATEGORY**")
        for channel in sorted(no_category):
            output.append(f"  #{channel}")
        output.append("")
    
    # Summary
    total_channels = len(guild.text_channels)
    output.append(f"📊 **SUMMARY:** {total_channels} total text channels")
    
    # Send as code block to preserve formatting
    full_output = "\n".join(output)
    
    if len(full_output) > 1900:  # Discord message limit
        # Split into multiple messages
        chunks = []
        current_chunk = ""
        
        for line in output:
            if len(current_chunk + line + "\n") > 1900:
                chunks.append(f"```\n{current_chunk}\n```")
                current_chunk = line
            else:
                current_chunk += line + "\n"
        
        if current_chunk:
            chunks.append(f"```\n{current_chunk}\n```")
        
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(f"```\n{full_output}\n```")



@bot.command(name='check_bookmarks')
async def check_bookmarks(ctx):
    """Simple check of bookmark database"""
    try:
        user_id = ctx.author.id
        
        # Count bookmarks for this user
        count = db_manager.execute_query(
            'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = %s' if db_manager.use_postgres else 
            'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?',
            (user_id,), fetch_one=True
        )
        
        if isinstance(count, dict):
            bookmark_count = count.get('count', 0)
        else:
            bookmark_count = count[0] if count else 0
            
        await ctx.send(f"📚 Your bookmarks in database: {bookmark_count}")
        
        # Show first few bookmarks if any exist
        if bookmark_count > 0:
            bookmarks = db_manager.execute_query(
                'SELECT auction_id, title FROM user_bookmarks WHERE user_id = %s LIMIT 3' if db_manager.use_postgres else 
                'SELECT auction_id, title FROM user_bookmarks WHERE user_id = ? LIMIT 3',
                (user_id,), fetch_all=True
            )
            
            for bookmark in bookmarks:
                if isinstance(bookmark, dict):
                    await ctx.send(f"• {bookmark['auction_id']}: {bookmark['title'][:50]}...")
                else:
                    await ctx.send(f"• {bookmark[0]}: {bookmark[1][:50]}...")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# Health check endpoint for the Discord bot
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            health_data = {
                'status': 'healthy',
                'bot_ready': bot.is_ready(),
                'guild_connected': guild is not None,
                'database_connected': db_manager.use_postgres,
                'timestamp': datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(health_data).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs





# Test command for trimlist
@bot.command(name='test_trimlist')
@commands.has_permissions(administrator=True)
async def test_trimlist(ctx, brand: str, price: float):
    """Test trimlist filtering with specific brand and price"""
    
    # Normalize brand name
    brand_map = {
        "cdg": "Comme des Garcons",
        "comme": "Comme des Garcons", 
        "rick": "Rick Owens",
        "junya": "Junya Watanabe"
    }
    
    full_brand = brand_map.get(brand.lower(), brand.title())
    
    test_data = {
        'auction_id': 'trimlist_test_123',
        'title': f'Test {full_brand} Item',
        'brand': full_brand,
        'price_usd': price,
        'deal_quality': 0.2
    }
    
    channels = determine_target_channel(price, full_brand, 0.2, f'Test {full_brand} Item', 'test_scraper')
    is_eligible = is_trimlist_eligible(full_brand, price)
    
    embed = discord.Embed(
        title="🏆 Trimlist Filter Test",
        color=0x00ff00 if is_eligible else 0xff9900
    )
    
    embed.add_field(
        name="Test Brand",
        value=full_brand,
        inline=True
    )
    
    embed.add_field(
        name="Test Price", 
        value=f"${price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Trimlist Eligible",
        value="🏆 YES" if is_eligible else "❌ NO",
        inline=True
    )
    
    embed.add_field(
        name="Reason",
        value=(
            "✅ Brand + Price match!" if is_eligible else
            f"❌ {'Wrong brand' if full_brand not in TRIMLIST_BRANDS else 'Over $60 limit'}"
        ),
        inline=True
    )
    
    embed.add_field(
        name="Target Channels",
        value="\n".join(channels) if channels else "None",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Monitor trimlist channel
@bot.command(name='check_trimlist')
@commands.has_permissions(administrator=True) 
async def check_trimlist(ctx):
    """Check recent items in trimlist channel"""
    
    trimlist_channel = discord.utils.get(guild.text_channels, name="🏆-trimlist")
    
    if not trimlist_channel:
        await ctx.send("❌ Trimlist channel #🏆-trimlist not found!")
        return
    
    # Get last 10 messages
    messages = []
    async for message in trimlist_channel.history(limit=10):
        if message.embeds:
            embed = message.embeds[0]
            title = embed.title or "Unknown"
            
            price = None
            brand = None
            
            for field in embed.fields:
                if "Price" in field.name:
                    try:
                        price_text = field.value.replace('$', '').replace(',', '').split()[0]
                        price = float(price_text)
                    except:
                        pass
                elif "Brand" in field.name:
                    brand = field.value
            
            if price is not None:
                messages.append({
                    'price': price,
                    'brand': brand or "Unknown",
                    'title': title[:30],
                    'timestamp': message.created_at,
                    'over_limit': price > TRIMLIST_MAX_PRICE,
                    'wrong_brand': brand not in TRIMLIST_BRANDS if brand else True
                })
    
    if not messages:
        await ctx.send("📭 No recent messages found in trimlist channel")
        return
    
    violations = [m for m in messages if m['over_limit'] or m['wrong_brand']]
    
    embed = discord.Embed(
        title="🏆 Trimlist Channel Analysis", 
        color=0xff0000 if violations else 0x00ff00
    )
    
    embed.add_field(
        name="Recent Items",
        value=f"{len(messages)} items checked",
        inline=True
    )
    
    embed.add_field(
        name="Violations",
        value=f"❌ {len(violations)} items" if violations else "✅ All correct",
        inline=True
    )
    
    embed.add_field(
        name="Price Limit",
        value=f"${TRIMLIST_MAX_PRICE}",
        inline=True
    )
    
    if violations:
        violation_details = []
        for v in violations[:5]:
            reason = []
            if v['over_limit']:
                reason.append(f"${v['price']:.2f} > ${TRIMLIST_MAX_PRICE}")
            if v['wrong_brand']:
                reason.append(f"Wrong brand: {v['brand']}")
            
            violation_details.append(f"• {v['title']}: {', '.join(reason)}")
        
        embed.add_field(
            name="❌ Violations Found",
            value="\n".join(violation_details),
            inline=False
        )
    
    brands_found = set(m['brand'] for m in messages if m['brand'] != "Unknown")
    embed.add_field(
        name="Brands Found",
        value=", ".join(brands_found) if brands_found else "None",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Quick setup verification
@bot.command(name='trimlist_setup')
@commands.has_permissions(administrator=True)
async def trimlist_setup(ctx):
    """Verify trimlist channel setup"""
    
    trimlist_channel = discord.utils.get(guild.text_channels, name="🏆-trimlist")
    
    embed = discord.Embed(
        title="🏆 Trimlist Setup Verification",
        color=0x00ff00 if trimlist_channel else 0xff0000
    )
    
    embed.add_field(
        name="Channel Exists",
        value="✅ Found #🏆-trimlist" if trimlist_channel else "❌ Channel missing!",
        inline=False
    )
    
    embed.add_field(
        name="Target Brands",
        value="\n".join(f"• {brand}" for brand in TRIMLIST_BRANDS),
        inline=True
    )
    
    embed.add_field(
        name="Price Limit", 
        value=f"${TRIMLIST_MAX_PRICE} or less",
        inline=True
    )
    
    embed.add_field(
        name="Test Commands",
        value="`!test_trimlist cdg 45`\n`!test_trimlist rick 70`\n`!check_trimlist`",
        inline=False
    )
    
    if not trimlist_channel:
        embed.add_field(
            name="🔧 Fix Required",
            value="Create the #🏆-trimlist channel first!",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Add debug command to test budget-steals filtering
@bot.command(name='test_budget_filter')
@commands.has_permissions(administrator=True)
async def test_budget_filter(ctx, price: float):
    """Test budget-steals filtering with a specific price"""
    
    test_data = {
        'auction_id': 'test_123',
        'title': 'Test Budget Item',
        'brand': 'Test Brand',
        'price_usd': price,
        'deal_quality': 0.2,
        'price_jpy': int(price * 147),
        'seller_id': 'test_seller',
        'yahoo_url': 'https://yahoo.jp/test',
        'zenmarket_url': 'https://zenmarket.jp/test',
        'image_url': None,
        'sizes': [],
        'end_time': '2025-08-20 12:00:00'
    }
    
    channels = determine_target_channel(price, 'Test Brand', 0.2, 'Test Budget Item', 'test_scraper')
    
    embed = discord.Embed(
        title="🧪 Budget Filter Test",
        color=0x00ff00 if price <= 100 else 0xff0000
    )
    
    embed.add_field(
        name="Test Price",
        value=f"${price:.2f}",
        inline=True
    )
    
    embed.add_field(
        name="Budget Steals Eligible", 
        value="✅ YES" if price <= 100 else "❌ NO",
        inline=True
    )
    
    embed.add_field(
        name="Target Channels",
        value="\n".join(channels) if channels else "None",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Add monitoring command to check recent budget-steals
@bot.command(name='check_budget_steals')
@commands.has_permissions(administrator=True)
async def check_budget_steals(ctx):
    """Check recent items sent to budget-steals channel"""
    
    budget_channel = discord.utils.get(guild.text_channels, name="💰-budget-steals")
    
    if not budget_channel:
        await ctx.send("❌ Budget-steals channel not found!")
        return
    
    # Get last 10 messages from budget-steals
    messages = []
    async for message in budget_channel.history(limit=10):
        if message.embeds:
            embed = message.embeds[0]
            for field in embed.fields:
                if "Price" in field.name:
                    price_text = field.value
                    try:
                        price = float(price_text.replace('$', '').replace(',', '').split()[0])
                        messages.append({
                            'price': price,
                            'timestamp': message.created_at,
                            'over_limit': price > 100
                        })
                    except:
                        pass
    
    if not messages:
        await ctx.send("📭 No recent messages found in budget-steals channel")
        return
    
    over_limit = [m for m in messages if m['over_limit']]
    
    embed = discord.Embed(
        title="💰 Budget-Steals Channel Analysis",
        color=0xff0000 if over_limit else 0x00ff00
    )
    
    embed.add_field(
        name="Recent Messages",
        value=f"{len(messages)} items checked",
        inline=True
    )
    
    embed.add_field(
        name="Over $100 Limit",
        value=f"❌ {len(over_limit)} items" if over_limit else "✅ All under $100",
        inline=True
    )
    
    if over_limit:
        over_prices = [f"${m['price']:.2f}" for m in over_limit[:5]]
        embed.add_field(
            name="Overpriced Items Found",
            value="\n".join(over_prices),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Action Required",
            value="Budget-steals filter is not working correctly!",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='test_exclusions')
@commands.has_permissions(administrator=True)
async def test_exclusions(ctx, *, title: str):
    """Test the enhanced spam filtering with a specific title"""
    
    # Create test listing data
    test_data = {
        'auction_id': 'test_exclusion_123',
        'title': title,
        'brand': 'Test Brand',
        'price_jpy': 10000,
        'price_usd': 67.00,
        'deal_quality': 0.5,
        'scraper_source': 'test_scraper'
    }
    
    # Test final spam check
    is_spam = final_spam_check(test_data)
    
    # Create test embed
    embed = create_enhanced_listing_embed(test_data)
    
    # Add test results
    embed.add_field(
        name="🧪 Test Results",
        value=f"**Spam Check:** {'🚫 BLOCKED' if is_spam else '✅ ALLOWED'}\n**Title:** {title[:100]}...",
        inline=False
    )
    
    embed.color = 0xff0000 if is_spam else 0x00ff00
    
    await ctx.send(embed=embed)
    
    # Additional detailed logging
    print(f"🧪 Test exclusions command used with title: {title}")
    print(f"   Result: {'BLOCKED' if is_spam else 'ALLOWED'}")

def run_flask():
    try:
        port = int(os.environ.get('PORT', 8000))
        print(f"🌐 Starting Flask server on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Flask server error: {e}")
        time.sleep(5)
        run_flask()

def run_discord_bot():
    """Run Discord bot in a separate thread"""
    try:
        print("🤖 Starting Discord bot in background...")
        
        # Use bot.run() which handles its own event loop properly
        bot.run(BOT_TOKEN)
            
    except Exception as e:
        print(f"❌ Discord bot thread error: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# NOTIFICATION TIER SYSTEM COMMANDS
# ============================================================================

@bot.command(name='setup_notification_tiers')
async def setup_notification_tiers(ctx):
    """Initialize the notification tier system (admin only)"""
    # Check if user is admin (you can customize this check)
    if ctx.author.id != 123456789012345678:  # Replace with your admin user ID
        await ctx.send("❌ This command is admin only.")
        return
    
    try:
        # Initialize tier system - if available
        if ADVANCED_FEATURES_AVAILABLE and tier_manager:
            tier_manager.set_bot(bot)
            
            # Find daily digest channel
            daily_digest_channel = discord.utils.get(ctx.guild.channels, name='daily-digest')
            if daily_digest_channel:
                tier_manager.set_daily_digest_channel(daily_digest_channel.id)
                await ctx.send(f"✅ Notification tier system initialized!\n📰 Daily digest channel: {daily_digest_channel.mention}")
            else:
                await ctx.send("⚠️ Please create a #daily-digest channel first, then run this command again.")
        
        # Start scheduler - if available
        if ADVANCED_FEATURES_AVAILABLE and daily_scheduler:
            daily_scheduler.start()
            await ctx.send("📅 Daily scheduler started (digest at 9 AM UTC, counter reset at midnight UTC)")
        else:
            await ctx.send("⚠️ Advanced features not available. Bot running in basic mode.")
        
    except Exception as e:
        await ctx.send(f"❌ Error initializing tier system: {e}")

@bot.command(name='upgrade_tier')
async def upgrade_tier(ctx, user: discord.Member, tier: str):
    """Upgrade a user's notification tier (admin only)"""
    # Check if user is admin
    if ctx.author.id != 123456789012345678:  # Replace with your admin user ID
        await ctx.send("❌ This command is admin only.")
        return
    
    if tier.lower() not in ['free', 'standard', 'instant']:
        await ctx.send("❌ Invalid tier. Use: free, standard, or instant")
        return
    
    try:
        success = await tier_manager.upgrade_user_tier(user.id, tier.lower())
        if success:
            tier_name = tier_manager.TIER_NAMES[tier.lower()]
            await ctx.send(f"✅ Upgraded {user.mention} to **{tier_name}** tier!")
        else:
            await ctx.send(f"❌ Failed to upgrade {user.mention}")
    except Exception as e:
        await ctx.send(f"❌ Error upgrading user: {e}")

@bot.command(name='my_notifications')
async def my_notifications(ctx):
    """Show user's current notification tier and usage"""
    try:
        user_id = ctx.author.id
        tier = await tier_manager.get_user_tier(user_id)
        count, last_reset = await tier_manager.get_user_daily_count(user_id)
        limit = tier_manager.TIER_LIMITS[tier]
        
        embed = discord.Embed(
            title="🔔 Your Notification Settings",
            color=0x7289da,
            timestamp=datetime.now(timezone.utc)
        )
        
        tier_name = tier_manager.TIER_NAMES[tier]
        embed.add_field(name="Current Tier", value=tier_name, inline=True)
        
        if tier == 'free':
            embed.add_field(
                name="Notifications", 
                value="Daily digest only\n(Posted to #daily-digest at 9 AM UTC)", 
                inline=True
            )
        elif tier == 'standard':
            embed.add_field(
                name="Daily Usage", 
                value=f"{count}/{limit} notifications used", 
                inline=True
            )
            embed.add_field(
                name="Reset Time", 
                value="Midnight UTC daily", 
                inline=True
            )
        else:  # instant
            embed.add_field(
                name="Notifications", 
                value="Unlimited real-time DMs", 
                inline=True
            )
        
        embed.add_field(
            name="Upgrade Options",
            value="**Standard ($12/month)**: 50 real-time DMs per day\n"
                  "**Instant ($25/month)**: Unlimited real-time notifications\n"
                  "Contact an admin to upgrade!",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error getting notification info: {e}")

@bot.command(name='send_digest_now')
async def send_digest_now(ctx):
    """Manually trigger daily digest (admin only)"""
    # Check if user is admin
    if ctx.author.id != 123456789012345678:  # Replace with your admin user ID
        await ctx.send("❌ This command is admin only.")
        return
    
    try:
        await ctx.send("📰 Sending daily digest...")
        success = await tier_manager.send_daily_digest()
        if success:
            await ctx.send("✅ Daily digest sent successfully!")
        else:
            await ctx.send("❌ Failed to send daily digest")
    except Exception as e:
        await ctx.send(f"❌ Error sending digest: {e}")

@bot.command(name='tier_stats')
async def tier_stats(ctx):
    """Show tier distribution statistics (admin only)"""
    # Check if user is admin
    if ctx.author.id != 123456789012345678:  # Replace with your admin user ID
        await ctx.send("❌ This command is admin only.")
        return
    
    try:
        stats = await tier_manager.get_tier_stats()
        
        embed = discord.Embed(
            title="📊 Notification Tier Statistics",
            color=0x7289da,
            timestamp=datetime.now(timezone.utc)
        )
        
        total_users = sum(stats.values())
        embed.add_field(name="Total Active Users", value=str(total_users), inline=True)
        
        for tier, count in stats.items():
            tier_name = tier_manager.TIER_NAMES[tier]
            percentage = (count / total_users * 100) if total_users > 0 else 0
            embed.add_field(
                name=tier_name, 
                value=f"{count} users ({percentage:.1f}%)", 
                inline=True
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error getting tier stats: {e}")

@bot.command(name='testdigest')
async def test_digest(ctx):
    """Manually trigger daily digest generation (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        await ctx.send("🔄 Generating test digest...")
        
        if digest_manager:
            success = await digest_manager.generate_daily_digest()
            if success:
                await ctx.send("✅ Test digest posted successfully")
            else:
                await ctx.send("❌ Failed to post test digest - check console logs")
        else:
            await ctx.send("❌ Digest manager not available")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Test digest error: {traceback.format_exc()}")

@bot.command(name='checkqueue')
async def check_queue(ctx):
    """Show queue statistics (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        if tier_manager_new:
            stats = await tier_manager_new.get_queue_stats()
            
            embed = discord.Embed(title="📊 Queue Statistics", color=0x00ff00)
            embed.add_field(name="Total Listings", value=stats.get("total_listings", 0), inline=True)
            embed.add_field(name="Unprocessed", value=stats.get("unprocessed_listings", 0), inline=True)
            embed.add_field(name="Past 24h", value=stats.get("past_24h_listings", 0), inline=True)
            embed.add_field(name="Standard Feed 24h", value=f"{stats.get('standard_feed_24h_count', 0)}/100", inline=True)
            
            # Add current time
            now = datetime.now(timezone.utc)
            embed.add_field(name="Current UTC Time", value=now.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Tier manager not available")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Check queue error: {traceback.format_exc()}")

@bot.command(name='resetstandard')
async def reset_standard(ctx):
    """Reset standard-feed counter for testing (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        if tier_manager_new:
            # Get current count before reset
            current_count = await tier_manager_new.get_standard_feed_count_24h()
            
            success = await tier_manager_new.reset_standard_feed_counter()
            if success:
                await ctx.send(f"✅ Standard-feed counter reset successfully (was at {current_count}/100)")
            else:
                await ctx.send("❌ Failed to reset standard-feed counter")
        else:
            await ctx.send("❌ Tier manager not available")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Reset standard error: {traceback.format_exc()}")

@bot.command(name='debugdigest')
async def debug_digest(ctx):
    """Debug daily digest generation (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        if tier_manager_new:
            # Check what listings exist
            stats = await tier_manager_new.get_queue_stats()
            
            # Try to get listings for digest
            listings = await tier_manager_new.get_top_listings_for_digest(hours=24, limit=20)
            
            embed = discord.Embed(title="🔍 Digest Debug Info", color=0xff9900)
            embed.add_field(name="Total Listings", value=stats.get("total_listings", 0), inline=True)
            embed.add_field(name="Unprocessed", value=stats.get("unprocessed_listings", 0), inline=True)
            embed.add_field(name="Past 24h", value=stats.get("past_24h_listings", 0), inline=True)
            embed.add_field(name="Digest Listings Found", value=len(listings), inline=True)
            
            if listings:
                # Show top 3 listings
                top_listings = listings[:3]
                for i, (listing_data, score) in enumerate(top_listings, 1):
                    title = listing_data.get('title', 'No title')[:50]
                    embed.add_field(
                        name=f"#{i} (Score: {score:.2f})", 
                        value=f"{title}...", 
                        inline=False
                    )
            else:
                embed.add_field(name="Issue", value="No listings found for digest", inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Tier manager not available")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Debug digest error: {traceback.format_exc()}")

@bot.command(name='debugstandard')
async def debug_standard(ctx):
    """Debug standard-feed routing (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        if tier_manager_new:
            # Get current count
            count_24h = await tier_manager_new.get_standard_feed_count_24h()
            
            # Check if tier system is available
            tier_available = TIER_SYSTEM_AVAILABLE
            channel_router_available = channel_router is not None
            
            embed = discord.Embed(title="🔍 Standard Feed Debug", color=0xff6600)
            embed.add_field(name="Current 24h Count", value=f"{count_24h}/100", inline=True)
            embed.add_field(name="Tier System Available", value="✅" if tier_available else "❌", inline=True)
            embed.add_field(name="Channel Router Available", value="✅" if channel_router_available else "❌", inline=True)
            
            # Check channel existence
            guild = ctx.guild
            standard_channel = discord.utils.get(guild.channels, name='standard-feed')
            if not standard_channel:
                standard_channel = discord.utils.get(guild.channels, name='📦-standard-feed')
            
            embed.add_field(name="Standard Feed Channel", value=f"#{standard_channel.name}" if standard_channel else "❌ Not found", inline=True)
            
            if standard_channel:
                has_permission = standard_channel.permissions_for(guild.me).send_messages
                embed.add_field(name="Bot Permission", value="✅" if has_permission else "❌", inline=True)
            
            # Check recent standard-feed posts in database
            import aiosqlite
            async with aiosqlite.connect(tier_manager_new.db_path) as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM listing_queue 
                    WHERE scraper_source = 'standard_feed_posted' 
                    AND received_at > datetime('now', '-1 hour')
                """)
                recent_posts = (await cursor.fetchone())[0]
                embed.add_field(name="Posts Last Hour", value=recent_posts, inline=True)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Tier manager not available")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Debug standard error: {traceback.format_exc()}")

@bot.command(name='teststandard')
async def test_standard_feed(ctx):
    """Manually trigger standard-feed posting (admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Admin only command")
        return
    
    try:
        await ctx.send("🔄 Manually posting top 5 listings to standard-feed...")
        await post_top_standard_feed_listings()
        await ctx.send("✅ Standard-feed posting completed - check #standard-feed channel")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
        import traceback
        print(f"❌ Test standard error: {traceback.format_exc()}")

@bot.command(name='subscribe')
async def subscribe_command(ctx, tier: str):
    """Subscribe to a tier using Stripe"""
    try:
        if not STRIPE_AVAILABLE or not stripe_manager:
            await ctx.send("❌ Stripe is not configured. Please contact an administrator.")
            return
            
        if tier.lower() not in ['standard', 'instant']:
            await ctx.send("❌ Invalid tier. Use: standard, instant")
            return
        
        discord_id = str(ctx.author.id)
        
        # Check if user already has this tier
        if tier_manager_new:
            current_tier = await tier_manager_new.get_user_tier(discord_id)
            if current_tier == tier.lower():
                await ctx.send(f"✅ You are already on the {tier.title()} tier.")
                return
        
        # Create Stripe checkout session
        success_url = f"https://motivated-stillness-production.up.railway.app/stripe-success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"https://motivated-stillness-production.up.railway.app/stripe-cancel"
        
        checkout_url = await stripe_manager.create_checkout_session(
            discord_id, tier.lower(), success_url, cancel_url
        )
        
        if checkout_url:
            embed = discord.Embed(
                title=f"💳 Upgrade to {tier.title()} Tier",
                description=f"Click the link below to complete your subscription for the {tier.title()} tier. This link will expire in 24 hours.",
                color=discord.Color.blue()
            )
            embed.add_field(name="Payment Link", value=f"[Click Here to Subscribe]({checkout_url})", inline=False)
            embed.set_footer(text="Please complete the payment within 24 hours.")
            await ctx.author.send(embed=embed)
            await ctx.send(f"✅ Check your DMs, {ctx.author.mention}! I've sent you the subscription link.")
        else:
            await ctx.send("❌ Failed to create a Stripe checkout session. Please try again later or contact support.")
        
    except Exception as e:
        await ctx.send(f"❌ An error occurred while creating your subscription. Please try again later.")
        print(f"❌ Subscribe command error: {e}")

@bot.command(name='subscription')
async def subscription_command(ctx):
    """Check subscription status"""
    try:
        if not STRIPE_AVAILABLE or not stripe_manager:
            await ctx.send("❌ Stripe is not configured. Please contact an administrator.")
            return
            
        discord_id = str(ctx.author.id)
        
        # Get user tier and subscription info
        if tier_manager_new:
            user_stats = await tier_manager_new.get_user_stats(discord_id)
            current_tier = user_stats.get('tier', 'free')
            
            embed = discord.Embed(title="💳 Your Subscription Status", color=discord.Color.gold())
            embed.add_field(name="Current Tier", value=current_tier.title(), inline=False)
            
            if current_tier != 'free':
                subscription_id = user_stats.get('stripe_subscription_id')
                if subscription_id and stripe_manager:
                    status = await stripe_manager.get_subscription_status(subscription_id)
                    embed.add_field(name="Stripe Status", value=status.replace('_', ' ').title() if status else "Unknown", inline=True)
                    
                    period_end = user_stats.get('current_period_end')
                    if period_end:
                        embed.add_field(name="Billing Period Ends", value=period_end, inline=True)
                else:
                    embed.add_field(name="Stripe Status", value="Not linked", inline=True)
            else:
                embed.add_field(name="Upgrade Options", value="Use `!subscribe standard` or `!subscribe instant` to upgrade", inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Tier system not available. Please contact an administrator.")
        
    except Exception as e:
        await ctx.send(f"❌ An error occurred while checking your subscription status.")
        print(f"❌ Subscription command error: {e}")

@bot.command(name='cancel')
async def cancel_command(ctx):
    """Cancel subscription"""
    try:
        if not STRIPE_AVAILABLE or not stripe_manager:
            await ctx.send("❌ Stripe is not configured. Please contact an administrator.")
            return
            
        discord_id = str(ctx.author.id)
        
        if tier_manager_new:
            user_stats = await tier_manager_new.get_user_stats(discord_id)
            current_tier = user_stats.get('tier', 'free')
            
            if current_tier == 'free':
                await ctx.send("❌ You don't have an active subscription to cancel.")
                return
            
            subscription_id = user_stats.get('stripe_subscription_id')
            if not subscription_id:
                await ctx.send("❌ Could not find your subscription ID. Please contact support.")
                return
            
            success = await stripe_manager.cancel_subscription(subscription_id)
            if success:
                # Downgrade user to free tier
                await tier_manager_new.set_user_tier(discord_id, 'free')
                await ctx.send("✅ Your subscription has been cancelled. You will be downgraded to Free tier at the end of your current billing period.")
                print(f"User {discord_id} cancelled subscription {subscription_id}")
            else:
                await ctx.send("❌ Failed to cancel your subscription. Please try again later or contact support.")
        else:
            await ctx.send("❌ Tier system not available. Please contact an administrator.")
        
    except Exception as e:
        await ctx.send(f"❌ An error occurred while cancelling your subscription. Please try again later.")
        print(f"❌ Cancel command error: {e}")

# ============================================================================
# TIER NOTIFICATION FUNCTIONS
# ============================================================================

async def send_tier_notifications(listing_data):
    """Send real-time notifications to users based on their tier"""
    try:
        # Get all active users with real-time notifications enabled
        users = db_manager.execute_query(
            'SELECT user_id FROM user_subscriptions WHERE status = %s AND tier IN (%s, %s)'
            if db_manager.use_postgres else
            'SELECT user_id FROM user_subscriptions WHERE status = ? AND tier IN (?, ?)',
            ('active', 'standard', 'instant'),
            fetch_all=True
        )
        
        if not users:
            return
        
        # Send notifications to eligible users
        notification_tasks = []
        for user_row in users:
            user_id = user_row['user_id'] if isinstance(user_row, dict) else user_row[0]
            notification_tasks.append(tier_manager.send_real_time_notification(user_id, listing_data))
        
        # Execute all notifications concurrently
        if notification_tasks:
            results = await asyncio.gather(*notification_tasks, return_exceptions=True)
            successful = sum(1 for result in results if result is True)
            logger.info(f"Sent {successful}/{len(notification_tasks)} real-time notifications for listing {listing_data.get('auction_id', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error sending tier notifications: {e}")

def main():
    try:
        print("🚀 Starting Discord bot...")
        
        # Initialize bot components before starting Discord thread
        print("🔧 Initializing bot components...")
        
        # Initialize preference learner and delayed manager
        preference_learner = UserPreferenceLearner()
        delayed_manager = DelayedListingManager()
        
        # Initialize notification tier system - if available
        if ADVANCED_FEATURES_AVAILABLE and tier_manager:
            tier_manager.set_bot(bot)
        
        print("🤖 Starting Discord bot in background thread...")
        discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
        discord_thread.start()
        
        # Give Discord bot time to initialize
        time.sleep(3)
        print("✅ Discord bot thread started")
        
        print("🔒 SECURITY: Performing startup security checks...")
        
        # For Railway deployment, allow Flask server to run without Discord bot token
        # The Discord bot will be started separately on local machine
        if not BOT_TOKEN or len(BOT_TOKEN) < 30:
            print("⚠️ Discord bot token not configured - Flask server will run without Discord bot")
            print("🌐 This is expected for Railway deployment")
            print("🤖 Discord bot should be started separately on local machine")
        else:
            print("✅ Discord bot token configured")
        
        if not GUILD_ID:
            print("⚠️ Discord guild ID not configured - Flask server will run without Discord bot")
            print("🌐 This is expected for Railway deployment")
            print("🤖 Discord bot should be started separately on local machine")
        else:
            print(f"✅ Discord guild ID configured: {GUILD_ID}")
        
        print("✅ SECURITY: Basic security checks passed")
        print(f"🎯 Target server ID: {GUILD_ID}")
        print(f"📦 Batch size: {BATCH_SIZE} listings per message")
        
        try:
            print("🔧 Attempting database initialization...")
            db_manager.init_database()
            print("✅ Database initialized")
            
            if init_subscription_tables():
                print("✅ Subscription tables ready")
            else:
                print("⚠️ Subscription tables warning - continuing anyway")
                
        except Exception as e:
            print(f"⚠️ Database initialization warning: {e}")
            print("🔄 Continuing without database - will retry later")
        
        print("🌐 Starting Flask server as main process...")
        print("🤖 Discord bot will be started separately to avoid asyncio conflicts")
        
        # Just run Flask server as main process - Discord bot can be started separately
        run_flask()
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in main(): {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        
        print("🌐 Emergency mode - keeping webhook server alive")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("👋 Shutting down...")

if __name__ == "__main__":
    # Initialize database
    if not test_postgres_connection():
        print("⚠️ Database connection issues detected")
    
    # Run the bot
    print("🤖 Starting Discord bot...")
    main()