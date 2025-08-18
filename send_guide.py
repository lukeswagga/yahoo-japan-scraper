#!/usr/bin/env python3
"""
Fixed version of send_guide.py with proper connection handling
"""

import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID_STR = os.getenv('GUILD_ID')
CHANNEL_NAME = "📋-start-here"

# Convert GUILD_ID to int with error handling
if GUILD_ID_STR:
    try:
        GUILD_ID = int(GUILD_ID_STR)
    except ValueError:
        print(f"❌ GUILD_ID '{GUILD_ID_STR}' is not a valid number")
        exit(1)
else:
    GUILD_ID = None

class GuideBot:
    def __init__(self):
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.client = discord.Client(intents=self.intents)

    async def send_guide(self):
        try:
            await self.client.wait_until_ready()
            guild = self.client.get_guild(GUILD_ID)
            
            if not guild:
                print(f"❌ Could not find guild with ID {GUILD_ID}")
                return
            
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
            if not channel:
                print(f"❌ Could not find channel '{CHANNEL_NAME}'")
                print("Available channels:")
                for ch in guild.text_channels:
                    print(f"  - {ch.name}")
                return
            
            print(f"📤 Sending guide to #{channel.name} in {guild.name}")
            
            # Main guide embed
            main_embed = discord.Embed(
                title="🎯 Discord Auction Bot - Complete User Guide",
                description="Welcome to the ultimate fashion auction discovery platform! This bot automatically finds rare designer pieces from Yahoo Auctions Japan and learns your personal style preferences.",
                color=0x000000
            )
            
            # Getting Started section
            setup_embed = discord.Embed(
                title="🚀 Getting Started",
                color=0x00ff00
            )
            setup_embed.add_field(
                name="Step 1: Initial Setup (Required)",
                value="```!setup```\nThis command will:\n• Show you available proxy services\n• Let you choose your preferred service\n• Create your personal bookmark system\n• Enable AI preference learning\n\n⚠️ **Important**: You cannot use reactions or bookmarks until setup is complete!",
                inline=False
            )
            setup_embed.add_field(
                name="Step 2: Start Exploring",
                value="Once setup is complete, you can:\n• Browse auction listings in brand channels\n• React to listings to train the AI\n• Use commands to manage preferences",
                inline=False
            )
            
            # Commands section
            commands_embed = discord.Embed(
                title="📋 Available Commands",
                color=0x0099ff
            )
            commands_embed.add_field(
                name="⚙️ Configuration",
                value="**`!setup`** - Complete initial setup or view current configuration\n**`!preferences`** - View your current settings",
                inline=False
            )
            commands_embed.add_field(
                name="📊 Statistics & Data",
                value="**`!stats`** - View your personal statistics\n**`!export`** - Download complete reaction history\n**`!my_tier`** - Check your membership tier",
                inline=False
            )
            commands_embed.add_field(
                name="📖 Help",
                value="**`!commands`** - Display the help menu anytime",
                inline=False
            )
            
            # Reactions section
            reactions_embed = discord.Embed(
                title="🎯 How to Use Reactions",
                color=0xff9900
            )
            reactions_embed.add_field(
                name="👍 Like (Thumbs Up)",
                value="When you react with 👍 to any auction listing:\n• **Automatically bookmarks** the item to your private channel\n• **Trains the AI** to show you more similar items\n• **Learns your preferences** for brands, sellers, and price ranges",
                inline=False
            )
            reactions_embed.add_field(
                name="👎 Dislike (Thumbs Down)",
                value="When you react with 👎 to any auction listing:\n• **Trains the AI** to avoid similar items\n• **Learns what you don't like** (sellers, styles, price points)\n• Helps improve future recommendations",
                inline=False
            )
            
            # Proxy services section
            proxy_embed = discord.Embed(
                title="🛒 Proxy Services Explained",
                description="During setup, you'll choose one of these services to buy items from Japan:",
                color=0x9932cc
            )
            proxy_embed.add_field(
                name="🛒 ZenMarket",
                value="**Best for**: Beginners and English speakers\n**Features**: Full English support, detailed guides\n**Fees**: Competitive rates with transparent pricing",
                inline=True
            )
            proxy_embed.add_field(
                name="📦 Buyee",
                value="**Best for**: Frequent buyers\n**Features**: Official Yahoo Auctions partner\n**Fees**: Often lower for multiple items",
                inline=True
            )
            proxy_embed.add_field(
                name="🇯🇵 Yahoo Japan Direct",
                value="**Best for**: Advanced users in Japan\n**Features**: No proxy fees, direct access\n**Requirements**: Japanese address and language",
                inline=True
            )
            
            # Tips section
            tips_embed = discord.Embed(
                title="💡 Pro Tips",
                color=0x00ced1
            )
            tips_embed.add_field(
                name="Getting the Most Out of the Bot",
                value="1. **React frequently** - The more you react, the better your recommendations\n2. **Use both 👍 and 👎** - Negative feedback is just as valuable\n3. **Check your bookmark channel** - Items you like get saved automatically\n4. **Explore all brand channels** - Don't miss finds in other designers\n5. **Run `!setup` properly** - Choose the right proxy service for your needs",
                inline=False
            )
            
            # FAQ section
            faq_embed = discord.Embed(
                title="❓ Frequently Asked Questions",
                color=0x8b0000
            )
            faq_embed.add_field(
                name="Common Questions",
                value="**Q: Can I change my proxy service later?**\nA: Yes, run `!setup` again to reconfigure\n\n**Q: Are my bookmarks private?**\nA: Yes, only you can see your bookmark channel\n\n**Q: How do I get better recommendations?**\nA: Keep reacting! The more you use 👍/👎, the smarter the bot becomes\n\n**Q: What brands are covered?**\nA: 19+ major designers including Raf Simons, Rick Owens, CDG, Margiela, and more",
                inline=False
            )
            
            # Final section
            final_embed = discord.Embed(
                title="🆘 Need Help?",
                description="If you encounter any issues or have questions:\n1. First try `!commands` to see all available options\n2. Ask in the general chat for community help\n3. Contact an admin for technical issues\n\n**Ready to start hunting for grails? Run `!setup` to begin your journey!** 🎯",
                color=0x8b0000
            )
            
            # Send all embeds with delays and proper error handling
            embeds = [
                main_embed, setup_embed, commands_embed, reactions_embed, 
                proxy_embed, tips_embed, faq_embed, final_embed
            ]
            
            messages = []
            for i, embed in enumerate(embeds):
                try:
                    print(f"📤 Sending embed {i+1}/{len(embeds)}")
                    message = await channel.send(embed=embed)
                    messages.append(message)
                    if i < len(embeds) - 1:  # Don't sleep after last message
                        await asyncio.sleep(2)  # Increased delay to avoid rate limits
                except Exception as e:
                    print(f"❌ Error sending embed {i+1}: {e}")
                    continue
            
            print(f"✅ Sent {len(messages)} guide messages")
            
            # Pin the first message
            if messages:
                try:
                    await messages[0].pin()
                    print("📌 Pinned the main guide message")
                except discord.errors.Forbidden:
                    print("⚠️  Could not pin message - bot needs 'Manage Messages' permission")
                except discord.errors.HTTPException:
                    print("⚠️  Could not pin message - channel may have too many pinned messages")
            
        except Exception as e:
            print(f"❌ Error in send_guide: {e}")
        finally:
            # Ensure proper cleanup
            if not self.client.is_closed():
                await self.client.close()

    async def start(self):
        try:
            @self.client.event
            async def on_ready():
                print(f"✅ Bot connected as {self.client.user}")
                await self.send_guide()
            
            # Use run instead of start for better error handling
            await self.client.start(BOT_TOKEN)
        except Exception as e:
            print(f"❌ Connection error: {e}")
        finally:
            if not self.client.is_closed():
                await self.client.close()

def main():
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables")
        print("Make sure you have a .env file with DISCORD_BOT_TOKEN=your_token_here")
        return
    
    if not GUILD_ID:
        print("❌ GUILD_ID not found in environment variables") 
        print("Make sure you have GUILD_ID=your_server_id in your .env file")
        return
    
    print("📋 Sending Discord Bot Guide...")
    print(f"Target guild ID: {GUILD_ID}")
    print(f"Target channel: #{CHANNEL_NAME}")
    print("This will send multiple embed messages and pin the first one.")
    
    response = input("\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    bot = GuideBot()
    try:
        asyncio.run(bot.start())
        print("✅ Guide deployment complete!")
    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()