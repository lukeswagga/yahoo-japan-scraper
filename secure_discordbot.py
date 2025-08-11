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
import hmac
import hashlib
from database_manager import (
    db_manager, get_user_proxy_preference, set_user_proxy_preference, 
    add_listing, add_user_bookmark, clear_user_bookmarks,
    init_subscription_tables, test_postgres_connection,
    get_user_size_preferences, set_user_size_preferences, mark_reminder_sent
)

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
        print(f"❌ Error getting size preferences: {e}")
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
        print(f"❌ Error setting size preferences: {e}")
        return False

def add_user_bookmark(user_id, auction_id, message_id, channel_id, auction_end_time):
    """Add a user bookmark to the database"""
    try:
        if db_manager.use_postgres:
            db_manager.execute_query('''
                INSERT INTO user_bookmarks (user_id, auction_id, message_id, channel_id, auction_end_time)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, auction_id, message_id, channel_id, auction_end_time))
        else:
            db_manager.execute_query('''
                INSERT INTO user_bookmarks (user_id, auction_id, message_id, channel_id, auction_end_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, auction_id, message_id, channel_id, auction_end_time))
        
        return True
        
    except Exception as e:
        print(f"❌ Error adding bookmark: {e}")
        return False

class BookmarkReminderSystem:
    def __init__(self, bot):
        self.bot = bot
        self.running = True
    
    async def start_reminder_loop(self):
        """Main loop for checking and sending bookmark reminders"""
        while self.running:
            try:
                await self.check_1h_reminders()
                await self.check_5m_reminders()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                print(f"❌ Reminder loop error: {e}")
                await asyncio.sleep(300)
    
    async def check_1h_reminders(self):
        """Check for auctions ending in 1 hour"""
        try:
            reminders = get_pending_reminders('1h')
            
            for user_id, auction_id, channel_id, title, zenmarket_url, end_time in reminders:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    user = self.bot.get_user(user_id)
                    if not user:
                        user = await self.bot.fetch_user(user_id)
                    
                    embed = discord.Embed(
                        title="⏰ 1 Hour Reminder - Auction Ending Soon!",
                        description=f"Your bookmarked auction is ending in **1 hour**!",
                        color=0xffa500
                    )
                    
                    embed.add_field(
                        name="📦 Item",
                        value=f"[{title[:100]}...]({zenmarket_url})" if len(title) > 100 else f"[{title}]({zenmarket_url})",
                        inline=False
                    )
                    
                    if end_time:
                        try:
                            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                            embed.add_field(
                                name="⏱️ Exact End Time",
                                value=f"{end_dt.strftime('%H:%M UTC')}",
                                inline=True
                            )
                        except:
                            pass
                    
                    embed.add_field(
                        name="💡 Action Required",
                        value="Place your bid now if you want this item!",
                        inline=False
                    )
                    
                    embed.set_footer(text=f"Auction ID: {auction_id}")
                    
                    await channel.send(f"{user.mention}", embed=embed)
                    
                    mark_reminder_sent(user_id, auction_id, '1h')
                    print(f"⏰ Sent 1h reminder to {user.name} for {auction_id}")
                    
                except Exception as e:
                    print(f"❌ Error sending 1h reminder: {e}")
                    
        except Exception as e:
            print(f"❌ Error checking 1h reminders: {e}")
    
    async def check_5m_reminders(self):
        """Check for auctions ending in 5 minutes"""
        try:
            reminders = get_pending_reminders('5m')
            
            for user_id, auction_id, channel_id, title, zenmarket_url, end_time in reminders:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    user = self.bot.get_user(user_id)
                    if not user:
                        user = await self.bot.fetch_user(user_id)
                    
                    embed = discord.Embed(
                        title="🚨 FINAL 5 MINUTE WARNING!",
                        description=f"**⚠️ YOUR BOOKMARKED AUCTION ENDS IN 5 MINUTES! ⚠️**",
                        color=0xff0000
                    )
                    
                    embed.add_field(
                        name="📦 Item",
                        value=f"[{title[:100]}...]({zenmarket_url})" if len(title) > 100 else f"[{title}]({zenmarket_url})",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🔥 LAST CHANCE",
                        value="**BID NOW OR LOSE THIS ITEM FOREVER!**",
                        inline=False
                    )
                    
                    embed.set_footer(text=f"Auction ID: {auction_id} | THIS IS YOUR FINAL REMINDER")
                    
                    message = await channel.send(f"🚨 {user.mention} 🚨", embed=embed)
                    
                    await message.add_reaction("⏰")
                    await message.add_reaction("🔥")
                    await message.add_reaction("💸")
                    
                    mark_reminder_sent(user_id, auction_id, '5m')
                    print(f"🚨 Sent FINAL 5m reminder to {user.name} for {auction_id}")
                    
                except Exception as e:
                    print(f"❌ Error sending 5m reminder: {e}")
                    
        except Exception as e:
            print(f"❌ Error checking 5m reminders: {e}")

def get_pending_reminders(reminder_type):
    """Get pending reminders from database"""
    try:
        if reminder_type == '1h':
            time_threshold = datetime.now() + timedelta(hours=1)
        elif reminder_type == '5m':
            time_threshold = datetime.now() + timedelta(minutes=5)
        else:
            return []
        
        if db_manager.use_postgres:
            reminders = db_manager.execute_query('''
                SELECT ub.user_id, ub.auction_id, ub.channel_id, l.title, l.zenmarket_url, ub.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.auction_end_time <= %s
                AND ub.reminder_1h_sent = FALSE
                ORDER BY ub.auction_end_time ASC
            ''', (time_threshold,), fetch_all=True)
        else:
            reminders = db_manager.execute_query('''
                SELECT ub.user_id, ub.auction_id, ub.channel_id, l.title, l.zenmarket_url, ub.auction_end_time
                FROM user_bookmarks ub
                JOIN listings l ON ub.auction_id = l.auction_id
                WHERE ub.auction_end_time <= ?
                AND ub.reminder_1h_sent = 0
                ORDER BY ub.auction_end_time ASC
            ''', (time_threshold,), fetch_all=True)
        
        return reminders
        
    except Exception as e:
        print(f"❌ Error getting pending reminders: {e}")
        return []

def mark_reminder_sent(user_id, auction_id, reminder_type):
    """Mark reminder as sent in database"""
    try:
        if reminder_type == '1h':
            if db_manager.use_postgres:
                db_manager.execute_query('''
                    UPDATE user_bookmarks 
                    SET reminder_1h_sent = TRUE 
                    WHERE user_id = %s AND auction_id = %s
                ''', (user_id, auction_id))
            else:
                db_manager.execute_query('''
                    UPDATE user_bookmarks 
                    SET reminder_1h_sent = 1 
                    WHERE user_id = ? AND auction_id = ?
                ''', (user_id, auction_id))
        elif reminder_type == '5m':
            if db_manager.use_postgres:
                db_manager.execute_query('''
                    UPDATE user_bookmarks 
                    SET reminder_5m_sent = TRUE 
                    WHERE user_id = %s AND auction_id = %s
                ''', (user_id, auction_id))
            else:
                db_manager.execute_query('''
                    UPDATE user_bookmarks 
                    SET reminder_5m_sent = 1 
                    WHERE user_id = ? AND auction_id = ?
                ''', (user_id, auction_id))
        
        print(f"✅ Marked {reminder_type} reminder as sent for {auction_id}")
        
    except Exception as e:
        print(f"❌ Error marking reminder sent: {e}")

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

app = Flask(__name__)
start_time = time.time()

@app.route('/health', methods=['GET'])
def health():
    try:
        return jsonify({
            "status": "healthy",
            "service": "discord-bot",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error", 
            "error": str(e)
        }), 500

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "Archive Collective Discord Bot", 
        "status": "running",
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
        print("❌ SECURITY ERROR: Invalid token format detected!")
        exit(1)
    
    print("✅ SECURITY: Secure configuration loaded from environment variables")
    print("🔒 Token length:", len(bot_token), "characters (hidden for security)")
    
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
BATCH_SIZE = 4
BATCH_TIMEOUT = 30
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
    "Yohji Yamamoto": "yohji_yamamoto"
}

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

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
        
        # Store with end time for reminders
        success = add_user_bookmark(
            user_id, 
            auction_data['auction_id'], 
            bookmark_message.id, 
            bookmark_channel.id,
            auction_data.get('auction_end_time')
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

async def send_single_listing_enhanced(auction_data):
    """Send listing with proper database error handling"""
    try:
        title = auction_data.get('title', 'Unknown Item')[:100]
        brand = auction_data.get('brand', 'Unknown')
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
        
        # Send to main channel
        main_channel = discord.utils.get(guild.text_channels, name="🎯-auction-alerts")
        main_message = None
        if main_channel:
            embed = create_listing_embed(auction_data)
            main_message = await main_channel.send(embed=embed)
            print(f"📤 Sent to MAIN channel: {title[:30]}...")
            
            # Add to database with end time - fixed function call
            success = add_listing(auction_data, main_message.id)
            if not success:
                print(f"❌ Failed to add listing to database: {auction_data['auction_id']}")
            
            # Add reactions for users to interact with
            await main_message.add_reaction("👍")
            await main_message.add_reaction("👎")
        
        # Send to brand channel
        brand_channel = None
        if brand and brand in BRAND_CHANNEL_MAP:
            brand_channel = await get_or_create_brand_channel(brand)
            if brand_channel:
                embed = create_listing_embed(auction_data)
                brand_message = await brand_channel.send(embed=embed)
                await brand_message.add_reaction("👍")
                await brand_message.add_reaction("👎")
                print(f"🏷️ Also sent to brand channel: {brand_channel.name}")
        
        # Check for size alerts with fixed query
        if sizes and size_alert_system:
            try:
                all_users = db_manager.execute_query(
                    'SELECT user_id FROM user_preferences WHERE size_alerts_enabled = TRUE' if db_manager.use_postgres else 'SELECT user_id FROM user_preferences WHERE size_alerts_enabled = 1',
                    fetch_all=True
                )
                
                if all_users:
                    for user_row in all_users:
                        user_id = user_row[0] if isinstance(user_row, (list, tuple)) else user_row['user_id']
                        user_sizes, alerts_enabled = get_user_size_preferences(user_id)
                        
                        if alerts_enabled and user_sizes:
                            matching_sizes = [size for size in sizes if any(user_size.lower() in size.lower() for user_size in user_sizes)]
                            
                            if matching_sizes:
                                try:
                                    user = await bot.fetch_user(user_id)
                                    if user:
                                        embed = create_listing_embed(auction_data)
                                        embed.title = f"🎯 SIZE ALERT: {embed.title}"
                                        embed.add_field(
                                            name="📏 Matching Sizes", 
                                            value=", ".join(matching_sizes), 
                                            inline=False
                                        )
                                        await user.send(embed=embed)
                                        print(f"📬 Size alert sent to user {user_id} for sizes: {matching_sizes}")
                                except Exception as e:
                                    print(f"❌ Failed to send size alert to user {user_id}: {e}")
            except Exception as e:
                print(f"❌ Error processing size alerts: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Full traceback: {e}")
        import traceback
        traceback.print_exc()
        return False

async def send_individual_listings_with_rate_limit(batch_data):
    try:
        for i, auction_data in enumerate(batch_data, 1):
            success = await send_single_listing_enhanced(auction_data)
            if success:
                print(f"✅ Sent {i}/{len(batch_data)}")
            else:
                print(f"⚠️ Skipped {i}/{len(batch_data)}")
            
            if i < len(batch_data):
                await asyncio.sleep(3)
        
    except Exception as e:
        print(f"❌ Error in rate-limited sending: {e}")

@bot.event
async def on_ready():
    global guild, auction_channel, preference_learner, tier_manager, delayed_manager, reminder_system, size_alert_system
    print(f'✅ Bot connected as {bot.user}!')
    guild = bot.get_guild(GUILD_ID)
    
    if guild:
        print(f'🎯 Connected to server: {guild.name}')
        auction_channel = await get_or_create_auction_channel()
        
        preference_learner = UserPreferenceLearner()
        tier_manager = PremiumTierManager(bot)
        delayed_manager = DelayedListingManager()
        
        # Initialize new systems
        reminder_system = BookmarkReminderSystem(bot)
        size_alert_system = SizeAlertSystem(bot)
        
        # Start background tasks
        bot.loop.create_task(process_batch_buffer())
        bot.loop.create_task(delayed_manager.process_delayed_queue())
        bot.loop.create_task(reminder_system.start_reminder_loop())
        
        print("⏰ Started batch buffer processor")
        print("🧠 User preference learning system initialized")
        print("💎 Premium tier system initialized")
        print("⏳ Delayed listing manager started")
        print("🔔 Bookmark reminder system started")
        print("📏 Size alert system initialized")
    else:
        print(f'❌ Could not find server with ID: {GUILD_ID}')


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
    if reaction.message.embeds and len(reaction.message.embeds) > 0:
        embed = reaction.message.embeds[0]
        if embed.title and "Setup" in embed.title:
            await handle_setup_reaction(reaction, user)
            return
    
    if str(reaction.emoji) not in ["👍", "👎"]:
        return
    
    proxy_service, setup_complete = get_user_proxy_preference(user.id)
    if not setup_complete:
        embed = discord.Embed(
            title="⚠️ Setup Required",
            description="Please complete your setup first using `!setup`!",
            color=0xff9900
        )
        dm_channel = await user.create_dm()
        await dm_channel.send(embed=embed)
        return
    
    if not (reaction.message.channel.name == AUCTION_CHANNEL_NAME or 
            reaction.message.channel.name.startswith("🏷️-")):
        return
    
    if not reaction.message.embeds:
        return
    
    embed = reaction.message.embeds[0]
    footer_text = embed.footer.text if embed.footer else ""
    
    auction_id_match = re.search(r'ID: (\w+)', footer_text)
    if not auction_id_match:
        return
    
    auction_id = auction_id_match.group(1)
    reaction_type = "thumbs_up" if str(reaction.emoji) == "👍" else "thumbs_down"
    
    result = db_manager.execute_query('''
        SELECT title, brand, price_jpy, price_usd, seller_id, yahoo_url, deal_quality
        FROM listings WHERE auction_id = ?
    ''', (auction_id,), fetch_one=True)
    
    if result:
        title, brand, price_jpy, price_usd, seller_id, yahoo_url, deal_quality = result
        
        auction_data = {
            'auction_id': auction_id,
            'title': title,
            'brand': brand,
            'price_jpy': price_jpy,
            'price_usd': price_usd,
            'seller_id': seller_id,
            'deal_quality': deal_quality,
            'zenmarket_url': generate_proxy_url(auction_id, proxy_service),
            'image_url': ''
        }
        
        if preference_learner:
            preference_learner.learn_from_reaction(user.id, auction_data, reaction_type)
        
        # Note: User reaction logged via preference_learner above
        
        if reaction_type == "thumbs_up":
            print(f"👍 User {user.name} liked {auction_data['title'][:30]}... - Creating bookmark")
            bookmark_success = await create_bookmark_for_user_enhanced(user.id, auction_data, reaction.message)
            
            if bookmark_success:
                await reaction.message.add_reaction("📚")
                await reaction.message.add_reaction("✅")
                print(f"✅ Bookmark created successfully for {user.name}")
            else:
                await reaction.message.add_reaction("⚠️")
                print(f"⚠️ Bookmark failed for {user.name}")
        else:
            await reaction.message.add_reaction("❌")
        
        print(f"✅ Learned from {user.name}'s {reaction_type} on {brand} item")

async def handle_setup_reaction(reaction, user):
    emoji = str(reaction.emoji)
    
    selected_proxy = None
    for key, proxy in SUPPORTED_PROXIES.items():
        if proxy['emoji'] == emoji:
            selected_proxy = key
            break
    
    if not selected_proxy:
        return
    
    set_user_proxy_preference(user.id, selected_proxy)
    
    proxy_info = SUPPORTED_PROXIES[selected_proxy]
    embed = discord.Embed(
        title="✅ Setup Complete!",
        description=f"Great choice! You've selected **{proxy_info['name']}** {proxy_info['emoji']}",
        color=0x00ff00
    )
    
    embed.add_field(
        name="🎯 What happens now?",
        value=f"All auction listings will now include links formatted for {proxy_info['name']}. You can start reacting to listings with 👍/👎 to train your personal AI!",
        inline=False
    )
    
    embed.add_field(
        name="📚 Bookmarks",
        value="When you react 👍 to listings, they'll be automatically bookmarked in your own private channel!",
        inline=False
    )
    
    dm_channel = await user.create_dm()
    await dm_channel.send(embed=embed)
    
    await reaction.message.channel.send(f"✅ {user.mention} - Setup complete! Check your DMs.", delete_after=10)

@bot.command(name='setup')
async def setup_command(ctx):
    user_id = ctx.author.id
    
    proxy_service, setup_complete = get_user_proxy_preference(user_id)
    
    if setup_complete:
        current_proxy = SUPPORTED_PROXIES[proxy_service]
        embed = discord.Embed(
            title="⚙️ Your Current Setup",
            description=f"You're already set up! Your current proxy service is **{current_proxy['name']}** {current_proxy['emoji']}",
            color=0x00ff00
        )
        
        bookmark_count = db_manager.execute_query(
            'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?',
            (user_id,),
            fetch_one=True
        )
        
        if bookmark_count:
            embed.add_field(
                name="📚 Your Bookmarks",
                value=f"You have **{bookmark_count[0]}** bookmarked items",
                inline=False
            )
        
        await ctx.send(embed=embed)
        return
    
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

@bot.command(name='set_sizes')
async def set_sizes_command(ctx, *sizes):
    """Set preferred sizes for alerts"""
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
            embed = create_listing_embed(auction_data)
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
        await ctx.send(f"User preferences count: {result[0] if result else 'Error'}")
        
        result2 = db_manager.execute_query('SELECT COUNT(*) FROM reactions', fetch_one=True)
        await ctx.send(f"Reactions count: {result2[0] if result2 else 'Error'}")
        
        listings_count = db_manager.execute_query('SELECT COUNT(*) FROM listings', fetch_one=True)
        await ctx.send(f"Total listings in DB: {listings_count[0] if listings_count else 'Error'}")
        
        recent_listings = db_manager.execute_query('''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > NOW() - INTERVAL '1 day'
        ''' if db_manager.use_postgres else '''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > datetime('now', '-1 day')
        ''', fetch_one=True)
        await ctx.send(f"Recent listings (24h): {recent_listings[0] if recent_listings else 'Error'}")
        
        recent_ids = db_manager.execute_query('''
            SELECT auction_id, title, created_at FROM listings 
            ORDER BY created_at DESC LIMIT 5
        ''', fetch_all=True)
        
        if recent_ids:
            ids_text = "\n".join([f"{aid[:10]}... - {title[:30]}... - {created}" for aid, title, created in recent_ids])
            await ctx.send(f"Recent auction IDs:\n```{ids_text}```")
        
        result3 = db_manager.execute_query('SELECT proxy_service, setup_complete FROM user_preferences WHERE user_id = ?', (ctx.author.id,), fetch_one=True)
        await ctx.send(f"Your settings: {result3 if result3 else 'None found'}")
        
        bookmark_count = db_manager.execute_query('SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?', (ctx.author.id,), fetch_one=True)
        await ctx.send(f"Your bookmarks: {bookmark_count[0] if bookmark_count else 0}")
        
    except Exception as e:
        await ctx.send(f"Database error: {e}")

@bot.command(name='clear_recent_listings')
@commands.has_permissions(administrator=True)
async def clear_recent_listings_command(ctx):
    try:
        recent_count = db_manager.execute_query('''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > NOW() - INTERVAL '6 hours'
        ''' if db_manager.use_postgres else '''
            SELECT COUNT(*) FROM listings 
            WHERE created_at > datetime('now', '-6 hours')
        ''', fetch_one=True)
        
        recent_listings = recent_count[0] if recent_count else 0
        
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
        total_count = db_manager.execute_query('SELECT COUNT(*) FROM listings', fetch_one=True)
        total_listings = total_count[0] if total_count else 0
        
        if total_listings == 0:
            await ctx.send("✅ No listings to clear!")
            return
        
        db_manager.execute_query('DELETE FROM listings')
        db_manager.execute_query('DELETE FROM reactions')
        db_manager.execute_query('DELETE FROM user_bookmarks WHERE user_id = ?', (ctx.author.id,))
        
        embed = discord.Embed(
            title="🚨 ALL LISTINGS CLEARED",
            description=f"**EMERGENCY RESET**: Removed **{total_listings}** listings and all associated data.\n\nFresh listings should start appearing within 5 minutes!",
            color=0xff4444
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error clearing all listings: {e}")

@bot.command(name='test')
async def test_command(ctx):
    await ctx.send("✅ Bot is working!")

@bot.command(name='stats')
async def stats_command(ctx):
    stats = db_manager.execute_query('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN reaction_type = 'thumbs_up' THEN 1 ELSE 0 END) as thumbs_up,
            SUM(CASE WHEN reaction_type = 'thumbs_down' THEN 1 ELSE 0 END) as thumbs_down
        FROM reactions 
        WHERE user_id = ?
    ''', (ctx.author.id,), fetch_one=True)
    
    total, thumbs_up, thumbs_down = stats[0], stats[1] or 0, stats[2] or 0
    
    top_brands = db_manager.execute_query('''
        SELECT brand, preference_score FROM user_brand_preferences 
        WHERE user_id = ? ORDER BY preference_score DESC LIMIT 3
    ''', (ctx.author.id,), fetch_all=True)
    
    bookmark_count = db_manager.execute_query(
        'SELECT COUNT(*) FROM user_bookmarks WHERE user_id = ?',
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
        embed.add_field(
            name="📚 Bookmarks",
            value=f"Total: {bookmark_count[0]}",
            inline=True
        )
    
    if total > 0:
        positivity = thumbs_up / total * 100
        embed.add_field(
            name="🎯 Positivity Rate",
            value=f"{positivity:.1f}%",
            inline=True
        )
    
    if top_brands:
        brand_text = "\n".join([f"{brand.replace('_', ' ').title()}: {score:.1%}" for brand, score in top_brands])
        embed.add_field(
            name="🏷️ Top Preferred Brands",
            value=brand_text,
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='preferences')
async def preferences_command(ctx):
    user_id = ctx.author.id
    
    prefs = db_manager.execute_query('''
        SELECT proxy_service, notifications_enabled, min_quality_threshold, max_price_alert 
        FROM user_preferences WHERE user_id = ?
    ''', (user_id,), fetch_one=True)
    
    if not prefs:
        await ctx.send("❌ No preferences found. Run `!setup` first!")
        return
    
    proxy_service, notifications, min_quality, max_price = prefs
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

@bot.command(name='export')
async def export_command(ctx):
    all_reactions = db_manager.execute_query('''
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
    
    liked_count = sum(1 for r in all_reactions if r[0] == 'thumbs_up')
    disliked_count = len(all_reactions) - liked_count
    
    export_text += f"## Summary\n"
    export_text += f"👍 Liked: {liked_count}\n"
    export_text += f"👎 Disliked: {disliked_count}\n"
    export_text += f"Positivity Rate: {liked_count/len(all_reactions)*100:.1f}%\n\n"
    
    for reaction_type in ['thumbs_up', 'thumbs_down']:
        emoji = "👍 LIKED" if reaction_type == 'thumbs_up' else "👎 DISLIKED"
        export_text += f"## {emoji} LISTINGS\n\n"
        
        filtered_reactions = [r for r in all_reactions if r[0] == reaction_type]
        
        for i, (_, created_at, title, brand, price_jpy, price_usd, seller_id, zenmarket_url, yahoo_url, auction_id, deal_quality, priority) in enumerate(filtered_reactions, 1):
            export_text += f"{i}. **{title}**\n"
            export_text += f"   Brand: {brand.replace('_', ' ').title()}\n"
            export_text += f"   Price: ¥{price_jpy:,} (~${price_usd:.2f})\n"
            export_text += f"   Quality: {deal_quality:.1%} | Priority: {priority:.0f}\n"
            export_text += f"   Seller: {seller_id}\n"
            export_text += f"   Date: {created_at}\n"
            export_text += f"   ZenMarket: {zenmarket_url}\n"
            export_text += f"   Yahoo: {yahoo_url}\n\n"
    
    filename = f"auction_reactions_{ctx.author.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(export_text)
        
        with open(filename, 'rb') as f:
            file = discord.File(f, filename)
            embed = discord.Embed(
                title="📋 Your Complete Reaction Export",
                description=f"**Total Reactions:** {len(all_reactions)}\n**Liked:** {liked_count}\n**Disliked:** {disliked_count}",
                color=0x0099ff
            )
            await ctx.send(embed=embed, file=file)
        
        os.remove(filename)
        
    except Exception as e:
        await ctx.send(f"❌ Error creating export file: {e}")

@bot.command(name='scraper_stats')
async def scraper_stats_command(ctx):
    recent_stats = db_manager.execute_query('''
        SELECT timestamp, total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched
        FROM scraper_stats 
        ORDER BY timestamp DESC 
        LIMIT 5
    ''', fetch_all=True)
    
    if not recent_stats:
        await ctx.send("❌ No scraper statistics found!")
        return
    
    embed = discord.Embed(
        title="🤖 Recent Scraper Statistics",
        color=0x0099ff
    )
    
    for i, (timestamp, total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched) in enumerate(recent_stats, 1):
        success_rate = (sent_to_discord / total_found * 100) if total_found > 0 else 0
        
        embed.add_field(
            name=f"Run #{i} - {timestamp}",
            value=f"🔍 Keywords: {keywords_searched}\n📊 Found: {total_found}\n✅ Quality: {quality_filtered}\n📤 Sent: {sent_to_discord}\n❌ Errors: {errors_count}\n📈 Success: {success_rate:.1f}%",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='commands')
async def commands_command(ctx):
    embed = discord.Embed(
        title="🤖 Auction Bot Commands",
        description="All available commands for the auction tracking bot",
        color=0x0099ff
    )
    
    embed.add_field(
        name="⚙️ Setup & Configuration",
        value="**!setup** - Initial setup for new users\n**!preferences** - View your current preferences",
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
        name="🧠 Bot Testing & Maintenance",
        value="**!test** - Test if bot is working\n**!commands** - Show this help\n**!db_debug** - Database diagnostics\n**!clear_recent_listings** - Clear recent duplicates\n**!force_clear_all** - Emergency: clear all listings",
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

@app.route('/check_duplicate/<auction_id>', methods=['GET'])
def check_duplicate(auction_id):
    try:
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
    
    return jsonify({
        "total_listings": total_listings[0] if total_listings else 0,
        "total_reactions": total_reactions[0] if total_reactions else 0,
        "active_users": active_users[0] if active_users else 0,
        "buffer_size": len(batch_buffer)
    }), 200

@app.route('/webhook/listing', methods=['POST'])
def webhook_listing():
    """Receive listing from Yahoo sniper"""
    try:
        if not request.is_json:
            return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 400
        
        listing_data = request.get_json()
        
        if not listing_data or 'auction_id' not in listing_data:
            return jsonify({"status": "error", "message": "Invalid listing data"}), 400
        
        # Run the async function in the bot's event loop
        if bot.is_ready():
            asyncio.run_coroutine_threadsafe(
                send_single_listing_enhanced(listing_data), 
                bot.loop
            )
            return jsonify({"status": "success", "message": "Listing received"}), 200
        else:
            return jsonify({"status": "error", "message": "Bot not ready"}), 503
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

class PremiumTierManager:
    def __init__(self, bot):
        self.bot = bot
        self.tier_roles = {
            'free': 'Free User',
            'pro': 'Pro User',
            'elite': 'Elite User'
        }
        
        self.tier_channels = {
            'free': [
                '📦-daily-digest',
                '💰-budget-steals', 
                '🗳️-community-votes',
                '💬-general-chat',
                '💡-style-advice'
            ],
            'pro': [
                '⏰-hourly-drops',
                '🔔-size-alerts',
                '📊-price-tracker',
                '🔍-sold-listings',
                '🏷️-raf-simons', '🏷️-rick-owens', '🏷️-maison-margiela',
                '🏷️-jean-paul-gaultier', '🏷️-yohji_yamamoto', '🏷️-junya-watanabe',
                '🏷️-undercover', '🏷️-vetements', '🏷️-martine-rose',
                '🏷️-balenciaga', '🏷️-alyx', '🏷️-celine', '🏷️-bottega-veneta',
                '🏷️-kiko-kostadinov', '🏷️-chrome-hearts', '🏷️-comme-des-garcons',
                '🏷️-prada', '🏷️-miu-miu', '🏷️-hysteric-glamour'
            ],
            'elite': [
                '⚡-instant-alerts',
                '🔥-grail-hunter', 
                '🎯-personal-alerts',
                '📊-market-intelligence',
                '🛡️-verified-sellers',
                '💎-investment-pieces',
                '🏆-vip-lounge',
                '📈-trend-analysis',
                '💹-investment-tracking'
            ]
        }
        
        self.tier_features = {
            'free': {
                'delay_multiplier': 8.0,
                'daily_limit': 10,
                'bookmark_limit': 25,
                'ai_personalized': False,
                'priority_support': False
            },
            'pro': {
                'delay_multiplier': 0.0,
                'daily_limit': None,
                'bookmark_limit': 500,
                'ai_personalized': True,
                'priority_support': False
            },
            'elite': {
                'delay_multiplier': 0.0,
                'daily_limit': None,
                'bookmark_limit': None,
                'ai_personalized': True,
                'priority_support': True,
                'early_access': True
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

class DelayedListingManager:
    def __init__(self):
        self.delayed_queue = []
        self.running = False
    
    async def queue_for_free_users(self, listing_data, delay_seconds):
        delivery_time = datetime.now() + timedelta(seconds=delay_seconds)
        
        self.delayed_queue.append({
            'listing': listing_data,
            'delivery_time': delivery_time,
            'target_channels': ['📦-daily-digest', '💰-budget-steals']
        })
        
        self.delayed_queue.sort(key=lambda x: x['delivery_time'])
    
    async def process_delayed_queue(self):
        self.running = True
        while self.running:
            try:
                now = datetime.now()
                ready_items = []
                
                for item in self.delayed_queue:
                    if item['delivery_time'] <= now:
                        ready_items.append(item)
                
                for item in ready_items:
                    self.delayed_queue.remove(item)
                    await self.deliver_to_free_channels(item)
                
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Delayed queue error: {e}")
                await asyncio.sleep(300)
    
    async def deliver_to_free_channels(self, queued_item):
        listing = queued_item['listing']
        
        for channel_name in queued_item['target_channels']:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                try:
                    embed = create_listing_embed(listing)
                    embed.set_footer(text=f"Free Tier - Upgrade for real-time alerts | ID: {listing['auction_id']}")
                    await channel.send(embed=embed)
                    print(f"📤 Delivered delayed listing to #{channel_name}")
                except Exception as e:
                    print(f"❌ Error delivering to #{channel_name}: {e}")

tier_manager = None
delayed_manager = None
reminder_system = None
size_alert_system = None

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
    global tier_manager
    tier_manager = PremiumTierManager(bot)
    
    await tier_manager.setup_tier_roles(ctx.guild)
    await tier_manager.setup_channel_permissions(ctx.guild)
    
    await ctx.send("✅ Tier system setup complete!")

@bot.command(name='upgrade_user')
@commands.has_permissions(administrator=True)
async def upgrade_user_command(ctx, member: discord.Member, tier: str):
    if tier not in ['free', 'pro', 'elite']:
        await ctx.send("❌ Invalid tier. Use: free, pro, or elite")
        return
    
    if not tier_manager:
        await ctx.send("❌ Tier system not initialized. Run `!setup_tiers` first")
        return
    
    success = await tier_manager.upgrade_user(member, tier)
    if success:
        embed = discord.Embed(
            title="🎯 User Upgraded",
            description=f"{member.mention} has been upgraded to **{tier.title()} Tier**",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Failed to upgrade user")

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
                bookmark_channel.id, 
                auction_end_time
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
                    0,  # 0 for DM
                    auction_end_time
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
            '''SELECT ub.auction_id, ub.created_at, ub.auction_end_time, 
                      l.title, l.brand, l.price_usd, l.zenmarket_url
               FROM user_bookmarks ub
               LEFT JOIN listings l ON ub.auction_id = l.auction_id
               WHERE ub.user_id = %s
               ORDER BY ub.created_at DESC
               LIMIT 10''' if db_manager.use_postgres else 
            '''SELECT ub.auction_id, ub.created_at, ub.auction_end_time, 
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
            title = bookmark[3] if isinstance(bookmark, (list, tuple)) else bookmark['title']
            brand = bookmark[4] if isinstance(bookmark, (list, tuple)) else bookmark['brand']
            price_usd = bookmark[5] if isinstance(bookmark, (list, tuple)) else bookmark['price_usd']
            zenmarket_url = bookmark[6] if isinstance(bookmark, (list, tuple)) else bookmark['zenmarket_url']
            
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





def run_flask():
    try:
        app.run(host='0.0.0.0', port=8000, debug=False)
    except Exception as e:
        print(f"❌ Flask server error: {e}")
        time.sleep(5)
        run_flask()

def main():
    try:
        print("🚀 Starting Discord bot...")
        
        print("🌐 Starting webhook server...")
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("🌐 Webhook server started on port 8000")
        
        print("🔒 SECURITY: Performing startup security checks...")
        
        if not BOT_TOKEN or len(BOT_TOKEN) < 50:
            print("❌ SECURITY FAILURE: Invalid bot token!")
            print("🌐 Keeping webhook server alive for health checks...")
            while True:
                time.sleep(60)
        
        if not GUILD_ID:
            print("❌ SECURITY FAILURE: Invalid guild ID!")
            print("🌐 Keeping webhook server alive for health checks...")
            while True:
                time.sleep(60)
        
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
        
        print("🤖 Connecting to Discord...")
        bot.run(BOT_TOKEN)
        
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
    bot.run(DISCORD_TOKEN)