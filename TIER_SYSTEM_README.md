# 3-Tier Channel-Based Notification System

This document describes the implementation of a 3-tier channel-based notification system for the Discord auction bot that receives Yahoo Japan auction listings via webhooks.

## System Architecture

### Tier Structure

#### Tier 1: Free (Role: @Free)
- **Channel Access**: `#daily-digest` only
- **Features**: 
  - Read-only access to daily digest
  - Top 20 listings from past 24h posted at 9 AM UTC
  - No other channels visible

#### Tier 2: Standard (Role: @Standard - $12/month)
- **Channel Access**: 
  - `#daily-digest` (same as free tier)
  - `#standard-feed` (up to 100 listings per day based on brand preferences)
- **Features**:
  - User can select preferred brands via `!setbrands` command
  - Counter tracks listings sent to #standard-feed (resets at midnight UTC)
  - When 100 limit reached, no more posts until reset
  - Listings filtered by user's brand preferences + priority scored

#### Tier 3: Instant (Role: @Instant - $25/month)
- **Channel Access**: All channels
  - `#auction-alerts` - All auction listings
  - `#ending-soon` - Auctions ending within 6 hours
  - `#budget-steals` - Items ≤$60
  - `#new-listings` - Newest auction listings
  - `#buy-it-now` - Fixed price listings
  - Brand-specific channels (18 channels)
- **Features**:
  - Unlimited listings
  - Real-time posting to all relevant channels
  - Each listing posted to appropriate channels based on scraper_source and brand

## File Structure

```
/project
├── secure_discordbot.py (MODIFIED)
├── tier_manager.py (NEW)
├── priority_calculator.py (NEW)
├── channel_router.py (NEW)
├── digest_manager.py (NEW)
├── setup_channels.py (NEW)
├── user_tiers.db (CREATED AT RUNTIME)
└── brands.json (EXISTING)
```

## Core Components

### 1. TierManager (`tier_manager.py`)
Handles user tiers, brand preferences, and daily counters.

**Key Methods:**
- `get_user_tier(discord_id)` - Get user's tier
- `set_user_tier(discord_id, tier)` - Set user's tier
- `get_preferred_brands(discord_id)` - Get user's brand preferences
- `set_preferred_brands(discord_id, brands)` - Set brand preferences
- `can_send_to_standard(discord_id)` - Check if user can receive more listings
- `increment_standard_count(discord_id)` - Increment daily counter
- `reset_daily_counters()` - Reset all counters at midnight UTC

### 2. PriorityCalculator (`priority_calculator.py`)
Calculates priority scores for listings based on multiple factors.

**Scoring Breakdown:**
- Price tier: <$50 (0.4), $50-100 (0.3), $100-200 (0.2), >$200 (0.1)
- Brand tier: tier 1 (0.3), tier 2 (0.25), tier 3 (0.2), tier 4 (0.15), tier 5 (0.1)
- Scraper source: ending_soon (0.2), budget_steals (0.15), new_listings (0.1), buy_it_now (0.05)
- Deal quality: existing deal_quality score (0-0.15)

### 3. ChannelRouter (`channel_router.py`)
Routes listings to appropriate channels based on tier access.

**Key Methods:**
- `route_listing(listing_data)` - Main routing method
- `_route_to_standard_feed(listing_data)` - Route to standard tier
- `_route_to_instant_channels(listing_data)` - Route to instant tier
- `_create_listing_embed(listing_data)` - Create Discord embed

### 4. DigestManager (`digest_manager.py`)
Handles daily digest generation and posting.

**Key Methods:**
- `generate_daily_digest()` - Generate and post daily digest
- `get_digest_stats()` - Get digest statistics
- `_create_digest_embed(listings)` - Create digest embed

## Database Schema

### users table
```sql
CREATE TABLE users (
    discord_id TEXT PRIMARY KEY,
    tier TEXT NOT NULL CHECK(tier IN ('free', 'standard', 'instant')),
    preferred_brands TEXT,  -- JSON array for standard tier
    standard_count_today INTEGER DEFAULT 0,
    last_reset_date TEXT,  -- ISO date for counter reset
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### listing_queue table
```sql
CREATE TABLE listing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id TEXT UNIQUE,
    listing_data TEXT,  -- JSON serialized
    priority_score REAL,
    brand TEXT,
    scraper_source TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT 0
);
```

### user_reactions table
```sql
CREATE TABLE user_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT,
    auction_id TEXT,
    reaction_type TEXT CHECK(reaction_type IN ('thumbs_up', 'thumbs_down')),
    reacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(discord_id, auction_id)
);
```

## Discord Channel Structure

### Channel Categories

#### 📊 DIGEST
- `#daily-digest` (visible to @Free, @Standard, @Instant)

#### 📦 STANDARD FEED
- `#standard-feed` (visible to @Standard, @Instant)

#### 🎯 INSTANT ALERTS
- `#auction-alerts` (visible to @Instant only)
- `#ending-soon` (visible to @Instant only)
- `#budget-steals` (visible to @Instant only)
- `#new-listings` (visible to @Instant only)
- `#buy-it-now` (visible to @Instant only)

#### 🏷️ BRAND CHANNELS
- `#raf-simons` (visible to @Instant only)
- `#rick-owens` (visible to @Instant only)
- `#maison-margiela` (visible to @Instant only)
- ... (one channel per brand, 22 total)

## Bot Commands

### User Commands
- `!tier` - Show your current tier and stats
- `!setbrands raf simons, rick owens, margiela` - Set preferred brands (Standard tier only)
- `!stats` - Show your notification stats

### Admin Commands
- `!settier @user free|standard|instant` - Set user tier
- `!digest_stats` - Show digest statistics
- `!channel_stats` - Show channel routing statistics

## Setup Instructions

### 1. Initial Setup
1. Run `python setup_channels.py` to create only new required channels and roles
   - Creates roles: Free, Standard, Instant
   - Creates only `#standard-feed` channel (skips existing channels)
   - Updates permissions for existing channels
2. The script intelligently skips channels that already exist
3. All existing brand channels and alert channels will have their permissions updated

### 2. Database Setup
The database will be created automatically on first run. No manual setup required.

### 3. Bot Deployment
1. Ensure all new files are deployed
2. Set `DISCORD_BOT_TOKEN` environment variable
3. The tier system will initialize automatically on bot startup

## Background Tasks

### Daily Counter Reset
- Runs every minute, resets counters at midnight UTC
- Resets `standard_count_today` to 0 for all standard tier users

### Daily Digest
- Runs every minute, posts digest at 9 AM UTC
- Generates top 20 listings from past 24 hours
- Posts to `#daily-digest` channel

## Webhook Integration

The webhook endpoint `/webhook/listing` has been modified to:
1. Calculate priority score using PriorityCalculator
2. Route listing through ChannelRouter
3. Post to appropriate channels based on tier access
4. Fall back to old system if tier system not ready

## Testing Checklist

- [ ] All roles created (Free, Standard, Instant)
- [ ] All channels created with correct permissions
- [ ] Free tier sees only #daily-digest
- [ ] Standard tier sees #daily-digest and #standard-feed
- [ ] Standard tier can set brand preferences
- [ ] Standard tier respects 100/day limit per user
- [ ] Instant tier sees all channels
- [ ] Listings route to correct channels based on scraper_source and brand
- [ ] Daily digest posts at 9 AM UTC with top 20
- [ ] Counters reset at midnight UTC
- [ ] Admin settier command works
- [ ] User commands work (tier, setbrands, stats)

## Deployment Notes

- Run `setup_channels.py` once after deployment to create channels
- Set environment variable `DISCORD_BOT_TOKEN`
- Database will be created automatically on first run
- Use UTC timezone for all operations
- Listings appear in standard-feed only once (not duplicated per user)
- Standard tier counter increments for ALL matching users when listing posted

## Error Handling

All components include comprehensive error handling:
- Database connection failures
- Missing channels/roles
- Invalid user input
- Network timeouts
- Graceful fallbacks to old system

## Performance Considerations

- Database indexes on frequently queried columns
- Async/await for all database operations
- Rate limiting for Discord API calls
- Efficient priority scoring algorithm
- Background task optimization

## Security

- Input validation and sanitization
- SQL injection prevention
- Role-based access control
- Secure database operations
- Error message sanitization
