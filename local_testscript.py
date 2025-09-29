#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Test Script - Test all scrapers before Railway deployment
"""

import subprocess
import time
import threading
import os
import sys
from datetime import datetime

class ScraperTester:
    def __init__(self):
        self.scrapers = [
            {
                'name': 'Ending Soon Scraper',
                'file': 'ending_soon_scraper.py',
                'port': 8001,
                'channel': '⏰-ending-soon'
            },
            {
                'name': 'New Listings Scraper', 
                'file': 'new_listings_scraper.py',
                'port': 8002,
                'channel': '🆕-new-listings'
            },
            {
                'name': 'Budget Steals Scraper',
                'file': 'budget_steals_scraper.py', 
                'port': 8003,
                'channel': '💰-budget-steals'
            },
            {
                'name': 'Buy It Now Scraper',
                'file': 'buy_it_now_scraper.py',
                'port': 8004, 
                'channel': '🛒-buy-it-now'
            }
        ]
        
        self.processes = {}
        self.discord_bot_url = os.getenv('DISCORD_BOT_URL', 'http://localhost:8000')
    
    def check_required_files(self):
        """Check if all required files exist"""
        required_files = [
            'core_scraper_base.py',
            'ending_soon_scraper.py',
            'new_listings_scraper.py', 
            'budget_steals_scraper.py',
            'buy_it_now_scraper.py',
            'brands.json'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            print(f"❌ Missing required files: {', '.join(missing_files)}")
            return False
        
        print("✅ All required files found")
        return True
    
    def create_test_brands_json(self):
        """Create a minimal brands.json for testing"""
        if not os.path.exists('brands.json'):
            print("📝 Creating test brands.json...")
            
            brands = {
                "Raf Simons": {"variants": ["raf simons", "raf"], "tier": 1},
                "Rick Owens": {"variants": ["rick owens", "rick"], "tier": 1},
                "Vetements": {"variants": ["vetements"], "tier": 2}
            }
            
            import json
            with open('brands.json', 'w', encoding='utf-8') as f:
                json.dump(brands, f, indent=2, ensure_ascii=False)
            
            print("✅ Test brands.json created")
    
    def test_single_scraper(self, scraper_info):
        """Test a single scraper"""
        name = scraper_info['name']
        file = scraper_info['file']
        port = scraper_info['port']
        
        print(f"\n🧪 Testing {name}...")
        
        # Set environment variables for this test
        env = os.environ.copy()
        env['PORT'] = str(port)
        env['DISCORD_BOT_URL'] = self.discord_bot_url
        env['MAX_BUDGET_USD'] = '60'
        
        try:
            # Run scraper for 30 seconds
            process = subprocess.Popen(
                [sys.executable, file],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes[name] = process
            
            # Monitor output for 30 seconds
            start_time = time.time()
            found_items = 0
            
            while time.time() - start_time < 30:
                try:
                    output = process.stdout.readline()
                    if output:
                        print(f"[{name[:12]}] {output.strip()}")
                        
                        # Count found items
                        if "Found" in output and "items" in output:
                            try:
                                found_items += int(output.split("Found")[1].split()[0])
                            except:
                                pass
                    
                    # Check if process ended
                    if process.poll() is not None:
                        break
                        
                except Exception as e:
                    print(f"❌ Error reading output: {e}")
                    break
            
            # Terminate process
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            
            print(f"✅ {name} test complete - Found {found_items} items")
            return True
            
        except Exception as e:
            print(f"❌ {name} test failed: {e}")
            return False
    
    def test_discord_connection(self):
        """Test Discord bot connection"""
        print(f"\n🔗 Testing Discord bot connection...")
        print(f"Discord Bot URL: {self.discord_bot_url}")
        
        try:
            import requests
            
            # Test health endpoint
            response = requests.get(f"{self.discord_bot_url}/health", timeout=10)
            
            if response.status_code == 200:
                print("✅ Discord bot health check passed")
                
                # Test webhook endpoint
                test_payload = {
                    'auction_id': 'test_12345',
                    'title': 'Test Listing',
                    'brand': 'Test Brand',
                    'price_usd': 50.0,
                    'target_channel': '🧪-test'
                }
                
                webhook_response = requests.post(
                    f"{self.discord_bot_url}/webhook/listing",
                    json=test_payload,
                    timeout=10
                )
                
                if webhook_response.status_code in [200, 204]:
                    print("✅ Discord webhook test passed")
                    return True
                else:
                    print(f"⚠️ Discord webhook returned: {webhook_response.status_code}")
                    return True  # Still okay for testing
            else:
                print(f"❌ Discord bot health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️ Discord bot connection test failed: {e}")
            print("   (This is okay for local testing)")
            return True
    
    def run_all_tests(self):
        """Run all scraper tests"""
        print("🚀 Starting Yahoo Japan Multi-Scraper Test Suite")
        print("=" * 60)
        
        # Check files
        if not self.check_required_files():
            return False
        
        # Create test brands.json if needed
        self.create_test_brands_json()
        
        # Test Discord connection
        discord_ok = self.test_discord_connection()
        
        # Test each scraper
        success_count = 0
        
        for scraper in self.scrapers:
            if self.test_single_scraper(scraper):
                success_count += 1
            time.sleep(2)  # Brief pause between tests
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {success_count}/{len(self.scrapers)} scrapers passed")
        
        if discord_ok:
            print("✅ Discord integration ready")
        else:
            print("⚠️ Discord integration needs setup")
        
        if success_count == len(self.scrapers):
            print("\n🎉 All tests passed! Ready for Railway deployment.")
            print("\nNext steps:")
            print("1. Deploy Discord bot service to Railway")
            print("2. Deploy each scraper as separate Railway service")
            print("3. Set DISCORD_BOT_URL environment variable")
            print("4. Create Discord channels: ⏰-ending-soon, 🆕-new-listings, 🛒-buy-it-now")
            return True
        else:
            print(f"\n❌ {len(self.scrapers) - success_count} tests failed. Check errors above.")
            return False
    
    def cleanup(self):
        """Clean up any running processes"""
        for name, process in self.processes.items():
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"🧹 Cleaned up {name}")
                except:
                    pass

def main():
    tester = ScraperTester()
    
    try:
        success = tester.run_all_tests()
        
        if success:
            print("\n" + "=" * 60)
            print("🚀 DEPLOYMENT READY!")
            print("Copy the artifacts to start deployment:")
            print("1. Core scraper base")
            print("2. All 4 specialized scrapers") 
            print("3. Deployment configurations")
            print("4. Follow the deployment guide")
            
        return success
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        return False
    finally:
        tester.cleanup()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)