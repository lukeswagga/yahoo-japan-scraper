# 🎯 Premium Tier System Setup Guide

## 📋 Overview

This guide will help you set up the role-based channel access system for your Discord Auction Bot with three tiers:
- **Free**: Basic access with 2+ hour delays
- **Pro ($20/month)**: Real-time alerts + brand channels  
- **Elite ($50/month)**: Everything + premium features

## 🚀 Step 1: Initial Setup (Existing Channels Only)

### 1.1 What You Already Have

The system will work with your existing channels:

#### **Free Tier Channels (Already Exist):**
- `📦-daily-digest` - Delayed listings for free users
- `💰-budget-steals` - Budget-friendly finds
- `🗳️-community-votes` - Community voting
- `💬-general-chat` - General discussion
- `💡-style-advice` - Style advice

#### **Pro Tier Channels (Brand Channels Already Exist):**
- All brand channels: `🏷️-raf-simons`, `🏷️-rick-owens`, `🏷️-maison-margiela`, etc.

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
- ✅ Set up channel permissions for existing channels only
- ✅ Configure the database tables
- ⚠️ Show you which premium channels are missing

### 2.2 Check Current Status

Use this command to see what channels are set up:

```
!list_channels
```

This will show you:
- ✅ Which channels are properly configured
- ❌ Which premium channels are missing
- 📋 Current tier assignments

## 🏗️ Step 3: Add Premium Channels Gradually

### 3.1 Pro Tier Channels (Add When Ready)

Create these channels when you want to offer Pro tier:

- `⏰-hourly-drops` - Hourly updates
- `🔔-size-alerts` - Size-specific alerts
- `📊-price-tracker` - Price tracking
- `🔍-sold-listings` - Recently sold items

### 3.2 Elite Tier Channels (Add When Ready)

Create these channels when you want to offer Elite tier:

- `⚡-instant-alerts` - Instant notifications
- `🔥-grail-hunter` - Rare finds only
- `🎯-personal-alerts` - AI personalized alerts
- `📊-market-intelligence` - Market analytics
- `🛡️-verified-sellers` - Verified seller listings
- `💎-investment-pieces` - High-value items
- `🏆-vip-lounge` - VIP discussions
- `📈-trend-analysis` - Trend analysis
- `💹-investment-tracking` - Investment tracking

### 3.3 Update Permissions

After creating new channels, run:

```
!update_channels
```

This will automatically set up permissions for the new channels without affecting existing ones.

## 👥 Step 4: User Management

### 4.1 Upgrade Users

Use this command to upgrade users to premium tiers:

```
!upgrade_user @username pro
!upgrade_user @username elite
```

### 4.2 Check User Tier

Users can check their current tier with:

```
!my_tier
```

## 💰 Step 5: Payment Integration (Future)

The system is ready for payment integration. You'll need to:

1. **Choose a payment processor** (Stripe, PayPal, etc.)
2. **Create webhook endpoints** for payment events
3. **Automate role assignment** based on payments
4. **Handle subscription renewals/cancellations**

### 5.1 Database Schema

The system includes a `user_subscriptions` table with:
- `user_id` - Discord user ID
- `tier` - Current tier (free/pro/elite)
- `upgraded_at` - When they upgraded
- `expires_at` - When subscription expires
- `payment_provider` - Payment processor used
- `subscription_id` - External subscription ID
- `status` - Subscription status

## 📊 Step 6: How It Works

### 6.1 Listing Distribution

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

### 6.2 Channel Access Control

The system automatically:
- ✅ Grants access to appropriate channels based on tier
- ✅ Denies access to premium channels for free users
- ✅ Handles role-based permissions
- ✅ Manages delayed listings for free users
- ✅ Only works with channels that actually exist

## 🔧 Step 7: Commands Reference

### Admin Commands:
- `!setup_tiers` - Initialize the tier system
- `!update_channels` - Update permissions for new channels
- `!list_channels` - Show channel tier assignments
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

4. **Missing channels warning**
   - This is normal! Create channels gradually and run `!update_channels`

### Debug Commands:
- Use `!list_channels` to see current status
- Check bot logs for detailed error messages
- Use `!db_debug` to check database status

## 📈 Step 8: Monitoring & Analytics

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

## 🔮 Step 9: Future Enhancements

1. **Automated Payment Processing**
2. **Subscription Management Dashboard**
3. **Advanced Analytics**
4. **Custom Tier Features**
5. **A/B Testing Framework**

---

## ✅ Setup Checklist

- [ ] Ensure bot has proper permissions
- [ ] Deploy updated bot code
- [ ] Run `!setup_tiers` command
- [ ] Check `!list_channels` to see current status
- [ ] Test user upgrade functionality
- [ ] Verify channel access controls
- [ ] Test delayed listing system
- [ ] Create premium channels gradually
- [ ] Run `!update_channels` after adding new channels
- [ ] Set up payment processing (when ready)

---

## 🎯 Recommended Launch Strategy

1. **Phase 1**: Launch with existing channels only
   - Free tier gets delayed access to brand channels
   - Pro tier gets real-time access to brand channels
   - Test the system with a few users

2. **Phase 2**: Add Pro tier channels
   - Create hourly-drops, size-alerts, etc.
   - Run `!update_channels`
   - Market Pro tier features

3. **Phase 3**: Add Elite tier channels
   - Create premium channels
   - Run `!update_channels`
   - Launch Elite tier

This gradual approach lets you test and refine the system before adding more premium features.

---

**Need Help?** Check the bot logs for detailed error messages and use `!list_channels` to see the current status of your channel setup. 