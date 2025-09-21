#!/usr/bin/env python3
"""
Standalone Discord bot launcher
Run this separately from the main Flask server to avoid asyncio conflicts
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
import asyncio

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the bot from the main file
from secure_discordbot import bot, BOT_TOKEN, GUILD_ID, ADVANCED_FEATURES_AVAILABLE

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
