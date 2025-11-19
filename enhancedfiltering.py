#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sqlite3
from datetime import datetime, timedelta

class EnhancedSpamDetector:
    def __init__(self):
        # NEW EXCLUDED KEYWORDS from user request
        self.new_excluded_keywords = [
            'lego', 'レゴ',
            'water tank', 'ウォータータンク', '水タンク',
            'bmw touring e91', 'bmw e91', 'e91',
            'mazda', 'マツダ',
            'band of outsiders', 'バンドオブアウトサイダーズ'
        ]
        
        # Enhanced exclusion terms - more comprehensive
        self.excluded_terms = [
            # NEW EXCLUSIONS
            'lego', 'レゴ', 'water tank', 'ウォータータンク', '水タンク',
            'bmw touring e91', 'bmw e91', 'e91', 'mazda', 'マツダ',
            'band of outsiders', 'バンドオブアウトサイダーズ',
            
            # Vehicles & Parts (enhanced)
            'automobile', 'motorcycle', 'motorbike', 'scooter', 'バイク', 'モーターサイクル',
            'car', 'truck', 'vehicle', '自動車', 'カー', 'トラック', 'bmw', 'honda',
            'engine', 'エンジン', 'parts', 'パーツ', 'wheels', 'タイヤ', 'exhaust',
            'cb400', 'vtr250', 'cbx', 'jade', 'hornet', 'undercowl',
            'cb', 'vtr', 'honda', 'yamaha', 'suzuki', 'kawasaki',
            'jdirectitems auction → automobile', 'jdirectitems auction → motorcycle',
            
            # Home/Industrial items
            'water tank', 'tank', 'タンク', 'storage', 'container',
            'industrial', '工業用', 'equipment', '機器',
            
            # Toys & Games
            'toy', 'おもちゃ', 'game', 'ゲーム', 'figure', 'フィギュア', 
            'doll', 'ドール', 'puzzle', 'パズル', 'pokemon', 'ポケモン',
            'trading card', 'トレーディングカード', 'anime', 'アニメ',
            'manga', 'マンガ', 'model kit', 'プラモデル', 'lego', 'レゴ',
            
            # Electronics (general)
            'computer', 'pc', 'smartphone', 'iphone', 'android', 'tablet',
            'スマートフォン', 'コンピューター', 'タブレット', 'laptop',
            'server', 'motherboard', 'graphics card', 'ram', 'ssd',
            
            # Food & Consumables
            'food', '食品', 'drink', '飲料', 'supplement', 'perfume', '香水',
            'cosmetics', '化粧品', 'medicine', '薬', 'snack', 'お菓子',
            
            # Sports Equipment
            'bicycle', '自転車', 'golf', 'ゴルフ', 'fishing', '釣り',
            'tennis', 'テニス', 'baseball', '野球', 'football', 'サッカー',
            
            # Home Goods
            'furniture', '家具', 'appliance', '家電', 'kitchen', 'キッチン',
            'bedding', '寝具', 'curtain', 'カーテン',
            
            # Obvious replicas/fakes
            'replica', 'fake', 'copy', 'knock off', 'bootleg', 'unauthorized',
            'スーパーコピー', 'レプリカ', '偽物', 'コピー品',
            
            # Non-clothing items that often appear
            'book', 'magazine', 'catalogue', 'catalog', 'cd', 'dvd', 'poster', 'sticker',
            '本', '雑誌', 'カタログ', 'ポスター', 'ステッカー', '写真',
            
            # Damaged/parts only
            'damaged', 'broken', 'parts only', 'repair', 'restoration',
            '破損', '破れ', '汚れ', 'ダメージ', '部品のみ',
            
            # Obvious non-fashion
            'phone case', 'iphone', 'android', 'computer', 'laptop',
            'ケース', 'スマホ', '携帯', 'パソコン'
        ]
        
        # Category-based filtering patterns
        self.category_patterns = {
            'automobile_motorcycle': [
                r'jdirectitems auction.*→.*automobile',
                r'jdirectitems auction.*→.*motorcycle',
                r'カテゴリ.*自動車',
                r'カテゴリ.*バイク',
                r'category.*auto',
                r'category.*motorcycle'
            ],
            'toys_games': [
                r'jdirectitems auction.*→.*toy',
                r'jdirectitems auction.*→.*game',
                r'カテゴリ.*おもちゃ',
                r'カテゴリ.*ゲーム'
            ],
            'electronics': [
                r'jdirectitems auction.*→.*computer',
                r'jdirectitems auction.*→.*electronic',
                r'カテゴリ.*電子機器',
                r'カテゴリ.*コンピューター'
            ]
        }
        
        # STRICT Fashion category enforcement
        self.allowed_fashion_patterns = [
            r'jdirectitems auction.*→.*fashion',
            r'jdirectitems auction.*→.*clothing',
            r'jdirectitems auction.*→.*apparel',
            r'カテゴリ.*ファッション',
            r'カテゴリ.*衣類',
            r'カテゴリ.*服'
        ]
        
        self.brand_specific_spam = {
            'Stone Island': [
                'badge only', 'patch only', 'logo only',
                'バッジのみ', 'ワッペンのみ'
            ],
            'Rick Owens': [
                'inspired', 'style', 'similar',
                '風', 'っぽい', '系'
            ]
        }
    
    def check_category_strict(self, title, description="", url=""):
        """STRICT category checking - block anything not clearly Fashion"""
        combined_text = f"{title} {description} {url}".lower()
        
        # First check if it's clearly a fashion item
        has_fashion_indicator = False
        for pattern in self.allowed_fashion_patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                has_fashion_indicator = True
                print(f"✅ Fashion category confirmed: {pattern}")
                break
        
        # If from JDirectItems but NO fashion indicator, block it
        if 'jdirectitems auction' in combined_text and not has_fashion_indicator:
            print(f"🚫 JDirectItems non-fashion blocked: missing fashion category")
            return True, "jdirectitems_non_fashion"
        
        # Check for explicitly blocked categories
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    print(f"🚫 Blocked category detected: {category} - {pattern}")
                    return True, f"blocked_category: {category}"
        
        return False, None
    
    def is_spam(self, title, brand=None, item=None, description="", url=""):
        """Enhanced spam detection with strict category checking"""
        if not title:
            return True, "empty_title"
        
        title_lower = title.lower()
        
        # PRIORITY 1: Check new excluded keywords first
        for excluded in self.new_excluded_keywords:
            if excluded.lower() in title_lower:
                print(f"🚫 NEW EXCLUDED KEYWORD detected: {excluded} in title")
                return True, f"new_excluded: {excluded}"
        
        # PRIORITY 2: Strict category checking
        is_category_blocked, category_reason = self.check_category_strict(title, description, url)
        if is_category_blocked:
            return True, category_reason
        
        # PRIORITY 3: Check for general excluded terms
        for excluded in self.excluded_terms:
            if excluded.lower() in title_lower:
                print(f"🚫 Excluded term detected: {excluded} in title")
                return True, f"excluded_term: {excluded}"
        
        # Check brand-specific spam patterns
        if brand and brand in self.brand_specific_spam:
            for pattern in self.brand_specific_spam[brand]:
                if pattern.lower() in title_lower:
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

class QualityChecker:
    """Improved quality checking with better price filtering"""
    
    def __init__(self):
        self.spam_detector = EnhancedSpamDetector()
    
    def check_listing_quality(self, auction_data):
        """Enhanced quality checks with better price thresholds"""
        issues = []
        confidence = 0.0
        
        title = auction_data.get('title', '')
        brand = auction_data.get('brand', '')
        price_usd = auction_data.get('price_usd', 0)
        description = auction_data.get('description', '')
        url = auction_data.get('url', '')
        
        # Enhanced spam detection with category checking
        is_spam, spam_type = self.spam_detector.is_spam(title, brand, None, description, url)
        if is_spam:
            issues.append(f"Spam detected: {spam_type}")
            confidence += 0.9  # Very high confidence for spam
        
        # IMPROVED PRICE FILTERING - much less aggressive
        if price_usd < 5:
            issues.append("Price too low - likely damaged/fake")
            confidence += 0.7
        elif price_usd > 3000:
            issues.append("Price extremely high - needs verification")
            confidence += 0.4
        elif price_usd > 2000:
            # Allow high prices for premium brands (Rick Owens, etc.)
            issues.append("High price - premium item")
            confidence += 0.1
        
        # Title quality requirements
        if len(title) < 15:
            issues.append("Title too short - insufficient detail")
            confidence += 0.3
        
        # REMOVED: Clothing keyword requirement - too restrictive
        # Trust that spam detector and scraper's is_clothing_item handles this
        # Removing this check allows more brand items through
        
        # Suspicious pattern detection
        suspicious_patterns = [
            r'\d+個セット',  # Bulk sets
            r'まとめ売り',   # Bulk sales
            r'ジャンク',     # Junk items
            r'parts?\s+only', # Parts only
            r'no\s+brand',   # No brand items
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                issues.append(f"Suspicious pattern: {pattern}")
                confidence += 0.3

        should_block = confidence > 0.75  # LESS AGGRESSIVE: Raised from 0.6 to 0.75

        return {
            'should_block': should_block,
            'confidence': confidence,
            'issues': issues,
            'action': 'block' if should_block else 'allow'
        }

def extract_category_from_item(item):
    """Enhanced category extraction from Yahoo Auctions"""
    try:
        category_text = ""
        
        # Multiple selector strategies for category extraction
        category_selectors = [
            '.Product__path',
            '.Product__category', 
            '.category-path',
            '[data-category]',
            '.breadcrumb',
            '.CategoryPath',
            '.category',
            '.auction-path',
            '.item-category'
        ]
        
        for selector in category_selectors:
            category_elem = item.select_one(selector)
            if category_elem:
                category_text = category_elem.get_text(strip=True).lower()
                print(f"🔍 Category found: {category_text}")
                break
        
        # Check URL for category hints
        if not category_text:
            links = item.find_all('a', href=True)
            for link in links:
                href = link['href']
                if 'category' in href or 'ctlg' in href:
                    category_text = href
                    print(f"🔍 Category from URL: {href}")
                    break
        
        # Check for JDirectItems specific patterns
        item_text = item.get_text()
        if 'jdirectitems auction' in item_text.lower():
            # Extract the category after the arrow
            match = re.search(r'jdirectitems auction.*?→\s*([^,\n]+)', item_text, re.IGNORECASE)
            if match:
                category_text = f"jdirectitems auction → {match.group(1).strip()}"
                print(f"🔍 JDirectItems category: {category_text}")
        
        return category_text
    except Exception as e:
        print(f"⚠️ Error extracting category: {e}")
        return None

def is_blocked_category(category_text):
    """Enhanced category blocking with strict fashion-only policy"""
    if not category_text:
        return False, None
    
    category_lower = category_text.lower()
    
    # STRICT: Block all non-fashion JDirectItems
    if 'jdirectitems auction' in category_lower:
        if not any(fashion_term in category_lower for fashion_term in ['fashion', 'clothing', 'apparel', 'ファッション', '衣類', '服']):
            print(f"🚫 JDirectItems non-fashion blocked: {category_text}")
            return True, "jdirectitems_non_fashion"
    
    # Block specific categories
    blocked_categories = [
        # Automobile/Vehicle related
        'automobile', 'auto', 'car', 'vehicle', '自動車', 'カー',
        'automotive', 'バイク', 'motorcycle', 'motorbike', 'scooter',
        'truck', 'トラック', 'parts', 'パーツ', 'engine', 'エンジン',
        
        # Toys and Games
        'toy', 'おもちゃ', 'game', 'ゲーム', 'figure', 'フィギュア',
        'doll', 'ドール', 'model', 'モデル', 'puzzle', 'パズル',
        'trading card', 'トレーディング', 'pokemon', 'ポケモン',
        'anime', 'アニメ', 'manga', 'マンガ', 'lego', 'レゴ',
        
        # Electronics (unless brand-specific)
        'computer', 'コンピューター', 'smartphone', 'スマートフォン',
        'tablet', 'タブレット', 'electronics', '電子機器',
        
        # Food and consumables
        'food', '食品', 'drink', '飲料', 'snack', 'お菓子',
        'supplement', 'サプリメント', 'cosmetics', '化粧品',
        
        # Sports equipment (unless fashion brands)
        'sports equipment', 'スポーツ用品', 'bicycle', '自転車',
        'fishing', '釣り', 'golf', 'ゴルフ',
        
        # Home goods
        'furniture', '家具', 'appliance', '家電', 'kitchen', 'キッチン',
        'industrial', '工業用', 'tank', 'タンク'
    ]
    
    for blocked in blocked_categories:
        if blocked in category_lower:
            return True, blocked
    
    return False, None

# Test function for the new filtering
def test_enhanced_filtering():
    """Test the enhanced filtering system"""
    detector = EnhancedSpamDetector()
    
    test_cases = [
        # NEW EXCLUDED KEYWORDS TESTS
        ("LEGO Star Wars Set 75000", "test", True, "Should block LEGO"),
        ("Water Tank Storage Industrial", "test", True, "Should block water tank"),
        ("BMW Touring E91 Parts", "test", True, "Should block BMW E91"),
        ("Mazda RX-7 Engine", "test", True, "Should block Mazda"),
        ("Band of Outsiders Vintage Tee", "test", True, "Should block Band of Outsiders"),
        
        # JDIRECTITEMS CATEGORY TESTS
        ("Rick Owens Jacket - JDirectItems Auction → Automobile", "rick_owens", True, "Should block automobile category"),
        ("Raf Simons Tee - JDirectItems Auction → Fashion", "raf_simons", False, "Should allow fashion category"),
        ("Undercover Jacket - JDirectItems Auction → Motorcycle", "undercover", True, "Should block motorcycle category"),
        
        # VALID FASHION ITEMS
        ("Rick Owens DRKSHDW Jacket Black Size 50", "rick_owens", False, "Valid fashion item"),
        ("Raf Simons Archive Tee Shirt", "raf_simons", False, "Valid fashion item"),
        ("Maison Margiela Replica Sneakers", "maison_margiela", False, "Valid fashion item"),
        
        # INVALID ITEMS
        ("Honda CB400 Engine Parts", "random", True, "Should block motorcycle parts"),
        ("Computer Server RAM Memory", "random", True, "Should block electronics"),
        ("Pokémon Trading Cards", "random", True, "Should block trading cards"),
    ]
    
    print("🧪 Testing Enhanced Filtering System:")
    print("=" * 50)
    
    for title, brand, should_be_spam, description in test_cases:
        is_spam, category = detector.is_spam(title, brand)
        status = "✅" if (is_spam == should_be_spam) else "❌"
        print(f"{status} {description}")
        print(f"   Title: '{title}'")
        print(f"   Result: Spam={is_spam} ({category})")
        print()

if __name__ == "__main__":
    print("🚀 Enhanced Filtering System v2.0")
    print("New Features:")
    print("- Added LEGO, Water Tank, BMW E91, Mazda, Band of Outsiders exclusions")
    print("- Strict JDirectItems category filtering (Fashion only)")
    print("- Improved price filtering thresholds")
    print("- Enhanced category detection")
    print()
    test_enhanced_filtering()
