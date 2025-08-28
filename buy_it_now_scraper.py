#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buy It Now Scraper - Finds fixed price listings (定額)
Sends to 🛒-buy-it-now channel
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_scraper_base import YahooScraperBase
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timezone
import threading
import schedule

class BuyItNowScraper(YahooScraperBase):
    def __init__(self):
        super().__init__("buy_it_now_scraper")
        self.target_channel = "🛒-buy-it-now"
        self.max_pages_initial = 5  # First few runs
        self.max_pages_regular = 2  # Regular runs
        self.cycle_count = 0
        
    def scrape_buy_it_now_page(self, keyword, page, brand_info):
        """Scrape a single page for buy it now listings"""
        try:
            # Build URL for fixed price only
            url = self.build_search_url(
                keyword=keyword, 
                page=page, 
                fixed_type=1,  # Fixed price only
                sort_type="new",  # Sort by newest
                sort_order="d"    # Descending (newest first)
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
                    # Mark as buy it now listing
                    auction_data['is_buy_it_now'] = True
                    auction_data['listing_type'] = 'buy_it_now'
                    
                    listings.append(auction_data)
                    self.seen_ids.add(auction_data['auction_id'])
            
            print(f"📄 Page {page} for '{keyword}': Found {len(listings)} buy it now items")
            return listings, len(items) >= 90  # Continue if page is full
            
        except Exception as e:
            print(f"❌ Error scraping page {page} for '{keyword}': {e}")
            return [], False
    
    def scrape_brand_buy_it_now(self, brand, brand_info):
        """Scrape all buy it now listings for a specific brand"""
        all_listings = []
        
        # Determine max pages based on cycle count
        max_pages = self.max_pages_initial if self.cycle_count < 3 else self.max_pages_regular
        
        # Use primary variant as keyword
        primary_variant = brand_info['variants'][0]
        
        print(f"🔍 Scanning {brand} for buy it now listings (up to {max_pages} pages)")
        
        for page in range(1, max_pages + 1):
            listings, should_continue = self.scrape_buy_it_now_page(
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
    
    def extract_auction_data(self, item):
        """Override to handle fixed price listings specifically"""
        auction_data = super().extract_auction_data(item)
        
        if auction_data:
            # For buy it now, there's no end time
            auction_data['end_time'] = None
            auction_data['listing_type'] = 'fixed_price'
            
            # Check if this is actually a fixed price listing
            # Look for "即決" (immediate decision) or similar indicators
            title_lower = auction_data['title'].lower()
            if any(indicator in title_lower for indicator in ['即決', '定額', 'buy it now', 'bin']):
                auction_data['confirmed_buy_it_now'] = True
            
        return auction_data
    
    def run_buy_it_now_cycle(self):
        """Run a complete buy it now scraping cycle"""
        cycle_start = time.time()
        self.cycle_count += 1
        
        print(f"\n🛒 Starting buy it now cycle #{self.cycle_count}")
        print(f"💯 Fixed price listings only (定額)")
        
        total_found = 0
        total_sent = 0
        
        # Process all brands
        for brand, brand_info in self.brand_data.items():
            try:
                listings = self.scrape_brand_buy_it_now(brand, brand_info)
                
                for listing in listings:
                    # Add scraper source for proper Discord bot routing
                    listing['scraper_source'] = 'buy_it_now_scraper'
                    
                    # Send to Discord bot (let it handle channel routing)
                    if self.send_to_discord(listing):
                        total_sent += 1
                        print(f"✅ Sent buy it now listing to Discord bot: {listing['title'][:50]}...")
                    
                    total_found += 1
                    
                    # Rate limiting between sends
                    time.sleep(0.5)
                
                # Rate limiting between brands
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Error processing {brand}: {e}")
                continue
        
        # Save seen items
        self.save_seen_items()
        
        cycle_duration = time.time() - cycle_start
        print(f"\n📊 Buy It Now Cycle #{self.cycle_count} Complete:")
        print(f"   ⏱️ Duration: {cycle_duration:.1f}s")
        print(f"   🔍 Found: {total_found} items")
        print(f"   📤 Sent: {total_sent} items")
        print(f"   💾 Tracking: {len(self.seen_ids)} seen items")
    
    def start_scheduler(self):
        """Start the scheduler for buy it now scraping"""
        print(f"🚀 Starting Buy It Now Scraper")
        print(f"🛒 Target Channel: {self.target_channel}")
        print(f"📅 Schedule: Every 12 minutes")
        print(f"💯 Listing Type: Fixed price only (定額)")
        
        # Schedule every 12 minutes
        schedule.every(12).minutes.do(self.run_buy_it_now_cycle)
        
        # Run immediately
        self.run_buy_it_now_cycle()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    scraper = BuyItNowScraper()
    
    # Start health server in background
    health_thread = threading.Thread(target=scraper.run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    # Start scraping
    try:
        scraper.start_scheduler()
    except KeyboardInterrupt:
        print("\n🛑 Buy It Now Scraper stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()