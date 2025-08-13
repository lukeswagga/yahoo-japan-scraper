#!/usr/bin/env python3
import requests
import json
import os
from datetime import datetime

def test_discord_bot_connection():
    """Test connection to Discord bot service"""
    
    # Get URLs from environment
    discord_bot_url = os.getenv('DISCORD_BOT_URL', 'https://motivated-stillness-production.up.railway.app')
    
    if not discord_bot_url.startswith(('http://', 'https://')):
        discord_bot_url = f"https://{discord_bot_url}"
    
    print(f"🔍 Testing Discord Bot connection...")
    print(f"🔗 Base URL: {discord_bot_url}")
    
    # Test 1: Health check
    print("\n1️⃣ Testing health endpoint...")
    try:
        response = requests.get(f"{discord_bot_url}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        if response.status_code == 200:
            print("   ✅ Health check passed")
        else:
            print("   ❌ Health check failed")
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    # Test 2: Webhook health check
    print("\n2️⃣ Testing webhook health endpoint...")
    try:
        response = requests.get(f"{discord_bot_url}/webhook/health", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        if response.status_code == 200:
            data = response.json()
            if data.get("bot_ready") and data.get("guild_connected"):
                print("   ✅ Webhook ready for listings")
            else:
                print("   ⚠️ Bot not ready or guild not connected")
        else:
            print("   ❌ Webhook health check failed")
    except Exception as e:
        print(f"   ❌ Webhook health error: {e}")
    
    # Test 3: Send test listing
    print("\n3️⃣ Testing webhook listing endpoint...")
    test_listing = {
        "auction_id": "test123456789",
        "title": "TEST LISTING - Comme Des Garcons Archive Piece",
        "brand": "Comme Des Garcons",
        "price_jpy": 15000,
        "price_usd": 100.0,
        "zenmarket_url": "https://zenmarket.jp/test",
        "yahoo_url": "https://auctions.yahoo.co.jp/test",
        "image_url": None,
        "seller_id": "test_seller",
        "auction_end_time": None,
        "deal_quality": 0.25,
        "priority": 85
    }
    
    try:
        response = requests.post(
            f"{discord_bot_url}/webhook/listing",
            json=test_listing,
            timeout=15,
            headers={'Content-Type': 'application/json'}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        if response.status_code == 200:
            print("   ✅ Test listing sent successfully!")
            print("   📱 Check your Discord channel for the test listing")
        else:
            print("   ❌ Test listing failed")
            
    except Exception as e:
        print(f"   ❌ Test listing error: {e}")
    
    print("\n" + "="*60)
    print("📋 DIAGNOSTIC SUMMARY:")
    print("="*60)
    print(f"Target URL: {discord_bot_url}")
    print("\nIf all tests pass, the Yahoo Sniper should be able to send listings.")
    print("If tests fail, check:")
    print("1. Discord bot service is running on Railway")
    print("2. Environment variables are set correctly")  
    print("3. Discord bot has proper permissions")
    print("4. Guild ID and bot token are correct")

def test_from_sniper_perspective():
    """Test exactly how the Yahoo Sniper would send"""
    print("\n🎯 Testing from Yahoo Sniper perspective...")
    
    # Use the same environment variable the sniper uses
    discord_bot_url = os.getenv('DISCORD_BOT_URL', 'http://localhost:8000')
    use_discord_bot = os.getenv('USE_DISCORD_BOT', 'true').lower() == 'true'
    
    print(f"DISCORD_BOT_URL: {discord_bot_url}")
    print(f"USE_DISCORD_BOT: {use_discord_bot}")
    
    if not use_discord_bot:
        print("❌ USE_DISCORD_BOT is false - sniper won't send to Discord")
        return
    
    webhook_url = f"{discord_bot_url}/webhook/listing"
    print(f"Webhook URL: {webhook_url}")
    
    # Simulate what the sniper sends
    listing_data = {
        "auction_id": f"sniper_test_{int(datetime.now().timestamp())}",
        "title": "SNIPER TEST - Rick Owens DRKSHDW Ramones",
        "brand": "Rick Owens",
        "price_jpy": 25000,
        "price_usd": 167.0,
        "zenmarket_url": "https://zenmarket.jp/en/auction.aspx?itemCode=test123",
        "yahoo_url": "https://page.auctions.yahoo.co.jp/jp/auction/test123",
        "image_url": None,
        "seller_id": "test_sniper",
        "auction_end_time": None,
        "deal_quality": 0.35,
        "priority": 95
    }
    
    try:
        print("📤 Sending test from sniper...")
        response = requests.post(
            webhook_url,
            json=listing_data,
            timeout=15,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Yahoo-Auction-Scraper/1.0'
            }
        )
        
        print(f"Status: {response.status_code}")
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Sniper test successful!")
        else:
            print("❌ Sniper test failed")
            
    except Exception as e:
        print(f"❌ Sniper test error: {e}")

if __name__ == "__main__":
    print("🔧 Discord Bot Connection Diagnostic")
    print("="*60)
    
    test_discord_bot_connection()
    test_from_sniper_perspective()
    
    print("\n🚀 If tests pass, restart your Yahoo Sniper service")
    print("💡 The issue is likely in environment variable configuration")
