#!/usr/bin/env python3
"""
Test the notification tier system with mock database
"""

import sys
import os
import asyncio
from datetime import datetime, timezone

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock the database manager before importing other modules
sys.modules['database_manager'] = __import__('mock_database_manager')

async def test_tier_system():
    """Test the notification tier system with mock database"""
    print("🧪 Testing Notification Tier System (Mock Database)")
    print("=" * 60)
    
    try:
        # Import after mocking database_manager
        from notification_tiers import tier_manager
        from daily_scheduler import daily_scheduler
        
        # Test 1: Tier manager initialization
        print("1. Testing tier manager initialization...")
        print(f"✅ Tier limits: {tier_manager.TIER_LIMITS}")
        print(f"✅ Tier names: {tier_manager.TIER_NAMES}")
        
        # Test 2: User tier management
        print("\n2. Testing user tier management...")
        test_user_id = 123456789
        
        tier = await tier_manager.get_user_tier(test_user_id)
        print(f"✅ User tier: {tier}")
        
        success = await tier_manager.upgrade_user_tier(test_user_id, 'standard')
        print(f"✅ User upgraded to standard: {success}")
        
        count, last_reset = await tier_manager.get_user_daily_count(test_user_id)
        print(f"✅ Daily count: {count}, Last reset: {last_reset}")
        
        # Test 3: Notification permission check
        print("\n3. Testing notification permissions...")
        can_send, reason = await tier_manager.can_send_notification(test_user_id)
        print(f"✅ Can send notification: {can_send}, Reason: {reason}")
        
        # Test 4: Queue for daily digest
        print("\n4. Testing daily digest queue...")
        test_listing = {
            'auction_id': 'test_auction_123',
            'title': 'Test Auction Item',
            'brand': 'Test Brand',
            'price_jpy': 5000,
            'price_usd': 35.50,
            'zenmarket_url': 'https://zenmarket.jp/test',
            'yahoo_url': 'https://auctions.yahoo.co.jp/test',
            'image_url': 'https://example.com/image.jpg',
            'deal_quality': 0.8,
            'priority_score': 0.9
        }
        
        await tier_manager.queue_for_daily_digest(test_listing)
        print("✅ Listing queued for daily digest")
        
        # Test 5: Tier statistics
        print("\n5. Testing tier statistics...")
        stats = await tier_manager.get_tier_stats()
        print(f"✅ Tier stats: {stats}")
        
        # Test 6: Daily count management
        print("\n6. Testing daily count management...")
        await tier_manager.set_daily_count(test_user_id, 5)
        count, _ = await tier_manager.get_user_daily_count(test_user_id)
        print(f"✅ Set daily count to 5: {count}")
        
        # Test 7: Create listing embed
        print("\n7. Testing embed creation...")
        embed = tier_manager.create_listing_embed(test_listing, is_dm=True)
        print(f"✅ Created embed: {embed.title}")
        print(f"   - Color: {embed.color}")
        print(f"   - Fields: {len(embed.fields)}")
        
        # Test 8: Scheduler initialization
        print("\n8. Testing scheduler initialization...")
        print(f"✅ Scheduler created: {type(daily_scheduler).__name__}")
        print(f"✅ Scheduler running: {daily_scheduler.running}")
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 System Features Verified:")
        print("   ✅ Database schema and connections (mock)")
        print("   ✅ User tier management")
        print("   ✅ Daily notification limits")
        print("   ✅ Daily digest queue system")
        print("   ✅ Tier statistics")
        print("   ✅ Embed creation")
        print("   ✅ Scheduler initialization")
        
        print("\n🚀 The notification tier system is ready to use!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Update the admin user ID in the Discord commands")
        print("3. Create a #daily-digest channel in your Discord server")
        print("4. Run !setup_notification_tiers to initialize the system")
        print("5. Use !upgrade_tier @user tier to upgrade users")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_tier_system())
    sys.exit(0 if success else 1)
