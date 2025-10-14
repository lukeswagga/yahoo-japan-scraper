#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tier Management System for Discord Auction Bot
Handles user tiers, brand preferences, and daily counters
"""

import aiosqlite
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class TierManager:
    def __init__(self, db_path: str = 'user_tiers.db'):
        self.db_path = db_path
    
    async def init_database(self):
        """Initialize the database with required tables"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create users table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        discord_id TEXT PRIMARY KEY,
                        tier TEXT NOT NULL CHECK(tier IN ('free', 'standard', 'instant')),
                        preferred_brands TEXT,  -- JSON array for standard tier
                        standard_count_today INTEGER DEFAULT 0,
                        last_reset_date TEXT,  -- ISO date for counter reset
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create listing_queue table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS listing_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        auction_id TEXT UNIQUE,
                        listing_data TEXT,  -- JSON serialized
                        priority_score REAL,
                        brand TEXT,
                        scraper_source TEXT,
                        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed BOOLEAN DEFAULT 0
                    )
                """)
                
                # Create user_reactions table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_reactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        discord_id TEXT,
                        auction_id TEXT,
                        reaction_type TEXT CHECK(reaction_type IN ('thumbs_up', 'thumbs_down')),
                        reacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(discord_id, auction_id)
                    )
                """)
                
                # Create indexes for better performance
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_tier ON users(tier)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_listing_queue_priority ON listing_queue(priority_score DESC)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_listing_queue_received ON listing_queue(received_at)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_user_reactions_user ON user_reactions(discord_id)")
                
                await db.commit()
                logger.info("✅ Database initialized successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    async def get_user_tier(self, discord_id: str) -> str:
        """Get user's tier, defaulting to 'free' if not found"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT tier FROM users WHERE discord_id = ?", 
                    (discord_id,)
                )
                result = await cursor.fetchone()
                return result[0] if result else 'free'
        except Exception as e:
            logger.error(f"❌ Failed to get user tier for {discord_id}: {e}")
            return 'free'
    
    async def set_user_tier(self, discord_id: str, tier: str) -> bool:
        """Set user's tier, creating user if not exists"""
        if tier not in ['free', 'standard', 'instant']:
            logger.error(f"❌ Invalid tier: {tier}")
            return False
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO users 
                    (discord_id, tier, updated_at) 
                    VALUES (?, ?, ?)
                """, (discord_id, tier, datetime.now(timezone.utc).isoformat()))
                await db.commit()
                logger.info(f"✅ Set user {discord_id} to {tier} tier")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to set user tier: {e}")
            return False
    
    async def get_preferred_brands(self, discord_id: str) -> List[str]:
        """Get user's preferred brands for standard tier"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT preferred_brands FROM users WHERE discord_id = ?", 
                    (discord_id,)
                )
                result = await cursor.fetchone()
                
                if result and result[0]:
                    return json.loads(result[0])
                return []
        except Exception as e:
            logger.error(f"❌ Failed to get preferred brands for {discord_id}: {e}")
            return []
    
    async def set_preferred_brands(self, discord_id: str, brands: List[str]) -> bool:
        """Set user's preferred brands (standard tier only)"""
        try:
            # Validate brands list
            if not isinstance(brands, list) or len(brands) > 20:
                logger.error(f"❌ Invalid brands list: {brands}")
                return False
            
            # Sanitize brand names
            sanitized_brands = [brand.strip().title() for brand in brands if brand.strip()]
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET preferred_brands = ?, updated_at = ? 
                    WHERE discord_id = ?
                """, (json.dumps(sanitized_brands), datetime.now(timezone.utc).isoformat(), discord_id))
                await db.commit()
                logger.info(f"✅ Set preferred brands for {discord_id}: {sanitized_brands}")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to set preferred brands: {e}")
            return False
    
    async def can_send_to_standard(self, discord_id: str) -> bool:
        """Check if user can receive more standard tier listings today"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT standard_count_today, tier 
                    FROM users 
                    WHERE discord_id = ?
                """, (discord_id,))
                result = await cursor.fetchone()
                
                if not result:
                    return False
                
                tier, count = result[0], result[1]
                return tier == 'standard' and count < 100
        except Exception as e:
            logger.error(f"❌ Failed to check standard tier limit: {e}")
            return False
    
    async def increment_standard_count(self, discord_id: str) -> bool:
        """Increment standard tier counter for user"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET standard_count_today = standard_count_today + 1,
                        updated_at = ?
                    WHERE discord_id = ? AND tier = 'standard'
                """, (datetime.now(timezone.utc).isoformat(), discord_id))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Failed to increment standard count: {e}")
            return False
    
    async def reset_daily_counters(self) -> bool:
        """Reset all standard tier counters (run at midnight UTC)"""
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE users 
                    SET standard_count_today = 0,
                        last_reset_date = ?,
                        updated_at = ?
                    WHERE tier = 'standard'
                """, (today, datetime.now(timezone.utc).isoformat()))
                await db.commit()
                logger.info("✅ Reset daily counters for all standard tier users")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to reset daily counters: {e}")
            return False
    
    async def get_all_standard_users(self) -> List[str]:
        """Get all discord_ids with standard tier"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT discord_id FROM users WHERE tier = 'standard'"
                )
                results = await cursor.fetchall()
                return [row[0] for row in results]
        except Exception as e:
            logger.error(f"❌ Failed to get standard users: {e}")
            return []
    
    async def get_standard_feed_count_24h(self) -> int:
        """Get count of posts to standard-feed in past 24 hours"""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM listing_queue 
                    WHERE scraper_source = 'standard_feed_posted' 
                    AND received_at > ?
                """, (cutoff.isoformat(),))
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"❌ Failed to get standard feed count: {e}")
            return 0
    
    async def record_standard_feed_post(self, auction_id: str) -> bool:
        """Record a post to standard-feed"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO listing_queue 
                    (auction_id, listing_data, priority_score, brand, scraper_source, received_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    f"standard_feed_{auction_id}",
                    json.dumps({"auction_id": auction_id, "posted_to": "standard_feed"}),
                    0.0,
                    "Standard Feed Post",
                    "standard_feed_posted",
                    datetime.now(timezone.utc).isoformat()
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Failed to record standard feed post: {e}")
            return False
    
    async def mark_listings_processed(self, auction_ids: List[str]) -> bool:
        """Mark listings as processed in digest"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for auction_id in auction_ids:
                    await db.execute("""
                        UPDATE listing_queue 
                        SET processed = 1 
                        WHERE auction_id = ?
                    """, (auction_id,))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Failed to mark listings as processed: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics for debugging"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total listings
                cursor = await db.execute("SELECT COUNT(*) FROM listing_queue")
                total = (await cursor.fetchone())[0]
                
                # Unprocessed listings
                cursor = await db.execute("SELECT COUNT(*) FROM listing_queue WHERE processed = 0")
                unprocessed = (await cursor.fetchone())[0]
                
                # Past 24h listings
                cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                cursor = await db.execute("SELECT COUNT(*) FROM listing_queue WHERE received_at > ?", (cutoff.isoformat(),))
                past_24h = (await cursor.fetchone())[0]
                
                # Standard feed posts in past 24h
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM listing_queue 
                    WHERE scraper_source = 'standard_feed_posted' 
                    AND received_at > ?
                """, (cutoff.isoformat(),))
                standard_feed_count = (await cursor.fetchone())[0]
                
                return {
                    "total_listings": total,
                    "unprocessed_listings": unprocessed,
                    "past_24h_listings": past_24h,
                    "standard_feed_24h_count": standard_feed_count
                }
        except Exception as e:
            logger.error(f"❌ Failed to get queue stats: {e}")
            return {}
    
    async def reset_standard_feed_counter(self) -> bool:
        """Reset standard-feed counter (for testing)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM listing_queue WHERE scraper_source = 'standard_feed_posted'")
                await db.commit()
                logger.info("✅ Reset standard-feed counter")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to reset standard-feed counter: {e}")
            return False
    
    async def get_user_stats(self, discord_id: str) -> Dict:
        """Get comprehensive user statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT tier, preferred_brands, standard_count_today, last_reset_date
                    FROM users 
                    WHERE discord_id = ?
                """, (discord_id,))
                result = await cursor.fetchone()
                
                if not result:
                    return {
                        'tier': 'free',
                        'brands': [],
                        'count': 0,
                        'limit': 0,
                        'last_reset': None
                    }
                
                tier, brands_json, count, last_reset = result
                brands = json.loads(brands_json) if brands_json else []
                
                return {
                    'tier': tier,
                    'brands': brands,
                    'count': count,
                    'limit': 100 if tier == 'standard' else 0,
                    'last_reset': last_reset
                }
        except Exception as e:
            logger.error(f"❌ Failed to get user stats: {e}")
            return {
                'tier': 'free',
                'brands': [],
                'count': 0,
                'limit': 0,
                'last_reset': None
            }
    
    async def add_listing_to_queue(self, listing_data: dict, priority_score: float) -> bool:
        """Add listing to queue for daily digest"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO listing_queue 
                    (auction_id, listing_data, priority_score, brand, scraper_source)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    listing_data.get('auction_id'),
                    json.dumps(listing_data),
                    priority_score,
                    listing_data.get('brand', 'Unknown'),
                    listing_data.get('scraper_source', '')
                ))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Failed to add listing to queue: {e}")
            return False
    
    async def get_top_listings_for_digest(self, hours: int = 24, limit: int = 20) -> List[Tuple[dict, float]]:
        """Get top listings for daily digest"""
        try:
            cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff = cutoff.replace(hour=cutoff.hour - hours)
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT listing_data, priority_score 
                    FROM listing_queue 
                    WHERE received_at > ? 
                    ORDER BY priority_score DESC 
                    LIMIT ?
                """, (cutoff.isoformat(), limit))
                
                results = await cursor.fetchall()
                return [(json.loads(row[0]), row[1]) for row in results]
        except Exception as e:
            logger.error(f"❌ Failed to get top listings: {e}")
            return []
    
    async def add_user_reaction(self, discord_id: str, auction_id: str, reaction_type: str) -> bool:
        """Add user reaction to listing"""
        if reaction_type not in ['thumbs_up', 'thumbs_down']:
            return False
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO user_reactions 
                    (discord_id, auction_id, reaction_type, reacted_at)
                    VALUES (?, ?, ?, ?)
                """, (discord_id, auction_id, reaction_type, datetime.now(timezone.utc).isoformat()))
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Failed to add user reaction: {e}")
            return False
    
    async def get_user_reaction(self, discord_id: str, auction_id: str) -> Optional[str]:
        """Get user's reaction to a listing"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT reaction_type FROM user_reactions 
                    WHERE discord_id = ? AND auction_id = ?
                """, (discord_id, auction_id))
                result = await cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"❌ Failed to get user reaction: {e}")
            return None
