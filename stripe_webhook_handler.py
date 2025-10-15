#!/usr/bin/env python3
"""
Stripe webhook handler for Discord bot integration
"""
from flask import Flask, request, jsonify
import asyncio
import logging
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

class StripeWebhookHandler:
    def __init__(self, stripe_manager, tier_manager, discord_bot):
        self.stripe_manager = stripe_manager
        self.tier_manager = tier_manager
        self.discord_bot = discord_bot
    
    async def handle_webhook_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process Stripe webhook event and update Discord user"""
        try:
            action = event_data.get('action')
            discord_id = event_data.get('discord_id')
            
            if not discord_id:
                logger.error("No discord_id in webhook event")
                return {'status': 'error', 'message': 'No discord_id'}
            
            if action == 'upgrade_user':
                return await self._upgrade_user(discord_id, event_data)
            elif action == 'activate_subscription':
                return await self._activate_subscription(discord_id, event_data)
            elif action == 'update_subscription':
                return await self._update_subscription(discord_id, event_data)
            elif action == 'cancel_subscription':
                return await self._cancel_subscription(discord_id, event_data)
            elif action == 'payment_failed':
                return await self._handle_payment_failed(discord_id, event_data)
            else:
                logger.warning(f"Unknown webhook action: {action}")
                return {'status': 'ignored', 'action': action}
                
        except Exception as e:
            logger.error(f"Error handling webhook event: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _upgrade_user(self, discord_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrade user to paid tier"""
        try:
            tier = event_data.get('tier')
            customer_id = event_data.get('customer_id')
            
            if not tier:
                return {'status': 'error', 'message': 'No tier specified'}
            
            # Update user in database
            await self.tier_manager.set_user_tier(discord_id, tier)
            await self.tier_manager.set_stripe_customer_id(discord_id, customer_id)
            
            # Assign Discord role
            await self._assign_discord_role(discord_id, tier)
            
            # Send confirmation DM
            await self._send_upgrade_confirmation(discord_id, tier)
            
            logger.info(f"Successfully upgraded {discord_id} to {tier}")
            return {'status': 'success', 'action': 'upgrade_user', 'tier': tier}
            
        except Exception as e:
            logger.error(f"Error upgrading user {discord_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _activate_subscription(self, discord_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Activate user's subscription"""
        try:
            subscription_id = event_data.get('subscription_id')
            status = event_data.get('status')
            
            # Update subscription status in database
            await self.tier_manager.set_subscription_status(discord_id, status)
            await self.tier_manager.set_stripe_subscription_id(discord_id, subscription_id)
            
            logger.info(f"Activated subscription for {discord_id}: {subscription_id}")
            return {'status': 'success', 'action': 'activate_subscription'}
            
        except Exception as e:
            logger.error(f"Error activating subscription for {discord_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _update_subscription(self, discord_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user's subscription status"""
        try:
            status = event_data.get('status')
            subscription_id = event_data.get('subscription_id')
            
            # Update subscription status
            await self.tier_manager.set_subscription_status(discord_id, status)
            
            # If subscription is past_due or unpaid, downgrade to free
            if status in ['past_due', 'unpaid', 'incomplete']:
                await self.tier_manager.set_user_tier(discord_id, 'free')
                await self._remove_discord_role(discord_id)
                await self._send_payment_failed_notification(discord_id)
            
            logger.info(f"Updated subscription for {discord_id}: {status}")
            return {'status': 'success', 'action': 'update_subscription', 'status': status}
            
        except Exception as e:
            logger.error(f"Error updating subscription for {discord_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _cancel_subscription(self, discord_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        try:
            # Downgrade to free tier
            await self.tier_manager.set_user_tier(discord_id, 'free')
            await self.tier_manager.set_subscription_status(discord_id, 'canceled')
            
            # Remove paid role
            await self._remove_discord_role(discord_id)
            
            # Send cancellation confirmation
            await self._send_cancellation_confirmation(discord_id)
            
            logger.info(f"Cancelled subscription for {discord_id}")
            return {'status': 'success', 'action': 'cancel_subscription'}
            
        except Exception as e:
            logger.error(f"Error cancelling subscription for {discord_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _handle_payment_failed(self, discord_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        try:
            # Update subscription status
            await self.tier_manager.set_subscription_status(discord_id, 'past_due')
            
            # Send payment failed notification
            await self._send_payment_failed_notification(discord_id)
            
            logger.warning(f"Payment failed for {discord_id}")
            return {'status': 'success', 'action': 'payment_failed'}
            
        except Exception as e:
            logger.error(f"Error handling payment failure for {discord_id}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def _assign_discord_role(self, discord_id: str, tier: str):
        """Assign appropriate Discord role to user"""
        try:
            guild = self.discord_bot.get_guild(int(os.getenv('GUILD_ID')))
            if not guild:
                logger.error("Guild not found")
                return
            
            member = guild.get_member(int(discord_id))
            if not member:
                logger.error(f"Member {discord_id} not found in guild")
                return
            
            # Remove existing paid roles
            free_role = discord.utils.get(guild.roles, name='Free')
            standard_role = discord.utils.get(guild.roles, name='Standard')
            instant_role = discord.utils.get(guild.roles, name='Instant')
            
            if free_role and free_role in member.roles:
                await member.remove_roles(free_role)
            
            # Assign new role
            if tier == 'standard' and standard_role:
                await member.add_roles(standard_role)
                logger.info(f"Assigned Standard role to {discord_id}")
            elif tier == 'instant' and instant_role:
                await member.add_roles(instant_role)
                logger.info(f"Assigned Instant role to {discord_id}")
            
        except Exception as e:
            logger.error(f"Error assigning Discord role: {e}")
    
    async def _remove_discord_role(self, discord_id: str):
        """Remove paid Discord role from user"""
        try:
            guild = self.discord_bot.get_guild(int(os.getenv('GUILD_ID')))
            if not guild:
                return
            
            member = guild.get_member(int(discord_id))
            if not member:
                return
            
            # Remove paid roles
            standard_role = discord.utils.get(guild.roles, name='Standard')
            instant_role = discord.utils.get(guild.roles, name='Instant')
            free_role = discord.utils.get(guild.roles, name='Free')
            
            if standard_role and standard_role in member.roles:
                await member.remove_roles(standard_role)
            if instant_role and instant_role in member.roles:
                await member.remove_roles(instant_role)
            
            # Add free role
            if free_role and free_role not in member.roles:
                await member.add_roles(free_role)
            
            logger.info(f"Removed paid roles from {discord_id}")
            
        except Exception as e:
            logger.error(f"Error removing Discord role: {e}")
    
    async def _send_upgrade_confirmation(self, discord_id: str, tier: str):
        """Send upgrade confirmation DM"""
        try:
            user = self.discord_bot.get_user(int(discord_id))
            if not user:
                return
            
            embed = discord.Embed(
                title="🎉 Welcome to Premium!",
                description=f"Your {tier.title()} subscription is now active.",
                color=0x00ff00
            )
            
            if tier == 'standard':
                embed.add_field(
                    name="What You Get",
                    value="• Access to #daily-digest\n• Access to #standard-feed (5 listings/hour)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="What You Get",
                    value="• All Standard features\n• Real-time alerts in all channels\n• Brand-specific channels",
                    inline=False
                )
            
            embed.add_field(
                name="Manage Your Subscription",
                value="Use `!subscription` to check your status\nUse `!cancel` to cancel anytime",
                inline=False
            )
            
            await user.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending upgrade confirmation: {e}")
    
    async def _send_cancellation_confirmation(self, discord_id: str):
        """Send cancellation confirmation DM"""
        try:
            user = self.discord_bot.get_user(int(discord_id))
            if not user:
                return
            
            embed = discord.Embed(
                title="👋 Subscription Cancelled",
                description="Your subscription has been cancelled.",
                color=0xffaa00
            )
            embed.add_field(
                name="What Happens Next",
                value="You'll keep your current access until the period ends, then be moved to Free tier.",
                inline=False
            )
            embed.add_field(
                name="Resubscribe Anytime",
                value="Use `!subscribe` to resubscribe whenever you're ready.",
                inline=False
            )
            
            await user.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending cancellation confirmation: {e}")
    
    async def _send_payment_failed_notification(self, discord_id: str):
        """Send payment failed notification DM"""
        try:
            user = self.discord_bot.get_user(int(discord_id))
            if not user:
                return
            
            embed = discord.Embed(
                title="⚠️ Payment Failed",
                description="We couldn't process your payment.",
                color=0xff0000
            )
            embed.add_field(
                name="What to Do",
                value="Please update your payment method in your Stripe customer portal or contact support.",
                inline=False
            )
            embed.add_field(
                name="Access",
                value="You'll keep your current access for a few days while we retry the payment.",
                inline=False
            )
            
            await user.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending payment failed notification: {e}")

# Flask webhook endpoint
def create_webhook_app(stripe_manager, tier_manager, discord_bot):
    """Create Flask app for Stripe webhooks"""
    app = Flask(__name__)
    webhook_handler = StripeWebhookHandler(stripe_manager, tier_manager, discord_bot)
    
    @app.route('/webhook/stripe', methods=['POST'])
    def stripe_webhook():
        """Handle Stripe webhook events"""
        try:
            # Get webhook data
            payload = request.data
            signature = request.headers.get('Stripe-Signature')
            
            if not signature:
                return jsonify({"error": "Missing signature"}), 400
            
            # Process webhook with Stripe manager
            event_data = asyncio.run(stripe_manager.handle_webhook(payload, signature))
            
            # Handle the event with webhook handler
            result = asyncio.run(webhook_handler.handle_webhook_event(event_data))
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {e}")
            return jsonify({"error": "Internal server error"}), 500
    
    return app
