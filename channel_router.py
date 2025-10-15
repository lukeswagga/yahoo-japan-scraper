#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Channel Router for Discord Auction Bot
Routes listings to appropriate channels based on tier access and user preferences
"""

import discord
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ChannelRouter:
    def __init__(self, bot, tier_manager):
        """
        Initialize channel router
        
        Args:
            bot: Discord bot instance
            tier_manager: TierManager instance for user tier management
        """
        self.bot = bot
        self.tier_manager = tier_manager
        
        # Channel name mapping for scraper sources (with emojis to match actual Discord channels)
        self.scraper_to_channel = {
            'ending_soon_scraper': '⏰-ending-soon',
            'budget_steals_scraper': '💰-budget-steals',
            'new_listings_scraper': '🆕-new-listings',
            'buy_it_now_scraper': '🛒-buy-it-now'
        }
        
        # Brand to channel name mapping (with emoji prefix to match actual Discord channels)
        # Must match BRAND_CHANNEL_MAP in secure_discordbot.py exactly
        self.brand_to_channel = {
            'Vetements': '🏷️-vetements',
            'Alyx': '🏷️-alyx',
            'Anonymous Club': '🏷️-anonymous-club',
            'Balenciaga': '🏷️-balenciaga',
            'Bottega Veneta': '🏷️-bottega-veneta',
            'Celine': '🏷️-celine',
            'Chrome Hearts': '🏷️-chrome-hearts',
            'Comme Des Garcons': '🏷️-comme-des-garcons',
            'Gosha Rubchinskiy': '🏷️-gosha-rubchinskiy',
            'Helmut Lang': '🏷️-helmut-lang',
            'Hood By Air': '🏷️-hood-by-air',
            'Miu Miu': '🏷️-miu-miu',
            'Hysteric Glamour': '🏷️-hysteric-glamour',
            'Junya Watanabe': '🏷️-junya-watanabe',
            'Kiko Kostadinov': '🏷️-kiko-kostadinov',
            'Maison Margiela': '🏷️-maison-margiela',
            'Martine Rose': '🏷️-martine-rose',
            'Prada': '🏷️-prada',
            'Raf Simons': '🏷️-raf-simons',
            'Rick Owens': '🏷️-rick-owens',
            'Undercover': '🏷️-undercover',
            'Jean Paul Gaultier': '🏷️-jean-paul-gaultier',
            'Yohji Yamamoto': '🏷️-yohji_yamamoto',
            'Issey Miyake': '🏷️-issey-miyake'
        }
    
    async def route_listing(self, listing_data: Dict[str, Any]) -> bool:
        """
        Route listing to appropriate channels based on tier access
        
        Args:
            listing_data: Dictionary containing listing information
            
        Returns:
            True if routing was successful, False otherwise
        """
        try:
            # 1. Add to listing_queue for daily digest (all tiers)
            await self._queue_for_digest(listing_data)
            
            # 2. Route to standard-feed (standard tier users with brand preference match)
            await self._route_to_standard_feed(listing_data)
            
            # 3. Route to instant tier channels
            await self._route_to_instant_channels(listing_data)
            
            logger.info(f"✅ Successfully routed listing {listing_data.get('auction_id')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to route listing: {e}")
            return False
    
    async def _queue_for_digest(self, listing_data: Dict[str, Any]) -> bool:
        """Add listing to queue for daily digest"""
        try:
            priority_score = listing_data.get('priority_score', 0.5)
            await self.tier_manager.add_listing_to_queue(listing_data, priority_score)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to queue listing for digest: {e}")
            return False
    
    async def _route_to_standard_feed(self, listing_data: Dict[str, Any]) -> bool:
        """
        Queue listing for hourly standard-feed posting (5 best listings per hour)
        No real-time posting - listings are queued and posted on schedule
        """
        try:
            auction_id = listing_data.get('auction_id', 'unknown')
            logger.info(f"📝 Queueing listing {auction_id} for standard-feed hourly posting...")
            
            # Mark listing as queued for standard-feed (not posted yet)
            await self.tier_manager.queue_for_standard_feed(listing_data)
            logger.info(f"✅ Queued {auction_id} for standard-feed hourly posting")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to queue for standard feed: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    async def _route_to_instant_channels(self, listing_data: Dict[str, Any]) -> bool:
        """Post to instant tier channels"""
        try:
            # Post to #auction-alerts (all listings)
            await self._post_to_channel('🎯-auction-alerts', listing_data)
            
            # Post to scraper-specific channel
            scraper_source = listing_data.get('scraper_source', '')
            channel_name = self.scraper_to_channel.get(scraper_source)
            if channel_name:
                await self._post_to_channel(channel_name, listing_data)
            
            # Post to brand-specific channel
            brand = listing_data.get('brand', 'Unknown')
            if brand != 'Unknown':
                brand_channel = self.brand_to_channel.get(brand)
                if brand_channel:
                    await self._post_to_channel(brand_channel, listing_data)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to route to instant channels: {e}")
            return False
    
    async def _post_to_channel(self, channel_name: str, listing_data: Dict[str, Any]) -> bool:
        """
        Post listing to specific channel (tries with and without emoji prefix)
        
        Args:
            channel_name: Name of the Discord channel
            listing_data: Listing information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try exact name first
            channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)
            
            # If not found, try with common emoji prefixes
            if not channel:
                emoji_prefixes = ['🎯-', '💰-', '⏰-', '🏷️-', '📦-', '📰-']
                for prefix in emoji_prefixes:
                    prefixed_name = prefix + channel_name
                    channel = discord.utils.get(self.bot.get_all_channels(), name=prefixed_name)
                    if channel:
                        logger.info(f"📝 Found channel with emoji prefix: #{prefixed_name}")
                        break
            
            if not channel:
                logger.warning(f"⚠️ Channel #{channel_name} not found (tried with emoji prefixes)")
                return False
            
            # Check bot permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.error(f"❌ No permission to send messages in #{channel.name}")
                return False
            
            embed = self._create_listing_embed(listing_data)
            await channel.send(embed=embed)
            logger.info(f"✅ Posted to #{channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to post to #{channel_name}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False
    
    def _create_listing_embed(self, listing_data: Dict[str, Any]) -> discord.Embed:
        """
        Create rich embed for listing
        
        Args:
            listing_data: Dictionary containing listing information
            
        Returns:
            Discord Embed object
        """
        try:
            # Create base embed
            embed = discord.Embed(
                title=listing_data.get('title', 'Unknown Title')[:256],
                url=listing_data.get('zenmarket_url', ''),
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add fields
            embed.add_field(
                name="🏷️ Brand", 
                value=listing_data.get('brand', 'Unknown'), 
                inline=True
            )
            
            price_jpy = listing_data.get('price_jpy', 0)
            price_usd = listing_data.get('price_usd', 0)
            embed.add_field(
                name="💰 Price", 
                value=f"¥{price_jpy:,} (${price_usd:.2f})", 
                inline=True
            )
            
            deal_quality = listing_data.get('deal_quality', 0)
            embed.add_field(
                name="⭐ Quality", 
                value=f"{deal_quality:.1%}", 
                inline=True
            )
            
            # Add priority score if available
            priority_score = listing_data.get('priority_score')
            if priority_score is not None:
                embed.add_field(
                    name="📊 Priority", 
                    value=f"{priority_score:.2f}", 
                    inline=True
                )
            
            # Add scraper source
            scraper_source = listing_data.get('scraper_source', '')
            if scraper_source:
                embed.add_field(
                    name="🔍 Source", 
                    value=scraper_source.replace('_scraper', '').replace('_', ' ').title(), 
                    inline=True
                )
            
            # Add image if available
            image_url = listing_data.get('image_url')
            if image_url:
                embed.set_thumbnail(url=image_url)
            
            # Add links
            yahoo_url = listing_data.get('yahoo_url', '')
            zenmarket_url = listing_data.get('zenmarket_url', '')
            if yahoo_url and zenmarket_url:
                embed.add_field(
                    name="🔗 Links", 
                    value=f"[Yahoo Japan]({yahoo_url}) | [ZenMarket]({zenmarket_url})", 
                    inline=False
                )
            
            # Add footer with auction ID
            auction_id = listing_data.get('auction_id', 'Unknown')
            embed.set_footer(text=f"Auction ID: {auction_id}")
            
            return embed
            
        except Exception as e:
            logger.error(f"❌ Failed to create listing embed: {e}")
            # Return minimal embed on error
            return discord.Embed(
                title="Listing Error",
                description="Failed to create listing embed",
                color=discord.Color.red()
            )
    
    async def get_channel_stats(self) -> Dict[str, Any]:
        """
        Get statistics about channel routing
        
        Returns:
            Dictionary with channel statistics
        """
        try:
            stats = {
                'total_channels': 0,
                'instant_channels': 0,
                'standard_channels': 0,
                'brand_channels': 0,
                'missing_channels': []
            }
            
            # Check all expected channels (with emojis to match actual Discord channels)
            all_expected_channels = [
                'daily-digest', 'standard-feed', '🎯-auction-alerts',
                '⏰-ending-soon', '💰-budget-steals', '🆕-new-listings', '🛒-buy-it-now'
            ]
            
            # Add brand channels
            all_expected_channels.extend(self.brand_to_channel.values())
            
            for channel_name in all_expected_channels:
                channel = discord.utils.get(self.bot.get_all_channels(), name=channel_name)
                if channel:
                    stats['total_channels'] += 1
                    
                    if channel_name in ['daily-digest', 'standard-feed']:
                        stats['standard_channels'] += 1
                    elif channel_name in self.brand_to_channel.values():
                        stats['brand_channels'] += 1
                    else:
                        stats['instant_channels'] += 1
                else:
                    stats['missing_channels'].append(channel_name)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get channel stats: {e}")
            return {'error': str(e)}
    
    def get_brand_channel_name(self, brand: str) -> Optional[str]:
        """
        Get Discord channel name for a brand
        
        Args:
            brand: Brand name
            
        Returns:
            Channel name or None if not found
        """
        return self.brand_to_channel.get(brand)
    
    def get_scraper_channel_name(self, scraper_source: str) -> Optional[str]:
        """
        Get Discord channel name for a scraper source
        
        Args:
            scraper_source: Scraper source name
            
        Returns:
            Channel name or None if not found
        """
        return self.scraper_to_channel.get(scraper_source)
