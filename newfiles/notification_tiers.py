"""
Notification Tier System for Discord Auction Bot

This module manages the tier-based notification system with:
- Free Tier: Daily digest only
- Standard Tier: 50 real-time DMs per day + daily digest
- Instant Tier: Unlimited real-time DMs + daily digest

Privacy-focused design with no email/phone collection.
"""

import discord
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from database_manager import db_manager

logger = logging.getLogger(__name__)

class NotificationTierManager:
    """Manages notification tiers and daily limits"""
    
    TIER_LIMITS = {
        'free': 0,      # No real-time notifications
        'standard': 50, # 50 DMs per day
        'instant': -1   # Unlimited (-1 means no limit)
    }
    
    TIER_NAMES = {
        'free': 'Free',
        'standard': 'Standard ($12/month)',
        'instant': 'Instant ($25/month)'
    }
    
    def __init__(self):
        self.daily_digest_channel_id = None
        self.bot = None
        
    def set_bot(self, bot):
        """Set the Discord bot instance"""
        self.bot = bot
        
    def set_daily_digest_channel(self, channel_id: int):
        """Set the daily digest channel ID"""
        self.daily_digest_channel_id = channel_id
        
    async def get_user_tier(self, user_id: int) -> str:
        """Get user's current tier"""
        try:
            result = db_manager.execute_query(
                'SELECT tier FROM user_subscriptions WHERE user_id = %s AND status = %s' 
                if db_manager.use_postgres else 
                'SELECT tier FROM user_subscriptions WHERE user_id = ? AND status = ?',
                (user_id, 'active'),
                fetch_one=True
            )
            
            if result:
                tier = result['tier'] if isinstance(result, dict) else result[0]
                return tier if tier in self.TIER_LIMITS else 'free'
            return 'free'
            
        except Exception as e:
            logger.error(f"Error getting user tier for {user_id}: {e}")
            return 'free'
    
    async def get_user_daily_count(self, user_id: int) -> Tuple[int, datetime]:
        """Get user's daily notification count and last reset time"""
        try:
            result = db_manager.execute_query(
                'SELECT daily_count, last_reset FROM user_subscriptions WHERE user_id = %s' 
                if db_manager.use_postgres else 
                'SELECT daily_count, last_reset FROM user_subscriptions WHERE user_id = ?',
                (user_id,),
                fetch_one=True
            )
            
            if result:
                if isinstance(result, dict):
                    count = result.get('daily_count', 0)
                    last_reset = result.get('last_reset')
                else:
                    count = result[0] if result[0] is not None else 0
                    last_reset = result[1]
                
                # Convert to datetime if it's a string
                if isinstance(last_reset, str):
                    last_reset = datetime.fromisoformat(last_reset.replace('Z', '+00:00'))
                elif last_reset is None:
                    last_reset = datetime.now(timezone.utc)
                    
                return count, last_reset
            return 0, datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error getting daily count for {user_id}: {e}")
            return 0, datetime.now(timezone.utc)
    
    async def reset_daily_count_if_needed(self, user_id: int) -> bool:
        """Reset daily count if it's a new day. Returns True if reset occurred."""
        try:
            count, last_reset = await self.get_user_daily_count(user_id)
            now = datetime.now(timezone.utc)
            
            # Check if it's a new day (after midnight UTC)
            if now.date() > last_reset.date():
                await self.set_daily_count(user_id, 0, now)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error resetting daily count for {user_id}: {e}")
            return False
    
    async def set_daily_count(self, user_id: int, count: int, reset_time: datetime = None):
        """Set user's daily notification count"""
        try:
            if reset_time is None:
                reset_time = datetime.now(timezone.utc)
                
            # Update or insert user subscription record
            db_manager.execute_query(
                '''INSERT INTO user_subscriptions (user_id, daily_count, last_reset, updated_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                   daily_count = %s, last_reset = %s, updated_at = %s'''
                if db_manager.use_postgres else
                '''INSERT OR REPLACE INTO user_subscriptions (user_id, daily_count, last_reset, updated_at)
                   VALUES (?, ?, ?, ?)''',
                (user_id, count, reset_time, reset_time, count, reset_time, reset_time)
                if db_manager.use_postgres else
                (user_id, count, reset_time, reset_time)
            )
            
        except Exception as e:
            logger.error(f"Error setting daily count for {user_id}: {e}")
    
    async def can_send_notification(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user can receive a real-time notification.
        Returns (can_send, reason)
        """
        try:
            tier = await self.get_user_tier(user_id)
            
            # Free tier users can't get real-time notifications
            if tier == 'free':
                return False, "Free tier users only get daily digest"
            
            # Check if we need to reset daily count
            await self.reset_daily_count_if_needed(user_id)
            
            # Get current count
            count, _ = await self.get_user_daily_count(user_id)
            limit = self.TIER_LIMITS[tier]
            
            # Instant tier has unlimited notifications
            if limit == -1:
                return True, "Instant tier - unlimited notifications"
            
            # Check if under limit
            if count < limit:
                return True, f"Standard tier - {count + 1}/{limit} notifications used today"
            else:
                return False, f"Daily limit reached ({limit} notifications). Resets at midnight UTC."
                
        except Exception as e:
            logger.error(f"Error checking notification permission for {user_id}: {e}")
            return False, "Error checking permissions"
    
    async def send_real_time_notification(self, user_id: int, listing_data: dict) -> bool:
        """
        Send real-time notification to user if they have permission.
        Returns True if sent successfully.
        """
        try:
            can_send, reason = await self.can_send_notification(user_id)
            
            if not can_send:
                logger.info(f"Not sending notification to {user_id}: {reason}")
                return False
            
            # Get user and send DM
            user = self.bot.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found")
                return False
            
            # Create embed for the listing
            embed = self.create_listing_embed(listing_data, is_dm=True)
            
            # Add tier upgrade prompt for standard tier users
            tier = await self.get_user_tier(user_id)
            if tier == 'standard':
                count, _ = await self.get_user_daily_count(user_id)
                limit = self.TIER_LIMITS[tier]
                embed.add_field(
                    name="💎 Upgrade to Instant Tier",
                    value=f"You've used {count}/{limit} notifications today. "
                          f"Upgrade to **Instant Tier** for unlimited notifications!",
                    inline=False
                )
            
            await user.send(embed=embed)
            
            # Increment daily count
            count, _ = await self.get_user_daily_count(user_id)
            await self.set_daily_count(user_id, count + 1)
            
            # Log the notification
            await self.log_notification(user_id, listing_data['auction_id'], 'dm')
            
            logger.info(f"Sent real-time notification to {user.name} ({user_id})")
            return True
            
        except discord.Forbidden:
            logger.warning(f"Cannot send DM to user {user_id} - DMs disabled")
            return False
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
            return False
    
    async def queue_for_daily_digest(self, listing_data: dict):
        """Queue a listing for the daily digest"""
        try:
            # Add to digest queue table
            db_manager.execute_query(
                '''INSERT INTO daily_digest_queue (auction_id, title, brand, price_jpy, price_usd, 
                   zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                if db_manager.use_postgres else
                '''INSERT INTO daily_digest_queue (auction_id, title, brand, price_jpy, price_usd, 
                   zenmarket_url, yahoo_url, image_url, deal_quality, priority_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    listing_data['auction_id'],
                    listing_data.get('title', ''),
                    listing_data.get('brand', ''),
                    listing_data.get('price_jpy', 0),
                    listing_data.get('price_usd', 0.0),
                    listing_data.get('zenmarket_url', ''),
                    listing_data.get('yahoo_url', ''),
                    listing_data.get('image_url', ''),
                    listing_data.get('deal_quality', 0.5),
                    listing_data.get('priority_score', 0.0),
                    datetime.now(timezone.utc)
                )
            )
            
        except Exception as e:
            logger.error(f"Error queuing listing for digest: {e}")
    
    async def send_daily_digest(self) -> bool:
        """Send the daily digest to the #daily-digest channel"""
        try:
            if not self.daily_digest_channel_id:
                logger.error("Daily digest channel not set")
                return False
            
            channel = self.bot.get_channel(self.daily_digest_channel_id)
            if not channel:
                logger.error(f"Daily digest channel {self.daily_digest_channel_id} not found")
                return False
            
            # Get top 20 listings from yesterday
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            listings = db_manager.execute_query(
                '''SELECT * FROM daily_digest_queue 
                   WHERE created_at >= %s AND created_at <= %s
                   ORDER BY priority_score DESC, deal_quality DESC
                   LIMIT 20'''
                if db_manager.use_postgres else
                '''SELECT * FROM daily_digest_queue 
                   WHERE created_at >= ? AND created_at <= ?
                   ORDER BY priority_score DESC, deal_quality DESC
                   LIMIT 20''',
                (start_of_day, end_of_day),
                fetch_all=True
            )
            
            if not listings:
                # Send message about no listings
                embed = discord.Embed(
                    title="📰 Daily Auction Digest",
                    description="No new listings found yesterday.",
                    color=0x7289da,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="Check back tomorrow for new deals!")
                await channel.send(embed=embed)
                return True
            
            # Create main digest embed
            embed = discord.Embed(
                title="📰 Daily Auction Digest",
                description=f"Top {len(listings)} highest-priority listings from yesterday:",
                color=0x7289da,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add upgrade prompt
            embed.add_field(
                name="💎 Want Real-Time Notifications?",
                value="**Free users** get daily digest only.\n"
                      "**Standard ($12/month)**: 50 real-time DMs per day\n"
                      "**Instant ($25/month)**: Unlimited real-time notifications\n"
                      "Contact an admin to upgrade!",
                inline=False
            )
            
            await channel.send(embed=embed)
            
            # Send listings in batches of 5 to avoid message limits
            for i in range(0, len(listings), 5):
                batch = listings[i:i+5]
                for listing in batch:
                    listing_embed = self.create_listing_embed(listing, is_digest=True)
                    message = await channel.send(embed=listing_embed)
                    
                    # Add reactions for feedback
                    await message.add_reaction("👍")
                    await message.add_reaction("👎")
                
                # Small delay between batches
                if i + 5 < len(listings):
                    await asyncio.sleep(1)
            
            # Clear processed listings from queue
            db_manager.execute_query(
                'DELETE FROM daily_digest_queue WHERE created_at >= %s AND created_at <= %s'
                if db_manager.use_postgres else
                'DELETE FROM daily_digest_queue WHERE created_at >= ? AND created_at <= ?',
                (start_of_day, end_of_day)
            )
            
            logger.info(f"Sent daily digest with {len(listings)} listings")
            return True
            
        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")
            return False
    
    def create_listing_embed(self, listing_data: dict, is_dm: bool = False, is_digest: bool = False) -> discord.Embed:
        """Create a Discord embed for a listing"""
        try:
            # Handle both dict and tuple formats from database
            if isinstance(listing_data, dict):
                auction_id = listing_data.get('auction_id', '')
                title = listing_data.get('title', 'No title')
                brand = listing_data.get('brand', 'Unknown')
                price_jpy = listing_data.get('price_jpy', 0)
                price_usd = listing_data.get('price_usd', 0.0)
                zenmarket_url = listing_data.get('zenmarket_url', '')
                yahoo_url = listing_data.get('yahoo_url', '')
                image_url = listing_data.get('image_url', '')
                deal_quality = listing_data.get('deal_quality', 0.5)
            else:
                # Tuple format from database
                auction_id = listing_data[1] if len(listing_data) > 1 else ''
                title = listing_data[2] if len(listing_data) > 2 else 'No title'
                brand = listing_data[3] if len(listing_data) > 3 else 'Unknown'
                price_jpy = listing_data[4] if len(listing_data) > 4 else 0
                price_usd = listing_data[5] if len(listing_data) > 5 else 0.0
                zenmarket_url = listing_data[6] if len(listing_data) > 6 else ''
                yahoo_url = listing_data[7] if len(listing_data) > 7 else ''
                image_url = listing_data[8] if len(listing_data) > 8 else ''
                deal_quality = listing_data[9] if len(listing_data) > 9 else 0.5
            
            # Create embed
            embed = discord.Embed(
                title=title[:256],  # Discord title limit
                color=0x00ff00 if deal_quality > 0.7 else 0xffaa00 if deal_quality > 0.4 else 0xff0000,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add fields
            if brand and brand != 'Unknown':
                embed.add_field(name="🏷️ Brand", value=brand, inline=True)
            
            embed.add_field(
                name="💰 Price", 
                value=f"¥{price_jpy:,} (${price_usd:.2f})", 
                inline=True
            )
            
            embed.add_field(
                name="⭐ Quality", 
                value=f"{deal_quality:.1%}", 
                inline=True
            )
            
            # Add context
            if is_dm:
                embed.add_field(
                    name="🔔 Real-Time Alert",
                    value="You received this because you have real-time notifications enabled!",
                    inline=False
                )
            elif is_digest:
                embed.add_field(
                    name="📰 Daily Digest",
                    value="This listing was included in today's digest.",
                    inline=False
                )
            
            # Add links
            if zenmarket_url:
                embed.add_field(name="🛒 Zenmarket", value=f"[View Listing]({zenmarket_url})", inline=True)
            
            if yahoo_url:
                embed.add_field(name="🏪 Yahoo", value=f"[Original]({yahoo_url})", inline=True)
            
            # Set image if available
            if image_url:
                embed.set_image(url=image_url)
            
            # Set footer
            embed.set_footer(text=f"Auction ID: {auction_id}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating listing embed: {e}")
            # Return a basic embed if there's an error
            return discord.Embed(
                title="Auction Listing",
                description="Error displaying listing details",
                color=0xff0000
            )
    
    async def log_notification(self, user_id: int, auction_id: str, notification_type: str):
        """Log a notification for analytics"""
        try:
            db_manager.execute_query(
                '''INSERT INTO notification_logs (user_id, auction_id, notification_type, sent_at)
                   VALUES (%s, %s, %s, %s)'''
                if db_manager.use_postgres else
                '''INSERT INTO notification_logs (user_id, auction_id, notification_type, sent_at)
                   VALUES (?, ?, ?, ?)''',
                (user_id, auction_id, notification_type, datetime.now(timezone.utc))
            )
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
    
    async def get_tier_stats(self) -> Dict[str, int]:
        """Get statistics about tier distribution"""
        try:
            result = db_manager.execute_query(
                'SELECT tier, COUNT(*) as count FROM user_subscriptions WHERE status = %s GROUP BY tier'
                if db_manager.use_postgres else
                'SELECT tier, COUNT(*) as count FROM user_subscriptions WHERE status = ? GROUP BY tier',
                ('active',),
                fetch_all=True
            )
            
            stats = {'free': 0, 'standard': 0, 'instant': 0}
            if result:
                for row in result:
                    if isinstance(row, dict):
                        tier = row['tier']
                        count = row['count']
                    else:
                        tier = row[0]
                        count = row[1]
                    
                    if tier in stats:
                        stats[tier] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting tier stats: {e}")
            return {'free': 0, 'standard': 0, 'instant': 0}
    
    async def upgrade_user_tier(self, user_id: int, new_tier: str) -> bool:
        """Upgrade a user's tier"""
        try:
            if new_tier not in self.TIER_LIMITS:
                return False
            
            # Update or insert user subscription
            db_manager.execute_query(
                '''INSERT INTO user_subscriptions (user_id, tier, upgraded_at, status, updated_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                   tier = %s, upgraded_at = %s, status = %s, updated_at = %s'''
                if db_manager.use_postgres else
                '''INSERT OR REPLACE INTO user_subscriptions (user_id, tier, upgraded_at, status, updated_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, new_tier, datetime.now(timezone.utc), 'active', datetime.now(timezone.utc),
                 new_tier, datetime.now(timezone.utc), 'active', datetime.now(timezone.utc))
                if db_manager.use_postgres else
                (user_id, new_tier, datetime.now(timezone.utc), 'active', datetime.now(timezone.utc))
            )
            
            # Reset daily count for new tier
            await self.set_daily_count(user_id, 0)
            
            logger.info(f"Upgraded user {user_id} to {new_tier} tier")
            return True
            
        except Exception as e:
            logger.error(f"Error upgrading user {user_id} to {new_tier}: {e}")
            return False

# Global instance
tier_manager = NotificationTierManager()
