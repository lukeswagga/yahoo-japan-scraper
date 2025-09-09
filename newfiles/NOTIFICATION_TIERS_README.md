# Discord Auction Bot - Notification Tier System

A comprehensive tier-based notification system for the Discord auction bot that provides different levels of real-time notifications based on user subscription tiers.

## 🎯 Overview

The notification tier system provides three distinct tiers:

- **Free Tier**: Daily digest only (posted to #daily-digest at 9 AM UTC)
- **Standard Tier ($12/month)**: 50 real-time Discord DMs per day + daily digest
- **Instant Tier ($25/month)**: Unlimited real-time Discord DMs + daily digest

## 🏗️ Architecture

### Core Components

1. **`notification_tiers.py`** - Main tier management class
2. **`daily_scheduler.py`** - Background scheduler for daily tasks
3. **Database tables** - User subscriptions, digest queue, notification logs
4. **Discord commands** - Admin and user management commands
5. **Webhook integration** - Real-time notification delivery

### Database Schema

#### `user_subscriptions` (Enhanced)
```sql
- user_id: BIGINT PRIMARY KEY
- tier: VARCHAR(20) DEFAULT 'free'
- daily_count: INTEGER DEFAULT 0
- last_reset: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- upgraded_at: TIMESTAMP
- status: VARCHAR(20) DEFAULT 'active'
```

#### `daily_digest_queue` (New)
```sql
- auction_id: VARCHAR(100)
- title: TEXT
- brand: VARCHAR(100)
- price_jpy: INTEGER
- price_usd: REAL
- zenmarket_url: TEXT
- yahoo_url: TEXT
- image_url: TEXT
- deal_quality: REAL DEFAULT 0.5
- priority_score: REAL DEFAULT 0.0
- created_at: TIMESTAMP
```

#### `notification_logs` (New)
```sql
- user_id: BIGINT
- auction_id: VARCHAR(100)
- notification_type: VARCHAR(20)
- sent_at: TIMESTAMP
```

## 🚀 Setup Instructions

### 1. Prerequisites

- Discord bot with existing webhook system
- Database (PostgreSQL or SQLite)
- Python 3.8+ with required dependencies

### 2. Installation

1. **Copy the new files** to your bot directory:
   - `notification_tiers.py`
   - `daily_scheduler.py`
   - `test_tier_system.py`

2. **Update your main bot file** (`secure_discordbot.py`):
   - Import statements added
   - Commands added
   - Webhook integration updated

3. **Database schema** will be automatically updated when the bot starts

### 3. Configuration

1. **Create #daily-digest channel** in your Discord server

2. **Update admin user ID** in the Discord commands:
   ```python
   # Replace this with your Discord user ID
   if ctx.author.id != 123456789012345678:
   ```

3. **Test the system**:
   ```bash
   python test_tier_system.py
   ```

### 4. Initialization

Run the setup command in Discord:
```
!setup_notification_tiers
```

## 📋 Discord Commands

### Admin Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `!setup_notification_tiers` | Initialize the tier system | Admin only |
| `!upgrade_tier @user tier` | Upgrade user's tier | `!upgrade_tier @user standard` |
| `!send_digest_now` | Manually trigger daily digest | Admin only |
| `!tier_stats` | Show tier distribution stats | Admin only |

### User Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `!my_notifications` | Show current tier and usage | Available to all users |

## 🔄 How It Works

### Real-Time Notifications

1. **Webhook receives listing** from scrapers
2. **System queues listing** for daily digest (all users)
3. **System checks user tiers** for real-time notifications
4. **Sends DMs** to eligible users (within daily limits)
5. **Logs notifications** for analytics

### Daily Digest

1. **Scheduler triggers** at 9 AM UTC daily
2. **System retrieves** top 20 listings from past 24 hours
3. **Posts to #daily-digest** channel with beautiful embeds
4. **Adds reactions** (👍/👎) for user feedback
5. **Clears processed** listings from queue

### Daily Counter Reset

1. **Scheduler triggers** at midnight UTC daily
2. **System resets** daily notification counts for all users
3. **Logs reset** activity for monitoring

## 🎨 Features

### Privacy-Focused Design
- No email or phone collection required
- Uses existing Discord infrastructure
- Minimal data collection (user_id, tier, daily_count, last_reset)

### Beautiful Embeds
- Rich listing information with images
- Color-coded quality indicators
- Upgrade prompts for standard tier users
- Professional formatting

### Smart Rate Limiting
- Daily limits with automatic reset
- Concurrent notification delivery
- Error handling and logging
- Graceful degradation

### Admin Analytics
- Tier distribution statistics
- Notification delivery tracking
- User upgrade management
- Manual digest triggers

## 🔧 Customization

### Tier Limits
Modify in `notification_tiers.py`:
```python
TIER_LIMITS = {
    'free': 0,      # No real-time notifications
    'standard': 50, # 50 DMs per day
    'instant': -1   # Unlimited (-1 means no limit)
}
```

### Schedule Times
Modify in `daily_scheduler.py`:
```python
# Daily digest at 9 AM UTC
schedule.every().day.at("09:00").do(self._run_daily_digest)

# Counter reset at midnight UTC
schedule.every().day.at("00:00").do(self._reset_daily_counters)
```

### Digest Channel
The system automatically looks for a channel named `daily-digest`. You can customize this in the bot initialization.

## 🐛 Troubleshooting

### Common Issues

1. **Daily digest not sending**
   - Check if #daily-digest channel exists
   - Verify scheduler is running
   - Check bot permissions in the channel

2. **Real-time notifications not working**
   - Verify user tier is set correctly
   - Check daily count limits
   - Ensure user has DMs enabled

3. **Database errors**
   - Run the test script to verify database setup
   - Check database permissions
   - Verify table creation

### Debug Commands

```bash
# Test the tier system
python test_tier_system.py

# Check tier stats in Discord
!tier_stats

# Check user's notification status
!my_notifications
```

## 📊 Monitoring

### Key Metrics to Monitor

- Daily digest delivery success rate
- Real-time notification delivery rate
- User tier distribution
- Daily counter reset success
- Database query performance

### Logs to Watch

- `notification_tiers.py` - Tier management logs
- `daily_scheduler.py` - Scheduler activity
- `secure_discordbot.py` - Webhook and command logs

## 🔒 Security Considerations

- Admin commands are protected by user ID checks
- Database queries use parameterized statements
- Input validation and sanitization
- Rate limiting to prevent abuse
- Error handling to prevent information leakage

## 🚀 Future Enhancements

Potential improvements for future versions:

1. **Payment integration** for automatic tier upgrades
2. **Advanced analytics** dashboard
3. **Custom notification preferences** per user
4. **A/B testing** for digest formats
5. **Mobile app** notifications
6. **Webhook API** for external integrations

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Run the test script
3. Review the logs
4. Check Discord bot permissions
5. Verify database connectivity

---

**Note**: Remember to update the admin user ID in the commands before deploying to production!
