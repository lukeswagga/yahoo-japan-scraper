# 🎯 Premium Tier System Setup Guide

## 📋 Overview

This guide will help you set up the role-based channel access system for your Discord Auction Bot with three tiers:
- **Free**: Basic access with 2+ hour delays
- **Pro ($20/month)**: Real-time alerts + brand channels  
- **Elite ($50/month)**: Everything + premium features

## 🚀 Step 1: Discord Server Setup

### 1.1 Create Required Channels

Your Discord server needs these channels for the tier system to work:

#### **Free Tier Channels:**
- `📦-daily-digest` - Delayed listings for free users
- `💰-budget-steals` - Budget-friendly finds
- `🗳️-community-votes` - Community voting
- `💬-general-chat` - General discussion
- `💡-style-advice` - Style advice

#### **Pro Tier Channels (Free + Premium):**
- `⏰-hourly-drops` - Hourly updates
- `🔔-size-alerts` - Size-specific alerts
- `📊-price-tracker` - Price tracking
- `🔍-sold-listings` - Recently sold items
- All brand channels: `🏷️-raf-simons`, `🏷️-rick-owens`, etc.

#### **Elite Tier Channels (Pro + Premium):**
- `⚡-instant-alerts` - Instant notifications
- `🔥-grail-hunter` - Rare finds only
- `🎯-personal-alerts` - AI personalized alerts
- `📊-market-intelligence` - Market analytics
- `🛡️-verified-sellers` - Verified seller listings
- `💎-investment-pieces` - High-value items
- `🏆-vip-lounge` - VIP discussions
- `📈-trend-analysis` - Trend analysis
- `💹-investment-tracking` - Investment tracking

### 1.2 Bot Permissions

Ensure your bot has these permissions:
- **Manage Roles** - To create and assign tier roles
- **Manage Channels** - To set channel permissions
- **Send Messages** - To send listings
- **Read Message History** - To read channel content
- **Add Reactions** - For user interactions

## 🛠️ Step 2: Initialize the Tier System

### 2.1 Run the Setup Command

Once your bot is running, use this admin command in your Discord server:

```
!setup_tiers
```

This will:
- ✅ Create the tier roles (Free User, Pro User, Elite User)
- ✅ Set up channel permissions for each tier
- ✅ Configure the database tables

### 2.2 Verify Setup

Check that the roles were created:
- **Free User** (Gray color)
- **Pro User** (Blue color) 
- **Elite User** (Gold color)

## 👥 Step 3: User Management

### 3.1 Upgrade Users

Use this command to upgrade users to premium tiers:

```
!upgrade_user @username pro
!upgrade_user @username elite
```

### 3.2 Check User Tier

Users can check their current tier with:

```
!my_tier
```

## 💰 Step 4: Payment Integration (Future)

The system is ready for payment integration. You'll need to:

1. **Choose a payment processor** (Stripe, PayPal, etc.)
2. **Create webhook endpoints** for payment events
3. **Automate role assignment** based on payments
4. **Handle subscription renewals/cancellations**

### 4.1 Database Schema

The system includes a `user_subscriptions` table with:
- `user_id` - Discord user ID
- `tier` - Current tier (free/pro/elite)
- `upgraded_at` - When they upgraded
- `expires_at` - When subscription expires
- `payment_provider` - Payment processor used
- `subscription_id` - External subscription ID
- `status` - Subscription status

## 📊 Step 5: How It Works

### 5.1 Listing Distribution

**Free Users:**
- Access to basic channels only
- Listings are delayed by 2+ hours
- Limited to 10 listings per day
- 25 bookmark limit

**Pro Users ($20/month):**
- Real-time alerts
- Access to all brand channels
- Unlimited bookmarks (500 limit)
- AI personalization
- Price tracking

**Elite Users ($50/month):**
- All Pro features
- Grail hunter alerts
- Market intelligence
- Investment tracking
- Priority support
- VIP lounge access
- Unlimited bookmarks

### 5.2 Channel Access Control

The system automatically:
- ✅ Grants access to appropriate channels based on tier
- ✅ Denies access to premium channels for free users
- ✅ Handles role-based permissions
- ✅ Manages delayed listings for free users

## 🔧 Step 6: Commands Reference

### Admin Commands:
- `!setup_tiers` - Initialize the tier system
- `!upgrade_user @user tier` - Upgrade user to specified tier

### User Commands:
- `!my_tier` - Show current tier and benefits

## 🚨 Troubleshooting

### Common Issues:

1. **"Tier system not initialized"**
   - Run `!setup_tiers` first

2. **"Error creating role"**
   - Check bot permissions (Manage Roles)

3. **"Error setting permissions"**
   - Check bot permissions (Manage Channels)

4. **Channels not found**
   - Ensure all required channels exist with exact names

### Debug Commands:
- Check bot logs for detailed error messages
- Use `!db_debug` to check database status

## 📈 Step 7: Monitoring & Analytics

### Track Usage:
- Monitor channel activity by tier
- Track upgrade conversions
- Analyze user engagement
- Monitor delayed listing delivery

### Key Metrics:
- Number of users per tier
- Channel access patterns
- Upgrade conversion rates
- User retention by tier

## 🔮 Future Enhancements

1. **Automated Payment Processing**
2. **Subscription Management Dashboard**
3. **Advanced Analytics**
4. **Custom Tier Features**
5. **A/B Testing Framework**

---

## ✅ Setup Checklist

- [ ] Create all required Discord channels
- [ ] Ensure bot has proper permissions
- [ ] Deploy updated bot code
- [ ] Run `!setup_tiers` command
- [ ] Test user upgrade functionality
- [ ] Verify channel access controls
- [ ] Test delayed listing system
- [ ] Set up payment processing (when ready)

---

**Need Help?** Check the bot logs for detailed error messages and ensure all channels exist with the exact names specified in this guide. 