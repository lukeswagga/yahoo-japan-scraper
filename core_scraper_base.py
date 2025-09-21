#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import time
import json
import os
import urllib.parse
from datetime import datetime, timezone, timedelta
import re
import sqlite3
from flask import Flask
import threading
from enhanced_filtering import EnhancedSpamDetector, QualityChecker, extract_category_from_item, is_blocked_category
import statistics
import random
from concurrent.futures import ThreadPoolExecutor

scraper_app = Flask(__name__)

@scraper_app.route('/health', methods=['GET'])
def health():
    return {"status": "healthy", "service": "auction-scraper"}, 200

@scraper_app.route('/', methods=['GET'])
def root():
    return {"service": "Yahoo Auction Scraper v2.0", "status": "running"}, 200

def run_health_server():
    port = int(os.environ.get('PORT', 8000))
    scraper_app.run(host='0.0.0.0', port=port, debug=False)

# Configuration
DISCORD_BOT_WEBHOOK = os.getenv('DISCORD_BOT_WEBHOOK', "http://localhost:8000/webhook")
DISCORD_BOT_HEALTH = os.getenv('DISCORD_BOT_HEALTH', "http://localhost:8000/health") 
DISCORD_BOT_STATS = os.getenv('DISCORD_BOT_STATS', "http://localhost:8000/stats")
DISCORD_BOT_URL = os.getenv('DISCORD_BOT_URL', 'http://localhost:8000')

if DISCORD_BOT_URL and not DISCORD_BOT_URL.startswith(('http://', 'https://')):
    DISCORD_BOT_URL = f"https://{DISCORD_BOT_URL}"

USE_DISCORD_BOT = True

# Constants
MAX_PRICE_YEN = 100000
SEEN_FILE = "seen_yahoo.json"
BRANDS_FILE = "brands.json"
EXCHANGE_RATE_FILE = "exchange_rate.json"
SCRAPER_DB = "auction_tracking.db"

# IMPROVED PRICE FILTERING (less aggressive)
MAX_PRICE_USD = 1500
MIN_PRICE_USD = 3  # Lowered from 5
PRICE_QUALITY_THRESHOLD = 0.05  # Lowered from 0.15 to allow more items
ENABLE_RESALE_BOOST = True
ENABLE_INTELLIGENT_FILTERING = True

# NEW EXCLUDED KEYWORDS (from user request)
NEW_EXCLUDED_KEYWORDS = {
    "lego", "レゴ",
    "water tank", "ウォータータンク", "水タンク", 
    "bmw touring e91", "bmw e91", "e91",
    "mazda", "マツダ",
    "band of outsiders", "バンドオブアウトサイダーズ"
}

# UPDATED EXCLUDED BRANDS
COMPLETELY_EXCLUDED_BRANDS = {
    "undercoverism",
    "band of outsiders",  # Added from user request
    "lego",               # Added from user request
}

BASE_URL = "https://auctions.yahoo.co.jp/search/search?p={}&n=50&b={}&{}&minPrice=1&maxPrice={}"
exchange_rate_cache = {"rate": 150.0, "timestamp": 0}
current_usd_jpy_rate = 147.0

# Initialize enhanced filtering
spam_detector = EnhancedSpamDetector()
quality_checker = QualityChecker()

def load_brand_data():
    """Load brand data with enhanced exclusion filtering"""
    try:
        with open(BRANDS_FILE, "r", encoding="utf-8") as f:
            brand_data = json.load(f)
            
        # Filter out completely excluded brands
        filtered_data = {}
        for brand_key, brand_info in brand_data.items():
            brand_lower = brand_key.lower()
            
            # Check against completely excluded brands
            is_excluded = False
            for excluded in COMPLETELY_EXCLUDED_BRANDS:
                if excluded.lower() in brand_lower:
                    print(f"🚫 Excluding brand: {brand_key}")
                    is_excluded = True
                    break
            
            if not is_excluded:
                filtered_data[brand_key] = brand_info
                
        print(f"✅ Loaded {len(filtered_data)} brands (excluded {len(brand_data) - len(filtered_data)})")
        return filtered_data
    except FileNotFoundError:
        print("⚠️ brands.json not found, using default brands")
        return {}

def is_quality_listing(title, brand, price_usd):
    """Enhanced quality filtering with new exclusions"""
    if not title or not brand or price_usd <= 0:
        return False, "Invalid data"
    
    title_lower = title.lower()
    
    # PRIORITY 1: Check new excluded keywords
    for excluded in NEW_EXCLUDED_KEYWORDS:
        if excluded.lower() in title_lower:
            return False, f"New excluded keyword: {excluded}"
    
    # PRIORITY 2: Enhanced spam detection
    is_spam, spam_reason = spam_detector.is_spam(title, brand)
    if is_spam:
        return False, f"Spam detected: {spam_reason}"
    
    # PRIORITY 3: Price range check (more lenient)
    if price_usd < MIN_PRICE_USD:
        return False, f"Price ${price_usd:.2f} below minimum ${MIN_PRICE_USD}"
    
    if price_usd > MAX_PRICE_USD:
        return False, f"Price ${price_usd:.2f} above maximum ${MAX_PRICE_USD}"
    
    # PRIORITY 4: Quality threshold check (lowered threshold)
    deal_quality = calculate_deal_quality(price_usd, brand, title)
    
    # Special handling for high-resale brands
    brand_key = brand.lower().replace(" ", "_") if brand else "unknown"
    high_resale_brands = ["raf_simons", "rick_owens", "maison_margiela", "jean_paul_gaultier", "undercover"]
    
    if any(hrb in brand_key for hrb in high_resale_brands):
        threshold = 0.02  # Very low threshold for premium brands
    else:
        threshold = PRICE_QUALITY_THRESHOLD
    
    if deal_quality < threshold:
        return False, f"Deal quality {deal_quality:.1%} below threshold {threshold:.1%}"
    
    return True, f"Quality listing: {deal_quality:.1%} deal quality"

def parse_yahoo_page_optimized(soup, keyword, brand, page_num=1):
    """Enhanced parsing with strict category filtering"""
    listings = []
    skipped_spam = 0
    skipped_category = 0
    skipped_duplicate = 0
    skipped_price = 0
    
    # Multiple selectors for Yahoo Auctions items
    item_selectors = [
        '.Product',
        '.auction',
        '.item',
        '[data-auction-id]',
        '.searchResultItem'
    ]
    
    items = []
    for selector in item_selectors:
        found_items = soup.select(selector)
        if found_items:
            items = found_items
            print(f"🔍 Found {len(items)} items using selector: {selector}")
            break
    
    if not items:
        print(f"⚠️ No items found on page {page_num} with any selector")
        return [], 0, 0, 0, 0
    
    for item in items:
        try:
            # Extract basic item data
            title_elem = item.select_one('a[data-original-title], .Product__title a, .auction-title a, h3 a')
            if not title_elem:
                continue
                
            title = title_elem.get('data-original-title') or title_elem.get_text(strip=True)
            if not title:
                continue
            
            # Extract auction ID
            auction_id = None
            id_patterns = [
                item.get('data-auction-id'),
                item.get('data-aid'),
                item.get('id')
            ]
            
            for pattern in id_patterns:
                if pattern:
                    auction_id = pattern
                    break
            
            if not auction_id:
                # Try to extract from URL
                link = title_elem.get('href', '')
                if link:
                    id_match = re.search(r'[?&]aID=([^&]+)', link)
                    if id_match:
                        auction_id = id_match.group(1)
            
            if not auction_id:
                continue
            
            # Skip if already seen
            if auction_id in seen_ids:
                skipped_duplicate += 1
                continue
            
            # Extract price
            price_elem = item.select_one('.Product__price, .auction-price, .price')
            if not price_elem:
                continue
                
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
            if not price_match:
                continue
                
            try:
                price_jpy = int(price_match.group().replace(',', ''))
                price_usd = convert_jpy_to_usd(price_jpy)
            except (ValueError, AttributeError):
                continue
            
            # ENHANCED CATEGORY FILTERING
            category_text = extract_category_from_item(item)
            if category_text:
                is_blocked, blocked_reason = is_blocked_category(category_text)
                if is_blocked:
                    print(f"🚫 Category blocked: {blocked_reason} for '{title[:30]}...'")
                    skipped_category += 1
                    continue
            
            # STRICT JDIRECTITEMS FILTERING
            item_text = item.get_text()
            if 'jdirectitems auction' in item_text.lower():
                # Extract category after arrow
                category_match = re.search(r'jdirectitems auction.*?→\s*([^,\n]+)', item_text, re.IGNORECASE)
                if category_match:
                    category = category_match.group(1).strip().lower()
                    # Only allow if it's clearly fashion-related
                    fashion_keywords = ['fashion', 'clothing', 'apparel', 'ファッション', '衣類', '服']
                    if not any(fashion_kw in category for fashion_kw in fashion_keywords):
                        print(f"🚫 JDirectItems non-fashion blocked: {category}")
                        skipped_category += 1
                        continue
                    else:
                        print(f"✅ JDirectItems fashion allowed: {category}")
            
            # Extract image URL
            img_elem = item.select_one('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # Brand detection
            detected_brand = detect_brand_in_title(title)
            if not detected_brand or detected_brand == "unknown":
                continue
            
            # Check if brand is completely excluded
            brand_lower = detected_brand.lower()
            if any(excluded.lower() in brand_lower for excluded in COMPLETELY_EXCLUDED_BRANDS):
                continue
            
            # ENHANCED QUALITY FILTERING
            is_quality, quality_reason = is_quality_listing(title, detected_brand, price_usd)
            if not is_quality:
                if 'price' in quality_reason.lower():
                    skipped_price += 1
                else:
                    skipped_spam += 1
                continue
            
            # Build Yahoo URL
            yahoo_url = title_elem.get('href', '')
            if yahoo_url and not yahoo_url.startswith('http'):
                yahoo_url = f"https://auctions.yahoo.co.jp{yahoo_url}"
            
            # Build ZenMarket URL
            zenmarket_url = f"https://zenmarket.jp/auction.aspx?itemCode=yahoo-{auction_id}"
            
            # Calculate additional metrics
            deal_quality = calculate_deal_quality(price_usd, detected_brand, title)
            priority = calculate_listing_priority({
                'price_usd': price_usd,
                'deal_quality': deal_quality,
                'title': title,
                'brand': detected_brand
            })
            
            listing_data = {
                'auction_id': auction_id,
                'title': title,
                'brand': detected_brand,
                'price_jpy': price_jpy,
                'price_usd': price_usd,
                'deal_quality': deal_quality,
                'priority': priority,
                'yahoo_url': yahoo_url,
                'zenmarket_url': zenmarket_url,
                'image_url': image_url,
                'category': category_text or 'unknown',
                'keyword_used': keyword
            }
            
            listings.append(listing_data)
            
        except Exception as e:
            print(f"⚠️ Error parsing item: {e}")
            continue
    
    print(f"📊 Page {page_num} results: {len(listings)} valid, {skipped_spam} spam, {skipped_category} wrong category, {skipped_duplicate} duplicates, {skipped_price} price filtered")
    return listings, skipped_spam, skipped_category, skipped_duplicate, skipped_price

def detect_brand_in_title(title):
    """Enhanced brand detection with exclusion filtering"""
    if not title:
        return "unknown"
    
    global BRAND_DATA
    if 'BRAND_DATA' not in globals():
        BRAND_DATA = load_brand_data()
    
    title_lower = title.lower()
    
    # Check for excluded keywords first
    for excluded in NEW_EXCLUDED_KEYWORDS:
        if excluded.lower() in title_lower:
            return "unknown"  # Don't match any brand if excluded keyword found
    
    # Brand matching
    for brand, brand_info in BRAND_DATA.items():
        for variant in brand_info.get("variants", []):
            if variant.lower() in title_lower:
                # Double-check brand isn't completely excluded
                if not any(excluded.lower() in brand.lower() for excluded in COMPLETELY_EXCLUDED_BRANDS):
                    return brand
    
    return "unknown"

def calculate_deal_quality(price_usd, brand, title):
    """Improved deal quality calculation"""
    if not brand or price_usd <= 0:
        return 0.0
    
    # Base quality score
    base_quality = 0.1
    
    # Brand multipliers (more generous)
    brand_multipliers = {
        'raf_simons': 2.5,
        'rick_owens': 2.3,
        'maison_margiela': 2.2,
        'jean_paul_gaultier': 2.0,
        'undercover': 1.8,
        'yohji_yamamoto': 1.7,
        'comme_des_garcons': 1.6,
        'junya_watanabe': 1.5,
        'martine_rose': 1.4,
        'kiko_kostadinov': 1.3,
        'alyx': 1.2,
    }
    
    brand_key = brand.lower().replace(' ', '_')
    multiplier = brand_multipliers.get(brand_key, 1.0)
    
    # Price-based scoring (more generous for lower prices)
    if price_usd <= 50:
        price_score = 0.8  # Great deals
    elif price_usd <= 100:
        price_score = 0.6  # Good deals
    elif price_usd <= 200:
        price_score = 0.4  # Decent deals
    elif price_usd <= 500:
        price_score = 0.2  # Fair deals
    else:
        price_score = 0.1  # Premium items
    
    # Title quality indicators
    title_lower = title.lower()
    title_bonus = 0.0
    
    quality_indicators = [
        ('archive', 0.3), ('rare', 0.2), ('vintage', 0.1),
        ('fw', 0.15), ('ss', 0.15), ('runway', 0.25),
        ('sample', 0.2), ('prototype', 0.25)
    ]
    
    for indicator, bonus in quality_indicators:
        if indicator in title_lower:
            title_bonus += bonus
    
    final_quality = (base_quality + price_score + title_bonus) * multiplier
    return min(final_quality, 1.0)

def calculate_listing_priority(listing_data):
    """Calculate priority score for listing"""
    price_usd = listing_data["price_usd"]
    deal_quality = listing_data["deal_quality"]
    title = listing_data["title"].lower()
    brand = listing_data["brand"].lower()
    
    priority = deal_quality * 100
    
    # Brand priority boost
    if any(hrb in brand for hrb in ["raf_simons", "rick_owens", "margiela", "martine_rose"]):
        priority += 30
    
    # Price priority boost
    if price_usd <= 100:
        priority += 25
    elif price_usd <= 200:
        priority += 15
    
    # Special keywords boost
    if any(word in title for word in ["archive", "rare", "fw", "ss", "アーカイブ", "レア"]):
        priority += 30
    
    return priority

def convert_jpy_to_usd(jpy_amount):
    """Convert JPY to USD using current exchange rate"""
    return jpy_amount / current_usd_jpy_rate

def get_usd_jpy_rate():
    """Fetch current USD/JPY exchange rate"""
    global current_usd_jpy_rate
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        if response.status_code == 200:
            data = response.json()
            current_usd_jpy_rate = data['rates']['JPY']
            print(f"💱 Updated exchange rate: 1 USD = ¥{current_usd_jpy_rate:.2f}")
            return current_usd_jpy_rate
    except Exception as e:
        print(f"⚠️ Could not fetch exchange rate: {e}")
    
    return current_usd_jpy_rate

def send_to_discord_bot(listing_data):
    """Send listing to Discord bot with enhanced error handling"""
    if not USE_DISCORD_BOT:
        return False
    
    try:
        webhook_url = f"{DISCORD_BOT_URL}/webhook"
        
        payload = {
            'auction_id': listing_data['auction_id'],
            'title': listing_data['title'],
            'brand': listing_data['brand'],
            'price_jpy': listing_data['price_jpy'],
            'price_usd': listing_data['price_usd'],
            'deal_quality': listing_data['deal_quality'],
            'priority': listing_data['priority'],
            'yahoo_url': listing_data['yahoo_url'],
            'zenmarket_url': listing_data['zenmarket_url'],
            'image_url': listing_data['image_url'],
            'category': listing_data.get('category', 'unknown'),
            'keyword_used': listing_data.get('keyword_used', 'unknown')
        }
        
        response = requests.post(webhook_url, json=payload, timeout=30)
        
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️ Discord bot returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending to Discord bot: {e}")
        return False

def search_yahoo_enhanced(keyword, max_pages=3):
    """Enhanced Yahoo search with better error handling and filtering"""
    all_listings = []
    total_errors = 0
    total_spam = 0
    total_category_blocks = 0
    total_duplicates = 0
    total_price_filtered = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    for page in range(1, max_pages + 1):
        try:
            encoded_keyword = urllib.parse.quote_plus(keyword)
            start_index = (page - 1) * 50 + 1
            
            # Use different sort orders for variety
            sort_orders = [
                "s1=new&o1=d",      # Newest first
                "s1=cbids&o1=a",    # Lowest current bid
                "s1=end&o1=a",      # Ending soonest
            ]
            sort_order = sort_orders[page % len(sort_orders)]
            
            url = BASE_URL.format(encoded_keyword, start_index, sort_order, MAX_PRICE_YEN)
            
            print(f"🔍 Searching page {page}: {keyword}")
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Enhanced parsing with category filtering
            listings, spam_count, category_count, duplicate_count, price_count = parse_yahoo_page_optimized(
                soup, keyword, keyword, page
            )
            
            all_listings.extend(listings)
            total_spam += spam_count
            total_category_blocks += category_count
            total_duplicates += duplicate_count
            total_price_filtered += price_count
            
            if not listings:
                print(f"⚠️ No valid listings found on page {page}")
                break
            
            # Rate limiting
            time.sleep(random.uniform(2.0, 4.0))
            
        except Exception as e:
            print(f"❌ Error on page {page} for '{keyword}': {str(e)}")
            total_errors += 1
            time.sleep(random.uniform(3.0, 5.0))
            continue
    
    print(f"🏁 Search complete for '{keyword}': {len(all_listings)} valid listings")
    print(f"   📊 Filtered: {total_spam} spam, {total_category_blocks} wrong category, {total_duplicates} duplicates, {total_price_filtered} price")
    print(f"   ❌ Errors: {total_errors}")
    
    return all_listings, total_errors

# Load configuration
seen_ids = set()
BRAND_DATA = {}

def load_seen_ids():
    """Load seen auction IDs from file"""
    global seen_ids
    try:
        with open(SEEN_FILE, "r") as f:
            seen_ids = set(json.load(f))
        print(f"📚 Loaded {len(seen_ids)} seen auction IDs")
    except FileNotFoundError:
        seen_ids = set()
        print("📚 Starting with empty seen IDs")

def save_seen_ids():
    """Save seen auction IDs to file"""
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_ids), f)
        print(f"💾 Saved {len(seen_ids)} seen auction IDs")
    except Exception as e:
        print(f"⚠️ Could not save seen IDs: {e}")

def generate_intelligent_keywords():
    """Generate focused keywords for high-quality brands"""
    keywords = []
    
    # Priority brands with specific searches
    priority_searches = [
        "raf simons", "raf simons shirt", "raf simons jacket",
        "rick owens", "rick owens drkshdw", "rick owens jacket",
        "maison margiela", "margiela", "margiela jacket",
        "jean paul gaultier", "gaultier jacket",
        "undercover", "undercover jacket", "undercover shirt",
        "yohji yamamoto", "yamamoto jacket",
        "junya watanabe", "junya jacket",
        "martine rose", "martine rose shirt",
        "comme des garcons", "cdg shirt"
    ]
    
    keywords.extend(priority_searches)
    
    # Add Japanese variants
    japanese_keywords = [
        "ラフシモンズ", "リックオウエンス", "マルジェラ",
        "ジャンポールゴルチエ", "アンダーカバー", "ヨウジヤマモト"
    ]
    
    keywords.extend(japanese_keywords)
    
    # Shuffle for variety
    random.shuffle(keywords)
    
    return keywords[:20]  # Limit to 20 keywords per cycle

def main_loop():
    """Enhanced main loop with better logging and error handling"""
    print("🚀 Yahoo Auction Sniper v2.0 Starting...")
    print("✨ Enhanced Features:")
    print("   - NEW Excluded Keywords: LEGO, Water Tank, BMW E91, Mazda, Band of Outsiders")
    print("   - STRICT JDirectItems Category Filtering (Fashion Only)")
    print("   - Improved Price Filtering (less aggressive)")
    print("   - Enhanced Spam Detection")
    print(f"💰 Price Range: ${MIN_PRICE_USD} - ${MAX_PRICE_USD}")
    print(f"🎯 Quality Threshold: {PRICE_QUALITY_THRESHOLD:.1%}")
    print(f"💾 Currently tracking {len(seen_ids)} seen items")
    
    # Start health server
    threading.Thread(target=run_health_server, daemon=True).start()
    
    get_usd_jpy_rate()
    
    try:
        iteration = 0
        while True:
            iteration += 1
            start_time = datetime.now()
            print(f"\n🔄 Starting iteration {iteration} at {start_time.strftime('%H:%M:%S')}")
            
            keywords = generate_intelligent_keywords()
            total_found = 0
            quality_filtered = 0
            sent_to_discord = 0
            total_errors = 0
            
            for i, kw in enumerate(keywords, 1):
                print(f"\n🔍 [{i}/{len(keywords)}] Searching: {kw}")
                
                listings, errors = search_yahoo_enhanced(kw, max_pages=2)
                total_found += len(listings)
                total_errors += errors
                
                for listing_data in listings:
                    quality_filtered += 1
                    
                    success = send_to_discord_bot(listing_data)
                    
                    if success:
                        seen_ids.add(listing_data["auction_id"])
                        sent_to_discord += 1
                        priority_emoji = "🔥" if listing_data["priority"] >= 100 else "🌟" if listing_data["priority"] >= 70 else "✨"
                        print(f"{priority_emoji} FIND: {listing_data['brand']} - {listing_data['title'][:40]}... - ¥{listing_data['price_jpy']:,} (${listing_data['price_usd']:.2f}) - {listing_data['deal_quality']:.1%} deal")
                    
                    time.sleep(0.5)
                
                # Brief pause between keywords
                time.sleep(2)
            
            save_seen_ids()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n📊 Iteration {iteration} Summary:")
            print(f"⏱️  Duration: {duration:.1f}s")
            print(f"🔍 Keywords searched: {len(keywords)}")
            print(f"📊 Total found: {total_found}")
            print(f"✅ Quality filtered: {quality_filtered}")
            print(f"📤 Sent to Discord: {sent_to_discord}")
            print(f"❌ Errors: {total_errors}")
            
            efficiency = sent_to_discord / max(1, total_found) if total_found > 0 else 0
            print(f"⚡ Efficiency: {efficiency:.1%} (sent/found)")
            
            print(f"⏳ Iteration complete. Sleeping for 5 minutes...")
            time.sleep(300)  # 5 minutes
            
    except KeyboardInterrupt:
        save_seen_ids()
        print("✅ Exiting gracefully.")

if __name__ == "__main__":
    load_seen_ids()
    BRAND_DATA = load_brand_data()
    main_loop()
