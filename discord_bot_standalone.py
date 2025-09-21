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

# Environment variables
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', 0))

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
        
        if not BOT_TOKEN or len(BOT_TOKEN) < 50:
            print("❌ SECURITY FAILURE: Invalid bot token!")
            return
        
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
