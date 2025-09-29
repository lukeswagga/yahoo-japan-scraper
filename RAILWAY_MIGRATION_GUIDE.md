# Railway Migration Guide: Switch to yahoo-japan-scraper Repository

## 🎯 Overview
This guide will help you switch your Railway deployment from the `discord-auction-bot` repository to the `yahoo-japan-scraper` repository to use your enhanced scraper system.

## 📋 Current Status
- ✅ Local Discord Bot: Working (connected as "Grail Hunter#8800" to "Drip Trenches")
- ✅ Enhanced Filtering: All spam filtering implemented and working
- ✅ Scrapers: Enhanced with new filtering, ready to send listings
- ❌ Railway Deployment: Still pointing to old discord-auction-bot repo
- ❌ Webhook Flow: Scrapers sending to Railway, but Railway doesn't have new webhook endpoints

## 🚀 Step-by-Step Migration Process

### Step 1: Prepare the yahoo-japan-scraper Repository

1. **Push all enhanced files to yahoo-japan-scraper repo:**
   ```bash
   # Navigate to your yahoo-japan-scraper repository
   cd /path/to/yahoo-japan-scraper
   
   # Copy all enhanced files from newfiles directory
   cp /Users/lukevogrin/Discord-Auction-Bot/newfiles/*.py .
   cp /Users/lukevogrin/Discord-Auction-Bot/newfiles/brands.json .
   cp /Users/lukevogrin/Discord-Auction-Bot/newfiles/requirements.txt .
   cp /Users/lukevogrin/Discord-Auction-Bot/newfiles/Procfile .
   
   # Commit and push
   git add .
   git commit -m "Add enhanced Yahoo Japan scraper system with improved filtering"
   git push origin main
   ```

### Step 2: Update Railway Deployment

1. **Go to Railway Dashboard:**
   - Visit https://railway.app/dashboard
   - Find your current deployment (likely named "discord-auction-bot" or similar)

2. **Change Repository Source:**
   - Click on your project
   - Go to Settings → Source
   - Change from `lukeswagga/discord-auction-bot` to `lukeswagga/yahoo-japan-scraper`
   - Click "Save"

3. **Update Environment Variables:**
   - Go to Variables tab
   - Set the following variables:
     ```
     DISCORD_BOT_TOKEN=your_discord_bot_token_here
     GUILD_ID=your_discord_server_id_here
     DISCORD_BOT_URL=https://your-new-railway-url.up.railway.app
     ```

4. **Update Build Settings:**
   - Ensure the build command is: `python secure_discordbot.py`
   - The Procfile should contain: `web: python secure_discordbot.py`

### Step 3: Update Scraper Configuration

1. **Update Discord Bot URL in scrapers:**
   - The `core_scraper_base.py` now uses environment variable `DISCORD_BOT_URL`
   - Set this in your local environment or Railway deployment
   - For local testing, create a `.env` file:
     ```
     DISCORD_BOT_URL=https://your-new-railway-url.up.railway.app
     ```

2. **Test the webhook endpoints:**
   - Your Railway deployment should have these endpoints:
     - `POST /webhook/listing` - Main webhook for auction listings
     - `POST /webhook/listing_with_delay` - Delayed webhook
     - `POST /webhook/stats` - Statistics webhook
     - `POST /webhook/process_buffer` - Buffer processing webhook

### Step 4: Verify the Migration

1. **Check Railway Deployment:**
   - Visit your new Railway URL
   - Should show: `{"service": "Yahoo Japan Scraper", "status": "running"}`

2. **Test Webhook Endpoints:**
   ```bash
   # Test the main webhook
   curl -X POST https://your-new-railway-url.up.railway.app/webhook/listing \
     -H "Content-Type: application/json" \
     -d '{"test": "webhook", "scraper_source": "test"}'
   ```

3. **Run Local Scraper Test:**
   ```bash
   # Test one of your enhanced scrapers
   python ending_soon_scraper.py
   ```

4. **Verify Discord Integration:**
   - Check if listings appear in your "Drip Trenches" Discord server
   - Verify they're going to the correct channels

## 🔧 Key Files for Migration

### Essential Files to Copy:
- `core_scraper_base.py` - Enhanced base scraper with filtering
- `ending_soon_scraper.py` - Enhanced ending soon scraper
- `budget_steals_scraper.py` - Enhanced budget steals scraper
- `new_listings_scraper.py` - Enhanced new listings scraper
- `buy_it_now_scraper.py` - Enhanced buy-it-now scraper
- `secure_discordbot.py` - Flask server with webhook endpoints
- `discord_bot_standalone.py` - Local Discord bot launcher
- `brands.json` - Brand data for filtering
- `requirements.txt` - Python dependencies
- `Procfile` - Railway deployment configuration

### Configuration Files:
- `notification_tiers.py` - Notification tier system
- `database_manager.py` - Database management
- `enhancedfiltering.py` - Enhanced filtering logic

## 🚨 Troubleshooting

### Common Issues:

1. **Webhook Not Receiving Data:**
   - Check Railway logs for errors
   - Verify DISCORD_BOT_URL is set correctly
   - Test webhook endpoint manually

2. **Discord Bot Not Responding:**
   - Verify DISCORD_BOT_TOKEN is set in Railway
   - Check GUILD_ID is correct
   - Ensure bot has proper permissions

3. **Scrapers Not Sending Data:**
   - Check local environment variables
   - Verify Railway URL is accessible
   - Test with a simple curl request

### Debug Commands:

```bash
# Check Railway deployment status
curl https://your-new-railway-url.up.railway.app/health

# Test webhook endpoint
curl -X POST https://your-new-railway-url.up.railway.app/webhook/listing \
  -H "Content-Type: application/json" \
  -d '{"auction_id": "test123", "title": "Test Item", "price_usd": 50.0, "scraper_source": "test"}'

# Check local scraper configuration
python -c "from core_scraper_base import YahooScraperBase; s = YahooScraperBase('test'); print(f'Discord URL: {s.discord_bot_url}')"
```

## ✅ Success Criteria

After migration, you should have:
- ✅ Railway deployment running from yahoo-japan-scraper repository
- ✅ All webhook endpoints responding correctly
- ✅ Local scrapers sending data to Railway
- ✅ Discord bot receiving and posting listings
- ✅ Enhanced filtering working (no LEGO, BMW, etc.)
- ✅ Proper channel routing in Discord

## 📞 Next Steps

1. Complete the Railway repository switch
2. Update environment variables
3. Test the complete flow
4. Monitor for any issues
5. Update any documentation or scripts that reference the old URL

---

**Note:** Keep your old Railway deployment running until you've verified the new one is working correctly. You can then delete the old deployment to avoid confusion.
