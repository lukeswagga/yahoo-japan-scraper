#!/usr/bin/env python3
"""
Stripe integration for Yahoo Japan auction bot subscriptions
"""
import stripe
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class StripeManager:
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.standard_price_id = os.getenv('STRIPE_STANDARD_PRICE_ID')
        self.instant_price_id = os.getenv('STRIPE_INSTANT_PRICE_ID')
        
        if not all([stripe.api_key, self.webhook_secret, self.standard_price_id, self.instant_price_id]):
            raise ValueError("Missing required Stripe environment variables")
    
    async def create_checkout_session(self, discord_id: str, tier: str, success_url: str, cancel_url: str) -> Dict[str, Any]:
        """Create Stripe checkout session for subscription"""
        try:
            # Validate tier
            if tier not in ['standard', 'instant']:
                raise ValueError(f"Invalid tier: {tier}")
            
            price_id = self.standard_price_id if tier == 'standard' else self.instant_price_id
            
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'discord_id': discord_id,
                    'tier': tier
                },
                customer_email=None,  # Let Stripe collect email
                subscription_data={
                    'metadata': {
                        'discord_id': discord_id,
                        'tier': tier
                    }
                }
            )
            
            logger.info(f"Created checkout session for {discord_id} - {tier}")
            return {
                'session_id': session.id,
                'url': session.url,
                'expires_at': session.expires_at
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise
    
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            logger.info(f"Received Stripe webhook: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'checkout.session.completed':
                return await self._handle_checkout_completed(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.created':
                return await self._handle_subscription_created(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.updated':
                return await self._handle_subscription_updated(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.deleted':
                return await self._handle_subscription_deleted(event['data']['object'])
            
            elif event['type'] == 'invoice.payment_failed':
                return await self._handle_payment_failed(event['data']['object'])
            
            else:
                logger.info(f"Unhandled webhook event: {event['type']}")
                return {'status': 'ignored', 'event_type': event['type']}
                
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            raise
    
    async def _handle_checkout_completed(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful checkout completion"""
        discord_id = session['metadata'].get('discord_id')
        tier = session['metadata'].get('tier')
        customer_id = session['customer']
        
        if not discord_id or not tier:
            logger.error("Missing metadata in checkout session")
            return {'status': 'error', 'message': 'Missing metadata'}
        
        # Update user in database
        # This would integrate with your tier_manager
        logger.info(f"Checkout completed for {discord_id} - {tier}")
        
        return {
            'status': 'success',
            'action': 'upgrade_user',
            'discord_id': discord_id,
            'tier': tier,
            'customer_id': customer_id
        }
    
    async def _handle_subscription_created(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle new subscription creation"""
        customer_id = subscription['customer']
        subscription_id = subscription['id']
        status = subscription['status']
        
        # Get customer details
        customer = stripe.Customer.retrieve(customer_id)
        discord_id = customer.metadata.get('discord_id')
        
        if not discord_id:
            logger.error(f"No discord_id in customer metadata: {customer_id}")
            return {'status': 'error', 'message': 'No discord_id found'}
        
        logger.info(f"Subscription created for {discord_id}: {subscription_id}")
        
        return {
            'status': 'success',
            'action': 'activate_subscription',
            'discord_id': discord_id,
            'subscription_id': subscription_id,
            'status': status
        }
    
    async def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription updates (status changes, plan changes)"""
        subscription_id = subscription['id']
        status = subscription['status']
        
        # Get customer to find discord_id
        customer_id = subscription['customer']
        customer = stripe.Customer.retrieve(customer_id)
        discord_id = customer.metadata.get('discord_id')
        
        if not discord_id:
            logger.error(f"No discord_id in customer metadata: {customer_id}")
            return {'status': 'error', 'message': 'No discord_id found'}
        
        logger.info(f"Subscription updated for {discord_id}: {subscription_id} - {status}")
        
        return {
            'status': 'success',
            'action': 'update_subscription',
            'discord_id': discord_id,
            'subscription_id': subscription_id,
            'status': status
        }
    
    async def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        subscription_id = subscription['id']
        
        # Get customer to find discord_id
        customer_id = subscription['customer']
        customer = stripe.Customer.retrieve(customer_id)
        discord_id = customer.metadata.get('discord_id')
        
        if not discord_id:
            logger.error(f"No discord_id in customer metadata: {customer_id}")
            return {'status': 'error', 'message': 'No discord_id found'}
        
        logger.info(f"Subscription cancelled for {discord_id}: {subscription_id}")
        
        return {
            'status': 'success',
            'action': 'cancel_subscription',
            'discord_id': discord_id,
            'subscription_id': subscription_id
        }
    
    async def _handle_payment_failed(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        customer_id = invoice['customer']
        
        # Get customer to find discord_id
        customer = stripe.Customer.retrieve(customer_id)
        discord_id = customer.metadata.get('discord_id')
        
        if not discord_id:
            logger.error(f"No discord_id in customer metadata: {customer_id}")
            return {'status': 'error', 'message': 'No discord_id found'}
        
        logger.warning(f"Payment failed for {discord_id}")
        
        return {
            'status': 'success',
            'action': 'payment_failed',
            'discord_id': discord_id,
            'invoice_id': invoice['id']
        }
    
    async def cancel_subscription(self, discord_id: str) -> Dict[str, Any]:
        """Cancel user's subscription"""
        try:
            # Find customer by discord_id
            customers = stripe.Customer.list(limit=100)
            customer = None
            
            for c in customers.data:
                if c.metadata.get('discord_id') == discord_id:
                    customer = c
                    break
            
            if not customer:
                return {'status': 'error', 'message': 'Customer not found'}
            
            # Find active subscription
            subscriptions = stripe.Subscription.list(customer=customer.id, status='active')
            
            if not subscriptions.data:
                return {'status': 'error', 'message': 'No active subscription found'}
            
            # Cancel subscription
            subscription = subscriptions.data[0]
            stripe.Subscription.modify(
                subscription.id,
                cancel_at_period_end=True
            )
            
            logger.info(f"Cancelled subscription for {discord_id}")
            
            return {
                'status': 'success',
                'message': 'Subscription will cancel at period end',
                'subscription_id': subscription.id,
                'current_period_end': subscription.current_period_end
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error cancelling subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            raise
    
    async def get_subscription_status(self, discord_id: str) -> Dict[str, Any]:
        """Get user's subscription status"""
        try:
            # Find customer by discord_id
            customers = stripe.Customer.list(limit=100)
            customer = None
            
            for c in customers.data:
                if c.metadata.get('discord_id') == discord_id:
                    customer = c
                    break
            
            if not customer:
                return {'status': 'no_subscription', 'tier': 'free'}
            
            # Get active subscription
            subscriptions = stripe.Subscription.list(customer=customer.id, status='active')
            
            if not subscriptions.data:
                return {'status': 'no_subscription', 'tier': 'free'}
            
            subscription = subscriptions.data[0]
            
            # Determine tier from price
            price_id = subscription['items']['data'][0]['price']['id']
            tier = 'standard' if price_id == self.standard_price_id else 'instant'
            
            return {
                'status': 'active',
                'tier': tier,
                'subscription_id': subscription.id,
                'current_period_end': subscription.current_period_end,
                'cancel_at_period_end': subscription.cancel_at_period_end
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting subscription status: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            raise
