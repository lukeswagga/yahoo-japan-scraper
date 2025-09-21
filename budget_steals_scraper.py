#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Budget Steals Scraper - Finds items ≤$60, sorted by lowest price
Sends to 💰-budget-steals channel
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

class BudgetStealsScraper(YahooScraperBase):
    def __init__(self):
        super().__init__("budget_steals_scraper")
        self.target_channel = "💰-budget-steals"
        self.max_budget = float(os.getenv('MAX_BUDGET_USD', '60'))  # Configurable budget limit
        self.cycle_count = 0
        self.max_pages_per_brand = 50  # High limit since we're going until we hit $60+
        
    def scrape_budget_page(self, keyword, page, brand_info):
        """Scrape a single page for budget items"""
        try:
            # Build URL for all items (auctions + fixed price), sorted by price ascending
            url = self.build_search_url(
                keyword=keyword, 
                page=page, 
                fixed_type=3,  # Both auctions and fixed price
                sort_type="price", 
                sort_order="a"  # Ascending (lowest price first)
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
            hit_price_limit = False
            
            for item in items:
                auction_data = self.extract_auction_data(item)
                if auction_data and auction_data['auction_id'] not in self.seen_ids:
                    price_usd = auction_data['price_usd']
                    
                    # Check if we've hit the budget limit
                    if price_usd > self.max_budget:
                        print(f"💰 Hit price limit: ${price_usd:.2f} > ${self.max_budget}")
                        hit_price_limit = True
                        break
                    
                    # This is a budget steal!
                    auction_data['is_budget_steal'] = True
                    listings.append(auction_data)
                    self.seen_ids.add(auction_data['auction_id'])
            
            print(f"📄 Page {page} for '{keyword}': Found {len(listings)} budget items")
            return listings, not hit_price_limit  # Continue if we haven't hit price limit
            
        except Exception as e:
            print(f"❌ Error scraping page {page} for '{keyword}': {e}")
            return [], False
    
    def scrape_brand_budget_steals(self, brand, brand_info):
        """Scrape all budget steals for a specific brand"""
        all_listings = []
        
        # Use primary variant as keyword
        primary_variant = brand_info['variants'][0]
        
        print(f"🔍 Scanning {brand} for budget steals ≤${self.max_budget}")
        
        page = 1
        while page <= self.max_pages_per_brand:
            listings, should_continue = self.scrape_budget_page(
                primary_variant, page, brand_info
            )
            
            all_listings.extend(listings)
            
            # Stop if we hit the price limit or no more items
            if not should_continue:
                if listings:  # If we found items but hit price limit
                    print(f"💰 Reached budget limit for {brand} at page {page}")
                else:  # If no items found
                    print(f"🔚 No more items for {brand} at page {page}")
                break
            
            page += 1
            
            # After first few cycles, only check first page for efficiency
            if self.cycle_count > 3 and page > 1:
                print(f"🔄 Regular cycle: stopping {brand} after page 1")
                break
            
            # Rate limiting
            time.sleep(1)
        
        return all_listings
    
    def run_budget_steals_cycle(self):
        """Run a complete budget steals scraping cycle"""
        cycle_start = time.time()
        self.cycle_count += 1
        
        print(f"\n💰 Starting budget steals cycle #{self.cycle_count}")
        print(f"🎯 Budget limit: ≤${self.max_budget}")
        print(f"📊 Sort order: Price ascending (cheapest first)")
        
        total_found = 0
        total_sent = 0
        
        # Process all brands
        for brand, brand_info in self.brand_data.items():
            try:
                listings = self.scrape_brand_budget_steals(brand, brand_info)
                
                for listing in listings:
                    # Add scraper-specific metadata
                    listing['scraper_source'] = 'budget_steals_scraper'
                    listing['is_budget_steal'] = True
                    listing['listing_type'] = 'budget_steal'
                    
                    # Enhanced logging for debugging
                    print(f"🔍 Processing budget steal: {listing['title'][:50]}...")
                    print(f"   💰 Price: ${listing['price_usd']:.2f} (¥{listing['price_jpy']:,})")
                    print(f"   🏷️ Brand: {listing['brand']}")
                    print(f"   📊 Quality Score: {listing.get('deal_quality', 0):.2f}")
                    print(f"   💸 Budget Limit: ${self.max_budget}")
                    
                    # Send to Discord bot (let it handle channel routing)
                    if self.send_to_discord(listing):
                        total_sent += 1
                        print(f"✅ Sent budget steal to Discord bot: {listing['title'][:50]}...")
                    
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
        print(f"\n📊 Budget Steals Cycle #{self.cycle_count} Complete:")
        print(f"   ⏱️ Duration: {cycle_duration:.1f}s")
        print(f"   🔍 Found: {total_found} items")
        print(f"   📤 Sent: {total_sent} items")
        print(f"   💰 Budget Limit: ${self.max_budget}")
        print(f"   💾 Tracking: {len(self.seen_ids)} seen items")
        print(f"   🚫 Enhanced spam filtering applied")
        print(f"   🎯 Target: {self.target_channel}")
    
    def start_scheduler(self):
        """Start the scheduler for budget steals scraping"""
        print(f"🚀 Starting Budget Steals Scraper")
        print(f"💰 Target Channel: {self.target_channel}")
        print(f"📅 Schedule: Every 20 minutes")
        print(f"🎯 Budget Limit: ≤${self.max_budget}")
        print(f"📈 Strategy: Scrape all pages until price > ${self.max_budget}")
        
        # Schedule every 20 minutes
        schedule.every(20).minutes.do(self.run_budget_steals_cycle)
        
        # Run immediately
        self.run_budget_steals_cycle()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    scraper = BudgetStealsScraper()
    
    # Start health server in background
    health_thread = threading.Thread(target=scraper.run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    # Start scraping
    try:
        scraper.start_scheduler()
    except KeyboardInterrupt:
        print("\n🛑 Budget Steals Scraper stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()