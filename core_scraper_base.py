#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core infrastructure for specialized Yahoo Japan scrapers
Shared functionality for all 4 scraper services
"""

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
import random

# Import enhanced filtering system
from enhancedfiltering import EnhancedSpamDetector, QualityChecker

class YahooScraperBase:
    def __init__(self, scraper_name):
        self.scraper_name = scraper_name
        self.seen_file = f"seen_{scraper_name}.json"
        self.scraper_db = "auction_tracking.db"

        # Discord Bot Integration
        self.discord_bot_url = os.getenv('DISCORD_BOT_URL', 'https://motivated-stillness-production.up.railway.app')
        if self.discord_bot_url and not self.discord_bot_url.startswith(('http://', 'https://')):
            self.discord_bot_url = f"https://{self.discord_bot_url}"

        # Exchange rate
        self.current_usd_jpy_rate = 147.0
        self.seen_ids = self.load_seen_items()

        # Brand data
        self.brand_data = self.load_brand_data()

        # Enhanced filtering system (integrated from enhancedfiltering.py)
        self.spam_detector = EnhancedSpamDetector()
        self.quality_checker = QualityChecker()

        # Filtering statistics for analytics
        self.stats = {
            'total_processed': 0,
            'spam_blocked': 0,
            'clothing_blocked': 0,
            'price_blocked': 0,
            'quality_blocked': 0,
            'sent': 0
        }

        # Flask health server
        self.app = Flask(__name__)
        self.setup_health_routes()

        print(f"🚀 {scraper_name} initialized")
        print(f"🛡️ Enhanced spam detector loaded")
        print(f"📊 Quality checker initialized")
    
    def setup_health_routes(self):
        @self.app.route('/health', methods=['GET'])
        def health():
            return {"status": "healthy", "service": self.scraper_name}, 200
            
        @self.app.route('/', methods=['GET'])
        def root():
            return {"service": f"Yahoo {self.scraper_name}", "status": "running"}, 200
    
    def run_health_server(self):
        port = int(os.environ.get('PORT', 8000))
        self.app.run(host='0.0.0.0', port=port, debug=False)
    
    def load_seen_items(self):
        try:
            if os.path.exists(self.seen_file):
                with open(self.seen_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            print(f"⚠️ Could not load seen items: {e}")
            return set()
    
    def save_seen_items(self):
        try:
            with open(self.seen_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_ids), f)
        except Exception as e:
            print(f"⚠️ Could not save seen items: {e}")
    
    def load_brand_data(self):
        try:
            if os.path.exists("brands.json"):
                with open("brands.json", 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.get_default_brands()
        except Exception as e:
            print(f"⚠️ Could not load brand data, using defaults: {e}")
            return self.get_default_brands()
    
    def get_default_brands(self):
        return {
            "Raf Simons": {"variants": ["raf simons", "raf", "ラフシモンズ"], "tier": 1},
            "Rick Owens": {"variants": ["rick owens", "rick", "リックオウエンス"], "tier": 1},
            "Maison Margiela": {"variants": ["margiela", "maison margiela", "メゾンマルジェラ"], "tier": 1},
            "Jean Paul Gaultier": {"variants": ["jean paul gaultier", "gaultier", "jpg", "ジャンポールゴルチエ"], "tier": 1},
            "Yohji Yamamoto": {"variants": ["yohji yamamoto", "yohji", "ヨウジヤマモト"], "tier": 2},
            "Junya Watanabe": {"variants": ["junya watanabe", "junya", "ジュンヤワタナベ"], "tier": 2},
            "Undercover": {"variants": ["undercover", "アンダーカバー"], "tier": 2},
            "Vetements": {"variants": ["vetements", "ヴェトモン"], "tier": 2},
            "Comme des Garcons": {"variants": ["comme des garcons", "cdg", "コムデギャルソン"], "tier": 3},
            "Martine Rose": {"variants": ["martine rose", "マルティーヌローズ"], "tier": 3},
            "Balenciaga": {"variants": ["balenciaga", "バレンシアガ"], "tier": 3},
            "Alyx": {"variants": ["alyx", "1017 alyx", "アリクス"], "tier": 3},
            "Celine": {"variants": ["celine", "セリーヌ"], "tier": 4},
            "Bottega Veneta": {"variants": ["bottega veneta", "bottega", "ボッテガヴェネタ"], "tier": 4},
            "Kiko Kostadinov": {"variants": ["kiko kostadinov", "kiko", "キコ"], "tier": 4},
            "Prada": {"variants": ["prada", "プラダ"], "tier": 5},
            "Miu Miu": {"variants": ["miu miu", "ミュウミュウ"], "tier": 5},
            "Chrome Hearts": {"variants": ["chrome hearts", "クロムハーツ"], "tier": 5}
        }
    
    def get_usd_jpy_rate(self):
        """Get current USD to JPY exchange rate"""
        try:
            response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.current_usd_jpy_rate = data['rates']['JPY']
                print(f"💱 Updated exchange rate: 1 USD = {self.current_usd_jpy_rate:.2f} JPY")
                return self.current_usd_jpy_rate
        except Exception as e:
            print(f"⚠️ Could not fetch exchange rate: {e}")
        
        return self.current_usd_jpy_rate
    
    def convert_jpy_to_usd(self, jpy_amount):
        """Convert JPY to USD using current exchange rate"""
        return jpy_amount / self.current_usd_jpy_rate
    
    def convert_usd_to_jpy(self, usd_amount):
        """Convert USD to JPY using current exchange rate"""
        return usd_amount * self.current_usd_jpy_rate
    
    def extract_auction_id_from_url(self, url):
        """Extract clean auction ID from Yahoo Japan URL"""
        try:
            auction_id = None
            
            # Method 1: Extract from /auction/ path
            if "/auction/" in url:
                auction_id = url.split("/auction/")[-1].split("?")[0]
            
            # Method 2: Extract from aID parameter
            elif "aID=" in url:
                auction_id = url.split("aID=")[-1].split("&")[0]
            
            # Method 3: Extract from URL segments
            else:
                url_parts = url.split("/")
                for part in reversed(url_parts):
                    if part and not part.startswith("?") and len(part) > 5:
                        auction_id = part.split("?")[0]
                        break
            
            if auction_id:
                # Clean up the auction ID - keep the 'u' prefix for ZenMarket
                auction_id = auction_id.strip()
                
                # Ensure the auction ID has the 'u' prefix for ZenMarket
                if not auction_id.startswith('u') and auction_id.isdigit():
                    auction_id = f"u{auction_id}"
                
                return auction_id
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error extracting auction ID from {url}: {e}")
            return None
    
    def build_search_url(self, keyword, page=1, fixed_type=3, sort_type="end", sort_order="a"):
        """
        Build Yahoo Japan search URL with all parameters
        
        Args:
            keyword: Search term
            page: Page number (1-based)
            fixed_type: 1=fixed price only, 2=auction only, 3=both
            sort_type: "end"=ending soon, "new"=newest, "price"=price
            sort_order: "a"=ascending, "d"=descending
        """
        base_url = "https://auctions.yahoo.co.jp/search/search"
        
        # Calculate starting position (Yahoo uses 1-based indexing)
        start_position = (page - 1) * 100 + 1
        
        params = {
            'p': keyword,
            'va': keyword,  # Verified auction parameter
            'fixed': str(fixed_type),
            'is_postage_mode': '1',
            'dest_pref_code': '13',  # Tokyo prefecture for shipping
            'b': str(start_position),
            'n': '100',  # 100 items per page
            'ei': 'utf-8'
        }
        
        # Add sorting parameters
        if sort_type == "end":
            params['s1'] = 'end'
            params['o1'] = sort_order
        elif sort_type == "new":
            params['s1'] = 'new' 
            params['o1'] = sort_order
        elif sort_type == "price":
            params['s1'] = 'cbids'
            params['o1'] = sort_order
        
        # Enhanced price filters (lowered minimum, increased maximum)
        min_price_jpy = int(3 * self.current_usd_jpy_rate)  # Lowered from $5 to $3
        max_price_jpy = int(1500 * self.current_usd_jpy_rate)  # Increased from $1000 to $1500
        params['aucminprice'] = str(min_price_jpy)
        params['aucmaxprice'] = str(max_price_jpy)
        
        param_string = '&'.join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
        return f"{base_url}?{param_string}"
    
    def extract_auction_data(self, item):
        """Extract auction data from BeautifulSoup item"""
        try:
            self.stats['total_processed'] += 1

            # Get auction link and ID
            link_tag = item.select_one("a.Product__titleLink")
            if not link_tag:
                return None

            link = link_tag.get('href', '')
            if not link.startswith("http"):
                link = "https://auctions.yahoo.co.jp" + link

            # Get auction ID using improved extraction
            auction_id = self.extract_auction_id_from_url(link)
            if not auction_id or auction_id in self.seen_ids:
                return None

            # Debug: Print the auction ID and URL for troubleshooting
            print(f"🔍 Extracted auction ID: '{auction_id}' from URL: {link}")

            # Get title
            title = link_tag.get_text(strip=True)
            if not title:
                return None

            # Detect brand early for spam detection
            brand = self.detect_brand_in_title(title)

            # ENHANCED spam filtering using EnhancedSpamDetector
            is_spam, spam_type = self.spam_detector.is_spam(title, brand, item, "", link)
            if is_spam:
                self.stats['spam_blocked'] += 1
                print(f"🚫 Spam blocked ({spam_type}): {title[:50]}...")
                return None

            # Clothing check (less aggressive now)
            if not self.is_clothing_item(title):
                self.stats['clothing_blocked'] += 1
                print(f"🚫 Clothing filter blocked: {title[:50]}...")
                return None
            
            # Get price
            price_tag = item.select_one(".Product__priceValue")
            if not price_tag:
                return None
                
            price_text = price_tag.get_text(strip=True)
            price_jpy = self.extract_price_from_text(price_text)
            if not price_jpy:
                return None
            
            price_usd = price_jpy / self.current_usd_jpy_rate
            
            # Get image
            img_tag = item.select_one("img")
            image_url = img_tag.get('src', '') if img_tag else ''
            
            # Get end time (for auctions only)
            end_time = None
            end_tag = item.select_one(".Product__time")
            if end_tag:
                end_time = self.parse_end_time(end_tag.get_text(strip=True))
            
            # Detect brand
            brand = self.detect_brand_in_title(title)
            
            # Get seller info
            seller_id = self.extract_seller_info(item)
            
            # Calculate deal quality (keep for scoring but don't filter)
            deal_quality = self.calculate_deal_quality(price_usd, brand, title)
            
            # Build correct ZenMarket URL
            # ZenMarket format: https://zenmarket.jp/en/auction.aspx?itemCode=u[auction_id]
            # The auction_id now includes the 'u' prefix
            zenmarket_url = f"https://zenmarket.jp/en/auction.aspx?itemCode={auction_id}"
            
            # Debug: Print the ZenMarket URL for verification
            print(f"🔗 ZenMarket URL: {zenmarket_url}")
            
            return {
                'auction_id': auction_id,
                'title': title,
                'brand': brand,
                'price_jpy': price_jpy,
                'price_usd': round(price_usd, 2),
                'deal_quality': deal_quality,
                'yahoo_url': link,
                'zenmarket_url': zenmarket_url,
                'image_url': image_url,
                'seller_id': seller_id,
                'end_time': end_time,
                'found_at': datetime.now(timezone.utc).isoformat(),
                'scraper_source': self.scraper_name
            }
            
        except Exception as e:
            print(f"❌ Error extracting auction data: {e}")
            return None
    
    def is_enhanced_spam(self, title, brand=None):
        """Enhanced spam detection with new exclusions and JDirectItems filtering"""
        title_lower = title.lower()
        
        # NEW HIGH PRIORITY EXCLUSIONS
        new_excluded_keywords = {
            "LEGO", "レゴ",  # LEGO blocks
            "Water Tank", "ウォータータンク", "水タンク",  # Water tanks
            "BMW Touring E91", "BMW E91", "E91",  # BMW car parts
            "Mazda", "マツダ",  # Mazda car parts
            "Band of Outsiders", "バンドオブアウトサイダーズ"  # Unwanted brand
        }
        
        for excluded in new_excluded_keywords:
            if excluded.lower() in title_lower:
                print(f"🚫 NEW EXCLUSION BLOCKED: {excluded}")
                return True
        
        # STRICT JDirectItems FILTERING
        if "jdirectitems" in title_lower:
            # Extract category using regex pattern
            import re
            pattern = r'jdirectitems auction.*?→\s*([^,\n]+)'
            match = re.search(pattern, title_lower)
            if match:
                category = match.group(1).strip().lower()
                
                # Only allow fashion-related categories
                allowed_categories = {
                    "fashion", "clothing", "apparel", 
                    "ファッション", "衣類", "服", "洋服"
                }
                
                if not any(allowed in category for allowed in allowed_categories):
                    print(f"🚫 JDirectItems NON-FASHION BLOCKED: {category}")
                    return True
                else:
                    print(f"✅ JDirectItems FASHION ALLOWED: {category}")
        
        # EXISTING EXCLUSIONS (enhanced)
        existing_excluded_items = {
            "perfume", "cologne", "fragrance", "香水", "watch", "時計", 
            "motorcycle", "engine", "エンジン", "cb400", "vtr250",
            "server", "raid", "pci", "computer", "食品", "food", "snack",
            "財布", "バッグ", "鞄", "カバン", "poster", "ポスター", 
            "sticker", "ステッカー", "magazine", "雑誌", "dvd", "book",
            "本", "figure", "フィギュア", "toy", "おもちゃ"
        }
        
        for excluded in existing_excluded_items:
            if excluded in title_lower:
                print(f"🚫 EXISTING EXCLUSION BLOCKED: {excluded}")
                return True
        
        return False
    
    def is_clothing_item(self, title):
        """Less restrictive clothing detection - allow more items through"""
        title_lower = title.lower()

        # Expanded clothing keywords for better coverage
        clothing_keywords = {
            # English keywords
            "shirt", "tee", "tshirt", "t-shirt", "jacket", "blazer", "coat", "parka",
            "pants", "trousers", "jeans", "denim", "hoodie", "sweatshirt", "sweater",
            "dress", "skirt", "shorts", "vest", "cardigan", "pullover", "knit",
            "top", "bottom", "wear", "outerwear", "innerwear", "clothing", "apparel",
            "suit", "blazer", "overcoat", "windbreaker", "bomber", "leather",
            "cargo", "chino", "jogger", "sweatpants", "tracksuit", "jersey",
            "polo", "henley", "tank", "sleeveless", "longsleeve", "crewneck",
            "boots", "shoes", "sneakers", "sandals", "loafers", "oxfords",

            # Japanese keywords (comprehensive)
            "シャツ", "Tシャツ", "ジャケット", "コート", "パンツ", "ジーンズ",
            "パーカー", "スウェット", "セーター", "ワンピース", "スカート",
            "ベスト", "カーディガン", "プルオーバー", "アウター", "インナー",
            "トップス", "ボトムス", "ウェア", "服", "衣類", "洋服",
            "デニム", "ニット", "スーツ", "ブレザー", "オーバーコート",
            "ボンバー", "レザー", "カーゴ", "チノ", "ジョガー",
            "ポロ", "タンクトップ", "長袖", "半袖", "クルーネック",
            "ブーツ", "シューズ", "スニーカー", "サンダル", "ローファー"
        }

        # Check for any clothing keyword
        for keyword in clothing_keywords:
            if keyword in title_lower:
                return True

        # LESS RESTRICTIVE: Allow items from known fashion brands even without keywords
        # If it's from a recognized brand, assume it's clothing
        brand = self.detect_brand_in_title(title)
        if brand != "Unknown":
            print(f"✅ Allowing brand item without clothing keyword: {brand}")
            return True

        # Default to ALLOWING (changed from blocking) - trust spam filter to catch non-fashion
        return True
    
    def extract_price_from_text(self, price_text):
        """Extract numeric price from price text"""
        price_match = re.search(r'([\d,]+)', price_text.replace(',', ''))
        if price_match:
            try:
                return int(price_match.group(1).replace(',', ''))
            except ValueError:
                return None
        return None
    
    def parse_end_time(self, time_text):
        """Parse auction end time from Japanese text"""
        try:
            # This would need proper Japanese time parsing
            # For now, return a placeholder
            return time_text
        except Exception:
            return None
    
    def detect_brand_in_title(self, title):
        """Detect brand in title"""
        title_lower = title.lower()
        
        for brand, brand_info in self.brand_data.items():
            for variant in brand_info.get('variants', []):
                if variant.lower() in title_lower:
                    return brand
        
        return "Unknown"
    
    def extract_seller_info(self, item):
        """Extract seller information"""
        try:
            seller_link = item.select_one("a[href*='sellerID']")
            if seller_link:
                href = seller_link.get('href', '')
                seller_match = re.search(r'sellerID=([^&]+)', href)
                if seller_match:
                    return seller_match.group(1)
            return "unknown"
        except Exception:
            return "unknown"
    
    def calculate_deal_quality(self, price_usd, brand, title):
        """Enhanced deal quality scoring with more generous thresholds"""
        title_lower = title.lower()
        quality = 0.2  # Higher base quality (was 0.1)
        
        # Enhanced brand quality boost (more generous)
        premium_brands = ["Raf Simons", "Rick Owens", "Maison Margiela", "Jean Paul Gaultier"]
        high_tier_brands = ["Yohji Yamamoto", "Junya Watanabe", "Undercover", "Vetements"]
        mid_tier_brands = ["Comme des Garcons", "Martine Rose", "Balenciaga", "Alyx"]
        
        if brand in premium_brands:
            quality += 0.4  # Increased from 0.3
        elif brand in high_tier_brands:
            quality += 0.3  # Increased from 0.2
        elif brand in mid_tier_brands:
            quality += 0.25  # New tier
        else:
            quality += 0.15  # Increased from 0.1
        
        # More generous price quality boost
        if price_usd <= 80:  # Lowered from 100
            quality += 0.35  # Increased from 0.3
        elif price_usd <= 150:  # Lowered from 200
            quality += 0.25  # Increased from 0.2
        elif price_usd <= 250:  # Lowered from 300
            quality += 0.15  # Increased from 0.1
        elif price_usd <= 400:  # New tier
            quality += 0.1
        
        # Archive/rare keywords (enhanced)
        archive_keywords = ["archive", "rare", "fw", "ss", "limited", "vintage", "deadstock", "sample"]
        if any(word in title_lower for word in archive_keywords):
            quality += 0.25  # Increased from 0.2
        
        # Size bonus (common sizes get slight boost)
        size_keywords = ["m", "l", "medium", "large", "28", "30", "32", "34", "36"]
        if any(word in title_lower for word in size_keywords):
            quality += 0.05
        
        return min(quality, 1.0)
    
    def send_to_discord(self, auction_data):
        """Send auction data to Discord via webhook"""
        try:
            webhook_url = f"{self.discord_bot_url}/webhook/listing"

            # Debug logging
            print(f"🔗 Attempting to send to: {webhook_url}")
            print(f"📦 Data includes scraper_source: {auction_data.get('scraper_source', 'NOT SET')}")

            # Ensure scraper_source is set for proper Discord bot routing
            if 'scraper_source' not in auction_data:
                auction_data['scraper_source'] = self.scraper_name

            response = requests.post(webhook_url, json=auction_data, timeout=10)

            print(f"📡 Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"📄 Response content: {response.text[:200]}...")

            if response.status_code in [200, 204]:
                self.stats['sent'] += 1  # Track successful sends
                print(f"✅ Sent to Discord bot: {auction_data['title'][:50]}...")
                return True
            else:
                print(f"❌ Discord webhook failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Discord webhook error: {e}")
            return False
    
    def determine_target_channels(self, auction_data, primary_channel):
        """Determine which channels to send the listing to"""
        channels = [primary_channel]
        
        price_usd = auction_data['price_usd']
        brand = auction_data['brand']
        
        # Always send to main auction alerts
        if primary_channel != '🎯-auction-alerts':
            channels.append('🎯-auction-alerts')
        
        # Send to budget steals if ≤ $60
        if price_usd <= 60 and primary_channel != '💰-budget-steals':
            channels.append('💰-budget-steals')
        
        # Send to brand channel if brand detected
        if brand != "Unknown":
            brand_channel = f"🏷️-{brand.lower().replace(' ', '-')}"
            if brand_channel not in channels:
                channels.append(brand_channel)
        
        return channels
    
    def get_request_headers(self):
        """Get random headers for requests"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    def analyze_filtering(self):
        """Log filtering statistics for debugging and optimization"""
        print(f"\n📊 ===== {self.scraper_name.upper()} FILTERING STATISTICS =====")
        print(f"   Total items processed:    {self.stats['total_processed']}")
        print(f"   🚫 Blocked by spam:       {self.stats['spam_blocked']}")
        print(f"   🚫 Blocked by clothing:   {self.stats['clothing_blocked']}")
        print(f"   🚫 Blocked by price:      {self.stats['price_blocked']}")
        print(f"   🚫 Blocked by quality:    {self.stats['quality_blocked']}")
        print(f"   ✅ Sent to Discord:       {self.stats['sent']}")
        print(f"   📦 Seen IDs tracked:      {len(self.seen_ids)}")

        # Calculate percentages
        if self.stats['total_processed'] > 0:
            sent_rate = (self.stats['sent'] / self.stats['total_processed']) * 100
            spam_rate = (self.stats['spam_blocked'] / self.stats['total_processed']) * 100
            print(f"\n   📈 Send rate:             {sent_rate:.1f}%")
            print(f"   📉 Spam block rate:       {spam_rate:.1f}%")

        print(f"========================================\n")

    def cleanup_old_seen_ids(self):
        """Remove seen IDs older than retention period to prevent memory bloat"""
        try:
            current_size = len(self.seen_ids)

            # Aggressive cleanup if we're over 50,000 items
            if current_size > 50000:
                print(f"🧹 AGGRESSIVE CLEANUP: {current_size} seen_ids (>50,000 limit)")
                # Keep only most recent 10,000 items
                self.seen_ids = set(list(self.seen_ids)[-10000:])
                self.save_seen_items()
                new_size = len(self.seen_ids)
                print(f"✅ Cleaned from {current_size} to {new_size} items")

            # Normal cleanup if we're over 30,000 items
            elif current_size > 30000:
                print(f"🧹 NORMAL CLEANUP: {current_size} seen_ids (>30,000)")
                # Keep most recent 20,000 items
                self.seen_ids = set(list(self.seen_ids)[-20000:])
                self.save_seen_items()
                new_size = len(self.seen_ids)
                print(f"✅ Cleaned from {current_size} to {new_size} items")

        except Exception as e:
            print(f"⚠️ Error during seen_ids cleanup: {e}")
