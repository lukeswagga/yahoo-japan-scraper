#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yahoo Japan Seller Monitor Scraper
Monitors specific seller accounts for new listings from proven archive/designer sellers
"""

import json
import os
import time
import random
import schedule
import threading
from datetime import datetime
from bs4 import BeautifulSoup
import requests

# Import base scraper functionality
from core_scraper_base import YahooScraperBase


class SellerMonitorScraper(YahooScraperBase):
    def __init__(self):
        super().__init__("seller_monitor_scraper")

        # Load seller configuration
        self.config = self.load_seller_config()
        self.sellers = self.config.get('sellers', [])
        self.settings = self.config.get('settings', {})

        # Per-seller tracking for NEW listing detection
        self.seller_seen_file = "seen_seller_listings.json"
        self.seller_seen_items = self.load_seller_seen_items()

        # Statistics per seller
        self.seller_stats = {}
        for seller in self.sellers:
            seller_id = seller['seller_id']
            self.seller_stats[seller_id] = {
                'last_checked': None,
                'total_found': 0,
                'new_listings': 0,
                'priority_finds': 0
            }

        # Priority keywords from config
        self.priority_keywords = self.settings.get('priority_keywords', [])
        self.price_thresholds = self.settings.get('price_alert_thresholds', {})

        print(f"🔍 Seller Monitor initialized")
        print(f"👥 Monitoring {len(self.sellers)} sellers")
        print(f"⭐ {len(self.priority_keywords)} priority keywords loaded")

    def load_seller_config(self):
        """Load seller configuration from sellers.json"""
        try:
            config_path = "sellers.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ sellers.json not found, using empty config")
                return {'sellers': [], 'settings': {}}
        except Exception as e:
            print(f"❌ Error loading seller config: {e}")
            return {'sellers': [], 'settings': {}}

    def load_seller_seen_items(self):
        """Load per-seller seen items tracking"""
        try:
            if os.path.exists(self.seller_seen_file):
                with open(self.seller_seen_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"⚠️ Could not load seller seen items: {e}")
            return {}

    def save_seller_seen_items(self):
        """Save per-seller seen items"""
        try:
            with open(self.seller_seen_file, 'w', encoding='utf-8') as f:
                json.dump(self.seller_seen_items, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save seller seen items: {e}")

    def build_seller_url(self, seller_id, page=1):
        """
        Build Yahoo Japan seller listing URL

        Args:
            seller_id: Yahoo seller ID
            page: Page number (1-based)
        """
        base_url = "https://auctions.yahoo.co.jp/seller"

        # Calculate starting position (100 items per page)
        start_position = (page - 1) * 100 + 1

        # Build seller page URL with pagination
        url = f"{base_url}/{seller_id}?b={start_position}&n=100&s1=new&o1=d"

        return url

    def check_priority_keywords(self, title):
        """
        Check if listing contains priority keywords

        Returns:
            (is_priority, matched_keywords)
        """
        title_lower = title.lower()
        matched = []

        for keyword in self.priority_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in title_lower:
                matched.append(keyword)

        return (len(matched) > 0, matched)

    def calculate_alert_level(self, price_usd, is_priority):
        """
        Calculate alert priority level based on price and keywords

        Returns:
            alert_level: "🔥 STEAL", "⭐ PRIORITY", "✨ GOOD DEAL", or None
        """
        thresholds = self.price_thresholds

        # Priority item under steal price
        if is_priority and price_usd <= thresholds.get('steal_price_usd', 50):
            return "🔥 STEAL"

        # Priority item under good deal price
        if is_priority and price_usd <= thresholds.get('good_deal_usd', 150):
            return "⭐ PRIORITY"

        # Any item under steal price
        if price_usd <= thresholds.get('steal_price_usd', 50):
            return "✨ GOOD DEAL"

        # Premium finds (over $500 from priority brands)
        if is_priority and price_usd >= thresholds.get('premium_find_usd', 500):
            return "💎 PREMIUM"

        return None

    def scrape_seller_listings(self, seller_id, max_pages=3):
        """
        Scrape all listings from a specific seller

        Args:
            seller_id: Yahoo seller ID
            max_pages: Maximum pages to scrape per seller

        Returns:
            List of auction data dictionaries
        """
        all_listings = []

        print(f"\n👤 Checking seller: {seller_id}")

        for page in range(1, max_pages + 1):
            try:
                url = self.build_seller_url(seller_id, page)

                print(f"  📄 Page {page}: {url}")

                headers = self.get_request_headers()
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    print(f"  ⚠️ Got status code {response.status_code}")
                    break

                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select("li.Product")

                if not items:
                    print(f"  ℹ️ No items found on page {page}")
                    break

                print(f"  📦 Found {len(items)} items on page {page}")

                for item in items:
                    auction_data = self.extract_auction_data(item)
                    if auction_data:
                        # Add seller context
                        auction_data['seller_id'] = seller_id
                        auction_data['scraper_source'] = 'seller_monitor_scraper'
                        all_listings.append(auction_data)

                # Rate limiting between pages
                if page < max_pages:
                    delay = self.settings.get('rate_limiting', {}).get('delay_between_pages_seconds', 2)
                    time.sleep(delay + random.uniform(0, 1))

            except Exception as e:
                print(f"  ❌ Error scraping page {page}: {e}")
                break

        return all_listings

    def is_new_listing(self, seller_id, auction_id):
        """Check if this is a new listing for this seller"""
        if seller_id not in self.seller_seen_items:
            self.seller_seen_items[seller_id] = []

        return auction_id not in self.seller_seen_items[seller_id]

    def mark_listing_seen(self, seller_id, auction_id):
        """Mark a listing as seen for a specific seller"""
        if seller_id not in self.seller_seen_items:
            self.seller_seen_items[seller_id] = []

        if auction_id not in self.seller_seen_items[seller_id]:
            self.seller_seen_items[seller_id].append(auction_id)

            # Keep only last 500 per seller to prevent infinite growth
            if len(self.seller_seen_items[seller_id]) > 500:
                self.seller_seen_items[seller_id] = self.seller_seen_items[seller_id][-500:]

    def cleanup_ended_listings(self):
        """
        Clean up old listings from seen items
        Keep only listings from last 30 days to prevent memory growth
        """
        # This is a placeholder - in production, you'd check auction end dates
        # For now, we'll just limit to last 500 per seller
        for seller_id in list(self.seller_seen_items.keys()):
            if len(self.seller_seen_items[seller_id]) > 500:
                self.seller_seen_items[seller_id] = self.seller_seen_items[seller_id][-500:]

    def process_and_send_listing(self, listing_data, is_new):
        """
        Process listing and send to Discord with priority flags

        Args:
            listing_data: Auction data dictionary
            is_new: Whether this is a new listing
        """
        if not is_new:
            return False

        # Check for priority keywords
        is_priority, matched_keywords = self.check_priority_keywords(listing_data['title'])

        # Calculate alert level
        alert_level = self.calculate_alert_level(listing_data['price_usd'], is_priority)

        # Add metadata to listing
        listing_data['is_new_listing'] = True
        listing_data['is_priority'] = is_priority
        listing_data['matched_keywords'] = matched_keywords
        listing_data['alert_level'] = alert_level

        # Send to Discord via webhook
        success = self.send_to_discord(listing_data)

        if success:
            seller_id = listing_data['seller_id']
            self.seller_stats[seller_id]['new_listings'] += 1
            if is_priority:
                self.seller_stats[seller_id]['priority_finds'] += 1

            # Print alert
            alert_str = f" {alert_level}" if alert_level else ""
            priority_str = f" [{', '.join(matched_keywords)}]" if matched_keywords else ""
            print(f"  ✅{alert_str} NEW: {listing_data['title'][:60]}{priority_str}")

        return success

    def run_seller_monitor_cycle(self):
        """
        Main monitoring cycle - check all sellers
        """
        print(f"\n{'='*80}")
        print(f"🔄 Starting seller monitor cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")

        total_new_listings = 0
        total_checked = 0

        max_pages = self.settings.get('max_pages_per_seller', 3)

        for seller_config in self.sellers:
            seller_id = seller_config['seller_id']

            # Skip disabled sellers
            if not seller_config.get('enabled', True):
                print(f"⏭️ Skipping disabled seller: {seller_id}")
                continue

            try:
                # Update last checked time
                self.seller_stats[seller_id]['last_checked'] = datetime.now().isoformat()

                # Scrape seller listings
                listings = self.scrape_seller_listings(seller_id, max_pages)

                self.seller_stats[seller_id]['total_found'] = len(listings)
                total_checked += len(listings)

                # Process each listing
                new_count = 0
                for listing in listings:
                    auction_id = listing['auction_id']

                    # Check if new
                    is_new = self.is_new_listing(seller_id, auction_id)

                    if is_new:
                        # Send to Discord
                        if self.process_and_send_listing(listing, is_new):
                            new_count += 1
                            total_new_listings += 1

                        # Mark as seen
                        self.mark_listing_seen(seller_id, auction_id)

                print(f"  📊 {new_count} new listings from {seller_id}")

                # Rate limiting between sellers
                delay = self.settings.get('rate_limiting', {}).get('delay_between_sellers_seconds', 3)
                time.sleep(delay + random.uniform(0, 1))

            except Exception as e:
                print(f"  ❌ Error checking seller {seller_id}: {e}")
                continue

        # Save seen items
        self.save_seller_seen_items()

        # Periodic cleanup
        self.cleanup_ended_listings()

        # Print summary
        print(f"\n{'='*80}")
        print(f"✅ Cycle complete: {total_checked} listings checked, {total_new_listings} new listings sent")
        print(f"{'='*80}\n")

        return {
            'total_checked': total_checked,
            'new_listings': total_new_listings,
            'timestamp': datetime.now().isoformat()
        }

    def start_scheduler(self):
        """Start the scheduled monitoring"""
        check_interval = self.settings.get('check_interval_minutes', 15)

        print(f"\n🕐 Scheduling seller monitor every {check_interval} minutes")

        # Run immediately on start
        self.run_seller_monitor_cycle()

        # Schedule periodic runs
        schedule.every(check_interval).minutes.do(self.run_seller_monitor_cycle)

        # Run scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        print(f"✅ Scheduler started successfully")

    def get_seller_statistics(self):
        """Get statistics for all monitored sellers"""
        return {
            'total_sellers': len(self.sellers),
            'enabled_sellers': sum(1 for s in self.sellers if s.get('enabled', True)),
            'seller_stats': self.seller_stats,
            'settings': self.settings
        }


def main():
    """Main entry point"""
    print("=" * 80)
    print("🚀 Yahoo Japan Seller Monitor Scraper")
    print("=" * 80)

    # Initialize scraper
    scraper = SellerMonitorScraper()

    # Start scheduler
    scraper.start_scheduler()

    # Run Flask health server (blocks)
    scraper.run_health_server()


if __name__ == "__main__":
    main()
