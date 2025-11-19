# Yahoo Japan Seller Monitor Scraper

## Overview

Monitors specific Yahoo Japan auction seller accounts for new designer/archive clothing listings. Tracks 29 proven sellers who consistently list valuable items from brands like Yohji Yamamoto, Raf Simons, Rick Owens, Margiela, and more.

## Features

- ✅ **Seller-specific monitoring** - Track 29 proven archive/designer sellers
- ✅ **NEW listing detection** - Only alerts on listings not seen before
- ✅ **Priority keyword filtering** - Highlights Yohji, Raf, Rick, Margiela, CDG, Undercover, etc.
- ✅ **4-tier alert system** - 🔥 STEAL / ⭐ PRIORITY / ✨ GOOD DEAL / 💎 PREMIUM
- ✅ **Pagination support** - Checks up to 3 pages per seller (300 items)
- ✅ **Rate limiting** - Smart delays to avoid detection
- ✅ **Discord integration** - Posts to `👤-seller-alerts` channel via existing webhook

## Architecture

```
┌─────────────────────────────────────┐
│  seller_monitor_scraper.py          │
│  (Railway Deployment)               │
└─────────────┬───────────────────────┘
              │
              │ Every 15 minutes:
              │ - Check all 29 sellers
              │ - Detect NEW listings
              │ - Filter by priority keywords
              │ - Calculate alert level
              │
              ↓
┌─────────────────────────────────────┐
│  POST /webhook/listing              │
│  secure_discordbot.py               │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│  Discord Channel                    │
│  👤-seller-alerts                   │
└─────────────────────────────────────┘
```

## Railway Deployment

### Step 1: Create New Railway Service

1. Go to your Railway project
2. Click **"New"** → **"GitHub Repo"**
3. Select your `yahoo-japan-scraper` repository
4. Choose branch: `claude/yahoo-seller-monitor-scraper-01KAAmFW83fasdudVY1c3SSJ`

### Step 2: Configure Service

**Service Name:** `seller-monitor-scraper`

**Start Command:**
```bash
python seller_monitor_scraper.py
```

**OR** add to your project root as a worker process (if you want single repo, multiple services):
```bash
# In Railway settings → Deploy → Start Command
python seller_monitor_scraper.py
```

### Step 3: Set Environment Variables

Copy these from your existing Discord bot service:

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_BOT_URL` | Your Discord bot webhook URL | `https://your-bot.up.railway.app` |
| `PORT` | Health check port (optional) | `8000` |

**Required variables already in your other scrapers:**
- `DISCORD_BOT_URL` - The seller monitor sends listings to your Discord bot via webhook

### Step 4: Deploy

1. Railway will auto-deploy from the branch
2. Check logs for: `🚀 seller_monitor_scraper initialized`
3. First run will check all sellers and mark existing listings as "seen"
4. Subsequent runs (every 15 min) will only alert on NEW listings

## Configuration

### Managing Sellers (`sellers.json`)

```json
{
  "sellers": [
    {
      "seller_id": "7sTcUa1QqrNPSJ6RHRpzcvewQBkkS",
      "enabled": true,
      "priority_level": "normal"
    }
  ]
}
```

**Add a seller:**
```json
{
  "seller_id": "NEW_SELLER_ID_HERE",
  "enabled": true,
  "priority_level": "normal"
}
```

**Disable a seller temporarily:**
```json
{
  "seller_id": "7sTcUa1QqrNPSJ6RHRpzcvewQBkkS",
  "enabled": false,  // ← Set to false
  "priority_level": "normal"
}
```

### Adjusting Settings (`sellers.json`)

```json
"settings": {
  "check_interval_minutes": 15,        // How often to check all sellers
  "max_pages_per_seller": 3,           // Pages to scrape per seller (100 items/page)
  "priority_keywords": [
    "Yohji Yamamoto",
    "Raf Simons",
    // Add more...
  ],
  "price_alert_thresholds": {
    "steal_price_usd": 50,             // 🔥 STEAL alert
    "good_deal_usd": 150,              // ⭐ PRIORITY alert
    "premium_find_usd": 500            // 💎 PREMIUM alert
  },
  "rate_limiting": {
    "delay_between_sellers_seconds": 3,
    "delay_between_pages_seconds": 2
  }
}
```

## Alert Levels Explained

| Alert | Trigger | Example |
|-------|---------|---------|
| 🔥 **STEAL** | Priority keyword + price ≤ $50 | Yohji coat for $45 |
| ⭐ **PRIORITY** | Priority keyword + price ≤ $150 | Raf Simons shirt for $120 |
| ✨ **GOOD DEAL** | Any item ≤ $50 | Generic designer item under $50 |
| 💎 **PREMIUM** | Priority keyword + price ≥ $500 | Rare Margiela jacket for $800 |

## Data Storage

### `seen_seller_listings.json`
Tracks which auction IDs have been seen per seller:

```json
{
  "7sTcUa1QqrNPSJ6RHRpzcvewQBkkS": [
    "u1234567890",
    "u1234567891"
  ]
}
```

- **Auto-managed** - No manual editing needed
- **Auto-cleanup** - Keeps last 500 items per seller
- **Persists between deployments** - Stored in Railway volume (or configure persistent storage)

### `seen_seller_monitor_scraper.json`
Global seen items inherited from base scraper class.

## Testing

### Local Testing

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables:**
```bash
export DISCORD_BOT_URL="https://your-bot.up.railway.app"
```

3. **Run a single cycle (testing mode):**
```bash
python seller_monitor_scraper.py
```

4. **Expected output:**
```
🚀 seller_monitor_scraper initialized
👥 Monitoring 29 sellers
⭐ 20 priority keywords loaded
================================================================================
🔄 Starting seller monitor cycle at 2025-11-19 10:30:00
================================================================================

👤 Checking seller: 7sTcUa1QqrNPSJ6RHRpzcvewQBkkS
  📄 Page 1: https://auctions.yahoo.co.jp/seller/...
  📦 Found 100 items on page 1
  ✅⭐ PRIORITY NEW: Yohji Yamamoto Wool Coat [Yohji Yamamoto]
  📊 3 new listings from 7sTcUa1QqrNPSJ6RHRpzcvewQBkkS

... (continues for all sellers)

================================================================================
✅ Cycle complete: 487 listings checked, 12 new listings sent
================================================================================
```

### Test Script

Run the included test script to verify configuration:

```bash
python test_seller_monitor.py
```

## Monitoring & Maintenance

### Railway Logs

**Check for successful cycles:**
```
✅ Cycle complete: 487 listings checked, 12 new listings sent
```

**Check for errors:**
```
❌ Error checking seller XYZ: ...
```

### Health Check

The scraper runs a Flask health server on port 8000:

```bash
curl https://your-seller-monitor.railway.app/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "seller_monitor_scraper"
}
```

### Performance Metrics

| Metric | Expected Value |
|--------|----------------|
| Cycle duration | 5-10 minutes for 29 sellers |
| Listings checked per cycle | ~400-800 (depends on seller activity) |
| New listings per cycle | 10-30 (varies by time of day) |
| Memory usage | ~100-150 MB |

## Troubleshooting

### No listings being sent to Discord

**Check 1:** Verify `DISCORD_BOT_URL` is set correctly
```bash
echo $DISCORD_BOT_URL
```

**Check 2:** Check `sellers.json` has `enabled: true`

**Check 3:** On first run, all listings are marked "seen". New listings only appear on subsequent runs.

**Check 4:** Verify Discord channel `👤-seller-alerts` exists and bot has permissions

### "seen_seller_listings.json" growing too large

- Auto-cleanup keeps last 500 items per seller
- Manual cleanup: Delete file to reset all tracking (will re-alert on all listings)

### Seller not being checked

**Check:** Seller enabled in `sellers.json`?
```json
"enabled": true
```

**Check:** Valid seller ID? Test URL manually:
```
https://auctions.yahoo.co.jp/seller/{SELLER_ID}
```

### Rate limiting / 429 errors

- Increase delays in `sellers.json`:
```json
"rate_limiting": {
  "delay_between_sellers_seconds": 5,
  "delay_between_pages_seconds": 3
}
```

## Integration with Existing System

### Discord Bot Integration

The seller monitor uses your existing webhook system:

**Channel routing** (`channel_router.py`):
```python
'seller_monitor_scraper': '👤-seller-alerts'
```

**Discord embed styling** (`secure_discordbot.py`):
```python
'seller_monitor_scraper': {
  'color': 0x9b59b6,  # Purple
  'emoji': '👤',
  'name': 'Seller Alert'
}
```

### Tier System Compatibility

Seller alerts are treated like other scraper sources:
- **Free tier**: Included in daily digest
- **Standard tier**: Real-time if brand preference matches
- **Instant tier**: Real-time for all

## Customization

### Add More Priority Keywords

Edit `sellers.json`:
```json
"priority_keywords": [
  "Yohji Yamamoto",
  "Raf Simons",
  "Archive",
  "YOUR_NEW_KEYWORD"
]
```

### Change Check Interval

```json
"check_interval_minutes": 30  // Check every 30 minutes instead of 15
```

### Check More Pages Per Seller

```json
"max_pages_per_seller": 5  // Check 5 pages (500 items) instead of 3
```

**Warning:** More pages = longer cycle time and more likely to hit rate limits

### Adjust Price Thresholds

```json
"price_alert_thresholds": {
  "steal_price_usd": 30,      // More aggressive steal alerts
  "good_deal_usd": 100,
  "premium_find_usd": 1000
}
```

## FAQ

**Q: Will I get alerts for listings that were posted before I started the monitor?**
A: No. On first run, all current listings are marked as "seen". Only NEW listings posted after that will trigger alerts.

**Q: Can I add sellers without redeploying?**
A: Currently no - you need to update `sellers.json` and redeploy. Future enhancement: database-backed seller management.

**Q: How do I find seller IDs?**
A: Visit a seller's page on Yahoo Japan Auctions. The URL is: `https://auctions.yahoo.co.jp/seller/{SELLER_ID}`

**Q: What happens if Railway restarts the service?**
A: `seen_seller_listings.json` persists if you configure Railway volumes. Otherwise, it will reset and mark all listings as "seen" again on restart.

**Q: Can I run this locally?**
A: Yes! Just set `DISCORD_BOT_URL` env var and run `python seller_monitor_scraper.py`

## Future Enhancements

- [ ] Database-backed seller management (add/remove via Discord commands)
- [ ] Per-user seller subscriptions (follow specific sellers)
- [ ] Seller statistics dashboard (most active, best finds, etc.)
- [ ] Webhook notifications when seller posts new listing (instant alerts)
- [ ] Historical tracking (see all items a seller has listed)
- [ ] Seller reliability scoring (how often they list desirable items)

## Support

For issues or questions:
1. Check Railway logs for error messages
2. Verify environment variables are set
3. Test with `python seller_monitor_scraper.py` locally
4. Check Discord bot is running and `👤-seller-alerts` channel exists

---

**Built with:** Python 3.11+, BeautifulSoup4, Requests, Schedule
**Deployment:** Railway
**Integration:** Discord Webhooks + Existing Bot System
