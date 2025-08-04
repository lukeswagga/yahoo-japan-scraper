#!/usr/bin/env python3
"""
Discord Server Setup Script
Run this once to automatically create your fashion platform structure
Usage: python setup_discord_server.py
"""

import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

class ServerSetup:
    def __init__(self):
        self.intents = discord.Intents.default()
        self.intents.guilds = True
        self.client = discord.Client(intents=self.intents)
        
        self.server_structure = {
            "🏛️ WELCOME LOBBY": [
                ("📋", "start-here", "Server rules, guides, and how to use the platform"),
                ("🎭", "introductions", "New member introductions and welcomes"),
                ("💬", "general-chat", "Main community discussion and daily conversation"),
                ("🎯", "daily-discussion", "Daily fashion topics and trending discussions"),
                ("📸", "fit-pics", "Outfit sharing, feedback, and styling showcase")
            ],
            
            "🔍 COMMUNITY DISCOVERY": [
                ("💡", "style-advice", "Styling help, tips, and wardrobe guidance"),
                ("🔄", "trade-requests", "Member-to-member trading and swaps"),
                ("🤝", "legit-checks", "Authentication help and verification requests"),
                ("📚", "fashion-education", "Brand history, guides, and educational content"),
                ("🗳️", "polls-and-opinions", "Community voting and fashion discussions"),
                ("🎨", "inspo-boards", "Mood boards, inspiration, and aesthetic discussions"),
                ("🏪", "member-sales", "Members selling their personal items")
            ],
            
            "📦 FIND ALERTS": [
                ("🌅", "daily-digest", "Curated daily finds and highlights"),
                ("💰", "budget-steals", "Great finds under $100"),
                ("🎯", "community-votes", "Crowd-sourced gems and community picks"),
                ("⏰", "hourly-drops", "Regular auction updates and new finds"),
                ("🔔", "size-alerts", "Personalized size-specific notifications")
            ],
            
            "🏷️ BRAND DISCUSSIONS": [
                ("💭", "raf-simons-talk", "Raf Simons discussion, history, and finds"),
                ("🖤", "rick-owens-discussion", "Rick Owens and DRKSHDW community discussion"),
                ("🎭", "margiela-chat", "Maison Margiela and MM6 conversations"),
                ("👘", "japanese-brands", "Yohji Yamamoto, Junya Watanabe, Undercover discussion"),
                ("🌐", "emerging-designers", "New and upcoming designer discussions"),
                ("📈", "brand-news", "Fashion releases, collaborations, and industry news")
            ],
            
            "💎 PREMIUM VAULT": [
                ("⚡", "instant-alerts", "Real-time alerts with no delay"),
                ("🔥", "grail-hunter", "Rare and archive pieces only"),
                ("🎯", "personal-alerts", "AI-curated finds for your personal style"),
                ("📊", "market-intelligence", "Pricing trends and market analytics"),
                ("🛡️", "verified-sellers", "High-trust seller finds only"),
                ("💎", "investment-pieces", "High-value items with strong resale potential"),
                ("🏆", "vip-lounge", "Premium member exclusive chat and discussions")
            ],
            
            "📈 MARKET & ANALYTICS": [
                ("📊", "price-tracker", "Price history and trend tracking"),
                ("🔍", "sold-listings", "Recently sold items and market data"),
                ("📈", "trend-analysis", "Detailed market insights and forecasting"),
                ("💹", "investment-tracking", "Portfolio tracking and investment analysis")
            ],
            
            "🎪 EVENTS & SPECIAL": [
                ("🎉", "drop-parties", "Live reactions to major fashion releases"),
                ("🏆", "find-of-the-week", "Community competitions and showcases"),
                ("📅", "fashion-calendar", "Upcoming releases, drops, and events"),
                ("🎁", "giveaways", "Community engagement rewards and contests")
            ]
        }
        
        # Your existing brand channels to organize
        self.existing_brand_channels = [
            "🏷️-raf-simons", "🏷️-rick-owens", "🏷️-maison-margiela", 
            "🏷️-jean-paul-gaultier", "🏷️-yohji-yamamoto", "🏷️-junya-watanabe",
            "🏷️-undercover", "🏷️-vetements", "🏷️-martine-rose", "🏷️-balenciaga",
            "🏷️-alyx", "🏷️-celine", "🏷️-bottega-veneta", "🏷️-kiko-kostadinov",
            "🏷️-chrome-hearts", "🏷️-comme-des-garcons", "🏷️-prada", 
            "🏷️-miu-miu", "🏷️-hysteric-glamour"
        ]

    async def setup_server(self):
        await self.client.wait_until_ready()
        guild = self.client.get_guild(GUILD_ID)
        
        if not guild:
            print(f"❌ Could not find guild with ID {GUILD_ID}")
            return
        
        print(f"🎯 Setting up server: {guild.name}")
        print("🚀 This will take a few minutes...")
        
        created_categories = 0
        created_channels = 0
        moved_channels = 0
        
        try:
            # Create categories and channels
            for category_name, channels in self.server_structure.items():
                print(f"\n📁 Processing category: {category_name}")
                
                # Check if category exists
                existing_category = discord.utils.get(guild.categories, name=category_name)
                
                if not existing_category:
                    category = await guild.create_category(category_name)
                    created_categories += 1
                    print(f"✅ Created category: {category_name}")
                    await asyncio.sleep(1)
                else:
                    category = existing_category
                    print(f"⚠️  Category already exists: {category_name}")
                
                # Create channels
                for emoji, channel_name, description in channels:
                    full_channel_name = f"{emoji}-{channel_name}"
                    
                    existing_channel = discord.utils.get(guild.text_channels, name=full_channel_name)
                    
                    if not existing_channel:
                        channel = await guild.create_text_channel(
                            full_channel_name,
                            category=category,
                            topic=description
                        )
                        created_channels += 1
                        print(f"  ✅ Created: {full_channel_name}")
                        await asyncio.sleep(0.8)
                    else:
                        print(f"  ⚠️  Already exists: {full_channel_name}")
            
            # Move existing brand channels to Brand Discussions category
            print(f"\n📁 Moving existing brand channels...")
            brand_category = discord.utils.get(guild.categories, name="🏷️ BRAND DISCUSSIONS")
            
            if brand_category:
                for brand_channel_name in self.existing_brand_channels:
                    existing_channel = discord.utils.get(guild.text_channels, name=brand_channel_name)
                    if existing_channel and existing_channel.category != brand_category:
                        await existing_channel.edit(category=brand_category)
                        moved_channels += 1
                        print(f"  📁 Moved: {brand_channel_name}")
                        await asyncio.sleep(0.5)
            
            # Set permissions for brand channels (read-only)
            print(f"\n🔒 Setting up permissions for brand channels...")
            brand_channels = [ch for ch in guild.text_channels if ch.name.startswith("🏷️-")]
            
            bot_member = guild.get_member(self.client.user.id)
            
            for channel in brand_channels:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=False,
                        add_reactions=True
                    ),
                    bot_member: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        add_reactions=True
                    )
                }
                
                await channel.edit(overwrites=overwrites)
                print(f"  🔒 Updated permissions: {channel.name}")
                await asyncio.sleep(0.5)
            
            # Create welcome messages
            await self.create_welcome_messages(guild)
            
            print(f"\n🎉 SERVER SETUP COMPLETE!")
            print(f"📊 Summary:")
            print(f"  • Categories created: {created_categories}")
            print(f"  • Channels created: {created_channels}")  
            print(f"  • Channels moved: {moved_channels}")
            print(f"  • Brand channels configured: {len(brand_channels)}")
            print(f"\n✅ Your server is now ready as a fashion platform!")
            
        except discord.errors.Forbidden:
            print("❌ Bot doesn't have permission to create channels. Grant Administrator permission.")
        except Exception as e:
            print(f"❌ Error during setup: {e}")
        
        await self.client.close()

    async def create_welcome_messages(self, guild):
        print(f"\n💬 Adding welcome messages...")
        
        # Start-here welcome
        start_here = discord.utils.get(guild.text_channels, name="📋-start-here")
        if start_here:
            embed = discord.Embed(
                title="🏛️ Welcome to Archive Collective",
                description="Your destination for rare fashion finds and community discussion",
                color=0x000000
            )
            embed.add_field(
                name="🎯 Navigation Guide",
                value="**🏛️ Welcome Lobby** - Introductions and general chat\n**🔍 Community Discovery** - Style advice, trading, education\n**🏷️ Brand Discussions** - Designer-specific conversations\n**📦 Find Alerts** - Live auction discoveries\n**Brand Channels** - Curated finds organized by designer",
                inline=False
            )
            embed.add_field(
                name="📋 Guidelines", 
                value="• Be respectful and helpful to all members\n• Use appropriate channels for discussions\n• React to auction finds to help train our AI\n• Share knowledge and help with authentication\n• Keep conversations fashion-focused",
                inline=False
            )
            embed.set_footer(text="Start exploring and welcome to the community! 👋")
            
            await start_here.send(embed=embed)
            print("  ✅ Added welcome message to #start-here")
        
        # Style advice guide
        style_advice = discord.utils.get(guild.text_channels, name="💡-style-advice")
        if style_advice:
            embed = discord.Embed(
                title="💡 Style Advice & Styling Help",
                description="Get personalized styling advice from the community",
                color=0x4169E1
            )
            embed.add_field(
                name="How to Get Great Advice",
                value="• Post clear photos of items or outfits\n• Mention your style goals or inspiration\n• Include your size and budget if relevant\n• Be specific about what you need help with\n• Show appreciation for helpful responses",
                inline=False
            )
            
            await style_advice.send(embed=embed)
            print("  ✅ Added guide to #style-advice")
        
        # Legit check guide
        legit_check = discord.utils.get(guild.text_channels, name="🤝-legit-checks")
        if legit_check:
            embed = discord.Embed(
                title="🤝 Community Authentication Help",
                description="Get help verifying the authenticity of designer pieces",
                color=0x32CD32
            )
            embed.add_field(
                name="Authentication Best Practices",
                value="• Take multiple clear, well-lit photos\n• Include close-ups of tags, labels, and hardware\n• Mention the specific brand and item\n• Be patient - good authentication takes time\n• Always seek multiple opinions\n• Share knowledge when you can help others",
                inline=False
            )
            
            await legit_check.send(embed=embed)
            print("  ✅ Added guide to #legit-checks")

    async def start_setup(self):
        @self.client.event
        async def on_ready():
            await self.setup_server()
        
        await self.client.start(BOT_TOKEN)

def main():
    if not BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables")
        print("Make sure you have a .env file with DISCORD_BOT_TOKEN=your_token_here")
        return
    
    if not GUILD_ID:
        print("❌ GUILD_ID not found in environment variables") 
        print("Make sure you have GUILD_ID=your_server_id in your .env file")
        return
    
    print("🎯 Discord Fashion Platform Setup")
    print("This will create categories, channels, and set up permissions")
    print("Make sure your bot has Administrator permissions!")
    
    response = input("\nProceed with setup? (y/n): ")
    if response.lower() != 'y':
        print("Setup cancelled.")
        return
    
    setup = ServerSetup()
    try:
        asyncio.run(setup.start_setup())
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()