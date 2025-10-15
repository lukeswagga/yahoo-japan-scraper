#!/usr/bin/env python3
"""
Discord bot commands for subscription management
"""
import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

class SubscriptionCommands(commands.Cog):
    def __init__(self, bot, stripe_manager, tier_manager):
        self.bot = bot
        self.stripe_manager = stripe_manager
        self.tier_manager = tier_manager
    
    @commands.command(name='subscribe')
    async def subscribe(self, ctx, tier: str = None):
        """Subscribe to Standard ($12/month) or Instant ($25/month) tier"""
        if not tier or tier.lower() not in ['standard', 'instant']:
            embed = discord.Embed(
                title="💳 Subscription Options",
                description="Choose your subscription tier:",
                color=0x00ff00
            )
            embed.add_field(
                name="🟢 Standard Tier - $12/month",
                value="• Access to #daily-digest\n• Access to #standard-feed (5 listings/hour)\n• Perfect for casual users",
                inline=False
            )
            embed.add_field(
                name="🔴 Instant Tier - $25/month", 
                value="• Everything in Standard\n• Real-time alerts in all channels\n• Brand-specific channels\n• Perfect for serious collectors",
                inline=False
            )
            embed.add_field(
                name="How to Subscribe",
                value="Use `!subscribe standard` or `!subscribe instant`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        tier = tier.lower()
        discord_id = str(ctx.author.id)
        
        try:
            # Check if user already has active subscription
            current_status = await self.stripe_manager.get_subscription_status(discord_id)
            
            if current_status['status'] == 'active':
                embed = discord.Embed(
                    title="⚠️ Already Subscribed",
                    description=f"You already have an active {current_status['tier']} subscription.",
                    color=0xffaa00
                )
                embed.add_field(
                    name="Current Subscription",
                    value=f"Tier: {current_status['tier'].title()}\nStatus: Active",
                    inline=False
                )
                if current_status.get('cancel_at_period_end'):
                    embed.add_field(
                        name="Cancellation",
                        value="Your subscription will cancel at the end of the current period.",
                        inline=False
                    )
                await ctx.send(embed=embed)
                return
            
            # Create checkout session
            success_url = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}"
            cancel_url = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}"
            
            session_data = await self.stripe_manager.create_checkout_session(
                discord_id=discord_id,
                tier=tier,
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            # Send DM with payment link
            try:
                embed = discord.Embed(
                    title="💳 Complete Your Subscription",
                    description=f"Click the link below to complete your {tier.title()} subscription:",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Payment Link",
                    value=f"[Complete Payment]({session_data['url']})",
                    inline=False
                )
                embed.add_field(
                    name="Expires In",
                    value="24 hours",
                    inline=True
                )
                embed.add_field(
                    name="Price",
                    value="$12/month" if tier == 'standard' else "$25/month",
                    inline=True
                )
                embed.set_footer(text="This link is secure and will redirect you to Stripe for payment processing.")
                
                await ctx.author.send(embed=embed)
                
                # Confirm in channel
                await ctx.send(f"✅ Payment link sent to your DMs, {ctx.author.mention}!")
                
            except discord.Forbidden:
                await ctx.send("❌ I couldn't send you a DM. Please check your privacy settings and try again.")
                
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            await ctx.send("❌ An error occurred while creating your subscription. Please try again later.")
    
    @commands.command(name='cancel')
    async def cancel_subscription(self, ctx):
        """Cancel your active subscription"""
        discord_id = str(ctx.author.id)
        
        try:
            # Check current subscription
            current_status = await self.stripe_manager.get_subscription_status(discord_id)
            
            if current_status['status'] != 'active':
                embed = discord.Embed(
                    title="❌ No Active Subscription",
                    description="You don't have an active subscription to cancel.",
                    color=0xff0000
                )
                await ctx.send(embed=embed)
                return
            
            # Cancel subscription
            result = await self.stripe_manager.cancel_subscription(discord_id)
            
            if result['status'] == 'success':
                embed = discord.Embed(
                    title="✅ Subscription Cancelled",
                    description="Your subscription has been cancelled and will end at the current period.",
                    color=0xffaa00
                )
                embed.add_field(
                    name="Current Period Ends",
                    value=f"<t:{result['current_period_end']}:F>",
                    inline=False
                )
                embed.add_field(
                    name="What Happens Next",
                    value="You'll keep your current tier access until the period ends, then be downgraded to Free tier.",
                    inline=False
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Error cancelling subscription: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            await ctx.send("❌ An error occurred while cancelling your subscription. Please try again later.")
    
    @commands.command(name='subscription', aliases=['sub', 'status'])
    async def subscription_status(self, ctx):
        """Check your subscription status"""
        discord_id = str(ctx.author.id)
        
        try:
            # Get subscription status
            status = await self.stripe_manager.get_subscription_status(discord_id)
            
            if status['status'] == 'no_subscription':
                embed = discord.Embed(
                    title="🆓 Free Tier",
                    description="You're currently on the Free tier.",
                    color=0x808080
                )
                embed.add_field(
                    name="What You Get",
                    value="• Access to #daily-digest (top 20 listings at 9 AM UTC)",
                    inline=False
                )
                embed.add_field(
                    name="Upgrade Options",
                    value="Use `!subscribe` to see available tiers",
                    inline=False
                )
            else:
                tier = status['tier']
                color = 0x00ff00 if tier == 'instant' else 0x0099ff
                
                embed = discord.Embed(
                    title=f"💳 {tier.title()} Subscription",
                    description=f"Your {tier.title()} subscription is active.",
                    color=color
                )
                
                embed.add_field(
                    name="Status",
                    value="Active" if not status.get('cancel_at_period_end') else "Cancelling at period end",
                    inline=True
                )
                embed.add_field(
                    name="Next Billing",
                    value=f"<t:{status['current_period_end']}:F>",
                    inline=True
                )
                
                if tier == 'standard':
                    embed.add_field(
                        name="What You Get",
                        value="• #daily-digest\n• #standard-feed (5 listings/hour)",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="What You Get",
                        value="• All Standard features\n• Real-time alerts in all channels\n• Brand-specific channels",
                        inline=False
                    )
                
                if not status.get('cancel_at_period_end'):
                    embed.add_field(
                        name="Manage Subscription",
                        value="Use `!cancel` to cancel your subscription",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            await ctx.send("❌ An error occurred while checking your subscription status.")
    
    @commands.command(name='upgrade')
    async def upgrade_subscription(self, ctx, new_tier: str = None):
        """Upgrade your subscription (Standard → Instant)"""
        if not new_tier or new_tier.lower() not in ['instant']:
            embed = discord.Embed(
                title="🔄 Upgrade Options",
                description="Available upgrades:",
                color=0x00ff00
            )
            embed.add_field(
                name="Standard → Instant",
                value="Use `!upgrade instant` to upgrade to Instant tier",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        new_tier = new_tier.lower()
        discord_id = str(ctx.author.id)
        
        try:
            # Check current subscription
            current_status = await self.stripe_manager.get_subscription_status(discord_id)
            
            if current_status['status'] != 'active':
                await ctx.send("❌ You need an active subscription to upgrade.")
                return
            
            if current_status['tier'] == new_tier:
                await ctx.send(f"❌ You're already on the {new_tier.title()} tier.")
                return
            
            if current_status['tier'] == 'instant':
                await ctx.send("❌ You're already on the highest tier.")
                return
            
            # For now, direct them to cancel and resubscribe
            # In production, you'd want to handle prorated upgrades
            embed = discord.Embed(
                title="🔄 Upgrade Process",
                description="To upgrade your subscription:",
                color=0x00ff00
            )
            embed.add_field(
                name="Step 1",
                value="Cancel your current subscription with `!cancel`",
                inline=False
            )
            embed.add_field(
                name="Step 2", 
                value="Subscribe to the new tier with `!subscribe instant`",
                inline=False
            )
            embed.add_field(
                name="Note",
                value="You'll keep your current access until the period ends, then get the new tier.",
                inline=False
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error upgrading subscription: {e}")
            await ctx.send("❌ An error occurred while processing your upgrade request.")

def setup(bot):
    """Setup function for the cog"""
    # This would be called when adding the cog to the bot
    pass
