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
from enhanced_filtering import EnhancedSpamDetector, QualityChecker
import statistics
import random
from concurrent.futures import ThreadPoolExecutor

scraper_app = Flask(__name__)

@scraper_app.route('/health', methods=['GET'])
def health():
    return {
        "status": "healthy", 
        "service": "auction-scraper",
        "cycle": getattr(tiered_system, 'iteration_counter', 0) if 'tiered_system' in globals() else 0,
        "uptime": time.time() - start_time if 'start_time' in globals() else 0
    }, 200

@scraper_app.route('/', methods=['GET'])
def root():
    return {"service": "Yahoo Auction Scraper", "status": "running"}, 200

def run_health_server():
    port = int(os.environ.get('PORT', 8000))
    scraper_app.run(host='0.0.0.0', port=port, debug=False)

# Discord Bot Configuration for Railway
DISCORD_BOT_URL = os.getenv('DISCORD_BOT_URL', 'https://motivated-stillness-production.up.railway.app')
USE_DISCORD_BOT = os.getenv('USE_DISCORD_BOT', 'true').lower() == 'true'

# Validate Discord Bot URL
if DISCORD_BOT_URL and not DISCORD_BOT_URL.startswith(('http://', 'https://')):
    DISCORD_BOT_URL = f"https://{DISCORD_BOT_URL}"

print(f"🌐 Discord Bot URL: {DISCORD_BOT_URL}")
print(f"🤖 Use Discord Bot: {USE_DISCORD_BOT}")

MAX_PRICE_YEN = 100000
SEEN_FILE = "seen_yahoo.json"
BRANDS_FILE = "brands.json"
EXCHANGE_RATE_FILE = "exchange_rate.json"
SCRAPER_DB = "auction_tracking.db"

MAX_PRICE_USD = 1500
MIN_PRICE_USD = 2
MAX_LISTINGS_PER_BRAND = 999
ONLY_BUY_IT_NOW = False
PRICE_QUALITY_THRESHOLD = 0.01
ENABLE_RESALE_BOOST = True
ENABLE_INTELLIGENT_FILTERING = True

SORT_ORDERS = [
    "s1=new&o1=d",      
    "s1=cbids&o1=a",    
    "s1=end&o1=a",      
    "s1=bids&o1=d",     
    "s1=featured"       
]

BASE_URL = "https://auctions.yahoo.co.jp/search/search?p={}&n=50&b={}&{}&minPrice=1&maxPrice={}"

exchange_rate_cache = {"rate": 150.0, "timestamp": 0}
current_usd_jpy_rate = 147.0

# PERSIST CYCLE COUNTER TO FILE
def load_cycle_counter():
    """Load cycle counter from file to survive restarts"""
    try:
        if os.path.exists('cycle_counter.json'):
            with open('cycle_counter.json', 'r') as f:
                data = json.load(f)
                return data.get('iteration_counter', 0)
    except Exception as e:
        print(f"⚠️ Could not load cycle counter: {e}")
    return 0

def save_cycle_counter(counter):
    """Save cycle counter to file"""
    try:
        with open('cycle_counter.json', 'w') as f:
            json.dump({
                'iteration_counter': counter,
                'last_updated': datetime.now().isoformat()
            }, f)
    except Exception as e:
        print(f"⚠️ Could not save cycle counter: {e}")

# Enhanced spam detector class
class EnhancedSpamDetector:
    def __init__(self):
        self.spam_patterns = [
            # Obvious replicas/fakes
            r'(?i)(replica|fake|copy|knock.?off|bootleg|unauthorized)',
            r'(?i)(スーパーコピー|レプリカ|偽物|コピー品)',
            
            # Non-clothing items that often appear
            r'(?i)(book|magazine|catalogue|catalog|cd|dvd|poster|sticker)',
            r'(?i)(本|雑誌|カタログ|ポスター|ステッカー|写真)',
            
            # Damaged/parts only
            r'(?i)(damaged|broken|parts?.only|repair|restoration)',
            r'(?i)(破損|破れ|汚れ|ダメージ|部品のみ)',
            
            # Obvious non-fashion
            r'(?i)(phone.?case|iphone|android|computer|laptop)',
            r'(?i)(ケース|スマホ|携帯|パソコン)'
        ]
        
        self.brand_specific_spam = {
            'Stone Island': [
                r'(?i)(badge.only|patch.only|logo.only)',
                r'(?i)(バッジのみ|ワッペンのみ)'
            ],
            'Rick Owens': [
                r'(?i)(inspired|style|similar)',
                r'(?i)(風|っぽい|系)'
            ]
        }
    
    def is_spam(self, title, brand=None):
        """Enhanced spam detection with brand-specific rules"""
        if not title:
            return True, "empty_title"
        
        title_lower = title.lower()
        
        # Check general spam patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, title):
                return True, f"spam_pattern: {pattern}"
        
        # Check brand-specific spam patterns
        if brand and brand in self.brand_specific_spam:
            for pattern in self.brand_specific_spam[brand]:
                if re.search(pattern, title):
                    return True, f"brand_spam: {brand}"
        
        # Length checks
        if len(title) < 10:
            return True, "title_too_short"
        
        if len(title) > 200:
            return True, "title_too_long"
        
        # Character ratio checks (too many numbers/symbols)
        alpha_chars = len(re.findall(r'[a-zA-Zあ-んア-ン一-龯]', title))
        total_chars = len(title)
        
        if total_chars > 0 and alpha_chars / total_chars < 0.3:
            return True, "low_alpha_ratio"
        
        return False, "passed_all_checks"

def detect_brand_in_title(title):
    """Detect brand in title with fallback"""
    if not title:
        return "unknown"
    
    # Load brand data if not already loaded
    if 'BRAND_DATA' not in globals():
        global BRAND_DATA
        BRAND_DATA = load_brand_data()
    
    title_lower = title.lower()
    
    for brand, brand_info in BRAND_DATA.items():
        if brand.lower() in title_lower:
            return brand
        
        # Check variants
        for variant in brand_info.get('variants', []):
            if variant.lower() in title_lower:
                return brand
    
    return "unknown"

def calculate_priority_score(price_usd, brand, title, deal_quality):
    """Calculate priority score for listing"""
    base_score = 50
    
    # Brand boost
    if brand in ["Stone Island", "Rick Owens", "Balenciaga", "Off-White"]:
        base_score += 30
    elif brand in ["Supreme", "Palace", "Bape"]:
        base_score += 20
    
    # Price boost (lower price = higher priority)
    if price_usd < 50:
        base_score += 25
    elif price_usd < 100:
        base_score += 15
    elif price_usd < 200:
        base_score += 10
    
    # Deal quality boost
    base_score += int(deal_quality * 100)
    
    # Title quality boost
    if len(title) > 20 and len(title) < 100:
        base_score += 10
    
    return min(100, base_score)

def send_discord_alert_fallback(title, price, link, image, item_id):
    """Fallback Discord alert function"""
    try:
        # Simple fallback - just print to console
        print(f"📢 FALLBACK ALERT: {title} - ¥{price:,} - {link}")
        return True
    except Exception as e:
        print(f"❌ Fallback alert failed: {e}")
        return False

class IntensiveKeywordGenerator:
    def __init__(self):
        self.clothing_categories = [
            "shirt", "jacket", "pants", "hoodie", "coat", "sweater", "tee", 
            "denim", "blazer", "bomber", "cargo", "trench", "vest", "knit",
            "シャツ", "ジャケット", "パンツ", "パーカー", "コート", "Tシャツ", "ニット"
        ]
        
        self.archive_terms = [
            "archive", "rare", "vintage", "fw", "ss", "aw", "runway", 
            "collection", "sample", "prototype", "limited", "exclusive",
            "アーカイブ", "レア", "ヴィンテージ", "限定", "サンプル", "コレクション"
        ]
        
        self.year_seasons = []
        current_year = datetime.now().year
        for year in range(current_year - 15, current_year + 1):
            for season in ["fw", "ss", "aw"]:
                self.year_seasons.append(f"{season}{str(year)[-2:]}")
    
    def generate_comprehensive_keywords(self, brand, brand_variants, cycle_num):
        keywords = []
        
        primary_variant = brand_variants[0] if brand_variants else brand
        
        for variant in brand_variants[:2]:
            keywords.append(variant)
            
            for category in self.clothing_categories:
                keywords.append(f"{variant} {category}")
            
            for term in self.archive_terms[:5]:
                keywords.append(f"{variant} {term}")
            
            season_samples = random.sample(self.year_seasons, min(5, len(self.year_seasons)))
            for season in season_samples:
                keywords.append(f"{variant} {season}")
        
        keywords = [kw for kw in keywords if "femme" not in kw.lower()]
        
        random.shuffle(keywords)
        
        return keywords

class AdaptiveTieredSystem:
    def __init__(self):
        self.tier_config = {
            'tier_1_premium': {
                'brands': ['Raf Simons', 'Rick Owens'],
                'base_keywords': 12,
                'base_pages': 8,
                'search_frequency': 1,
                'delay': 0.5,
                'max_listings': 999,
                'sort_orders': ['new', 'cbids', 'end']
            },
            'tier_1_high': {
                'brands': ['Maison Margiela', 'Jean Paul Gaultier'],
                'base_keywords': 10,
                'base_pages': 6,
                'search_frequency': 1,
                'delay': 0.8,
                'max_listings': 999,
                'sort_orders': ['new', 'cbids']
            },
            'tier_2': {
                'brands': ['Yohji Yamamoto', 'Junya Watanabe', 'Undercover', 'Vetements'],
                'base_keywords': 8,
                'base_pages': 5,
                'search_frequency': 1,
                'delay': 1,
                'max_listings': 999,
                'sort_orders': ['new', 'cbids']
            },
            'tier_3': {
                'brands': ['Comme Des Garcons', 'Martine Rose', 'Balenciaga', 'Alyx'],
                'base_keywords': 7,
                'base_pages': 4,
                'search_frequency': 1,
                'delay': 1.5,
                'max_listings': 999,
                'sort_orders': ['new']
            },
            'tier_4': {
                'brands': ['Celine', 'Bottega Veneta', 'Kiko Kostadinov', 'Chrome Hearts'],
                'base_keywords': 6,
                'base_pages': 3,
                'search_frequency': 2,
                'max_listings': 999,
                'delay': 2,
                'sort_orders': ['new']
            },
            'tier_5_minimal': {
                'brands': ['Prada', 'Miu Miu', 'Hysteric Glamour'],
                'base_keywords': 5,
                'base_pages': 3,
                'search_frequency': 2,
                'delay': 2.5,
                'max_listings': 999,
                'sort_orders': ['new']
            }
        }
        
        self.performance_tracker = {}
        self.iteration_counter = 0
        self.low_volume_cycles = 0
        self.load_performance_data()
    
    def load_performance_data(self):
        try:
            with open('tier_performance.json', 'r') as f:
                self.performance_tracker = json.load(f)
        except FileNotFoundError:
            for tier_name in self.tier_config.keys():
                self.performance_tracker[tier_name] = {
                    'total_searches': 0,
                    'successful_finds': 0,
                    'last_find': None,
                    'avg_efficiency': 0.0
                }
    
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
    
    def get_adaptive_config(self, tier_name, is_low_volume=False):
        config = self.tier_config[tier_name].copy()
        
        if is_low_volume:
            config['max_keywords'] = min(20, config['base_keywords'] * 2)
            config['max_pages'] = min(10, config['base_pages'] * 2)
            config['delay'] = max(0.3, config['delay'] * 0.5)
        else:
            config['max_keywords'] = config['base_keywords']
            config['max_pages'] = config['base_pages']
        
        return config
    
    def update_performance(self, tier_name, searches_made, finds_count):
        """Update performance tracking with full defensive initialization"""
        if tier_name not in self.performance_tracker:
            self.performance_tracker[tier_name] = {
                'total_searches': 0,
                'total_finds': 0,           # KEY FIX: Add this missing field
                'successful_finds': 0,
                'last_find': None,
                'avg_efficiency': 0.0,
                'efficiency': 0.0,
                'last_updated': datetime.now().isoformat()
            }
        
        tracker = self.performance_tracker[tier_name]
        
        # Additional defensive checks for existing entries
        if 'total_searches' not in tracker:
            tracker['total_searches'] = 0
        if 'total_finds' not in tracker:
            tracker['total_finds'] = 0
        if 'successful_finds' not in tracker:
            tracker['successful_finds'] = 0
        if 'avg_efficiency' not in tracker:
            tracker['avg_efficiency'] = 0.0
        if 'efficiency' not in tracker:
            tracker['efficiency'] = 0.0
        if 'last_updated' not in tracker:
            tracker['last_updated'] = datetime.now().isoformat()
        
        # Update all relevant fields
        tracker['total_searches'] += searches_made
        tracker['total_finds'] += finds_count      # This was missing before
        tracker['successful_finds'] += finds_count
        
        if finds_count > 0:
            tracker['last_find'] = datetime.now().isoformat()
        
        # Calculate efficiency using total_finds
        if tracker['total_searches'] > 0:
            tracker['avg_efficiency'] = tracker['total_finds'] / tracker['total_searches']
            tracker['efficiency'] = tracker['avg_efficiency']  # Keep both for compatibility
        
        tracker['last_updated'] = datetime.now().isoformat()
    
    def detect_low_volume(self, total_sent):
        if total_sent <= 5:
            self.low_volume_cycles += 1
        else:
            self.low_volume_cycles = 0
        
        return self.low_volume_cycles >= 2
    
    def next_iteration(self):
        self.iteration_counter += 1

class AdaptiveKeywordManager:
    def __init__(self):
        self.keyword_performance = {}
        self.brand_keyword_success = {}
        self.dead_keywords = set()
        self.hot_keywords = set()
        self.revive_threshold = 50
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
                'searches': 0, 'finds': 0, 'avg_time': 0.0, 'consecutive_fails': 0,
                'last_searched': None, 'cycles_dead': 0
            }
        
        perf = self.keyword_performance[keyword]
        perf['searches'] += 1
        perf['finds'] += finds_count
        perf['avg_time'] = (perf['avg_time'] + search_time) / 2
        perf['last_searched'] = datetime.now().isoformat()
        
        if finds_count > 0:
            perf['consecutive_fails'] = 0
            perf['cycles_dead'] = 0
            self.hot_keywords.add(keyword)
            self.dead_keywords.discard(keyword)
            
            if brand not in self.brand_keyword_success:
                self.brand_keyword_success[brand] = {}
            self.brand_keyword_success[brand][keyword] = self.brand_keyword_success[brand].get(keyword, 0) + finds_count
        else:
            perf['consecutive_fails'] += 1
            # DISABLED: Dead keyword marking - was too aggressive
            # if perf['consecutive_fails'] >= 15:
            #     self.dead_keywords.add(keyword)
            #     self.hot_keywords.discard(keyword)
            #     perf['cycles_dead'] += 1
    
    def should_revive_keyword(self, keyword):
        if keyword not in self.keyword_performance:
            return True
        
        perf = self.keyword_performance[keyword]
        cycles_dead = perf.get('cycles_dead', 0)
        
        if cycles_dead >= self.revive_threshold:
            perf['cycles_dead'] = 0
            perf['consecutive_fails'] = 0
            self.dead_keywords.discard(keyword)
            return True
        
        return False
    
    def get_best_keywords_for_brand(self, brand, max_count):
        brand_keywords = self.brand_keyword_success.get(brand, {})
        
        active_keywords = []
        for kw, count in brand_keywords.items():
            if kw not in self.dead_keywords or self.should_revive_keyword(kw):
                active_keywords.append((kw, count))
        
        active_keywords.sort(key=lambda x: x[1], reverse=True)
        best_keywords = [kw for kw, count in active_keywords[:max_count]]
        
        if len(best_keywords) < max_count:
            best_keywords.extend(self.generate_fallback_keywords(brand, max_count - len(best_keywords)))
        
        return best_keywords
    
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
            f"{primary_variant} vintage",
            f"{primary_variant} fw",
            f"{primary_variant} ss"
        ]
        
        if len(brand_info['variants']) > 1:
            fallback_keywords.append(brand_info['variants'][1])
        
        return fallback_keywords[:max_count]

class EmergencyModeManager:
    def __init__(self):
        self.emergency_mode = False
        self.consecutive_failures = 0
        self.max_failures = 10
        
    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_failures:
            self.emergency_mode = True
            print("🚨 EMERGENCY MODE ACTIVATED - Too many consecutive failures")
    
    def record_success(self):
        self.consecutive_failures = 0
        if self.emergency_mode:
            self.emergency_mode = False
            print("✅ Emergency mode deactivated - Success recorded")
    
    def should_skip_search(self):
        return self.emergency_mode

class OptimizedTieredSystem:
    def __init__(self):
        # Load previous cycle counter instead of starting at 0
        self.iteration_counter = load_cycle_counter()
        print(f"🔄 Resumed from cycle {self.iteration_counter}")
        
        self.performance_tracker = {}
        self.tier_config = {
            'tier_1': {
                'brands': ['Raf Simons', 'Rick Owens', 'Maison Margiela', 'Balenciaga'],
                'search_frequency': 1,  # Every cycle
                'max_keywords': 4,
                'max_pages': 2,
                'delay': 3.0,  # Increased from 1.0 to 3.0 seconds
                'max_listings': 100
            },
            'tier_2': {
                'brands': ['Jean Paul Gaultier', 'Yohji Yamamoto', 'Comme Des Garcons', 'Junya Watanabe'],
                'search_frequency': 1,  # Every cycle
                'max_keywords': 4,
                'max_pages': 2,
                'delay': 3.0,  # Increased from 1.0 to 3.0 seconds
                'max_listings': 100
            },
            'tier_3': {
                'brands': ['Undercover', 'Vetements', 'Martine Rose', 'Alyx'],
                'search_frequency': 1,  # Every cycle
                'max_keywords': 4,
                'max_pages': 2,
                'delay': 3.0,  # Increased from 1.0 to 3.0 seconds
                'max_listings': 100
            },
            'tier_4': {
                'brands': ['Celine', 'Bottega Veneta', 'Kiko Kostadinov', 'Chrome Hearts'],
                'search_frequency': 1,  # Every cycle
                'max_keywords': 4,
                'max_pages': 2,
                'delay': 3.0,  # Increased from 1.0 to 3.0 seconds
                'max_listings': 100
            },
            'tier_5': {
                'brands': ['Prada', 'Miu Miu', 'Helmut Lang', 'Hysteric Glamour'],
                'search_frequency': 1,  # Every cycle
                'max_keywords': 4,
                'max_pages': 2,
                'delay': 3.0,  # Increased from 1.0 to 3.0 seconds
                'max_listings': 100
            }
        }
        self.load_performance_data()
    
    def next_iteration(self):
        self.iteration_counter += 1
        # Save after every increment to persist through crashes
        save_cycle_counter(self.iteration_counter)
    
    def should_search_tier(self, tier_name):
        if tier_name not in self.performance_tracker:
            return True
        
        tracker = self.performance_tracker[tier_name]
        if tracker['total_searches'] < 5:
            return True
        
        # Skip if efficiency is too low
        if tracker['avg_efficiency'] < 0.01:
            return False
        
        return True
    
    def update_performance(self, tier_name, searches_count, finds_count):
        """Update performance tracking with defensive initialization"""
        if tier_name not in self.performance_tracker:
            self.performance_tracker[tier_name] = {}
        
        tracker = self.performance_tracker[tier_name]
        
        # Defensive initialization - ensure all keys exist
        if 'total_searches' not in tracker:
            tracker['total_searches'] = 0
        if 'total_finds' not in tracker:
            tracker['total_finds'] = 0
        if 'efficiency' not in tracker:
            tracker['efficiency'] = 0.0
        if 'last_updated' not in tracker:
            tracker['last_updated'] = datetime.now().isoformat()
        
        # Now safely update
        tracker['total_searches'] += searches_count
        tracker['total_finds'] += finds_count
        
        if tracker['total_searches'] > 0:
            tracker['efficiency'] = tracker['total_finds'] / tracker['total_searches']
        
        tracker['last_updated'] = datetime.now().isoformat()
    
    def load_performance_data(self):
        try:
            if os.path.exists('tier_performance.json'):
                with open('tier_performance.json', 'r') as f:
                    self.performance_tracker = json.load(f)
        except Exception as e:
            print(f"⚠️ Could not load tier performance data: {e}")
    
    def save_performance_data(self):
        try:
            with open('tier_performance.json', 'w') as f:
                json.dump(self.performance_tracker, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save tier performance data: {e}")
    
    def get_tier_for_brand(self, brand):
        """Get the tier name and config for a given brand"""
        for tier_name, tier_config in self.tier_config.items():
            if brand in tier_config['brands']:
                return tier_name, tier_config
        return 'tier_1', self.tier_config['tier_1']  # Default fallback

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

def extract_auction_end_time(soup, item):
    try:
        time_element = item.select_one(".Product__time, .Product__remaining")
        if time_element:
            time_text = time_element.get_text(strip=True)
            
            if "時間" in time_text or "分" in time_text:
                hours = 0
                minutes = 0
                
                hour_match = re.search(r'(\d+)\s*時間', time_text)
                if hour_match:
                    hours = int(hour_match.group(1))
                
                min_match = re.search(r'(\d+)\s*分', time_text)
                if min_match:
                    minutes = int(min_match.group(1))
                
                end_time = datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)
                return end_time.isoformat()
        
        date_element = item.select_one(".Product__endDate")
        if date_element:
            date_text = date_element.get_text(strip=True)
            return None
            
    except Exception:
        pass
    
    return None

def calculate_deal_quality(price_usd, brand, title):
    title_lower = title.lower()
    
    if any(word in title_lower for word in ["tee", "t-shirt", "シャツ", "Tシャツ"]):
        base_price = 40
    elif any(word in title_lower for word in ["shirt", "button", "dress shirt"]):
        base_price = 60
    elif any(word in title_lower for word in ["jacket", "blazer", "ジャケット"]):
        base_price = 120
    elif any(word in title_lower for word in ["coat", "outerwear", "コート"]):
        base_price = 150
    elif any(word in title_lower for word in ["hoodie", "sweatshirt", "パーカー"]):
        base_price = 80
    elif any(word in title_lower for word in ["pants", "trousers", "jeans", "パンツ"]):
        base_price = 80
    else:
        base_price = 60
    
    brand_multipliers = {
        "raf_simons": 3.0,
        "rick_owens": 2.5,
        "maison_margiela": 2.2,
        "jean_paul_gaultier": 2.0,
        "yohji_yamamoto": 1.8,
        "junya_watanabe": 1.6,
        "comme_des_garcons": 1.5,
        "undercover": 1.4,
        "martine_rose": 1.5,
        "miu_miu": 1.3,
        "vetements": 1.4,
        "balenciaga": 1.3,
        "chrome_hearts": 1.4,
        "celine": 1.2,
        "bottega_veneta": 1.2,
        "alyx": 1.3,
        "kiko_kostadinov": 1.3,
        "prada": 1.2,
        "hysteric_glamour": 1.0
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
            print(f"🔥 Archive boost: {keyword} found")
            break
    
    brand_lower = brand.lower() if brand else ""
    
    if "raf" in brand_lower:
        if any(word in title_lower for word in ["tee", "t-shirt", "shirt", "シャツ", "Tシャツ"]):
            boost += 0.4
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

def is_quality_listing(price_usd, brand, title):
    if price_usd < MIN_PRICE_USD or price_usd > MAX_PRICE_USD:
        return False, f"Price outside range"
    
    if not is_clothing_item(title):
        return False, f"Not clothing"
    
    deal_quality = calculate_deal_quality(price_usd, brand, title)
    threshold = PRICE_QUALITY_THRESHOLD
    
    return deal_quality >= threshold, f"Quality: {deal_quality:.1%}"

def is_clothing_item(title):
    title_lower = title.lower()
    
    excluded_items = {
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
        "fred perry", "フレッドペリー", "femme"
    }
    
    for excluded in excluded_items:
        if excluded in title_lower:
            return False
    
    clothing_keywords = {
        "shirt", "tee", "tshirt", "t-shirt", "polo", "button-up", "dress shirt",
        "jacket", "blazer", "coat", "outerwear", "bomber", "varsity", "denim jacket",
        "pants", "trousers", "jeans", "chinos", "slacks", "cargo", "sweatpants",
        "hoodie", "sweatshirt", "pullover", "sweater", "jumper", "cardigan",
        "shorts", "bermuda", "cargo shorts", "denim shorts",
        "tank top", "vest", "camisole", "blouse", "top",
        "シャツ", "Tシャツ", "ポロシャツ", "ブラウス", "トップス",
        "ジャケット", "ブレザー", "コート", "アウター", "ボンバー",
        "パンツ", "ズボン", "ジーンズ", "チノパン", "スラックス",
        "パーカー", "スウェット", "プルオーバー", "セーター", "ニット",
        "ショーツ", "ショートパンツ", "タンクトップ", "ベスト"
    }
    
    for clothing_word in clothing_keywords:
        if clothing_word in title_lower:
            return True
    
    return True

def is_valid_brand_item(title):
    title_lower = title.lower()
    
    if "femme" in title_lower:
        return False, None
    
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
    
    excluded_brands = {"undercoverism", "thrasher", "gap", "adidas", "uniqlo", "gu", "zara", "h&m"}
    for excluded in excluded_brands:
        if excluded.lower() in matched_brand.lower() or excluded.lower() in title_lower:
            return False, None
    
    if not is_clothing_item(title):
        return False, None
    
    return True, matched_brand

def extract_size_info(title):
    title_lower = title.lower()
    
    sizes_found = []
    
    size_patterns = [
        r'\b(xs|s|m|l|xl|xxl|xxxl)\b',
        r'\b(small|medium|large|x-large|xx-large)\b',
        r'\b(44|46|48|50|52|54|56)\b',
        r'\b(サイズ[SML])\b',
        r'size\s*[:：]\s*(\w+)',
    ]
    
    for pattern in size_patterns:
        matches = re.findall(pattern, title_lower)
        sizes_found.extend(matches)
    
    return list(set(sizes_found))

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
    
    is_new_listing = listing_data.get("is_new_listing", False)
    if is_new_listing:
        priority += 50
    
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

def search_yahoo_multi_page_intensive(keyword_combo, max_pages, brand, keyword_manager, sort_order="new"):
    start_time = time.time()
    all_listings = []
    total_errors = 0
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    quality_checker = QualityChecker()
    
    sort_param = {
        "new": "s1=new&o1=d",
        "cbids": "s1=cbids&o1=a",
        "end": "s1=end&o1=a",
        "bids": "s1=bids&o1=d",
        "featured": "s1=featured"
    }.get(sort_order, "s1=new&o1=d")
    
    for page in range(1, max_pages + 1):
        try:
            encoded_kw = urllib.parse.quote(keyword_combo)
            b_param = (page - 1) * 50 + 1
            url = BASE_URL.format(encoded_kw, b_param, sort_param, MAX_PRICE_YEN)
            
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"❌ HTTP {resp.status_code} for {keyword_combo} page {page}")
                total_errors += 1
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.Product")
            
            if len(items) < 10 and page > 1:
                break
            
            page_listings = []
            page_quality_count = 0
            
            for item in items:
                try:
                    link_tag = item.select_one("a.Product__titleLink")
                    if not link_tag:
                        continue
                        
                    link = link_tag["href"]
                    if not link.startswith("http"):
                        link = "https://auctions.yahoo.co.jp" + link
                        
                    title = link_tag.get_text(strip=True)
                    
                    if "femme" in title.lower():
                        continue
                    
                    auc_id = extract_auction_id_safe(item) or link.split("/")[-1].split("?")[0]
                    
                    if not auc_id or auc_id in seen_ids:
                        continue
                    
                    if check_if_auction_exists_in_db(auc_id):
                        seen_ids.add(auc_id)
                        continue

                    is_valid, matched_brand = is_valid_brand_item(title)
                    if not is_valid:
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
                    auction_end_time = extract_auction_end_time(soup, item)
                    sizes = extract_size_info(title)

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
                        "deal_quality": deal_quality,
                        "auction_end_time": auction_end_time,
                        "sizes": sizes,
                        "is_new_listing": (sort_order == "new" and page == 1)
                    }
                    
                    add_to_scraper_db(auc_id)
                    page_listings.append(listing_data)
                    page_quality_count += 1

                except Exception as e:
                    total_errors += 1
                    continue
            
            all_listings.extend(page_listings)
            
            print(f"📄 {sort_order.upper()} Page {page}/{max_pages} for '{keyword_combo}': {page_quality_count} quality items")
            
            if page_quality_count == 0 and page > 2:
                break
            
            if page < max_pages:
                time.sleep(0.5)
                
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

def build_search_url(keyword, page=1):
    """Build Yahoo Japan search URL with proper encoding"""
    base_url = "https://auctions.yahoo.co.jp/search/search"
    
    params = {
        'p': keyword,
        'tab_ex': 'commerce',
        'ei': 'utf-8',
        'b': (page - 1) * 50 + 1,  # Yahoo shows 50 items per page
        'n': 50,
        'auccat': '0',
        'aucminprice': str(int(MIN_PRICE_USD * current_usd_jpy_rate)) if current_usd_jpy_rate else '1000',
        'aucmaxprice': str(int(MAX_PRICE_USD * current_usd_jpy_rate)) if current_usd_jpy_rate else '150000',
        'sort': 'end',  # Sort by ending soon for fresh results
        'order': 'a'    # Ascending order
    }
    
    # Build URL manually to ensure proper encoding
    param_string = '&'.join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
    return f"{base_url}?{param_string}"

def search_yahoo_multi_page_optimized(keyword, max_pages, brand, keyword_manager=None):
    """Enhanced Yahoo Japan search with better error handling"""
    all_listings = []
    total_errors = 0
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    print(f"🔍 Starting search for '{keyword}' (up to {max_pages} pages)")
    
    for page in range(1, max_pages + 1):
        if consecutive_errors >= max_consecutive_errors:
            print(f"⚠️ Too many consecutive errors ({consecutive_errors}), stopping search for '{keyword}'")
            break
            
        try:
            url = build_search_url(keyword, page)
            
            # Enhanced request with better headers and retry logic
            headers = {
                'User-Agent': random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ja,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            # Retry logic for failed requests
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    
                    if response.status_code == 200:
                        consecutive_errors = 0  # Reset on success
                        break
                    elif response.status_code == 429:
                        print(f"⏰ Rate limited on page {page}, waiting {retry_delay * (attempt + 1)}s...")
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    elif response.status_code in [500, 502, 503, 504]:
                        print(f"❌ HTTP {response.status_code} for {keyword} page {page}, attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            raise requests.exceptions.RequestException(f"HTTP {response.status_code} after {max_retries} attempts")
                    else:
                        print(f"❌ HTTP {response.status_code} for {keyword} page {page}")
                        raise requests.exceptions.RequestException(f"HTTP {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print(f"⏰ Timeout on {keyword} page {page}, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise
                except requests.exceptions.ConnectionError:
                    print(f"🔌 Connection error on {keyword} page {page}, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * 2)
                        continue
                    else:
                        raise
            else:
                # If we exhausted all retries
                print(f"❌ Failed to fetch {keyword} page {page} after {max_retries} attempts")
                total_errors += 1
                consecutive_errors += 1
                continue
            
            # Parse the response
            soup = BeautifulSoup(response.content, 'html.parser')
            page_listings = parse_yahoo_page_optimized(soup, keyword, brand, keyword_manager)
            
            if not page_listings:
                print(f"📭 No listings found on page {page} for '{keyword}'")
                # Don't count empty pages as errors, but limit consecutive empty pages
                if page > 1:  # Allow first page to be empty
                    consecutive_errors += 0.5  # Half error for empty page
            else:
                print(f"✅ Found {len(page_listings)} listings on page {page}")
                all_listings.extend(page_listings)
                consecutive_errors = 0  # Reset on successful page with listings
            
            # Respectful delay between pages
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            print(f"❌ Error on page {page} for '{keyword}': {str(e)}")
            total_errors += 1
            consecutive_errors += 1
            
            # Update keyword performance for failures
            if keyword_manager and keyword_manager.keyword_performance:
                if keyword not in keyword_manager.keyword_performance:
                    keyword_manager.keyword_performance[keyword] = {
                        'searches': 0, 'finds': 0, 'consecutive_fails': 0, 'last_success': None
                    }
                keyword_manager.keyword_performance[keyword]['consecutive_fails'] += 1
            
            # Longer delay on error
            time.sleep(random.uniform(3.0, 5.0))
            continue
    
    # Update keyword performance statistics
    if keyword_manager and keyword_manager.keyword_performance:
        if keyword not in keyword_manager.keyword_performance:
            keyword_manager.keyword_performance[keyword] = {
                'searches': 0, 'finds': 0, 'consecutive_fails': 0, 'last_success': None
            }
        
        keyword_manager.keyword_performance[keyword]['searches'] += 1
        
        if all_listings:
            keyword_manager.keyword_performance[keyword]['finds'] += len(all_listings)
            keyword_manager.keyword_performance[keyword]['consecutive_fails'] = 0
            keyword_manager.keyword_performance[keyword]['last_success'] = datetime.now().isoformat()
        
        # Mark as dead keyword if too many consecutive failures
        if keyword_manager.keyword_performance[keyword]['consecutive_fails'] >= 5:
            keyword_manager.dead_keywords.add(keyword)
            print(f"💀 Marked keyword as dead: {keyword}")
        elif len(all_listings) > 3:  # Good performance
            keyword_manager.hot_keywords.add(keyword)
    
    print(f"🏁 Search complete for '{keyword}': {len(all_listings)} total listings, {total_errors} errors")
    return all_listings, total_errors

def parse_yahoo_page_optimized(soup, keyword, brand, keyword_manager=None):
    """Parse with enhanced debugging and extraction"""
    listings = []
    skipped_spam = 0
    skipped_duplicates = 0
    processed_count = 0
    no_id_count = 0
    
    print(f"🔍 Parsing page for keyword: {keyword}")
    
    try:
        # Find auction items with multiple possible selectors
        items = []
        
        # Enhanced selectors for current Yahoo structure
        selectors = [
            'div.Product',  # Most common
            'li.Product',
            'div[class*="Product"]',
            'div[class*="item"]',
            'li[class*="item"]',
            '.auctiontile',
            '[data-auction-id]',
            'div.Item',
            'li.Item'
        ]
        
        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items and len(items) > 10:  # Make sure we got a meaningful result
                print(f"✅ Using selector: {selector} - found {len(items)} items")
                break
        
        if not items:
            print("❌ No items found with any selector")
            return []
        
        for item in items[:50]:  # Process first 50
            processed_count += 1
            
            # Debug first few items
            if processed_count <= 3:
                debug_item_structure(item, processed_count)
            
            # Extract auction ID with enhanced method
            auction_id = extract_auction_id_from_item(item)
            
            if not auction_id:
                no_id_count += 1
                if processed_count <= 5:  # Debug first few failures
                    print(f"⚠️ Item {processed_count}: No auction ID found")
                continue
            
            print(f"✅ Found auction ID: {auction_id}")
            
            # Skip if already seen
            if auction_id in seen_ids:
                skipped_duplicates += 1
                continue
            
            # Extract title with fallback methods
            title = None
            title_selectors = [
                '.Product__title a',
                '.Product__title',
                'h3 a',
                'h3',
                '.title a',
                '.title',
                'a[title]'
            ]
            
            for selector in title_selectors:
                title_elem = item.select_one(selector)
                if title_elem:
                    title = title_elem.get('title') or title_elem.get_text(strip=True)
                    if title:
                        break
            
            if not title:
                print(f"⚠️ Could not extract title for auction {auction_id}")
                continue
            
            # Extract price with fallback methods
            price_jpy = None
            price_selectors = [
                '.Product__price',
                '.Price',
                '.price',
                '[class*="price"]',
                '[class*="Price"]'
            ]
            
            for selector in price_selectors:
                price_elem = item.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_numbers = re.findall(r'[\d,]+', price_text)
                    if price_numbers:
                        try:
                            price_jpy = int(price_numbers[0].replace(',', ''))
                            break
                        except ValueError:
                            continue
            
            if not price_jpy:
                print(f"⚠️ Could not extract price for auction {auction_id}")
                continue
            
            # Convert to USD
            price_usd = price_jpy / current_usd_jpy_rate if current_usd_jpy_rate else price_jpy / 147.0
            
            # Skip if price is outside range
            if price_usd < MIN_PRICE_USD or price_usd > MAX_PRICE_USD:
                continue
            
            # Enhanced spam detection (if enabled)
            spam_detector = EnhancedSpamDetector()
            matched_brand = detect_brand_in_title(title)
            
            is_spam, spam_category = spam_detector.is_spam(title, matched_brand)
            if is_spam:
                skipped_spam += 1
                print(f"🚫 Enhanced spam filter blocked: {title[:30]}...")
                continue
            
            # Quality check
            is_quality, quality_reason = is_quality_listing(price_usd, matched_brand, title)
            if not is_quality:
                print(f"❌ Quality check failed: {quality_reason}")
                continue
            
            # Extract image URL
            image_url = None
            img_elem = item.find('img')
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src')
                if image_url and image_url.startswith('//'):
                    image_url = 'https:' + image_url
            
            # Build URLs
            yahoo_url = f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}"
            zenmarket_url = f"https://zenmarket.jp/en/auction.aspx?itemCode={auction_id}"
            
            # Calculate deal quality and priority
            deal_quality = calculate_deal_quality(price_usd, matched_brand, title)
            priority = calculate_priority_score(price_usd, matched_brand, title, deal_quality)
            
            try:
                listing_data = {
                    'auction_id': auction_id,
                    'title': title,
                    'brand': matched_brand,
                    'price_jpy': price_jpy,
                    'price_usd': price_usd,
                    'zenmarket_url': zenmarket_url,
                    'yahoo_url': yahoo_url,
                    'image_url': image_url,
                    'deal_quality': deal_quality,
                    'priority': priority,
                    'seller_id': 'unknown',
                    'auction_end_time': None  # Would need additional parsing
                }
                
                listings.append(listing_data)
                seen_ids.add(auction_id)
                
            except Exception as e:
                print(f"❌ Error processing item {processed_count}: {str(e)}")
                continue
        
        print(f"📊 Processed {processed_count} items, {no_id_count} without auction ID, {len(listings)} valid listings")
        
    except Exception as e:
        print(f"❌ Error parsing page: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return listings

def extract_auction_id_from_item(item):
    """Simple auction ID extraction - stop overthinking it"""
    try:
        for link in item.find_all('a', href=True):
            href = link.get('href', '')
            
            # Skip dummy links
            if href == '#dummy' or 'dummy' in href:
                continue
                
            # Extract auction ID from Yahoo auction URLs
            if 'auctions.yahoo.co.jp' in href and '/auction/' in href:
                # Get everything after /auction/
                auction_id = href.split('/auction/')[-1]
                
                # Remove any query parameters or fragments
                auction_id = auction_id.split('?')[0].split('#')[0]
                
                return auction_id
        
        return None
        
    except Exception as e:
        return None


def debug_item_structure(item, index):
    """Debug function to understand item structure"""
    if index <= 3:  # Only debug first few items
        print(f"\n🔍 DEBUG Item {index}:")
        print(f"   Tag: {item.name}")
        print(f"   Classes: {item.get('class', [])}")
        
        # Look for any links and extract auction IDs
        links = item.find_all('a', href=True)
        if links:
            print(f"   Links found: {len(links)}")
            for i, link in enumerate(links):
                href = link.get('href', '')
                print(f"     Link {i}: {href}")
                
                # Try to extract auction ID from each link
                if '/auction/' in href:
                    auction_id = href.split('/auction/')[-1]
                    print(f"     --> Extracted: {auction_id}")


def send_to_discord_bot(listing_data):
    """Send listing to Discord bot with enhanced error handling"""
    try:
        if not USE_DISCORD_BOT:
            print("❌ Discord bot is disabled")
            return False
        
        # Validate listing data
        required_fields = ['auction_id', 'title', 'brand', 'price_jpy', 'price_usd', 'zenmarket_url']
        missing_fields = [field for field in required_fields if field not in listing_data]
        
        if missing_fields:
            print(f"❌ Missing required fields: {missing_fields}")
            return False
        
        # Add default fields if missing
        if 'auction_end_time' not in listing_data:
            listing_data['auction_end_time'] = None
        if 'seller_id' not in listing_data:
            listing_data['seller_id'] = 'unknown'
        if 'image_url' not in listing_data:
            listing_data['image_url'] = None
        if 'yahoo_url' not in listing_data:
            listing_data['yahoo_url'] = None
        
        # Construct webhook URL
        webhook_url = f"{DISCORD_BOT_URL}/webhook/listing"
        
        print(f"📤 Sending to Discord bot: {listing_data['title'][:50]}...")
        print(f"🔗 Using URL: {webhook_url}")
        
        # Send request with proper headers and timeout
        response = requests.post(
            webhook_url,
            json=listing_data,
            timeout=15,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Yahoo-Auction-Scraper/1.0'
            }
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"✅ Successfully sent: {listing_data['auction_id']}")
            print(f"📊 Response: {response_data}")
            return True
        else:
            print(f"❌ Discord bot error: {response.status_code}")
            print(f"❌ Response text: {response.text}")
            print(f"❌ Request URL: {webhook_url}")
            print(f"❌ Request data: {json.dumps(listing_data, indent=2)}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout sending to Discord bot (15s)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error to Discord bot: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error to Discord bot: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error sending to Discord bot: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_discord_bot_health():
    """Check if Discord bot is responding with detailed diagnostics"""
    try:
        if not USE_DISCORD_BOT:
            return False, "Discord bot disabled"
        
        health_url = f"{DISCORD_BOT_URL}/health"
        webhook_health_url = f"{DISCORD_BOT_URL}/webhook/health"
        
        print(f"🏥 Checking Discord bot health at: {health_url}")
        
        # Check main health endpoint
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Main health check passed: {data}")
            
            # Check webhook-specific health
            try:
                webhook_response = requests.get(webhook_health_url, timeout=10)
                if webhook_response.status_code == 200:
                    webhook_data = webhook_response.json()
                    print(f"✅ Webhook health check: {webhook_data}")
                    
                    if webhook_data.get("bot_ready") and webhook_data.get("guild_connected"):
                        return True, "Bot healthy and ready"
                    else:
                        return False, f"Bot not ready: {webhook_data}"
                else:
                    print(f"⚠️ Webhook health check failed: {webhook_response.status_code}")
                    return False, f"Webhook health check failed: {webhook_response.status_code}"
            except Exception as e:
                print(f"⚠️ Webhook health check error: {e}")
                return False, f"Webhook health check error: {e}"
        else:
            return False, f"Health check failed: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "Health check timeout"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:
        return False, f"Health check error: {e}"

def get_discord_bot_stats():
    """Get Discord bot statistics"""
    try:
        if not USE_DISCORD_BOT:
            return None
        
        response = requests.get(
            f"{DISCORD_BOT_STATS}",
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting bot stats: {e}")
        return None

def generate_optimized_keywords_for_brand(brand, tier_config, keyword_manager, cycle_num):
    """Generate optimized keywords for a brand based on performance and tier"""
    keywords = []
    
    if brand not in BRAND_DATA:
        return [brand]
    
    brand_info = BRAND_DATA[brand]
    variants = brand_info.get('variants', [brand])
    
    # Start with brand name and main variants
    keywords.extend(variants[:2])
    
    # Add category combinations
    categories = ["jacket", "pants", "hoodie", "shirt", "sweater", "coat"]
    for variant in variants[:2]:
        for category in categories[:3]:
            keywords.append(f"{variant} {category}")
    
    # Add seasonal terms
    seasons = ["fw", "ss", "aw"]
    years = [str(datetime.now().year - i)[-2:] for i in range(3)]
    for variant in variants[:2]:
        for season in seasons:
            for year in years[:2]:
                keywords.append(f"{variant} {season}{year}")
    
    # Add archive/rare terms
    archive_terms = ["archive", "rare", "vintage", "limited"]
    for variant in variants[:2]:
        for term in archive_terms[:2]:
            keywords.append(f"{variant} {term}")
    
    # Filter out duplicates and limit to tier max
    unique_keywords = list(dict.fromkeys(keywords))
    max_keywords = tier_config.get('max_keywords', 6)
    
    return unique_keywords[:max_keywords]

def get_all_brands_round_robin(tiered_system):
    """Get all brands in a round-robin fashion instead of tier-based"""
    all_brands = []
    # Collect all brands from all tiers

# Enhanced main loop with better error handling
def main_scraping_loop():
    """Main scraping loop with enhanced Discord bot integration"""
    print("🚀 Starting enhanced scraping loop...")
    
    # Check Discord bot health before starting
    bot_healthy, status = check_discord_bot_health()
    if bot_healthy:
        print("✅ Discord bot is healthy and ready")
    else:
        print(f"⚠️ Discord bot status: {status}")
        print("⚠️ Will attempt to send anyway...")
    
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
            
            # Process each tier
            for tier_name, tier_config in tiered_system.tier_config.items():
                if not tiered_system.should_search_tier(tier_name):
                    continue
                
                print(f"\n🎯 Processing {tier_name}...")
                
                for brand in tier_config['brands']:
                    keyword_variations = keyword_manager.get_brand_keywords(brand)
                    
                    for keyword_combo in keyword_variations[:tier_config['max_keywords']]:
                        try:
                            listings, errors = search_yahoo_multi_page_optimized(
                                keyword_combo, 
                                tier_config['max_pages'], 
                                tier_name, 
                                keyword_manager
                            )
                            
                            total_found += len(listings)
                            total_errors += errors
                            total_searches += 1
                            
                            # Process listings with immediate sending
                            for listing_data in listings[:tier_config['max_listings']]:
                                try:
                                    quality_filtered += 1
                                    
                                    # Send immediately to Discord bot
                                    success = send_to_discord_bot(listing_data)
                                    
                                    if success:
                                        seen_ids.add(listing_data["auction_id"])
                                        sent_to_discord += 1
                                        
                                        priority_emoji = "🔥" if listing_data.get("priority", 0) >= 100 else "🌟" if listing_data.get("priority", 0) >= 70 else "✨"
                                        print(f"{priority_emoji} SENT: {listing_data['brand']} - {listing_data['title'][:40]}... - ¥{listing_data['price_jpy']:,} (${listing_data['price_usd']:.2f})")
                                    else:
                                        print(f"❌ FAILED to send: {listing_data['title'][:40]}...")
                                    
                                    time.sleep(0.5)  # Rate limiting
                                    
                                except Exception as e:
                                    print(f"❌ Error processing listing: {e}")
                                    total_errors += 1
                            
                            time.sleep(tier_config['delay'])
                            
                        except Exception as e:
                            print(f"❌ Error searching {keyword_combo}: {e}")
                            total_errors += 1
                            continue
            
            # Log cycle statistics
            cycle_duration = (datetime.now() - cycle_start_time).total_seconds()
            
            print(f"\n📊 CYCLE {tiered_system.iteration_counter} SUMMARY:")
            print(f"⏱️ Duration: {cycle_duration:.1f}s")
            print(f"🔍 Total searches: {total_searches}")
            print(f"📊 Raw items found: {total_found}")
            print(f"✅ Quality filtered: {quality_filtered}")
            print(f"📤 Sent to Discord: {sent_to_discord}")
            print(f"❌ HTTP errors: {total_errors}")
            
            success_rate = (sent_to_discord / quality_filtered * 100) if quality_filtered > 0 else 0
            print(f"📈 Success rate: {success_rate:.1f}%")
            
            # Log stats to Discord bot if available
            try:
                if USE_DISCORD_BOT:
                    stats_data = {
                        "total_found": total_found,
                        "quality_filtered": quality_filtered,
                        "sent_to_discord": sent_to_discord,
                        "errors_count": total_errors,
                        "keywords_searched": total_searches
                    }
                    
                    stats_response = requests.post(
                        f"{DISCORD_BOT_URL}/webhook/stats",
                        json=stats_data,
                        timeout=5
                    )
                    
                    if stats_response.status_code == 200:
                        print("📊 Stats logged to Discord bot")
                    else:
                        print(f"⚠️ Failed to log stats: {stats_response.status_code}")
            except Exception as e:
                print(f"⚠️ Error logging stats: {e}")
            
            # Sleep between cycles
            print(f"😴 Cycle complete. Sleeping for 120 seconds...")
            time.sleep(120)
            
    except KeyboardInterrupt:
        print("\n🛑 Scraping stopped by user")
    except Exception as e:
        print(f"❌ Critical error in main loop: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(30)  # Wait before potential restart
    for tier_name, tier_config in tiered_system.tier_config.items():
        all_brands.extend(tier_config['brands'])
    # Remove duplicates while preserving order
    unique_brands = list(dict.fromkeys(all_brands))
    print(f"🔄 Round-robin mode: {len(unique_brands)} brands every cycle")
    return unique_brands

def generate_brand_keywords_simple(brand, brand_info, max_keywords=3):
    """Simplified keyword generation for round-robin approach"""
    keywords = []
    # Primary variant
    primary_variant = brand_info['variants'][0] if brand_info['variants'] else brand
    keywords.append(primary_variant)
    
    # Add season variants if max_keywords > 1
    if max_keywords > 1:
        keywords.extend([
            f"{primary_variant} fw",
            f"{primary_variant} ss"
        ])
    
    # Add clothing type variants if space
    if max_keywords > 3:
        keywords.extend([
            f"{primary_variant} jacket",
            f"{primary_variant} pants"
        ])
    
    return keywords[:max_keywords]

def main_loop():
    """REVERTED: Working tier-based main search loop"""
    print("🎯 Starting WORKING Yahoo Japan Sniper - TIER BASED SYSTEM...")
    
    # Start health server for Railway
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    print(f"🌐 Health server started on port {os.environ.get('PORT', 8000)}")
    
    # Initialize with persistence (keep the fixes)
    tiered_system = OptimizedTieredSystem()
    keyword_manager = AdaptiveKeywordManager()
    emergency_manager = EmergencyModeManager()
    
    print(f"🔄 Resuming from CYCLE {tiered_system.iteration_counter}")
    
    print("\n🏆 TIER-BASED SYSTEM RESTORED:")
    print("✅ Proven working system")
    print("✅ All critical fixes maintained")
    print(f"💰 Price range: ${MIN_PRICE_USD} - ${MAX_PRICE_USD}")
    print(f"⭐ Quality threshold: {PRICE_QUALITY_THRESHOLD:.1%}")
    
    # Initial setup
    get_usd_jpy_rate()
    
    # DEBUG: Print Discord bot configuration
    print(f"🌐 DISCORD_BOT_URL: {DISCORD_BOT_URL}")
    print(f"🤖 USE_DISCORD_BOT: {USE_DISCORD_BOT}")
    
    if USE_DISCORD_BOT:
        bot_healthy, status = check_discord_bot_health()
        if bot_healthy:
            print("✅ Discord bot is healthy and ready")
        else:
            print(f"⚠️ Discord bot status: {status}")
    
    try:
        while True:
            cycle_start_time = datetime.now()
            
            try:
                tiered_system.next_iteration()  # Keep persistence fix
                
                print(f"\n🔄 CYCLE {tiered_system.iteration_counter} - {cycle_start_time.strftime('%H:%M:%S')}")
                
                total_found = 0
                quality_filtered = 0
                sent_to_discord = 0
                total_errors = 0
                total_searches = 0
                
                # REVERTED: Use the WORKING tier-based approach
                for tier_name, tier_config in tiered_system.tier_config.items():
                    if not tiered_system.should_search_tier(tier_name):
                        print(f"⏭️ Skipping {tier_name} (frequency check)")
                        continue
                    
                    print(f"\n🎯 Processing {tier_name.upper()} tier...")
                    tier_searches = 0
                    tier_finds = 0
                    
                    for brand in tier_config['brands']:
                        if brand not in BRAND_DATA:
                            continue
                        
                        brand_info = BRAND_DATA[brand]
                        print(f"🏷️ Searching {brand}...")
                        
                        # Generate keywords for this brand
                        keywords = generate_brand_keywords_simple(brand, brand_info, max_keywords=3)
                        
                        for keyword in keywords:
                            if keyword in keyword_manager.dead_keywords:
                                continue
                            
                            try:
                                # Search using the WORKING method
                                listings, errors = search_yahoo_multi_page_optimized(
                                    keyword, 
                                    tier_config.get('max_pages', 2), 
                                    brand, 
                                    keyword_manager
                                )
                                
                                total_found += len(listings)
                                total_errors += errors
                                total_searches += 1
                                tier_searches += 1
                                
                                # IMMEDIATE SENDING: Process each listing as it's found
                                for listing_data in listings:
                                    if listing_data["auction_id"] in seen_ids:
                                        continue
                                    
                                    quality_filtered += 1
                                    tier_finds += 1
                                    
                                    # DEBUG: Print what we're about to send
                                    print(f"🔄 ATTEMPTING TO SEND: {listing_data['auction_id']} - {listing_data['title'][:40]}...")
                                    
                                    # SEND IMMEDIATELY - NO TRY/EXCEPT TO HIDE ERRORS
                                    if USE_DISCORD_BOT:
                                        print(f"🌐 Sending to: {DISCORD_BOT_URL}/webhook/listing")
                                        
                                        response = requests.post(
                                            f"{DISCORD_BOT_URL}/webhook/listing",
                                            json=listing_data,
                                            timeout=10,
                                            headers={'Content-Type': 'application/json'}
                                        )
                                        
                                        print(f"📡 Response status: {response.status_code}")
                                        print(f"📡 Response text: {response.text}")
                                        
                                        if response.status_code == 200:
                                            seen_ids.add(listing_data["auction_id"])
                                            sent_to_discord += 1
                                            
                                            priority_emoji = "🔥" if listing_data["priority"] >= 100 else "🌟" if listing_data["priority"] >= 70 else "✨"
                                            print(f"{priority_emoji} ✅ SENT: {listing_data['brand']} - {listing_data['title'][:40]}... - ¥{listing_data['price_jpy']:,} (${listing_data['price_usd']:.2f})")
                                        else:
                                            print(f"❌ SEND FAILED: Status {response.status_code} - {response.text}")
                                    else:
                                        print("❌ USE_DISCORD_BOT is False!")
                                    
                                    # Small delay between sends
                                    time.sleep(0.5)
                                
                                # Delay between keywords
                                time.sleep(tier_config.get('delay', 2.0))
                                
                            except Exception as e:
                                print(f"❌ Error searching {keyword} for {brand}: {e}")
                                total_errors += 1
                    
                    # BEFORE calling tiered_system.update_performance, add this check:
                    if not hasattr(tiered_system, 'performance_tracker'):
                        tiered_system.performance_tracker = {}
                    
                    # Ensure tier exists in tracker before updating
                    if tier_name not in tiered_system.performance_tracker:
                        tiered_system.performance_tracker[tier_name] = {
                            'total_searches': 0,
                            'total_finds': 0,
                            'successful_finds': 0,
                            'avg_efficiency': 0.0,
                            'efficiency': 0.0,
                            'last_find': None,
                            'last_updated': datetime.now().isoformat()
                        }
                    
                    # NOW it's safe to call:
                    tiered_system.update_performance(tier_name, tier_searches, tier_finds)
                    
                    if tier_finds > 0:
                        efficiency = tier_finds / max(1, tier_searches)
                        print(f"📊 {tier_name.upper()}: {tier_finds} finds from {tier_searches} searches (efficiency: {efficiency:.2f})")
                
                # Keep the cycle clearing fix but reduce frequency
                if tiered_system.iteration_counter % 25 == 0:  # Reduced from 35
                    items_before = len(seen_ids)
                    print(f"🗑️ CYCLE {tiered_system.iteration_counter}: Force clearing {items_before} seen items...")
                    seen_ids.clear()
                    save_seen_ids()
                    print(f"✅ Cleared {items_before} seen items - fresh searches incoming!")
                
                # Save data more frequently (keep this improvement)
                save_seen_ids()
                keyword_manager.save_keyword_data()
                tiered_system.save_performance_data()
                
                # Cycle statistics
                cycle_end_time = datetime.now()
                cycle_duration = (cycle_end_time - cycle_start_time).total_seconds()
                
                cycle_efficiency = sent_to_discord / max(1, total_searches)
                conversion_rate = (quality_filtered / max(1, total_found)) * 100 if total_found > 0 else 0
                
                print(f"\n📊 CYCLE {tiered_system.iteration_counter} SUMMARY:")
                print(f"⏱️  Duration: {cycle_duration:.1f}s")
                print(f"🔍 Total searches: {total_searches}")
                print(f"📊 Raw items found: {total_found}")
                print(f"✅ Quality filtered: {quality_filtered}")
                print(f"📤 Sent to Discord: {sent_to_discord}")
                print(f"❌ HTTP errors: {total_errors}")
                print(f"⚡ Cycle efficiency: {cycle_efficiency:.3f} finds per search")
                print(f"🎯 Conversion rate: {conversion_rate:.1f}%")
                
                # Check Discord bot health periodically
                if USE_DISCORD_BOT and tiered_system.iteration_counter % 5 == 0:
                    bot_healthy, status = check_discord_bot_health()
                    if not bot_healthy:
                        print(f"⚠️ Discord bot health check failed: {status}")
                    else:
                        bot_stats = get_discord_bot_stats()
                        if bot_stats:
                            print(f"🤖 Discord Bot: {bot_stats.get('total_listings', 0)} total listings")
                
                # Log stats
                log_scraper_stats(total_found, quality_filtered, sent_to_discord, total_errors, total_searches)
                
                # Sleep calculation
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
                
            except Exception as cycle_error:
                print(f"❌ ERROR IN CYCLE {tiered_system.iteration_counter}: {cycle_error}")
                import traceback
                traceback.print_exc()
                
                # Save state before continuing (keep this improvement)
                save_cycle_counter(tiered_system.iteration_counter)
                save_seen_ids()
                keyword_manager.save_keyword_data()
                tiered_system.save_performance_data()
                
                print("💾 State saved after error - continuing...")
                time.sleep(30)  # Brief pause before retry
                continue
                
    except KeyboardInterrupt:
        print("👋 Graceful shutdown...")
        save_cycle_counter(tiered_system.iteration_counter)
        save_seen_ids()
        keyword_manager.save_keyword_data()
        tiered_system.save_performance_data()
        
    except Exception as fatal_error:
        print(f"💀 FATAL ERROR: {fatal_error}")
        import traceback
        traceback.print_exc()
        
        # Emergency save
        save_cycle_counter(tiered_system.iteration_counter)
        save_seen_ids()
        keyword_manager.save_keyword_data()
        tiered_system.save_performance_data()
        print("💾 Emergency state save completed")
        
load_exchange_rate()

def log_scraper_stats(total_found, quality_filtered, sent_to_discord, total_errors, total_searches):
    """Log scraper statistics to database"""
    try:
        if USE_DISCORD_BOT:
            response = requests.post(
                f"{DISCORD_BOT_URL}/webhook/stats",
                json={
                    "total_found": total_found,
                    "quality_filtered": quality_filtered, 
                    "sent_to_discord": sent_to_discord,
                    "errors_count": total_errors,
                    "keywords_searched": total_searches
                },
                timeout=5
            )
            if response.status_code == 200:
                print(f"✅ Logged stats: {sent_to_discord} sent, {total_errors} errors")
    except Exception as e:
        print(f"⚠️ Could not log stats: {e}")

if __name__ == "__main__":
    main_loop()