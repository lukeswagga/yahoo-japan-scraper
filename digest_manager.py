#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Digest Manager for Discord Auction Bot
Handles daily digest generation and posting
"""

import discord
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DigestManager:
    def __init__(self, bot, tier_manager):
        """
        Initialize digest manager
        
        Args:
            bot: Discord bot instance
            tier_manager: TierManager instance for database access
        """
        self.bot = bot
        self.tier_manager = tier_manager
    
    async def generate_daily_digest(self) -> bool:
        """
        Generate and post daily digest at 9 AM
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🔄 Starting daily digest generation...")
            
            # Get top 20 listings from past 24 hours
            listings = await self.tier_manager.get_top_listings_for_digest(hours=24, limit=20)
            
            logger.info(f"📊 Found {len(listings)} listings for daily digest")
            
            if not listings:
                logger.info("📭 No listings found for daily digest")
                return True
            
            # Try to find channel (with and without emoji prefix)
            channel = discord.utils.get(self.bot.get_all_channels(), name='daily-digest')
            if not channel:
                # Try with emoji prefix
                channel = discord.utils.get(self.bot.get_all_channels(), name='📰-daily-digest')
            
            if not channel:
                logger.error("❌ #daily-digest channel not found (tried both 'daily-digest' and '📰-daily-digest')")
                logger.info(f"Available channels: {[ch.name for ch in self.bot.get_all_channels() if 'digest' in ch.name.lower()]}")
                return False
            
            logger.info(f"📰 Found digest channel: #{channel.name}")
            
            # Check bot permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.error(f"❌ No permission to send messages in #{channel.name}")
                return False
            
            # Mark listings as processed to prevent duplicates
            await self._mark_listings_processed(listings)
            
            # Create and send digest embed
            embed = await self._create_digest_embed(listings)
            await channel.send(embed=embed)
            
            logger.info(f"✅ Posted daily digest with {len(listings)} listings to #{channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to generate daily digest: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    async def _mark_listings_processed(self, listings: List[Tuple[Dict[str, Any], float]]) -> bool:
        """Mark listings as processed to prevent duplicates"""
        try:
            auction_ids = [json.loads(listing_data)[0].get('auction_id') for listing_data, _ in listings]
            await self.tier_manager.mark_listings_processed(auction_ids)
            logger.info(f"✅ Marked {len(auction_ids)} listings as processed")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to mark listings as processed: {e}")
            return False
    
    async def _create_digest_embed(self, listings: List[Tuple[Dict[str, Any], float]]) -> discord.Embed:
        """
        Create rich embed for daily digest
        
        Args:
            listings: List of (listing_data, priority_score) tuples
            
        Returns:
            Discord Embed object
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Create main embed
            embed = discord.Embed(
                title="🌅 Daily Digest - Top 20 Listings",
                description=f"Best deals from the past 24 hours\nPosted {now.strftime('%Y-%m-%d %H:%M UTC')}",
                color=discord.Color.gold(),
                timestamp=now
            )
            
            # Add listings to embed
            for idx, (listing_data, priority_score) in enumerate(listings, 1):
                try:
                    # Create listing summary
                    brand = listing_data.get('brand', 'Unknown')
                    price_usd = listing_data.get('price_usd', 0)
                    title = listing_data.get('title', 'Unknown Title')
                    zenmarket_url = listing_data.get('zenmarket_url', '')
                    
                    # Truncate title if too long
                    display_title = title[:60] + "..." if len(title) > 60 else title
                    
                    # Create field value
                    field_value = f"**${price_usd:.0f}** • Priority: {priority_score:.2f}\n"
                    if zenmarket_url:
                        field_value += f"[{display_title}]({zenmarket_url})"
                    else:
                        field_value += display_title
                    
                    # Add source info
                    scraper_source = listing_data.get('scraper_source', '')
                    if scraper_source:
                        source_display = scraper_source.replace('_scraper', '').replace('_', ' ').title()
                        field_value += f"\n*Source: {source_display}*"
                    
                    embed.add_field(
                        name=f"{idx}. {brand}",
                        value=field_value,
                        inline=False
                    )
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to add listing {idx} to digest: {e}")
                    continue
            
            # Add footer with statistics
            total_listings = len(listings)
            avg_priority = sum(score for _, score in listings) / total_listings if total_listings > 0 else 0
            
            embed.set_footer(
                text=f"📊 {total_listings} listings • Avg Priority: {avg_priority:.2f} • Daily Digest"
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"❌ Failed to create digest embed: {e}")
            # Return minimal embed on error
            return discord.Embed(
                title="Daily Digest Error",
                description="Failed to create daily digest",
                color=discord.Color.red()
            )
    
    async def generate_weekly_digest(self) -> bool:
        """
        Generate and post weekly digest (optional feature)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get top 50 listings from past 7 days
            listings = await self.tier_manager.get_top_listings_for_digest(hours=168, limit=50)
            
            if not listings:
                logger.info("📭 No listings found for weekly digest")
                return True
            
            # Create weekly digest embed
            channel = discord.utils.get(self.bot.get_all_channels(), name='daily-digest')
            if not channel:
                logger.error("❌ #daily-digest channel not found")
                return False
            
            embed = await self._create_weekly_digest_embed(listings)
            await channel.send(embed=embed)
            
            logger.info(f"✅ Posted weekly digest with {len(listings)} listings")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to generate weekly digest: {e}")
            return False
    
    async def _create_weekly_digest_embed(self, listings: List[Tuple[Dict[str, Any], float]]) -> discord.Embed:
        """
        Create rich embed for weekly digest
        
        Args:
            listings: List of (listing_data, priority_score) tuples
            
        Returns:
            Discord Embed object
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Create main embed
            embed = discord.Embed(
                title="📅 Weekly Digest - Top 50 Listings",
                description=f"Best deals from the past 7 days\nPosted {now.strftime('%Y-%m-%d %H:%M UTC')}",
                color=discord.Color.purple(),
                timestamp=now
            )
            
            # Group listings by brand for better organization
            brand_groups = {}
            for listing_data, priority_score in listings:
                brand = listing_data.get('brand', 'Unknown')
                if brand not in brand_groups:
                    brand_groups[brand] = []
                brand_groups[brand].append((listing_data, priority_score))
            
            # Add brand sections to embed
            for brand, brand_listings in list(brand_groups.items())[:10]:  # Top 10 brands
                try:
                    # Sort by priority within brand
                    brand_listings.sort(key=lambda x: x[1], reverse=True)
                    
                    # Create brand section
                    brand_text = f"**{brand}** ({len(brand_listings)} items)\n"
                    
                    for listing_data, priority_score in brand_listings[:5]:  # Top 5 per brand
                        price_usd = listing_data.get('price_usd', 0)
                        title = listing_data.get('title', 'Unknown Title')
                        zenmarket_url = listing_data.get('zenmarket_url', '')
                        
                        # Truncate title
                        display_title = title[:40] + "..." if len(title) > 40 else title
                        
                        brand_text += f"• **${price_usd:.0f}** "
                        if zenmarket_url:
                            brand_text += f"[{display_title}]({zenmarket_url})"
                        else:
                            brand_text += display_title
                        brand_text += f" *({priority_score:.2f})*\n"
                    
                    if len(brand_listings) > 5:
                        brand_text += f"*...and {len(brand_listings) - 5} more*\n"
                    
                    embed.add_field(
                        name=f"🏷️ {brand}",
                        value=brand_text,
                        inline=True
                    )
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to add brand {brand} to weekly digest: {e}")
                    continue
            
            # Add footer with statistics
            total_listings = len(listings)
            avg_priority = sum(score for _, score in listings) / total_listings if total_listings > 0 else 0
            
            embed.set_footer(
                text=f"📊 {total_listings} listings • Avg Priority: {avg_priority:.2f} • Weekly Digest"
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"❌ Failed to create weekly digest embed: {e}")
            return discord.Embed(
                title="Weekly Digest Error",
                description="Failed to create weekly digest",
                color=discord.Color.red()
            )
    
    async def get_digest_stats(self) -> Dict[str, Any]:
        """
        Get statistics about digest performance
        
        Returns:
            Dictionary with digest statistics
        """
        try:
            # Get listings from past 24 hours
            recent_listings = await self.tier_manager.get_top_listings_for_digest(hours=24, limit=100)
            
            # Get listings from past 7 days
            weekly_listings = await self.tier_manager.get_top_listings_for_digest(hours=168, limit=500)
            
            # Calculate statistics
            stats = {
                'recent_listings_24h': len(recent_listings),
                'weekly_listings_7d': len(weekly_listings),
                'avg_priority_24h': 0.0,
                'avg_priority_7d': 0.0,
                'top_brands_24h': {},
                'top_brands_7d': {}
            }
            
            # Calculate average priorities
            if recent_listings:
                stats['avg_priority_24h'] = sum(score for _, score in recent_listings) / len(recent_listings)
            
            if weekly_listings:
                stats['avg_priority_7d'] = sum(score for _, score in weekly_listings) / len(weekly_listings)
            
            # Count brands
            for listing_data, _ in recent_listings:
                brand = listing_data.get('brand', 'Unknown')
                stats['top_brands_24h'][brand] = stats['top_brands_24h'].get(brand, 0) + 1
            
            for listing_data, _ in weekly_listings:
                brand = listing_data.get('brand', 'Unknown')
                stats['top_brands_7d'][brand] = stats['top_brands_7d'].get(brand, 0) + 1
            
            # Sort brand counts
            stats['top_brands_24h'] = dict(sorted(stats['top_brands_24h'].items(), key=lambda x: x[1], reverse=True)[:10])
            stats['top_brands_7d'] = dict(sorted(stats['top_brands_7d'].items(), key=lambda x: x[1], reverse=True)[:10])
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get digest stats: {e}")
            return {'error': str(e)}
    
    async def cleanup_old_listings(self, days: int = 7) -> bool:
        """
        Clean up old listings from the queue
        
        Args:
            days: Number of days to keep listings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # This would require a method in tier_manager to delete old listings
            # For now, just log the intention
            logger.info(f"🧹 Would clean up listings older than {cutoff_date.isoformat()}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old listings: {e}")
            return False
