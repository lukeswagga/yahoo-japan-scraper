import requests
from bs4 import BeautifulSoup
import time
import json
import os
import urllib.parse
from datetime import datetime, timezone
import re
import sqlite3
from flask import Flask
import threading
from enhanced_filtering import EnhancedSpamDetector
import statistics
import random

scraper_app = Flask(__name__)

@scraper_app.route('/health', methods=['GET'])
def health():
    return {"status": "healthy", "service": "auction-scraper"}, 200

@scraper_app.route('/', methods=['GET'])
def root():
    return {"service": "Yahoo Auction Scraper", "status": "running"}, 200

def run_health_server():
    port = int(os.environ.get('PORT', 8000))
    scraper_app.run(host='0.0.0.0', port=port, debug=False)

DISCORD_BOT_WEBHOOK = os.getenv('DISCORD_BOT_WEBHOOK', "http://localhost:8000/webhook")
DISCORD_BOT_HEALTH = os.getenv('DISCORD_BOT_HEALTH', "http://localhost:8000/health") 
DISCORD_BOT_STATS = os.getenv('DISCORD_BOT_STATS', "http://localhost:8000/stats")
USE_DISCORD_BOT = True

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1389882074097520740/k1NDpWtPt1q116RF0Ndf2DDLmYCtwGSUGZla7n9kVD5d2ZX-vVerVx4RROCpGiyEtHzu"
MAX_PRICE_YEN = 100000
SEEN_FILE = "seen_yahoo.json"
BRANDS_FILE = "brands.json"
EXCHANGE_RATE_FILE = "exchange_rate.json"
SCRAPER_DB = "auction_tracking.db"

MAX_PRICE_USD = 1200
MIN_PRICE_USD = 3
MAX_LISTINGS_PER_BRAND = 25
ONLY_BUY_IT_NOW = False
PRICE_QUALITY_THRESHOLD = 0.15
ENABLE_RESALE_BOOST = True
ENABLE_INTELLIGENT_FILTERING = True

BASE_URL = "https://auctions.yahoo.co.jp/search/search?p={}&n=50&b={}&s1=new&o1=d&minPrice=1&maxPrice={}"

exchange_rate_cache = {"rate": 150.0, "timestamp": 0}

class OptimizedTieredSystem:
    def __init__(self):
        self.tier_config = {
            'tier_1_premium': {
                'brands': ['Raf Simons', 'Rick Owens'],
                'max_keywords': 6,
                'max_pages': 4,
                'search_frequency': 1,
                'delay': 1.5,
                'max_listings': 8
            },
            'tier_1_high': {
                'brands': ['Maison Margiela', 'Jean Paul Gaultier'],
                'max_keywords': 5,
                'max_pages': 3,
                'search_frequency': 1,
                'delay': 2,
                'max_listings': 6
            },
            'tier_2': {
                'brands': ['Yohji Yamamoto', 'Junya Watanabe', 'Undercover', 'Vetements'],
                'max_keywords': 4,
                'max_pages': 2,
                'search_frequency': 2,
                'delay': 2.5,
                'max_listings': 5
            },
            'tier_3': {
                'brands': ['Comme Des Garcons', 'Martine Rose', 'Balenciaga', 'Alyx'],
                'max_keywords': 3,
                'max_pages': 2,
                'search_frequency': 3,
                'delay': 3,
                'max_listings': 4
            },
            'tier_4': {
                'brands': ['Celine', 'Bottega Veneta', 'Kiko Kostadinov'],
                'max_keywords': 2,
                'max_pages': 1,
                'search_frequency': 4,
                'delay': 4,
                'max_listings': 3
            },
            'tier_5_minimal': {
                'brands': ['Prada', 'Miu Miu', 'Chrome Hearts', 'Hysteric Glamour'],
                'max_keywords': 1,
                'max_pages': 1,
                'search_frequency': 6,
                'delay': 5,
                'max_listings': 2
            }
        }
        
        self.performance_tracker = {}
        for tier in self.tier_config.keys():
            self.performance_tracker[tier] = {
                'total_searches': 0,
                'successful_finds': 0,
                'last_find': None,
                'avg_efficiency': 0.0
            }
        
        self.iteration_counter = 0
        self.load_performance_data()
    
    def load_performance_data(self):
        try:
            with open('tier_performance.json', 'r') as f:
                self.performance_tracker = json.load(f)
        except FileNotFoundError:
            pass
    
    def save_performance_data(self):
        with open('tier_performance.json', 'w') as f:
            json.dump(self.performance_tracker, f, indent=2)
    
    def get_tier_for_brand(self, brand):
        for tier_name, config in self.tier_config.items():
            if brand in config['brands']:
                return tier_name, config
        return 'tier_5_minimal', self.tier_config['tier_5_minimal']
    
    def should_search_tier(self, tier_name):
        frequency = self.tier_config[tier_name]['search_frequency']
        return (self.iteration_counter % frequency) == 0
    
    def update_performance(self, tier_name, searches_made, finds_count):
        tracker = self.performance_tracker[tier_name]
        tracker['total_searches'] += searches_made
        tracker['successful_finds'] += finds_count
        
        if finds_count > 0:
            tracker['last_find'] = datetime.now().isoformat()
        
        if tracker['total_searches'] > 0:
            tracker['avg_efficiency'] = tracker['successful_finds'] / tracker['total_searches']
    
    def next_iteration(self):
        self.iteration_counter += 1

class AdaptiveKeywordManager:
    def __init__(self):
        self.keyword_performance = {}
        self.brand_keyword_success = {}
        self.dead_keywords = set()
        self.hot_keywords = set()
        self.load_keyword_data()
    
    def load_keyword_data(self):
        try:
            with open('keyword_performance.json', 'r') as f:
                data = json.load(f)
                self.keyword_performance = data.get('keyword_performance', {})
                self.brand_keyword_success = data.get('brand_keyword_success', {})
                self.dead_keywords = set(data.get('dead_keywords', []))
                self.hot_keywords = set(data.get('hot_keywords', []))
        except FileNotFoundError:
            pass
    
    def save_keyword_data(self):
        data = {
            'keyword_performance': self.keyword_performance,
            'brand_keyword_success': self.brand_keyword_success,
            'dead_keywords': list(self.dead_keywords),
            'hot_keywords': list(self.hot_keywords),
            'last_updated': datetime.now().isoformat()
        }
        with open('keyword_performance.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_keyword_result(self, keyword, brand, finds_count, search_time):
        if keyword not in self.keyword_performance:
            self.keyword_performance[keyword] = {
                'searches': 0, 'finds': 0, 'avg_time': 0.0, 'consecutive_fails': 0
            }
        
        perf = self.keyword_performance[keyword]
        perf['searches'] += 1
        perf['finds'] += finds_count
        perf['avg_time'] = (perf['avg_time'] + search_time) / 2
        
        if finds_count > 0:
            perf['consecutive_fails'] = 0
            self.hot_keywords.add(keyword)
            self.dead_keywords.discard(keyword)
            
            if brand not in self.brand_keyword_success:
                self.brand_keyword_success[brand] = {}
            self.brand_keyword_success[brand][keyword] = self.brand_keyword_success[brand].get(keyword, 0) + finds_count
        else:
            perf['consecutive_fails'] += 1
            if perf['consecutive_fails'] >= 8:
                self.dead_keywords.add(keyword)
                self.hot_keywords.discard(keyword)
    
    def get_best_keywords_for_brand(self, brand, max_count):
        brand_keywords = self.brand_keyword_success.get(brand, {})
        
        if brand_keywords:
            sorted_keywords = sorted(brand_keywords.items(), key=lambda x: x[1], reverse=True)
            best_keywords = [kw for kw, count in sorted_keywords[:max_count] if kw not in self.dead_keywords]
            if best_keywords:
                return best_keywords
        
        return self.generate_fallback_keywords(brand, max_count)
    
    def generate_fallback_keywords(self, brand, max_count):
        if brand not in BRAND_DATA:
            return [brand.lower()]
        
        brand_info = BRAND_DATA[brand]
        primary_variant = brand_info['variants'][0]
        
        fallback_keywords = [
            primary_variant,
            f"{primary_variant} archive",
            f"{primary_variant} jacket",
            f"{primary_variant} shirt",
            f"{primary_variant} rare",
            f"{primary_variant} vintage"
        ]
        
        if len(brand_info['variants']) > 1:
            fallback_keywords.append(brand_info['variants'][1])
        
        return fallback_keywords[:max_count]

def load_brand_data():
    try:
        with open(BRANDS_FILE, "r", encoding="utf-8") as f:
            brand_data = json.load(f)
            
        filtered_data = {}
        for brand_key, brand_info in brand_data.items():
            brand_lower = brand_key.lower()
            excluded_brands = {"undercoverism"}
            if not any(excluded in brand_lower for excluded in excluded_brands):
                filtered_data[brand_key] = brand_info
            else:
                print(f"🚫 Excluding brand: {brand_key}")
                
        return filtered_data
        
    except FileNotFoundError:
        print(f"❌ {BRANDS_FILE} not found")
        return {}

BRAND_DATA = load_brand_data()
seen_ids = set(json.load(open(SEEN_FILE))) if os.path.exists(SEEN_FILE) else set()

def save_seen_ids():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)

def load_exchange_rate():
    global exchange_rate_cache
    try:
        if os.path.exists(EXCHANGE_RATE_FILE):
            with open(EXCHANGE_RATE_FILE, "r") as f:
                exchange_rate_cache = json.load(f)
    except Exception as e:
        print(f"Error loading exchange rate: {e}")

def save_exchange_rate():
    try:
        with open(EXCHANGE_RATE_FILE, "w") as f:
            json.dump(exchange_rate_cache, f)
    except Exception as e:
        print(f"Error saving exchange rate: {e}")

def get_usd_jpy_rate():
    global exchange_rate_cache
    current_time = time.time()
    
    if current_time - exchange_rate_cache.get("timestamp", 0) < 3600:
        return exchange_rate_cache["rate"]
    
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rate = data["rates"]["JPY"]
            if rate and 100 < rate < 200:
                exchange_rate_cache = {"rate": float(rate), "timestamp": current_time}
                save_exchange_rate()
                print(f"✅ Updated exchange rate: 1 USD = {rate:.2f} JPY")
                return rate
    except Exception as e:
        print(f"Failed to get exchange rate: {e}")
    
    fallback_rate = exchange_rate_cache.get("rate", 150.0)
    print(f"⚠️  Using fallback exchange rate: 1 USD = {fallback_rate:.2f} JPY")
    return fallback_rate

def convert_jpy_to_usd(jpy_amount):
    rate = get_usd_jpy_rate()
    return jpy_amount / rate

def check_discord_bot_health():
    try:
        response = requests.get(DISCORD_BOT_HEALTH, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("bot_ready") and data.get("guild_connected"):
                return True, "Bot healthy"
            else:
                return False, f"Bot not ready: {data}"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, f"Connection error: {e}"

def log_scraper_stats(total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched):
    try:
        conn = sqlite3.connect(SCRAPER_DB)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_found INTEGER DEFAULT 0,
                quality_filtered INTEGER DEFAULT 0,
                sent_to_discord INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                keywords_searched INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            INSERT INTO scraper_stats 
            (total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched)
            VALUES (?, ?, ?, ?, ?)
        ''', (total_found, quality_filtered, sent_to_discord, errors_count, keywords_searched))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Could not log scraper stats: {e}")

def check_if_auction_exists_in_db(auction_id):
    try:
        conn = sqlite3.connect(SCRAPER_DB)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS scraped_items (auction_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('SELECT auction_id FROM scraped_items WHERE auction_id = ?', (auction_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False

def add_to_scraper_db(auction_id):
    try:
        conn = sqlite3.connect(SCRAPER_DB)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS scraped_items (auction_id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        cursor.execute('INSERT OR IGNORE INTO scraped_items (auction_id) VALUES (?)', (auction_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Could not add to scraper DB: {e}")
        return False

EXCLUDED_ITEMS = {
    "perfume", "cologne", "fragrance", "香水",
    "watch", "時計", 
    "motorcycle", "engine", "エンジン", "cb400", "vtr250",
    "server", "raid", "pci", "computer",
    "食品", "food", "snack", "チップ",
    "財布", "バッグ", "鞄", "カバン", "ハンドバッグ", "トートバッグ", "クラッチ", "ポーチ",
    "香水", "フレグランス", "コロン", "スプレー",
    "時計", "ネックレス", "ブレスレット", "指輪", "イヤリング",
    "ベルト", "ネクタイ", "スカーフ", "手袋", "帽子", "キャップ", "ビーニー",
    "chip", "chips", "チップ", "スナック", "食品", "food", "snack",
    "poster", "ポスター", "sticker", "ステッカー", "magazine", "雑誌",
    "dvd", "book", "本", "figure", "フィギュア", "toy", "おもちゃ",
    "phone case", "ケース", "iphone", "samsung", "tech", "電子",
    "fred perry", "フレッドペリー"
}

CLOTHING_KEYWORDS = {
    "shirt", "tee", "tshirt", "t-shirt", "polo", "button-up", "dress shirt",
    "jacket", "blazer", "coat", "outerwear", "bomber", "varsity", "denim jacket",
    "pants", "trousers", "jeans", "chinos", "slacks", "cargo", "sweatpants",
    "hoodie", "sweatshirt", "pullover", "sweater", "jumper", "cardigan",
    "dress", "gown", "midi", "maxi", "mini dress", "cocktail dress",
    "skirt", "mini skirt", "pencil skirt", "pleated", "a-line",
    "shorts", "bermuda", "cargo shorts", "denim shorts",
    "tank top", "vest", "camisole", "blouse", "top",
    "シャツ", "Tシャツ", "ポロシャツ", "ブラウス", "トップス",
    "ジャケット", "ブレザー", "コート", "アウター", "ボンバー",
    "パンツ", "ズボン", "ジーンズ", "チノパン", "スラックス",
    "パーカー", "スウェット", "プルオーバー", "セーター", "ニット",
    "ワンピース", "ドレス", "ガウン", "ミディ", "マキシ",
    "スカート", "ミニスカート", "ペンシル", "プリーツ",
    "ショーツ", "ショートパンツ", "タンクトップ", "ベスト"
}

EXCLUDED_BRANDS = {
    "thrasher", "gap", "adidas", "uniqlo", "gu", "zara", "h&m",
    "スラッシャー", "シュプリーム", "ナイキ", "アディダス", "ユニクロ"
}

COMPLETELY_EXCLUDED_BRANDS = {
    "undercoverism"
}

def is_clothing_item(title):
    title_lower = title.lower()
    
    for excluded in EXCLUDED_ITEMS:
        if excluded in title_lower:
            return False
    
    for clothing_word in CLOTHING_KEYWORDS:
        if clothing_word in title_lower:
            return True
    
    return True

def calculate_resale_value_boost(title, brand, price_usd):
    title_lower = title.lower()
    boost = 0.0
    
    archive_keywords = [
        "archive", "rare", "vintage", "fw", "ss", "runway", "campaign",
        "limited", "exclusive", "sample", "prototype", "deadstock",
        "アーカイブ", "レア", "ヴィンテージ", "限定", "サンプル",
        "collaboration", "collab", "コラボ"
    ]
    
    for keyword in archive_keywords:
        if keyword in title_lower:
            boost += 0.4
            print(f"🔥 Archive boost: {keyword} found in {title[:30]}...")
            break
            
    brand_lower = brand.lower() if brand else ""
    
    if "raf" in brand_lower:
        if any(word in title_lower for word in ["tee", "t-shirt", "shirt", "シャツ", "Tシャツ"]):
            boost += 0.4
            print(f"🌟 Raf Simons tee boost: {title[:30]}...")
        elif any(word in title_lower for word in ["jacket", "hoodie", "sweater", "pants"]):
            boost += 0.25
    elif "rick" in brand_lower:
        boost += 0.2
    elif any(designer in brand_lower for designer in ["margiela", "gaultier", "yohji", "junya"]):
        boost += 0.15
    
    collab_keywords = ["collaboration", "collab", "x ", " x ", "コラボ"]
    for keyword in collab_keywords:
        if keyword in title_lower:
            boost += 0.2
            break
    
    size_keywords = ["xl", "xxl", "large", "l ", "50", "52", "54"]
    for size in size_keywords:
        if size in title_lower:
            boost += 0.05
            break
    
    return min(boost, 0.8)

def calculate_deal_quality(price_usd, brand, title):
    title_lower = title.lower()
    
    if any(word in title_lower for word in ["tee", "t-shirt", "シャツ", "Tシャツ"]):
        base_price = 40
        item_type = "tee"
    elif any(word in title_lower for word in ["shirt", "button", "dress shirt"]):
        base_price = 60
        item_type = "shirt"
    elif any(word in title_lower for word in ["jacket", "blazer", "ジャケット"]):
        base_price = 120
        item_type = "jacket"
    elif any(word in title_lower for word in ["coat", "outerwear", "コート"]):
        base_price = 150
        item_type = "coat"
    elif any(word in title_lower for word in ["hoodie", "sweatshirt", "パーカー"]):
        base_price = 80
        item_type = "hoodie"
    elif any(word in title_lower for word in ["pants", "trousers", "jeans", "パンツ"]):
        base_price = 80
        item_type = "pants"
    else:
        base_price = 60
        item_type = "other"
    
    brand_multipliers = {
        "raf_simons": 2.0,
        "rick_owens": 1.8,
        "maison_margiela": 1.7,
        "jean_paul_gaultier": 1.6,
        "yohji_yamamoto": 1.5,
        "junya_watanabe": 1.4,
        "comme_des_garcons": 1.3,
        "undercover": 1.2,
        "martine_rose": 1.3,
        "miu_miu": 1.1,
        "vetements": 1.2,
        "balenciaga": 1.1,
        "chrome_hearts": 1.2,
        "celine": 1.0,
        "bottega_veneta": 1.0,
        "alyx": 1.1,
        "kiko_kostadinov": 1.1,
        "prada": 1.0,
        "hysteric_glamour": 0.9
    }
    
    brand_key = brand.lower().replace(" ", "_") if brand else "unknown"
    brand_multiplier = brand_multipliers.get(brand_key, 1.0)
    market_price = base_price * brand_multiplier
    
    if price_usd >= market_price * 1.5:
        base_quality = 0.2
    elif price_usd >= market_price:
        base_quality = 0.5
    else:
        base_quality = min(1.0, 0.8 + (market_price - price_usd) / market_price)
    
    resale_boost = calculate_resale_value_boost(title, brand, price_usd)
    final_quality = min(1.0, base_quality + resale_boost)
    
    return max(0.0, final_quality)

def is_quality_listing(price_usd, brand, title):
    if price_usd < MIN_PRICE_USD or price_usd > MAX_PRICE_USD:
        return False, f"Price ${price_usd:.2f} outside range ${MIN_PRICE_USD}-{MAX_PRICE_USD}"
    
    if not is_clothing_item(title):
        return False, f"Not clothing item"
    
    deal_quality = calculate_deal_quality(price_usd, brand, title)
    
    brand_key = brand.lower().replace(" ", "_") if brand else "unknown"
    high_resale_brands = ["raf_simons", "rick_owens", "maison_margiela", "jean_paul_gaultier", "martine_rose"]
    
    if any(hrb in brand_key for hrb in high_resale_brands):
        threshold = 0.1
    else:
        threshold = PRICE_QUALITY_THRESHOLD
    
    if deal_quality < threshold:
        return False, f"Deal quality {deal_quality:.1%} below threshold {threshold:.1%}"
    
    return True, f"Quality listing: {deal_quality:.1%} deal quality"

def is_valid_brand_item(title):
    title_lower = title.lower()
    
    brand_match = False
    matched_brand = None
    for brand, details in BRAND_DATA.items():
        for variant in details["variants"]:
            if variant.lower() in title_lower:
                brand_match = True
                matched_brand = brand
                break
        if brand_match:
            break
    
    if not brand_match:
        return False, None
    
    for excluded in COMPLETELY_EXCLUDED_BRANDS:
        if excluded.lower() in matched_brand.lower():
            return False, None
    
    for excluded in EXCLUDED_BRANDS:
        if excluded.lower() in title_lower:
            return False, None
    
    if not is_clothing_item(title):
        return False, None
    
    return True, matched_brand

def calculate_listing_priority(listing_data):
    price_usd = listing_data["price_usd"]
    deal_quality = listing_data["deal_quality"]
    title = listing_data["title"].lower()
    brand = listing_data["brand"].lower()
    
    priority = deal_quality * 100
    
    if any(hrb in brand for hrb in ["raf_simons", "rick_owens", "margiela", "martine_rose"]):
        priority += 30
    
    if price_usd <= 100:
        priority += 25
    elif price_usd <= 200:
        priority += 15
    
    if any(word in title for word in ["archive", "rare", "fw", "ss", "アーカイブ", "レア"]):
        priority += 30
    
    if "raf" in brand and any(word in title for word in ["tee", "t-shirt", "shirt"]):
        priority += 25
    
    return priority

def extract_seller_info(soup, item):
    try:
        seller_link = item.select_one("a[href*='sellerID']")
        if seller_link:
            href = seller_link.get('href', '')
            seller_match = re.search(r'sellerID=([^&]+)', href)
            if seller_match:
                return seller_match.group(1)
        
        seller_span = item.select_one(".Product__seller")
        if seller_span:
            return seller_span.get_text(strip=True)
        
        return "unknown"
        
    except Exception:
        return "unknown"

def search_yahoo_multi_page_optimized(keyword_combo, max_pages, brand, keyword_manager):
    """Multi-page search with intelligent stopping and performance tracking"""
    
    start_time = time.time()
    all_listings = []
    total_errors = 0
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    spam_detector = EnhancedSpamDetector()
    
    for page in range(1, max_pages + 1):
        try:
            encoded_kw = urllib.parse.quote(keyword_combo)
            url = BASE_URL.format(encoded_kw, page, MAX_PRICE_YEN)
            
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"❌ HTTP {resp.status_code} for {keyword_combo} page {page}")
                total_errors += 1
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.Product")
            
            if len(items) < 10 and page > 1:
                print(f"🔚 Page {page} for '{keyword_combo}' has few items ({len(items)}), stopping pagination")
                break
            
            page_listings = []
            page_quality_count = 0
            skipped_seen = 0
            skipped_db = 0
            skipped_spam = 0
            
            for item in items:
                try:
                    link_tag = item.select_one("a.Product__titleLink")
                    if not link_tag:
                        continue
                        
                    link = link_tag["href"]
                    if not link.startswith("http"):
                        link = "https://auctions.yahoo.co.jp" + link
                        
                    title = link_tag.get_text(strip=True)
                    auc_id = link.split("/")[-1].split("?")[0]
                    
                    if auc_id in seen_ids:
                        skipped_seen += 1
                        continue
                    
                    if check_if_auction_exists_in_db(auc_id):
                        skipped_db += 1
                        seen_ids.add(auc_id)
                        continue

                    is_valid, matched_brand = is_valid_brand_item(title)
                    if not is_valid:
                        continue

                    is_spam, spam_category = spam_detector.is_spam(title, matched_brand)
                    if is_spam:
                        skipped_spam += 1
                        continue

                    price_tag = item.select_one(".Product__priceValue")
                    if not price_tag:
                        continue
                        
                    price_text = price_tag.text.replace("円", "").replace(",", "").strip()
                    try:
                        price = int(price_text)
                    except ValueError:
                        continue
                        
                    if price > MAX_PRICE_YEN:
                        continue

                    usd_price = convert_jpy_to_usd(price)

                    is_quality, quality_reason = is_quality_listing(usd_price, matched_brand, title)
                    if not is_quality:
                        continue

                    img_tag = item.select_one("img")
                    img = img_tag["src"] if img_tag and img_tag.has_attr("src") else ""
                    if img and not img.startswith("http"):
                        img = "https:" + img if img.startswith("//") else "https://auctions.yahoo.co.jp" + img

                    zen_link = f"https://zenmarket.jp/en/auction.aspx?itemCode={auc_id}"
                    seller_id = extract_seller_info(soup, item)
                    deal_quality = calculate_deal_quality(usd_price, matched_brand, title)

                    listing_data = {
                        "auction_id": auc_id,
                        "title": title,
                        "price_jpy": price,
                        "price_usd": round(usd_price, 2),
                        "brand": matched_brand,
                        "seller_id": seller_id,
                        "zenmarket_url": zen_link,
                        "yahoo_url": link,
                        "image_url": img,
                        "deal_quality": deal_quality
                    }
                    
                    add_to_scraper_db(auc_id)
                    page_listings.append(listing_data)
                    page_quality_count += 1

                except Exception as e:
                    total_errors += 1
                    continue
            
            all_listings.extend(page_listings)
            
            print(f"📄 Page {page}/{max_pages} for '{keyword_combo}': {len(items)} items, {page_quality_count} quality (skipped: {skipped_seen} seen, {skipped_db} DB, {skipped_spam} spam)")
            
            if page_quality_count == 0 and page > 1:
                print(f"🔚 No quality items on page {page}, stopping pagination")
                break
            
            quality_ratio = page_quality_count / max(1, len(items))
            if quality_ratio < 0.02 and page > 1:
                print(f"🔚 Low quality ratio ({quality_ratio:.1%}) on page {page}, stopping")
                break
            
            if page < max_pages:
                time.sleep(0.8)
                
        except Exception as e:
            print(f"❌ Error fetching page {page} for {keyword_combo}: {e}")
            total_errors += 1
            continue
    
    for listing in all_listings:
        listing["priority"] = calculate_listing_priority(listing)
    
    all_listings.sort(key=lambda x: x["priority"], reverse=True)
    
    search_duration = time.time() - start_time
    if keyword_manager:
        keyword_manager.record_keyword_result(keyword_combo, brand, len(all_listings), search_duration)
    
    return all_listings, total_errors

def send_to_discord_bot(auction_data):
    try:
        response = requests.post(DISCORD_BOT_WEBHOOK, json=auction_data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Sent to Discord bot: {auction_data['title'][:50]}...")
            return True
        else:
            print(f"❌ Discord bot failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Discord bot error: {e}")
        return False

def send_discord_alert_fallback(title, price, link, image, item_id):
    usd_price = convert_jpy_to_usd(price)
    
    embed = {
        "title": title[:100] + "..." if len(title) > 100 else title,
        "url": link,
        "description": f"💴 ¥{price:,} (~${usd_price:.2f} USD)\n[View on ZenMarket]({link})",
        "image": {"url": image} if image else None,
        "color": 0x00ff00 if usd_price < 200 else 0xffa500,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if not image:
        embed.pop("image", None)
    
    data = {"content": f"🎯 Clothing Find - ${usd_price:.2f}", "embeds": [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=10)
        if response.status_code in [200, 204]:
            print(f"✅ Discord alert sent: {title[:50]}...")
            return True
        else:
            print(f"❌ Discord alert failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Discord alert error: {e}")
        return False

def get_discord_bot_stats():
    try:
        response = requests.get(DISCORD_BOT_STATS, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

class EmergencyModeManager:
    def __init__(self):
        self.emergency_active = False
        self.cycles_without_finds = 0
        self.last_emergency = None
        self.emergency_keywords = []
    
    def check_should_activate(self, finds_this_cycle, cycle_duration):
        if finds_this_cycle == 0:
            self.cycles_without_finds += 1
        else:
            self.cycles_without_finds = 0
        
        if self.cycles_without_finds >= 3:
            return True
        
        if cycle_duration > 1800 and finds_this_cycle < 2:
            return True
        
        return False
    
    def get_emergency_keywords(self, keyword_manager):
        if not self.emergency_keywords and keyword_manager:
            all_hot_keywords = list(keyword_manager.hot_keywords)
            proven_keywords = []
            
            for keyword in all_hot_keywords:
                perf = keyword_manager.keyword_performance.get(keyword, {})
                if perf.get('searches', 0) > 0:
                    success_rate = perf['finds'] / perf['searches']
                    if success_rate > 0.1:
                        proven_keywords.append((keyword, success_rate))
            
            proven_keywords.sort(key=lambda x: x[1], reverse=True)
            self.emergency_keywords = [kw for kw, rate in proven_keywords[:15]]
        
        if not self.emergency_keywords:
            self.emergency_keywords = [
                "raf simons", "rick owens", "margiela", "jean paul gaultier",
                "raf simons archive", "rick owens jacket", "margiela jacket"
            ]
        
        return self.emergency_keywords
    
    def activate_emergency_mode(self):
        self.emergency_active = True
        self.last_emergency = datetime.now()
        print("🚨 EMERGENCY MODE ACTIVATED - Using only proven high-performance keywords")
    
    def deactivate_emergency_mode(self, finds_count):
        if finds_count > 0:
            self.emergency_active = False
            self.cycles_without_finds = 0
            print("✅ Emergency mode deactivated - normal operation resumed")

def generate_optimized_keywords_for_brand(brand, tier_config, keyword_manager, cycle_count):
    """Generate optimized keywords using performance data and rotation"""
    
    if brand not in BRAND_DATA:
        return [brand.lower()]
    
    max_keywords = tier_config['max_keywords']
    
    if keyword_manager:
        learned_keywords = keyword_manager.get_best_keywords_for_brand(brand, max_keywords)
        
        performance_filtered = []
        for keyword in learned_keywords:
            if keyword not in keyword_manager.dead_keywords:
                perf = keyword_manager.keyword_performance.get(keyword, {})
                if perf.get('consecutive_fails', 0) < 5:
                    performance_filtered.append(keyword)
        
        if performance_filtered:
            return performance_filtered
    
    brand_info = BRAND_DATA[brand]
    primary_variant = brand_info['variants'][0]
    
    rotation_cycle = cycle_count % 4
    
    if rotation_cycle == 0:
        keywords = [
            primary_variant,
            f"{primary_variant} archive",
            f"{primary_variant} jacket",
            f"{primary_variant} shirt"
        ]
    elif rotation_cycle == 1:
        keywords = [
            primary_variant,
            f"{primary_variant} rare",
            f"{primary_variant} vintage",
            f"{primary_variant} hoodie"
        ]
    elif rotation_cycle == 2:
        keywords = [
            primary_variant,
            f"{primary_variant} fw",
            f"{primary_variant} ss",
            f"{primary_variant} pants"
        ]
    else:
        keywords = [primary_variant]
        if len(brand_info['variants']) > 1:
            keywords.append(brand_info['variants'][1])
        keywords.extend([f"{primary_variant} coat", f"{primary_variant} sweater"])
    
    if len(brand_info['variants']) > 1 and max_keywords > 4:
        keywords.append(brand_info['variants'][1])
    
    japanese_terms = ["シャツ", "ジャケット", "パンツ", "パーカー"]
    if max_keywords > 5:
        keywords.append(f"{primary_variant} {random.choice(japanese_terms)}")
    
    return keywords[:max_keywords]

def main_loop():
    print("🎯 Starting OPTIMIZED Yahoo Japan Sniper with FULL FUNCTIONALITY...")
    
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    tiered_system = OptimizedTieredSystem()
    keyword_manager = AdaptiveKeywordManager()
    emergency_manager = EmergencyModeManager()
    
    print("\n🏆 OPTIMIZED TIERED MONITORING SYSTEM:")
    print("Tier 1 Premium: Raf Simons, Rick Owens (6 keywords, 4 pages, every cycle)")
    print("Tier 1 High: Margiela, JPG (5 keywords, 3 pages, every cycle)")
    print("Tier 2: Yohji, Junya, Undercover, Vetements (4 keywords, 2 pages, every 2nd cycle)")
    print("Tier 3: CDG, Martine Rose, Balenciaga, Alyx (3 keywords, 2 pages, every 3rd cycle)")
    print("Tier 4: Celine, Bottega, Kiko (2 keywords, 1 page, every 4th cycle)")
    print("Tier 5: Prada, Miu Miu, Chrome Hearts (1 keyword, 1 page, every 6th cycle)")
    print(f"🚫 Enhanced spam filtering: Women's, Kids, Shoes, Non-clothing")
    print(f"💰 Max Price: ¥{MAX_PRICE_YEN:,} (~${convert_jpy_to_usd(MAX_PRICE_YEN):.2f} USD)")
    print(f"🔥 Multi-page scraping: Up to 4 pages for top brands")
    print(f"🧠 Adaptive learning: Dead keyword detection + performance optimization")
    print(f"🚨 Emergency mode: Proven keywords when efficiency drops")
    print(f"💾 Currently tracking {len(seen_ids)} seen items")
    print(f"🤖 Discord Bot Mode: {'Enabled' if USE_DISCORD_BOT else 'Disabled'}")
    
    get_usd_jpy_rate()
    
    if USE_DISCORD_BOT:
        bot_healthy, status = check_discord_bot_health()
        if bot_healthy:
            print("✅ Discord bot is healthy and ready")
        else:
            print(f"⚠️ Discord bot status: {status}")
    
    try:
        while True:
            cycle_start_time = datetime.now()
            tiered_system.next_iteration()
            
            print(f"\n🔄 CYCLE {tiered_system.iteration_counter} - {cycle_start_time.strftime('%H:%M:%S')}")
            
            total_found = 0
            quality_filtered = 0
            sent_to_discord = 0
            total_errors = 0
            total_searches = 0
            
            if emergency_manager.emergency_active:
                print("🚨 EMERGENCY MODE ACTIVE")
                emergency_keywords = emergency_manager.get_emergency_keywords(keyword_manager)
                
                for keyword in emergency_keywords[:12]:
                    print(f"🚨 Emergency search: {keyword}")
                    
                    listings, errors = search_yahoo_multi_page_optimized(keyword, 2, "emergency", keyword_manager)
                    total_found += len(listings)
                    total_errors += errors
                    total_searches += 1
                    
                    for listing_data in listings[:3]:
                        quality_filtered += 1
                        
                        success = send_to_discord_bot(listing_data) if USE_DISCORD_BOT else send_discord_alert_fallback(
                            listing_data["title"], 
                            listing_data["price_jpy"], 
                            listing_data["zenmarket_url"], 
                            listing_data["image_url"], 
                            listing_data["auction_id"]
                        )
                        
                        if success:
                            seen_ids.add(listing_data["auction_id"])
                            sent_to_discord += 1
                            print(f"🚨 EMERGENCY FIND: {listing_data['brand']} - ${listing_data['price_usd']:.2f}")
                        
                        time.sleep(0.3)
                    
                    time.sleep(1.5)
                
                emergency_manager.deactivate_emergency_mode(sent_to_discord)
            
            else:
                for tier_name, tier_config in tiered_system.tier_config.items():
                    if not tiered_system.should_search_tier(tier_name):
                        continue
                    
                    print(f"\n🎯 Processing {tier_name.upper()} - {len(tier_config['brands'])} brands")
                    tier_searches = 0
                    tier_finds = 0
                    
                    for brand in tier_config['brands']:
                        if brand not in BRAND_DATA:
                            continue
                        
                        keywords = generate_optimized_keywords_for_brand(brand, tier_config, keyword_manager, tiered_system.iteration_counter)
                        
                        brand_listings = []
                        
                        for keyword in keywords:
                            if keyword_manager and keyword in keyword_manager.dead_keywords:
                                print(f"⏭️ Skipping dead keyword: {keyword}")
                                continue
                            
                            print(f"🔍 Searching: {keyword} (up to {tier_config['max_pages']} pages)")
                            
                            listings, errors = search_yahoo_multi_page_optimized(keyword, tier_config['max_pages'], brand, keyword_manager)
                            total_found += len(listings)
                            total_errors += errors
                            total_searches += 1
                            tier_searches += 1
                            
                            brand_listings.extend(listings)
                            
                            if len(listings) > 0:
                                tier_finds += len(listings)
                                print(f"✅ {keyword}: {len(listings)} quality items found")
                            
                            time.sleep(tier_config['delay'])
                        
                        brand_listings.sort(key=lambda x: x["priority"], reverse=True)
                        limited_brand_listings = brand_listings[:tier_config['max_listings']]
                        
                        for listing_data in limited_brand_listings:
                            quality_filtered += 1
                            
                            success = send_to_discord_bot(listing_data) if USE_DISCORD_BOT else send_discord_alert_fallback(
                                listing_data["title"], 
                                listing_data["price_jpy"], 
                                listing_data["zenmarket_url"], 
                                listing_data["image_url"], 
                                listing_data["auction_id"]
                            )
                            
                            if success:
                                seen_ids.add(listing_data["auction_id"])
                                sent_to_discord += 1
                                
                                priority_emoji = "🔥" if listing_data["priority"] >= 100 else "🌟" if listing_data["priority"] >= 70 else "✨"
                                print(f"{priority_emoji} {tier_name.upper()}: {listing_data['brand']} - {listing_data['title'][:40]}... - ¥{listing_data['price_jpy']:,} (${listing_data['price_usd']:.2f}) - {listing_data['deal_quality']:.1%} deal")
                            
                            time.sleep(0.5)
                    
                    tiered_system.update_performance(tier_name, tier_searches, tier_finds)
                    
                    if tier_finds > 0:
                        efficiency = tier_finds / max(1, tier_searches)
                        print(f"📊 {tier_name.upper()}: {tier_finds} finds from {tier_searches} searches (efficiency: {efficiency:.2f})")
            
            save_seen_ids()
            keyword_manager.save_keyword_data()
            tiered_system.save_performance_data()
            
            cycle_end_time = datetime.now()
            cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
            
            cycle_efficiency = sent_to_discord / max(1, total_searches)
            
            print(f"\n📊 CYCLE {tiered_system.iteration_counter} SUMMARY:")
            print(f"⏱️  Duration: {cycle_duration:.1f}s")
            print(f"🔍 Total searches: {total_searches}")
            print(f"📊 Raw items found: {total_found}")
            print(f"✅ Quality filtered: {quality_filtered}")
            print(f"📤 Sent to Discord: {sent_to_discord}")
            print(f"❌ Errors: {total_errors}")
            print(f"⚡ Cycle efficiency: {cycle_efficiency:.3f} finds per search")
            
            if USE_DISCORD_BOT:
                bot_stats = get_discord_bot_stats()
                if bot_stats:
                    print(f"🤖 Discord Bot: {bot_stats.get('total_listings', 0)} total listings, {bot_stats.get('active_users', 0)} active users")
            
            if tiered_system.iteration_counter % 10 == 0:
                print(f"\n🧠 PERFORMANCE INSIGHTS (Every 10 cycles):")
                
                active_keywords = len([k for k, v in keyword_manager.keyword_performance.items() if v.get('consecutive_fails', 0) < 5])
                dead_keywords = len(keyword_manager.dead_keywords)
                hot_keywords = len(keyword_manager.hot_keywords)
                
                print(f"📈 Keywords: {active_keywords} active, {hot_keywords} hot, {dead_keywords} dead")
                
                for tier_name, tracker in tiered_system.performance_tracker.items():
                    if tracker['total_searches'] > 0:
                        print(f"📊 {tier_name.upper()}: {tracker['avg_efficiency']:.2f} avg efficiency")
                
                if keyword_manager.hot_keywords:
                    best_keywords = sorted(
                        [(k, v['finds']/v['searches']) for k, v in keyword_manager.keyword_performance.items() 
                         if k in keyword_manager.hot_keywords and v['searches'] > 0],
                        key=lambda x: x[1], reverse=True
                    )[:5]
                    print(f"🔥 Top keywords: {[f'{kw}({rate:.1%})' for kw, rate in best_keywords]}")
            
            if emergency_manager.check_should_activate(sent_to_discord, cycle_duration):
                emergency_manager.activate_emergency_mode()
            
            log_scraper_stats(total_found, quality_filtered, sent_to_discord, total_errors, total_searches)
            
            base_sleep_time = 300
            if cycle_efficiency > 0.2:
                sleep_time = base_sleep_time - 60
                print(f"🚀 High efficiency detected, reducing sleep to {sleep_time}s")
            elif cycle_efficiency < 0.05:
                sleep_time = base_sleep_time + 60
                print(f"⚠️ Low efficiency, extending sleep to {sleep_time}s")
            else:
                sleep_time = base_sleep_time
            
            actual_sleep = max(120, sleep_time - cycle_duration)
            print(f"⏳ Cycle complete. Sleeping for {actual_sleep:.0f} seconds...")
            time.sleep(actual_sleep)
            
    except KeyboardInterrupt:
        save_seen_ids()
        keyword_manager.save_keyword_data()
        tiered_system.save_performance_data()
        print("✅ Exiting gracefully with all data saved.")

load_exchange_rate()

if __name__ == "__main__":
    main_loop()