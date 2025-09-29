# 🚀 Railway Migration Quick Reference

## ⚡ Quick Steps

### 1. Switch Railway Repository
- Go to Railway Dashboard → Your Project → Settings → Source
- Change from `lukeswagga/discord-auction-bot` to `lukeswagga/yahoo-japan-scraper`
- Click Save

### 2. Update Environment Variables
Set these in Railway Variables tab:
```
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_server_id_here
DISCORD_BOT_URL=https://your-new-railway-url.up.railway.app
```

### 3. Test the Migration
```bash
# Run the test script
python test_webhook_migration.py

# Or test manually
curl https://your-new-railway-url.up.railway.app/health
```

## 🔗 Key URLs

- **Current Railway URL**: `https://motivated-stillness-production.up.railway.app`
- **New Railway URL**: `https://your-new-railway-url.up.railway.app` (update after switch)

## 📁 Essential Files

- `secure_discordbot.py` - Main Railway deployment file
- `core_scraper_base.py` - Enhanced base scraper (updated with environment variable)
- All scraper files: `ending_soon_scraper.py`, `budget_steals_scraper.py`, etc.
- `Procfile` - Railway deployment configuration

## 🧪 Webhook Endpoints

- `POST /webhook/listing` - Main auction listing webhook
- `POST /webhook/listing_with_delay` - Delayed webhook
- `POST /webhook/stats` - Statistics webhook
- `POST /webhook/process_buffer` - Buffer processing webhook

## ✅ Success Indicators

- Railway health check returns 200 OK
- Webhook endpoints accept POST requests
- Discord bot receives and posts listings
- Enhanced filtering blocks LEGO, BMW, etc.
- Listings appear in correct Discord channels

## 🚨 If Something Goes Wrong

1. Check Railway logs for errors
2. Verify environment variables are set
3. Test webhook endpoints manually
4. Ensure `secure_discordbot.py` is deployed (not `yahoo_sniper.py`)
5. Check Discord bot permissions and server ID

## 📞 Test Commands

```bash
# Test Railway health
curl https://your-new-railway-url.up.railway.app/health

# Test webhook
curl -X POST https://your-new-railway-url.up.railway.app/webhook/listing \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook", "scraper_source": "test"}'

# Test local scraper
python ending_soon_scraper.py
```
