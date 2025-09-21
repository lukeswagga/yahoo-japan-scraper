#!/usr/bin/env python3
"""
Standalone Discord bot launcher
Run this separately from the main Flask server to avoid asyncio conflicts
"""

import os
import sys
import time
import asyncio
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID_STR = os.getenv('GUILD_ID', '0')
GUILD_ID = int(GUILD_ID_STR) if GUILD_ID_STR.isdigit() else 0

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Discord bot connected as {bot.user}!')
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f'🎯 Connected to server: {guild.name}')
    else:
        print(f'❌ Could not find guild with ID {GUILD_ID}')

async def main():
    """Run the Discord bot standalone"""
    try:
        print("🤖 Starting standalone Discord bot...")
        print(f"🎯 Target server ID: {GUILD_ID}")
        
        if not BOT_TOKEN:
            print("❌ SECURITY FAILURE: DISCORD_BOT_TOKEN environment variable not set!")
            print("📝 Please set your Discord bot token:")
            print("   export DISCORD_BOT_TOKEN='your_bot_token_here'")
            print("   export GUILD_ID='your_server_id_here'")
            return
        
        if len(BOT_TOKEN) < 30:
            print("❌ SECURITY FAILURE: Bot token appears to be invalid (too short)!")
            print(f"   Token length: {len(BOT_TOKEN)} characters")
            print("   Discord bot tokens are typically 30+ characters long")
            return
        
        if GUILD_ID == 0:
            print("⚠️ WARNING: GUILD_ID not set or invalid!")
            print("   The bot will connect but won't know which server to join")
        
        print("✅ SECURITY: Bot token validated successfully")
        
        # Connect to Discord
        await bot.start(BOT_TOKEN)
        
    except Exception as e:
        print(f"❌ Discord bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await bot.close()

if __name__ == "__main__":
    print("🚀 Discord Bot Standalone Launcher")
    print("📝 This runs the Discord bot separately from the Flask server")
    print("🔗 Make sure the Flask server is running for webhook endpoints")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Discord bot shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
