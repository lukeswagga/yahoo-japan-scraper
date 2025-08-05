#!/usr/bin/env python3
"""
One-time script to send and pin the bot guide
Usage: python send_guide.py
"""

import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID_STR = os.getenv('GUILD_ID')
CHANNEL_NAME = "📋-start-here"  # Change this to your desired channel

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
            value="**`!setup`** - Complete initial setup or reconfigure\n**`!preferences`** - View your current settings",
            inline=False
        )
        commands_embed.add_field(
            name="📚 Bookmark Management", 
            value="**`!bookmarks`** - View your 10 most recent bookmarks\n**`!clear_bookmarks`** - Remove all saved bookmarks",
            inline=False
        )
        commands_embed.add_field(
            name="📊 Statistics & Analytics",
            value="**`!stats`** - View your personal statistics\n**`!export`** - Download complete reaction history",
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
            value="When you react with 👍 to any auction listing:\n• **Automatically bookmarks** the item to your private channel\n• **Trains the AI** to show you more similar items\n• **Learns your preferences** for brands, sellers, and price ranges\n• Item appears in your `!bookmarks` list",
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
        
        # Auto-bookmarking section
        bookmark_embed = discord.Embed(
            title="📚 Auto-Bookmarking System",
            color=0x32cd32
        )
        bookmark_embed.add_field(
            name="How It Works",
            value="1. React 👍 to any auction listing\n2. Bot automatically creates a bookmark in your private channel\n3. Your private channel name: `bookmarks-[your-username]`\n4. Only you can see your bookmark channel",
            inline=False
        )
        bookmark_embed.add_field(
            name="Bookmark Features",
            value="• **Full listing details** preserved (title, price, image, links)\n• **Organized chronologically** (newest first)\n• **Searchable** using Discord's search function\n• **Permanent storage** until you clear them",
            inline=False
        )
        
        # AI Learning section
        ai_embed = discord.Embed(
            title="🧠 AI Learning System",
            description="The bot learns your preferences through your reactions:",
            color=0xff1493
        )
        ai_embed.add_field(
            name="What the AI Learns",
            value="• **Brand preferences** - Which designers you like most\n• **Price ranges** - Your comfort zone for spending\n• **Item types** - Jackets vs shirts vs pants preferences\n• **Seller trustworthiness** - Reliable sellers you prefer\n• **Quality standards** - Archive pieces vs regular items",
            inline=False
        )
        ai_embed.add_field(
            name="How Learning Improves Your Experience",
            value="• Better quality listings shown over time\n• Reduced spam and irrelevant items\n• Personalized recommendations\n• Smarter price alerts",
            inline=False
        )
        
        # Navigation section
        nav_embed = discord.Embed(
            title="📍 Channel Navigation",
            color=0x4169e1
        )
        nav_embed.add_field(
            name="Brand Channels (🏷️)",
            value="Each major designer has a dedicated channel:\n• `🏷️-raf-simons` - Raf Simons finds\n• `🏷️-rick-owens` - Rick Owens and DRKSHDW\n• `🏷️-maison-margiela` - Margiela and MM6\n• `🏷️-jean-paul-gaultier` - JPG archive pieces\n• And many more...",
            inline=False
        )
        nav_embed.add_field(
            name="Main Channels",
            value="• `🎯-auction-alerts` - All general finds\n• `📚 USER BOOKMARKS` - Your private bookmark area",
            inline=False
        )
        
        # Troubleshooting section
        trouble_embed = discord.Embed(
            title="🔧 Troubleshooting",
            color=0xff4500
        )
        trouble_embed.add_field(
            name="Setup Issues",
            value="• **\"Setup Required\" message**: Run `!setup` first\n• **Can't react**: Complete setup before using reactions\n• **Missing bookmark channel**: React 👍 to any item to create it",
            inline=False
        )
        trouble_embed.add_field(
            name="Common Questions",
            value="**Q: Can I change my proxy service?**\nA: Yes, run `!setup` again to reconfigure\n\n**Q: Are my bookmarks private?**\nA: Yes, only you can see your bookmark channel\n\n**Q: How do I get better recommendations?**\nA: Keep reacting! The more you use 👍/👎, the smarter the bot becomes",
            inline=False
        )
        
        # Pro tips section
        tips_embed = discord.Embed(
            title="🎉 Pro Tips",
            color=0x00ced1
        )
        tips_embed.add_field(
            name="Getting the Most Out of the Bot",
            value="1. **React frequently** - The more you react, the better your recommendations\n2. **Use both 👍 and 👎** - Negative feedback is just as valuable\n3. **Check bookmarks regularly** - Use `!bookmarks` to review saved items\n4. **Explore all brand channels** - Don't miss finds in other designers\n5. **Set up properly** - Choose the right proxy service for your needs",
            inline=False
        )
        
        # Final section
        final_embed = discord.Embed(
            title="🆘 Need Help?",
            description="If you encounter any issues or have questions:\n1. First try `!commands` to see all available options\n2. Check your setup with `!preferences`\n3. Ask in the general chat for community help\n4. Contact an admin for technical issues\n\n**Ready to start hunting for grails? Run `!setup` to begin your journey!** 🎯",
            color=0x8b0000
        )
        
        # Send all embeds
        embeds = [
            main_embed, setup_embed, commands_embed, reactions_embed, 
            proxy_embed, bookmark_embed, ai_embed, nav_embed, 
            trouble_embed, tips_embed, final_embed
        ]
        
        messages = []
        for embed in embeds:
            message = await channel.send(embed=embed)
            messages.append(message)
            await asyncio.sleep(1)  # Small delay between messages
        
        print(f"✅ Sent {len(messages)} guide messages")
        
        # Pin the first message (main guide header)
        try:
            await messages[0].pin()
            print("📌 Pinned the main guide message")
        except discord.errors.Forbidden:
            print("⚠️  Could not pin message - bot needs 'Manage Messages' permission")
        except discord.errors.HTTPException:
            print("⚠️  Could not pin message - channel may have too many pinned messages")
        
        await self.client.close()

    async def start(self):
        @self.client.event
        async def on_ready():
            await self.send_guide()
        
        await self.client.start(BOT_TOKEN)

def main():
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables")
        print("Make sure you have a .env file with DISCORD_BOT_TOKEN=your_token_here")
        return
    
    if not GUILD_ID:
        print("❌ GUILD_ID not found in environment variables") 
        print("Make sure you have GUILD_ID=your_server_id in your .env file")
        print("\nTo find your Guild ID:")
        print("1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)")
        print("2. Right-click your server name")
        print("3. Click 'Copy Server ID'")
        print("4. Add GUILD_ID=your_copied_id to your .env file")
        return
    
    print("📋 Sending Discord Bot Guide...")
    print(f"Target channel: #{CHANNEL_NAME}")
    print("This will send multiple embed messages and pin the first one.")
    
    response = input("\nProceed? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    bot = GuideBot()
    try:
        asyncio.run(bot.start())
        print("✅ Guide sent successfully!")
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()