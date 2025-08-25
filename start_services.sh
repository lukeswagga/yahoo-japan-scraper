#!/bin/bash

echo "🚀 Starting Discord Auction Bot Services..."

# Check if Discord bot environment variables are set
if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "⚠️ DISCORD_BOT_TOKEN not set - Discord bot will not function properly"
    echo "🔄 Starting scraper only..."
    python yahoo_sniper.py
else
    echo "✅ Discord bot environment variables found"
    echo "🔄 Starting Discord bot in background..."
    python secure_discordbot.py &
    DISCORD_PID=$!
    
    echo "⏳ Waiting for Discord bot to initialize..."
    sleep 15
    
    echo "🔄 Starting scraper..."
    python yahoo_sniper.py
    
    # If scraper exits, kill Discord bot
    echo "🛑 Stopping Discord bot..."
    kill $DISCORD_PID
fi
