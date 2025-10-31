# Whop.com Integration Setup Guide

## 🎯 Overview
This guide will help you connect your Whop.com storefront to your Discord bot to automatically assign roles when users purchase subscriptions.

## 📋 Prerequisites
- ✅ Whop.com account with products set up
- ✅ Discord server with your bot already connected
- ✅ Discord roles created: `Free`, `Standard`, `Instant`

## 🔧 Step 1: Configure Whop Products

### In Whop Dashboard:

1. **Go to Products/Passes**
   - Navigate to each product (Standard, Instant)
   - Click "Edit" on each product

2. **Add Discord Role as Benefit**
   - In the product settings, find "Benefits" or "Discord Integration"
   - Add the corresponding Discord role:
     - **Standard product** → Assign `Standard` role
     - **Instant product** → Assign `Instant` role
   
3. **Verify Product Names**
   - Make sure your product names contain "Standard" or "Instant" (case-insensitive)
   - OR use the webhook metadata to map products to tiers (see Step 3)

## 🔗 Step 2: Set Up Whop Webhook (Recommended - Backup System)

### In Whop Dashboard:

1. **Go to Settings → Webhooks**
   - Click "Add Webhook" or "New Webhook"

2. **Configure Webhook**
   - **URL**: `https://yahoo-japan-scraper-production.up.railway.app/whop/webhook`
   - **Events to subscribe to**:
     - `order.paid` - When a purchase is completed
     - `subscription.created` - When a subscription starts
     - `subscription.cancelled` - When a subscription is cancelled
     - `pass.activated` - When a pass is activated
     - `pass.revoked` - When a pass is revoked
     - `subscription.expired` - When a subscription expires

3. **Copy Webhook Secret**
   - If Whop provides a webhook secret, copy it
   - Add it to Railway environment variables as `WHOP_WEBHOOK_SECRET`

4. **Test Webhook**
   - Use Whop's "Test Webhook" button if available
   - Or make a test purchase to verify

## ⚙️ Step 3: Configure Railway Environment Variables

### Add to Railway:

1. **Go to Railway Dashboard → Your Project → Variables**

2. **Add Environment Variable** (if using webhook secret):
   - Name: `WHOP_WEBHOOK_SECRET`
   - Value: (Your webhook secret from Whop)

3. **Redeploy** if needed

## 🧪 Step 4: Test the Integration

### Test Methods:

1. **Use the test command**:
   ```
   !testwhop <discord_id> <tier>
   ```
   Example: `!testwhop 123456789 standard`

2. **Make a test purchase**:
   - Create a test account on Whop
   - Purchase a Standard or Instant product
   - Verify the role is assigned in Discord

3. **Check Railway logs**:
   - Look for webhook events in the logs
   - Verify role assignment messages

## ✅ Step 5: Verify Role Hierarchy

### In Discord:

1. **Go to Server Settings → Roles**

2. **Check Role Order**:
   - Your bot's role must be **above** `Standard` and `Instant` roles
   - This allows the bot to assign those roles

3. **Verify Permissions**:
   - Bot needs "Manage Roles" permission
   - Bot role should be higher than the roles it assigns

## 🔍 Troubleshooting

### Roles Not Assigning?

1. **Check Railway Logs**:
   - Look for webhook events
   - Check for errors in role assignment

2. **Verify Discord ID**:
   - Make sure Whop is sending the correct Discord user ID
   - Test with `!testwhop` command

3. **Check Product Names**:
   - Product names must contain "Standard" or "Instant"
   - Or use metadata/custom fields to specify tier

4. **Verify Bot Permissions**:
   - Bot needs "Manage Roles" permission
   - Bot role must be above target roles

### Webhook Not Receiving Events?

1. **Check Webhook URL**:
   - Verify the URL is correct in Whop dashboard
   - Test the endpoint: `curl https://yahoo-japan-scraper-production.up.railway.app/whop/webhook`

2. **Check Railway Logs**:
   - Look for incoming webhook requests
   - Check for signature verification errors

3. **Verify Event Types**:
   - Make sure you subscribed to the correct events in Whop
   - Check if Whop is sending the events you expect

## 📝 Notes

- **Whop's native Discord integration** should handle most role assignments automatically
- **Our webhook** acts as a backup/verification system
- **Product names** are used to determine which tier to assign
- **Test thoroughly** before launching to customers

## 🚀 Next Steps

1. Test with a real purchase (your own account)
2. Monitor logs for the first few transactions
3. Verify roles are assigned correctly
4. Test cancellation/refund flow

