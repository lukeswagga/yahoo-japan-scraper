#!/usr/bin/env python3
"""Test different Discord bot URLs to find the correct one"""

import requests
import os
from datetime import datetime

def test_discord_urls():
    """Test various Discord bot URLs"""
    print("🔍 Testing Discord Bot URLs...")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    # List of possible Discord bot URLs to test
    test_urls = [
        "https://motivated-stillness-production.up.railway.app",
        "https://discord-auction-bot-production.up.railway.app",  # Same as scraper
        "http://localhost:8000",
        "https://localhost:8000",
        "https://discord-bot-production.up.railway.app",
        "https://archive-collective-bot.up.railway.app",
        "https://discord-bot-archive.up.railway.app"
    ]
    
    # Also check environment variable
    env_url = os.getenv('DISCORD_BOT_URL')
    if env_url and env_url not in test_urls:
        test_urls.insert(0, env_url)
    
    working_urls = []
    
    for url in test_urls:
        print(f"\n🔗 Testing: {url}")
        try:
            # Test health endpoint
            response = requests.get(f"{url}/health", timeout=5)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Response: {data}")
                working_urls.append(url)
                
                # Test webhook endpoint
                try:
                    webhook_response = requests.get(f"{url}/webhook/health", timeout=5)
                    print(f"   Webhook Status: {webhook_response.status_code}")
                    if webhook_response.status_code == 200:
                        webhook_data = webhook_response.json()
                        print(f"   ✅ Webhook: {webhook_data}")
                except Exception as e:
                    print(f"   ❌ Webhook test failed: {e}")
                    
            else:
                print(f"   ❌ Failed with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("   ❌ Connection refused")
        except requests.exceptions.Timeout:
            print("   ❌ Timeout")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print("=" * 60)
    
    if working_urls:
        print("✅ Working Discord Bot URLs:")
        for url in working_urls:
            print(f"   • {url}")
    else:
        print("❌ No working Discord Bot URLs found")
        print("\n💡 Next steps:")
        print("1. Check if Discord bot service is deployed on Railway")
        print("2. Verify the correct Railway URL for the Discord bot")
        print("3. Set DISCORD_BOT_URL environment variable")
        print("4. Or temporarily disable Discord integration")

if __name__ == "__main__":
    test_discord_urls()
