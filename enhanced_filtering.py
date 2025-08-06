"""
Enhanced filtering system for auction bot (Simplified version - no ML dependencies)
Add this as enhanced_filtering.py
"""

import sqlite3
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict

class EnhancedSpamDetector:
    """Improved spam detection with pattern matching"""
    
    def __init__(self):
        self.spam_patterns = {
            'motorcycle_parts': [
                r'cb\d+[sf]?', r'vtr\d+', r'cbx\d+', r'jade', r'hornet',
                r'undercowl', r'アンダーカウル', r'フロント', r'リア', 
                r'エンジン', r'motorcycle', r'engine', r'バイク'
            ],
            'luxury_accessories': [
                r'財布', r'wallet', r'purse', r'clutch', r'handbag',
                r'earring', r'pierce', r'ピアス', r'ring', r'指輪',
                r'necklace', r'ネックレス', r'bracelet', r'perfume', r'香水',
                r'bag', r'バッグ', r'ポーチ', r'pouch'
            ],
            'bootleg_brands': [
                r'ifsixwasnine', r'share spirit', r'kmrii', r'14th addiction',
                r'civarize', r'fuga', r'tornado mart', r'luxe/?r', r'doll bear',
                r'goa', r'ekam', r'midas'
            ],
            'electronics': [
                r'server', r'raid', r'pci', r'computer', r'motherboard',
                r'graphics card', r'cpu', r'ram', r'ssd', r'hdd', r'monitor'
            ],
            'food_items': [
                r'food', r'食品', r'snack', r'チップ', r'chips', r'candy',
                r'chocolate', r'drink', r'beverage'
            ],
            'media_items': [
                r'poster', r'ポスター', r'sticker', r'magazine', r'雑誌',
                r'dvd', r'book', r'本', r'figure', r'フィギュア', r'toy'
            ],
            'womens_clothing': [
                r'femme', r'women', r'ladies', r'レディース', r'ウィメンズ',
                r'dress', r'ドレス', r'skirt', r'スカート', r'blouse', r'ブラウス',
                r'heel', r'ヒール', r'pump', r'パンプス', r'sandal', r'サンダル',
                r'bra', r'ブラ', r'lingerie', r'ランジェリー'
            ],
            'kids_clothing': [
                r'kids', r'child', r'children', r'baby', r'infant', r'toddler',
                r'キッズ', r'子供', r'ベビー', r'幼児', r'こども', r'子ども',
                r'boys', r'girls', r'youth', r'junior'
            ]
        }
        
        # Brand-specific spam patterns
        self.brand_specific_spam = {
            'prada': [
                'wallet', '財布', 'bag', 'バッグ', 'purse', 'handbag', 'keychain', 'キーホルダー',
                'pouch', 'ポーチ', 'case', 'ケース', 'accessory', 'アクセサリー',
                'necklace', 'ネックレス', 'bracelet', 'ブレスレット', 'earring', 'ピアス',
                'ring', '指輪', 'perfume', '香水', 'fragrance', 'cologne',
                'prada sport', 'プラダスポーツ', 'vintage', 'ヴィンテージ'
            ],
            'celine': ['wallet', '財布', 'bag', 'バッグ', 'purse', 'handbag'],
            'bottega_veneta': ['wallet', '財布', 'bag', 'バッグ', 'clutch'],
            'miu_miu': [
                'dress', 'skirt', 'blouse', 'femme', 'women', 'ladies',
                'ドレス', 'スカート', 'ブラウス', 'レディース'
            ],
            'jean_paul_gaultier': ['femme', 'women', 'ladies', 'レディース'],
            'balenciaga': ['yeezy', 'gap', 'yeezy gap']
        }
        
        # Special allowed terms that override spam detection
        self.brand_specific_allowed = {
            'maison_margiela': ['replica', 'レプリカ'],
            'margiela': ['replica', 'レプリカ'],
            'undercover': ['cb400', 'vtr250', 'motorcycle', 'バイク', 'engine', 'cb', 'vtr'],
            'rick_owens': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'balenciaga': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'prada': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'celine': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'bottega_veneta': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'maison_margiela': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'comme_des_garcons': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'raf_simons': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'martine_rose': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'alyx': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'kiko_kostadinov': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'chrome_hearts': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'hysteric_glamour': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'junya_watanabe': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'vetements': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ'],
            'jean_paul_gaultier': ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ']
        }
        
        # Universal exclusions
        self.universal_exclusions = [
            'zara', 'ザラ'
        ]
    
    def is_spam(self, title, brand):
        """Enhanced spam detection with pattern matching"""
        title_lower = title.lower()
        brand_lower = brand.lower() if brand else ""
        
        # Check universal exclusions first
        for exclusion in self.universal_exclusions:
            if exclusion in title_lower:
                print(f"🚫 Universal exclusion detected: {exclusion} in '{title[:30]}...'")
                return True, "universal_exclusion"
        
        # Check for kids clothing (universal block)
        for pattern in self.spam_patterns['kids_clothing']:
            if re.search(pattern, title_lower) or re.search(pattern, brand_lower):
                print(f"🚫 Kids clothing detected: {pattern} in '{title[:30]}...'")
                return True, "kids_clothing"
        
        # Check for women's clothing ONLY for Miu Miu and Jean Paul Gaultier
        if 'miu_miu' in brand_lower or 'miu miu' in brand_lower or 'jean_paul_gaultier' in brand_lower or 'jean paul gaultier' in brand_lower:
            for pattern in self.spam_patterns['womens_clothing']:
                if re.search(pattern, title_lower):
                    print(f"🚫 Women's clothing detected for {brand}: {pattern} in '{title[:30]}...'")
                    return True, "womens_clothing"
        
        # Check motorcycle parts - but allow Undercover to have motorcycle themes
        for pattern in self.spam_patterns['motorcycle_parts']:
            if re.search(pattern, title_lower) or re.search(pattern, brand_lower):
                # Allow Undercover to have motorcycle themes
                if 'undercover' in brand_lower:
                    print(f"✅ Motorcycle theme allowed for Undercover: {pattern} in '{title[:30]}...'")
                    continue
                else:
                    print(f"🚫 Motorcycle parts detected: {pattern} in '{title[:30]}...'")
                    return True, "motorcycle_parts"
        
        # Check luxury accessories - but allow shoes for fashion brands
        for pattern in self.spam_patterns['luxury_accessories']:
            if re.search(pattern, title_lower) or re.search(pattern, brand_lower):
                # Check if this is a shoe-related term that should be allowed for fashion brands
                shoe_terms = ['boot', 'sneaker', 'shoe', '靴', 'シューズ', 'ブーツ']
                if any(shoe_term in pattern for shoe_term in shoe_terms):
                    # Allow shoes for fashion brands
                    fashion_brands = ['rick_owens', 'balenciaga', 'prada', 'celine', 'bottega_veneta', 
                                     'maison_margiela', 'comme_des_garcons', 'raf_simons', 'martine_rose',
                                     'alyx', 'kiko_kostadinov', 'chrome_hearts', 'hysteric_glamour',
                                     'junya_watanabe', 'vetements', 'jean_paul_gaultier']
                    if any(fashion_brand in brand_lower for fashion_brand in fashion_brands):
                        print(f"✅ Shoes allowed for fashion brand {brand}: {pattern} in '{title[:30]}...'")
                        continue
                
                print(f"🚫 Luxury accessory detected: {pattern} in '{title[:30]}...'")
                return True, "luxury_accessories"
        
        # Check general spam patterns (excluding motorcycle_parts and luxury_accessories which are handled above)
        for category, patterns in self.spam_patterns.items():
            if category in ['kids_clothing', 'womens_clothing', 'motorcycle_parts', 'luxury_accessories']:
                continue  # Already checked above
            for pattern in patterns:
                if re.search(pattern, title_lower) or re.search(pattern, brand_lower):
                    print(f"🚫 Spam detected ({category}): {pattern} in '{title[:30]}...'")
                    return True, category
        
        # Check brand-specific spam
        brand_clean = brand_lower.replace('_', ' ').replace('-', ' ')
        for spam_brand, spam_items in self.brand_specific_spam.items():
            spam_brand_clean = spam_brand.replace('_', ' ').replace('-', ' ')
            if spam_brand_clean in brand_clean:
                for spam_item in spam_items:
                    if spam_item in title_lower:
                        # Check if this is an allowed term for this brand
                        allowed_terms = self.brand_specific_allowed.get(spam_brand, [])
                        if spam_item not in allowed_terms:
                            print(f"🚫 Brand-specific spam: {spam_item} in {spam_brand}")
                            return True, f"{spam_brand}_spam"
                        else:
                            print(f"✅ Allowed term for {spam_brand}: {spam_item}")
        
        # Additional heuristics
        if self._has_suspicious_pricing(title):
            return True, "suspicious_pricing"
        
        if self._has_spam_keywords(title):
            return True, "spam_keywords"
        
        return False, None
    
    def _has_suspicious_pricing(self, title):
        """Detect suspiciously formatted prices or bulk listings"""
        price_patterns = [
            r'\d+個セット', r'\d+点セット', r'まとめ売り',
            r'bulk', r'wholesale', r'lot of \d+', r'set of \d+'
        ]
        
        return any(re.search(pattern, title.lower()) for pattern in price_patterns)
    
    def _has_spam_keywords(self, title):
        """Detect additional spam keywords"""
        spam_keywords = [
            'replica', r'レプリカ', 'fake', 'copy', 'bootleg',
            'damaged', 'broken', 'parts only', 'for parts'
        ]
        
        title_lower = title.lower()
        return any(re.search(keyword, title_lower) for keyword in spam_keywords)

class SimplePriceAnalytics:
    """Simplified price analysis without heavy dependencies"""
    
    def __init__(self, db_file="auction_tracking.db"):
        self.db_file = db_file
        self.price_cache = {}
        self.cache_expiry = timedelta(hours=6)
    
    def get_basic_market_data(self, brand, days=30):
        """Get basic market statistics for a brand"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT price_usd, deal_quality 
                FROM listings 
                WHERE brand = ? AND created_at > datetime('now', '-{} days')
                ORDER BY created_at DESC
                LIMIT 50
            '''.format(days), (brand,))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return None
            
            prices = [row[0] for row in results]
            qualities = [row[1] for row in results]
            
            # Simple statistics
            prices.sort()
            n = len(prices)
            
            return {
                'total_listings': n,
                'min_price': min(prices),
                'max_price': max(prices),
                'median_price': prices[n // 2] if n > 0 else 0,
                'avg_price': sum(prices) / n if n > 0 else 0,
                'avg_quality': sum(qualities) / len(qualities) if qualities else 0
            }
        except Exception as e:
            print(f"Error getting market data: {e}")
            conn.close()
            return None
    
    def is_good_deal(self, price_usd, brand, title):
        """Simple deal analysis"""
        market_data = self.get_basic_market_data(brand)
        
        if not market_data:
            return None
        
        median_price = market_data['median_price']
        
        if price_usd <= median_price * 0.6:
            savings = ((median_price - price_usd) / median_price) * 100
            return {'level': 'steal', 'savings_pct': savings}
        elif price_usd <= median_price * 0.8:
            savings = ((median_price - price_usd) / median_price) * 100
            return {'level': 'good', 'savings_pct': savings}
        elif price_usd <= median_price * 1.2:
            return {'level': 'fair', 'savings_pct': 0}
        else:
            markup = ((price_usd - median_price) / median_price) * 100
            return {'level': 'expensive', 'markup_pct': markup}

class SimpleTrendAnalyzer:
    """Basic trend analysis without ML"""
    
    def __init__(self, db_file="auction_tracking.db"):
        self.db_file = db_file
    
    def get_trending_brands(self, days=7):
        """Get brands with recent activity"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT brand, 
                       COUNT(*) as recent_listings,
                       AVG(deal_quality) as avg_quality,
                       COUNT(CASE WHEN r.reaction_type = 'thumbs_up' THEN 1 END) as likes
                FROM listings l
                LEFT JOIN reactions r ON l.auction_id = r.auction_id
                WHERE l.created_at > datetime('now', '-{} days')
                GROUP BY brand
                HAVING recent_listings >= 2
                ORDER BY recent_listings DESC, likes DESC
                LIMIT 10
            '''.format(days))
            
            results = cursor.fetchall()
            conn.close()
            
            trending = []
            for brand, listings, quality, likes in results:
                # Simple momentum score
                momentum = (listings * 2) + (likes or 0) + (quality * 10)
                trending.append({
                    'brand': brand,
                    'listings': listings,
                    'avg_quality': quality or 0,
                    'likes': likes or 0,
                    'momentum_score': momentum
                })
            
            return sorted(trending, key=lambda x: x['momentum_score'], reverse=True)
            
        except Exception as e:
            print(f"Error getting trending brands: {e}")
            conn.close()
            return []
    
    def get_recent_deals(self, hours=24):
        """Get recent good deals"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT auction_id, title, brand, price_usd, deal_quality, zenmarket_url
                FROM listings 
                WHERE created_at > datetime('now', '-{} hours')
                AND deal_quality > 0.6
                AND price_usd < 500
                ORDER BY deal_quality DESC, price_usd ASC
                LIMIT 15
            '''.format(hours))
            
            results = cursor.fetchall()
            conn.close()
            
            deals = []
            for auction_id, title, brand, price_usd, quality, url in results:
                deals.append({
                    'auction_id': auction_id,
                    'title': title,
                    'brand': brand,
                    'price_usd': price_usd,
                    'deal_quality': quality,
                    'url': url
                })
            
            return deals
            
        except Exception as e:
            print(f"Error getting recent deals: {e}")
            conn.close()
            return []

class QualityChecker:
    """Enhanced quality checking with stricter thresholds"""
    
    def __init__(self):
        self.spam_detector = EnhancedSpamDetector()
        self.price_analyzer = SimplePriceAnalytics()
    
    def check_listing_quality(self, auction_data):
        """Run enhanced quality checks on a listing with much stricter standards"""
        issues = []
        confidence = 0.0
        
        title = auction_data.get('title', '')
        brand = auction_data.get('brand', '')
        price_usd = auction_data.get('price_usd', 0)
        
        # Spam detection
        is_spam, spam_type = self.spam_detector.is_spam(title, brand)
        if is_spam:
            issues.append(f"Spam detected: {spam_type}")
            confidence += 0.8
        
        # MUCH STRICTER PRICE FILTERING
        if price_usd < 10:
            issues.append("Price too low - likely fake/damaged")
            confidence += 0.6
        elif price_usd > 1000:
            issues.append("Price very high - needs verification")
            confidence += 0.3
        
        # STRICTER TITLE REQUIREMENTS
        if len(title) < 15:
            issues.append("Title too short - insufficient detail")
            confidence += 0.4
        
        # REQUIRE CLOTHING KEYWORDS
        clothing_keywords = [
            'shirt', 'tee', 'jacket', 'pants', 'hoodie', 'sweater', 'coat',
            'シャツ', 'Tシャツ', 'ジャケット', 'パンツ', 'パーカー', 'セーター'
        ]
        
        has_clothing_keyword = any(keyword in title.lower() for keyword in clothing_keywords)
        if not has_clothing_keyword:
            issues.append("No clear clothing category identified")
            confidence += 0.5
        
        # BLOCK SUSPICIOUS PATTERNS
        suspicious_patterns = [
            'まとめ売り', 'セット', 'ジャンク', 'parts only', 'for parts',
            'damaged', 'broken', '破れ', '汚れ', '難あり', 'stain', 'hole'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in title.lower():
                issues.append(f"Suspicious pattern detected: {pattern}")
                confidence += 0.7
        
        # REQUIRE ARCHIVE/QUALITY INDICATORS FOR EXPENSIVE ITEMS
        if price_usd > 200:
            quality_indicators = [
                'archive', 'rare', 'vintage', 'runway', 'collection',
                'アーカイブ', 'レア', 'ヴィンテージ', 'コレクション', 'fw', 'ss',
                'mainline', 'メインライン', 'homme', 'オム'
            ]
            has_quality_indicator = any(indicator in title.lower() for indicator in quality_indicators)
            if not has_quality_indicator:
                issues.append("Expensive item lacks quality indicators")
                confidence += 0.4
        
        # BLOCK VERY CHEAP ITEMS WITHOUT ARCHIVE KEYWORDS
        if price_usd < 25:
            archive_keywords = ['archive', 'rare', 'vintage', 'アーカイブ', 'レア', 'ヴィンテージ']
            has_archive = any(keyword in title.lower() for keyword in archive_keywords)
            if not has_archive:
                issues.append("Very cheap item without archive justification")
                confidence += 0.6
        
        # BLOCK ITEMS WITH TOO MANY SUSPICIOUS TERMS
        suspicious_count = 0
        suspicious_terms = [
            'used', '中古', 'second hand', 'pre owned', 'worn', '着用',
            'condition', 'コンディション', 'state', '状態'
        ]
        for term in suspicious_terms:
            if term in title.lower():
                suspicious_count += 1
        
        if suspicious_count >= 3:
            issues.append("Too many condition-related terms")
            confidence += 0.3
        
        should_block = confidence > 0.5  # Stricter threshold
        
        return {
            'should_block': should_block,
            'confidence': confidence,
            'issues': issues,
            'action': 'block' if should_block else 'allow'
        }

# Test function
def test_spam_detection():
    """Test the spam detection"""
    detector = EnhancedSpamDetector()
    
    test_cases = [
        ("Raf Simons Archive Tee Shirt Size 50", "raf_simons", False),
        ("CB400SF Engine Parts Motorcycle", "undercover", False),
        ("Celine Wallet Leather Handbag", "celine", True),
        ("Rick Owens DRKSHDW Jacket Black", "rick_owens", False),
        ("Rick Owens Boots Size 42", "rick_owens", False),
        ("Computer Server RAM Memory", "maison_margiela", True),
        ("Miu Miu Dress Women's Size 38", "miu_miu", True),
        ("Jean Paul Gaultier Femme Blouse", "jean_paul_gaultier", True),
        ("Balenciaga Kids T-Shirt Size 10", "balenciaga", True),
        ("Balenciaga Triple S Sneakers", "balenciaga", False),
        ("Martine Rose Shirt Size L", "martine_rose", False),
        ("Undercover Motorcycle Jacket", "undercover", False),
        ("Random Brand CB400 Engine Parts", "random_brand", True),
        ("Prada Boots Leather", "prada", False),
        ("Celine Sneakers White", "celine", False),
        ("Celine Wallet Brown", "celine", True),
        ("Prada Bag Black", "prada", True),
        ("Undercover CB400 Jacket", "undercover", False),
        ("Random Brand CB400 Parts", "random_brand", True)
    ]
    
    for title, brand, should_be_spam in test_cases:
        is_spam, category = detector.is_spam(title, brand)
        status = "✅" if (is_spam == should_be_spam) else "❌"
        print(f"{status} '{title}' -> Spam: {is_spam} ({category})")

if __name__ == "__main__":
    print("Testing Enhanced Filtering...")
    test_spam_detection()
    print("✅ Enhanced filtering ready!")