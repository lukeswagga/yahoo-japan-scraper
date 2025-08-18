# Discord Bot Deployment Instructions

## Option 1: Deploy as Separate Railway Service

1. **Create a new Railway project for the Discord bot:**
   ```bash
   # In Railway dashboard, create new project
   # Name: "discord-auction-bot-discord"
   ```

2. **Set environment variables in Railway:**
   ```bash
   DISCORD_BOT_TOKEN=your_discord_bot_token
   GUILD_ID=your_guild_id
   PORT=8000
   ```

3. **Deploy using the Discord Dockerfile:**
   - Use `Dockerfile.discord` as the build file
   - Railway will automatically detect and use it

4. **Get the Discord bot URL:**
   - Railway will provide a URL like: `https://discord-auction-bot-discord-production.up.railway.app`

5. **Update scraper with Discord bot URL:**
   ```bash
   # Set environment variable in scraper Railway project
   DISCORD_BOT_URL=https://discord-auction-bot-discord-production.up.railway.app
   ```

## Option 2: Deploy Both Services on Same Railway

1. **Create a multi-service setup:**
   - Use Docker Compose or Railway's multi-service feature
   - Run both scraper and Discord bot on same project

2. **Update the main Dockerfile to run both:**
   ```dockerfile
   # Add to main Dockerfile
   COPY secure_discordbot.py .
   COPY database_manager.py .
   
   # Run both services
   CMD ["sh", "-c", "python secure_discordbot.py & python yahoo_sniper.py"]
   ```

## Option 3: Quick Test - Local Discord Bot

1. **Run Discord bot locally:**
   ```bash
   export DISCORD_BOT_TOKEN=your_token
   export GUILD_ID=your_guild_id
   python secure_discordbot.py
   ```

2. **Update scraper to use localhost:**
   ```bash
   export DISCORD_BOT_URL=http://localhost:8000
   ```

## Testing the Setup

1. **Check Discord bot health:**
   ```bash
   curl https://your-discord-bot-url.up.railway.app/health
   ```

2. **Check webhook health:**
   ```bash
   curl https://your-discord-bot-url.up.railway.app/webhook/health
   ```

3. **Test webhook endpoint:**
   ```bash
   curl -X POST https://your-discord-bot-url.up.railway.app/webhook/listing \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

## Current Status

- ✅ Scraper is running and finding listings
- ✅ Listings are being saved locally
- ❌ Discord bot service not deployed
- ❌ Listings not being sent to Discord

## Next Steps

1. Deploy Discord bot service
2. Get Discord bot URL
3. Update scraper with correct Discord bot URL
4. Re-enable Discord integration
5. Test end-to-end functionality
