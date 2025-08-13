# Environment Variables Setup Guide

## Discord Bot Service (Railway)

The Discord Bot service runs on Railway and exposes webhook endpoints for the Yahoo Sniper.

### Required Environment Variables:
```bash
DISCORD_BOT_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
PORT=8000
```

### Exposed Endpoints:
- **`/health`** - Main health check
- **`/webhook/listing`** - Receive auction listings from Yahoo Sniper
- **`/webhook/health`** - Webhook-specific health check
- **`/webhook/stats`** - Receive scraper statistics

## Yahoo Sniper Service

The Yahoo Sniper service connects to the Discord Bot via webhooks.

### Required Environment Variables:
```bash
# Discord Bot Connection
DISCORD_BOT_URL=https://motivated-stillness-production.up.railway.app
USE_DISCORD_BOT=true
PORT=8001

# Optional: Override defaults
DISCORD_BOT_URL=https://your-railway-url.up.railway.app
USE_DISCORD_BOT=false  # Set to false to disable Discord integration
```

### Webhook Endpoints Used:
- **`{DISCORD_BOT_URL}/webhook/listing`** - Send auction listings
- **`{DISCORD_BOT_URL}/webhook/stats`** - Send scraper statistics
- **`{DISCORD_BOT_URL}/health`** - Check bot health
- **`{DISCORD_BOT_URL}/webhook/health`** - Check webhook health

## Service Communication Flow

```
Yahoo Sniper (Port 8001) → Discord Bot (Port 8000 on Railway)
     ↓                              ↓
Discovers auctions              Receives webhooks
     ↓                              ↓
Sends to /webhook/listing      Posts to Discord channels
     ↓                              ↓
Logs statistics                 Updates database
```

## Testing the Connection

### 1. Check Discord Bot Health:
```bash
curl https://motivated-stillness-production.up.railway.app/health
```

### 2. Check Webhook Health:
```bash
curl https://motivated-stillness-production.up.railway.app/webhook/health
```

### 3. Test Webhook Endpoint:
```bash
curl -X POST https://motivated-stillness-production.up.railway.app/webhook/listing \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

## Troubleshooting

### Common Issues:

1. **Connection Refused**: Check if Discord Bot service is running on Railway
2. **404 Errors**: Verify endpoint URLs are correct
3. **Timeout Errors**: Check network connectivity and Railway service status
4. **Authentication Errors**: Verify Discord Bot token and permissions

### Debug Steps:

1. Check Railway service logs for Discord Bot
2. Verify environment variables are set correctly
3. Test webhook endpoints manually
4. Check Discord Bot health status
5. Verify guild ID and channel permissions

## Security Notes

- Keep `DISCORD_BOT_TOKEN` secure and never commit to version control
- Use HTTPS URLs for production webhook communication
- Consider implementing webhook authentication if needed
- Monitor webhook usage and implement rate limiting if necessary
