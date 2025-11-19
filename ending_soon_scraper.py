#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ending Soon Scraper - Finds auctions ending within 6 hours
Sends to ⏰-ending-soon channel
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_scraper_base import YahooScraperBase
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timezone, timedelta
import threading
import schedule

class EndingSoonScraper(YahooScraperBase):
    def __init__(self):
        super().__init__("ending_soon_scraper")
        self.target_channel = "⏰-ending-soon"
        self.ending_soon_threshold = 6  # 6 hours
        self.max_pages_initial = 10  # First few runs
        self.max_pages_regular = 2   # Regular runs
        self.cycle_count = 0
        
    def is_ending_soon(self, end_time_text):
        """Check if auction is ending within 6 hours"""
        if not end_time_text:
            return False
            
        try:
            # Parse Japanese time format
            # Common formats: "1日", "5時間", "30分", "終了"
            end_time_text = end_time_text.strip()
            
            # Already ended
            if "終了" in end_time_text or "ended" in end_time_text.lower():
                return False
            
            # Parse time remaining
            if "日" in end_time_text:  # Days remaining
                days = int(end_time_text.split("日")[0])
                return days == 0  # Only today
                
            elif "時間" in end_time_text:  # Hours remaining
                hours = int(end_time_text.split("時間")[0])
                return hours <= self.ending_soon_threshold
                
            elif "分" in end_time_text:  # Minutes remaining
                return True  # All items with minutes remaining
                
            elif "秒" in end_time_text:  # Seconds remaining
                return True
                
            return False
            
        except Exception as e:
            print(f"⚠️ Error parsing end time '{end_time_text}': {e}")
            return False
    
    def scrape_ending_soon_page(self, keyword, page, brand_info):
        """Scrape a single page for ending soon auctions"""
        try:
            # Build URL for auctions only, sorted by ending soon
            url = self.build_search_url(
                keyword=keyword, 
                page=page, 
                fixed_type=2,  # Auctions only
                sort_type="end", 
                sort_order="a"  # Ascending (soonest first)
            )
            
            headers = self.get_request_headers()
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code} for {keyword} page {page}")
                return [], False
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("li.Product")
            
            if not items:
                print(f"🔚 No items found on page {page} for '{keyword}'")
                return [], False
            
            listings = []
            should_continue = True
            
            for item in items:
                # Extract end time first to check if we should continue
                end_tag = item.select_one(".Product__time")
                if end_tag:
                    end_time_text = end_tag.get_text(strip=True)
                    
                    # If we find an item not ending soon, stop pagination
                    if not self.is_ending_soon(end_time_text):
                        print(f"⏹️ Found item not ending soon: {end_time_text}, stopping pagination")
                        should_continue = False
                        break
                
                # Extract auction data
                auction_data = self.extract_auction_data(item)
                if auction_data and auction_data['auction_id'] not in self.seen_ids:
                    # Double-check it's ending soon
                    if self.is_ending_soon(auction_data.get('end_time', '')):
                        listings.append(auction_data)
                        self.seen_ids.add(auction_data['auction_id'])
                    else:
                        should_continue = False
                        break
            
            print(f"📄 Page {page} for '{keyword}': Found {len(listings)} ending soon items")
            return listings, should_continue
            
        except Exception as e:
            print(f"❌ Error scraping page {page} for '{keyword}': {e}")
            return [], False
    
    def scrape_brand_ending_soon(self, brand, brand_info):
        """Scrape all ending soon auctions for a specific brand"""
        all_listings = []
        
        # Determine max pages based on cycle count
        max_pages = self.max_pages_initial if self.cycle_count < 3 else self.max_pages_regular
        
        # Use primary variant as keyword
        primary_variant = brand_info['variants'][0]
        
        print(f"🔍 Scanning {brand} for ending soon auctions (up to {max_pages} pages)")
        
        for page in range(1, max_pages + 1):
            listings, should_continue = self.scrape_ending_soon_page(
                primary_variant, page, brand_info
            )
            
            all_listings.extend(listings)
            
            # Stop if we've found items that aren't ending soon
            if not should_continue:
                print(f"🛑 Stopping pagination for {brand} at page {page}")
                break
            
            # Rate limiting
            if page < max_pages:
                time.sleep(1)
        
        return all_listings
    
    def run_ending_soon_cycle(self):
        """Run a complete ending soon scraping cycle"""
        cycle_start = time.time()
        self.cycle_count += 1
        
        print(f"\n🏃‍♂️ Starting ending soon cycle #{self.cycle_count}")
        print(f"⏰ Looking for auctions ending within {self.ending_soon_threshold} hours")
        
        total_found = 0
        total_sent = 0
        
        # Process all brands
        for brand, brand_info in self.brand_data.items():
            try:
                listings = self.scrape_brand_ending_soon(brand, brand_info)
                
                for listing in listings:
                    # Add scraper-specific metadata
                    listing['scraper_source'] = 'ending_soon_scraper'
                    listing['is_ending_soon'] = True
                    listing['listing_type'] = 'ending_soon_auction'
                    
                    # Enhanced logging for debugging
                    print(f"🔍 Processing ending soon listing: {listing['title'][:50]}...")
                    print(f"   💰 Price: ${listing['price_usd']:.2f} (¥{listing['price_jpy']:,})")
                    print(f"   🏷️ Brand: {listing['brand']}")
                    print(f"   ⏰ End Time: {listing.get('end_time', 'Unknown')}")
                    print(f"   📊 Quality Score: {listing.get('deal_quality', 0):.2f}")
                    
                    # Send to Discord bot (let it handle channel routing)
                    if self.send_to_discord(listing):
                        total_sent += 1
                        print(f"✅ Sent ending soon listing to Discord bot: {listing['title'][:50]}...")
                    
                    total_found += 1

                    # OPTIMIZED: Reduced from 0.5s to 0.1s for faster processing
                    time.sleep(0.1)

                # OPTIMIZED: Reduced from 2s to 0.5s for faster brand switching
                time.sleep(0.5)

            except Exception as e:
                print(f"❌ Error processing {brand}: {e}")
                continue

        # Save seen items
        self.save_seen_items()

        # ANALYTICS: Show filtering statistics
        self.analyze_filtering()

        # Cleanup seen_ids if needed
        self.cleanup_old_seen_ids()
        
        cycle_duration = time.time() - cycle_start
        print(f"\n📊 Ending Soon Cycle #{self.cycle_count} Complete:")
        print(f"   ⏱️ Duration: {cycle_duration:.1f}s")
        print(f"   🔍 Found: {total_found} items")
        print(f"   📤 Sent: {total_sent} items")
        print(f"   💾 Tracking: {len(self.seen_ids)} seen items")
        print(f"   🚫 Enhanced spam filtering applied")
        print(f"   🎯 Target: {self.target_channel}")
    
    def start_scheduler(self):
        """Start the scheduler for ending soon scraping"""
        print(f"🚀 Starting Ending Soon Scraper")
        print(f"⏰ Target Channel: {self.target_channel}")
        print(f"📅 Schedule: Every 15 minutes")
        print(f"🎯 Threshold: {self.ending_soon_threshold} hours")
        
        # Schedule every 15 minutes
        schedule.every(15).minutes.do(self.run_ending_soon_cycle)
        
        # Run immediately
        self.run_ending_soon_cycle()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    scraper = EndingSoonScraper()
    
    # Start health server in background
    health_thread = threading.Thread(target=scraper.run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    # Start scraping
    try:
        scraper.start_scheduler()
    except KeyboardInterrupt:
        print("\n🛑 Ending Soon Scraper stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()