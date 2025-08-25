#!/usr/bin/env python3
"""
Standalone Mercari Scraper - Completely Independent
Does NOT interfere with your existing Yahoo scraper
Sends to same Discord bot via webhook
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json
import sqlite3
from datetime import datetime
import threading
from urllib.parse import quote_plus

# Configuration
DISCORD_BOT_URL = "https://motivated-stillness-production.up.railway.app"
MERCARI_WEBHOOK_URL = f"{DISCORD_BOT_URL}/webhook/listing"

# Target configuration (only your priority brands)
TARGET_BRANDS = {
    "Rick Owens": {
        "variants": ["Rick Owens", "リックオーウェンス", "DRKSHDW"],
        "japanese": ["リック", "リックオーウェンス", "ドレクシア"]
    },
    "Junya Watanabe": {
        "variants": ["Junya Watanabe", "ジュンヤワタナベ", "Junya"],
        "japanese": ["ジュンヤ", "ワタナベ", "ジュンヤワタナベ"]
    },
    "Comme Des Garcons": {
        "variants": ["Comme Des Garcons", "CDG", "コムデギャルソン"],
        "japanese": ["コムデ", "ギャルソン", "CDG"]
    }
}

CLOTHING_TYPES = {
    "english": ["jacket", "shirt", "pants", "hoodie", "sweater", "blazer"],
    "japanese": ["ジャケット", "シャツ", "パンツ", "パーカー", "セーター", "ブレザー"]
}

CONDITION_KEYWORDS = ["美品", "中古", "古着", "新品"]  # Excellent, Used, Vintage, New

MAX_PRICE_USD = 100
SCRAPE_INTERVAL_MINUTES = 30

class MercariScraper:
    def __init__(self):
        self.seen_items = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database for tracking seen items"""
        conn = sqlite3.connect('mercari_scraper.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mercari_items (
                item_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                brand TEXT NOT NULL,
                price_yen INTEGER NOT NULL,
                price_usd REAL NOT NULL,
                url TEXT NOT NULL,
                found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seen_items (
                item_id TEXT PRIMARY KEY,
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def is_seen_item(self, item_id):
        """Check if item was already processed"""
        conn = sqlite3.connect('mercari_scraper.db')
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM seen_items WHERE item_id = ?', (item_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
        
    def mark_item_seen(self, item_id):
        """Mark item as seen"""
        conn = sqlite3.connect('mercari_scraper.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO seen_items (item_id) VALUES (?)', (item_id,))
        conn.commit()
        conn.close()
        
    def save_item(self, item_data):
        """Save found item to database"""
        conn = sqlite3.connect('mercari_scraper.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO mercari_items 
            (item_id, title, brand, price_yen, price_usd, url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            item_data['item_id'],
            item_data['title'],
            item_data['brand'],
            item_data['price_yen'],
            item_data['price_usd'],
            item_data['url']
        ))
        conn.commit()
        conn.close()
        
    def search_mercari_japan(self, keyword, max_pages=2):
        """
        Search Mercari Japan directly with enhanced anti-bot evasion
        """
        items = []
        
        for page in range(max_pages):
            try:
                # Mercari Japan search URL
                search_url = f"https://jp.mercari.com/search?keyword={quote_plus(keyword)}&page={page + 1}&order=created_time&status=on_sale"
                
                print(f"🔍 Searching Mercari JP: {keyword} (page {page + 1})")
                
                # Add random delay to avoid detection
                time.sleep(random.uniform(3, 6))
                
                response = self.session.get(search_url, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Try multiple selectors for Mercari items
                    item_containers = self.find_mercari_items(soup)
                    
                    print(f"📦 Found {len(item_containers)} containers on page {page + 1}")
                    
                    for container in item_containers:
                        try:
                            item_data = self.extract_mercari_item(container)
                            if item_data and self.is_target_item(item_data):
                                items.append(item_data)
                                print(f"✅ Found: {item_data['brand']} - {item_data['title'][:50]}... - ¥{item_data['price_yen']:,}")
                        except Exception as e:
                            continue
                            
                elif response.status_code == 403:
                    print(f"🚫 Mercari blocked request (403) - trying alternative approach")
                    break
                elif response.status_code == 404:
                    print(f"❌ Search returned 404 - may be invalid keyword")
                    break
                else:
                    print(f"⚠️ Mercari returned status {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error searching Mercari for {keyword}: {e}")
                break
                
        return items
        
    def find_mercari_items(self, soup):
        """Find item containers using multiple approaches"""
        # Try different selectors that Mercari might use
        selectors = [
            '[data-testid*="item"]',
            '.item',
            '.product',
            'mer-item-thumbnail',
            '[class*="ItemThumbnail"]',
            'article',
            'div[data-item-id]'
        ]
        
        for selector in selectors:
            containers = soup.select(selector)
            if containers and len(containers) > 5:  # Valid if we find multiple items
                print(f"✅ Using selector: {selector} - found {len(containers)} items")
                return containers
                
        # Fallback: look for any links to item pages
        item_links = soup.find_all('a', href=re.compile(r'/item/m\d+'))
        if item_links:
            containers = [link.find_parent(['div', 'article']) for link in item_links]
            containers = [c for c in containers if c]  # Remove None values
            print(f"✅ Using fallback link approach - found {len(containers)} items")
            return containers
            
        print("❌ No item containers found with any selector")
        return []
        
    def extract_mercari_item(self, container):
        """Extract item data from container"""
        try:
            # Extract item URL and ID
            link_elem = container.find('a', href=re.compile(r'/item/m\d+'))
            if not link_elem:
                return None
                
            item_url = link_elem['href']
            if not item_url.startswith('http'):
                item_url = f"https://jp.mercari.com{item_url}"
                
            # Extract item ID
            item_id_match = re.search(r'/item/(m\d+)', item_url)
            if not item_id_match:
                return None
            item_id = item_id_match.group(1)
            
            # Skip if already seen
            if self.is_seen_item(item_id):
                return None
                
            # Extract title
            title_elem = (
                container.find('h3') or
                container.find('[data-testid*="name"]') or
                container.find('.item-name') or
                link_elem
            )
            
            if not title_elem:
                return None
                
            title = title_elem.get('title') or title_elem.get_text(strip=True)
            
            # Extract price
            price_text = container.get_text()
            price_match = re.search(r'[¥￥]\s*([\d,]+)', price_text)
            
            if not price_match:
                return None
                
            price_yen = int(price_match.group(1).replace(',', ''))
            price_usd = price_yen / 150.0  # Approximate conversion
            
            # Filter by price
            if price_usd > MAX_PRICE_USD:
                return None
                
            # Detect brand
            brand = self.detect_brand(title)
            if not brand:
                return None
                
            return {
                'item_id': item_id,
                'title': title,
                'brand': brand,
                'price_yen': price_yen,
                'price_usd': price_usd,
                'url': item_url,
                'source': 'Mercari Japan'
            }
            
        except Exception as e:
            return None
            
    def detect_brand(self, title):
        """Detect target brands in title"""
        title_lower = title.lower()
        
        for brand, data in TARGET_BRANDS.items():
            # Check English variants
            for variant in data['variants']:
                if variant.lower() in title_lower:
                    return brand
                    
            # Check Japanese variants
            for japanese in data['japanese']:
                if japanese in title:
                    return brand
                    
        return None
        
    def is_target_item(self, item_data):
        """Check if item matches our criteria"""
        title_lower = item_data['title'].lower()
        
        # Check for clothing types
        is_clothing = False
        for clothing_type in CLOTHING_TYPES['english'] + CLOTHING_TYPES['japanese']:
            if clothing_type in title_lower:
                is_clothing = True
                break
                
        if not is_clothing:
            return False
            
        # Exclude women's items
        if any(word in title_lower for word in ['femme', 'women', 'レディース', 'womens']):
            return False
            
        return True
        
    def send_to_discord(self, item_data):
        """Send item to Discord via your existing bot webhook"""
        try:
            # Format for your existing Discord bot
            payload = {
                "auction_id": f"mercari_{item_data['item_id']}",
                "title": item_data['title'],
                "brand": item_data['brand'].replace(' ', '_'),  # Match your format
                "price_jpy": item_data['price_yen'],
                "price_usd": item_data['price_usd'],
                "zenmarket_url": f"https://zenmarket.jp/en/shop/jp.mercari.com/item/{item_data['item_id']}",
                "yahoo_url": item_data['url'],  # Original Mercari URL
                "image_url": None,
                "seller_id": "mercari_seller",
                "deal_quality": self.calculate_deal_quality(item_data),
                "priority": 80,  # Lower than Yahoo auctions
                "auction_end_time": None,
                "source": "Mercari Japan"
            }
            
            response = requests.post(MERCARI_WEBHOOK_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Sent to Discord: {item_data['title'][:50]}...")
                return True
            else:
                print(f"❌ Discord webhook failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending to Discord: {e}")
            return False
            
    def calculate_deal_quality(self, item_data):
        """Calculate deal quality score"""
        base_quality = 0.3
        
        # Brand bonus
        if 'rick owens' in item_data['brand'].lower():
            base_quality += 0.3
        elif 'junya watanabe' in item_data['brand'].lower():
            base_quality += 0.25
        elif 'comme des garcons' in item_data['brand'].lower():
            base_quality += 0.2
            
        # Price bonus
        if item_data['price_usd'] <= 30:
            base_quality += 0.3
        elif item_data['price_usd'] <= 60:
            base_quality += 0.2
            
        # Condition bonus
        title_lower = item_data['title'].lower()
        if '美品' in title_lower:  # Excellent condition
            base_quality += 0.2
        elif '新品' in title_lower:  # New
            base_quality += 0.3
            
        return min(1.0, base_quality)
        
    def run_search_cycle(self):
        """Run one complete search cycle"""
        print(f"\n🚀 Starting Mercari search cycle at {datetime.now().strftime('%H:%M:%S')}")
        
        total_found = 0
        
        for brand, data in TARGET_BRANDS.items():
            print(f"\n🎯 Searching for {brand}")
            
            # Search brand variants
            for variant in data['variants'][:2]:  # Limit to top 2 variants
                items = self.search_mercari_japan(variant, max_pages=1)
                
                for item in items:
                    if not self.is_seen_item(item['item_id']):
                        self.save_item(item)
                        self.mark_item_seen(item['item_id'])
                        
                        if self.send_to_discord(item):
                            total_found += 1
                            
                        time.sleep(2)  # Rate limit Discord
                        
                # Rate limit between searches
                time.sleep(random.uniform(5, 8))
                
        print(f"\n✅ Mercari cycle complete - found {total_found} new items")
        return total_found
        
    def run_continuous(self):
        """Run scraper continuously"""
        print("🎯 Starting Standalone Mercari Scraper")
        print(f"💰 Max price: ${MAX_PRICE_USD}")
        print(f"🔄 Interval: {SCRAPE_INTERVAL_MINUTES} minutes")
        print(f"🎯 Brands: {', '.join(TARGET_BRANDS.keys())}")
        print(f"👕 Clothing: {', '.join(CLOTHING_TYPES['english'])}")
        print(f"📡 Discord: {DISCORD_BOT_URL}")
        
        while True:
            try:
                self.run_search_cycle()
                
                print(f"\n⏰ Waiting {SCRAPE_INTERVAL_MINUTES} minutes until next cycle...")
                time.sleep(SCRAPE_INTERVAL_MINUTES * 60)
                
            except KeyboardInterrupt:
                print("\n👋 Stopping Mercari scraper...")
                break
            except Exception as e:
                print(f"\n❌ Error in main loop: {e}")
                print("⏰ Waiting 5 minutes before retry...")
                time.sleep(300)

def test_scraper():
    """Test the scraper with a single search"""
    print("🧪 Testing Mercari scraper...")
    
    scraper = MercariScraper()
    items = scraper.search_mercari_japan("Rick Owens", max_pages=1)
    
    if items:
        print(f"\n✅ Test successful! Found {len(items)} items:")
        for item in items[:3]:
            print(f"  - {item['brand']}: {item['title'][:60]}... - ¥{item['price_yen']:,} (${item['price_usd']:.2f})")
    else:
        print("\n⚠️ No items found in test (may be blocked or no matches)")
        
    return len(items) > 0

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode
        test_scraper()
    else:
        # Production mode
        scraper = MercariScraper()
        scraper.run_continuous()