#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
New Listings Scraper - Finds newest auction listings
Sends to 🆕-new-listings channel
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

class NewListingsScraper(YahooScraperBase):
    def __init__(self):
        super().__init__("new_listings_scraper")
        self.target_channel = "🆕-new-listings"
        self.max_pages_initial = 5  # First few runs
        self.max_pages_regular = 2  # Regular runs  
        self.cycle_count = 0
        self.last_run_time = None
        
    def scrape_new_listings_page(self, keyword, page, brand_info):
        """Scrape a single page for new auction listings"""
        try:
            # Build URL for auctions only, sorted by newest
            url = self.build_search_url(
                keyword=keyword, 
                page=page, 
                fixed_type=2,  # Auctions only
                sort_type="new", 
                sort_order="d"  # Descending (newest first)
            )
            
            headers = self.get_request_headers()
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code} for {keyword} page {page}")
                return [], True
            
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("li.Product")
            
            if not items:
                print(f"🔚 No items found on page {page} for '{keyword}'")
                return [], False
            
            listings = []
            
            for item in items:
                auction_data = self.extract_auction_data(item)
                if auction_data and auction_data['auction_id'] not in self.seen_ids:
                    # Check if this is actually a new listing
                    if self.is_new_listing(auction_data):
                        listings.append(auction_data)
                        self.seen_ids.add(auction_data['auction_id'])
            
            print(f"📄 Page {page} for '{keyword}': Found {len(listings)} new items")
            return listings, len(items) >= 90  # Continue if page is full
            
        except Exception as e:
            print(f"❌ Error scraping page {page} for '{keyword}': {e}")
            return [], False
    
    def is_new_listing(self, auction_data):
        """
        Determine if this is a genuinely new listing
        For now, we'll consider any unseen listing as new
        Could be enhanced with timestamp parsing in the future
        """
        return True  # Since we're sorting by newest and checking seen_ids
    
    def scrape_brand_new_listings(self, brand, brand_info):
        """Scrape all new listings for a specific brand"""
        all_listings = []
        
        # Determine max pages based on cycle count
        max_pages = self.max_pages_initial if self.cycle_count < 3 else self.max_pages_regular
        
        # Use primary variant as keyword
        primary_variant = brand_info['variants'][0]
        
        print(f"🔍 Scanning {brand} for new listings (up to {max_pages} pages)")
        
        for page in range(1, max_pages + 1):
            listings, should_continue = self.scrape_new_listings_page(
                primary_variant, page, brand_info
            )
            
            all_listings.extend(listings)
            
            # Stop if page isn't full (likely no more results)
            if not should_continue:
                print(f"🛑 Stopping pagination for {brand} at page {page}")
                break
            
            # Rate limiting
            if page < max_pages:
                time.sleep(1)
        
        return all_listings
    
    def run_new_listings_cycle(self):
        """Run a complete new listings scraping cycle"""
        cycle_start = time.time()
        self.cycle_count += 1
        current_time = datetime.now(timezone.utc)
        
        print(f"\n🆕 Starting new listings cycle #{self.cycle_count}")
        print(f"🕐 Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        total_found = 0
        total_sent = 0
        
        # Process all brands
        for brand, brand_info in self.brand_data.items():
            try:
                listings = self.scrape_brand_new_listings(brand, brand_info)
                
                for listing in listings:
                    # Add scraper-specific metadata
                    listing['is_new_listing'] = True
                    listing['scraper_source'] = 'new_listings_scraper'
                    listing['listing_type'] = 'new_auction'
                    
                    # Enhanced logging for debugging
                    print(f"🔍 Processing new listing: {listing['title'][:50]}...")
                    print(f"   💰 Price: ${listing['price_usd']:.2f} (¥{listing['price_jpy']:,})")
                    print(f"   🏷️ Brand: {listing['brand']}")
                    print(f"   📊 Quality Score: {listing.get('deal_quality', 0):.2f}")
                    print(f"   🆕 New listing detected")
                    
                    # Send to Discord bot (let it handle channel routing)
                    if self.send_to_discord(listing):
                        total_sent += 1
                        print(f"✅ Sent new listing to Discord bot: {listing['title'][:50]}...")
                    
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
        
        # Update last run time
        self.last_run_time = current_time
        
        cycle_duration = time.time() - cycle_start
        print(f"\n📊 New Listings Cycle #{self.cycle_count} Complete:")
        print(f"   ⏱️ Duration: {cycle_duration:.1f}s")
        print(f"   🔍 Found: {total_found} items")
        print(f"   📤 Sent: {total_sent} items")
        print(f"   💾 Tracking: {len(self.seen_ids)} seen items")
        print(f"   🚫 Enhanced spam filtering applied")
        print(f"   🎯 Target: {self.target_channel}")
    
    def start_scheduler(self):
        """Start the scheduler for new listings scraping"""
        print(f"🚀 Starting New Listings Scraper")
        print(f"🆕 Target Channel: {self.target_channel}")
        print(f"📅 Schedule: Every 10 minutes")
        print(f"🔄 Sort Order: Newest first")
        
        # Schedule every 10 minutes (more frequent for new listings)
        schedule.every(10).minutes.do(self.run_new_listings_cycle)
        
        # Run immediately
        self.run_new_listings_cycle()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    scraper = NewListingsScraper()
    
    # Start health server in background
    health_thread = threading.Thread(target=scraper.run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    # Start scraping
    try:
        scraper.start_scheduler()
    except KeyboardInterrupt:
        print("\n🛑 New Listings Scraper stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()