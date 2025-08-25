#!/usr/bin/env python3
"""
ZenMarket Mercari Scraper Module
Add this to your existing yahoo_sniper.py system
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import re
from urllib.parse import quote_plus

# ZenMarket Mercari search URL structure
ZENMARKET_MERCARI_BASE = "https://zenmarket.jp/en/mercari/search"
ZENMARKET_ITEM_BASE = "https://zenmarket.jp/en/mercari/item"

def search_zenmarket_mercari(keyword, max_pages=2):
    """
    Search ZenMarket's Mercari integration for fashion items
    Returns items in the same format as Yahoo Auctions scraper
    """
    items = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    for page in range(1, max_pages + 1):
        try:
            # ZenMarket Mercari search URL
            search_url = f"{ZENMARKET_MERCARI_BASE}?keyword={quote_plus(keyword)}&page={page}&sort=created_at&order=desc"
            
            print(f"🔍 Searching ZenMarket Mercari: {keyword} (page {page})")
            
            response = requests.get(search_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find product containers (adapt selectors based on ZenMarket's structure)
                product_containers = soup.find_all(['div', 'article'], class_=re.compile(r'item|product|listing', re.I))
                
                if not product_containers:
                    # Fallback selectors
                    product_containers = soup.find_all('div', attrs={'data-item-id': True})
                
                if not product_containers:
                    # More general fallback
                    product_containers = soup.select('a[href*="/mercari/item/"]')
                    product_containers = [link.find_parent(['div', 'article']) for link in product_containers if link.find_parent(['div', 'article'])]
                
                print(f"📦 Found {len(product_containers)} potential items on page {page}")
                
                for container in product_containers[:15]:  # Process first 15 items per page
                    try:
                        item_data = extract_zenmarket_mercari_item(container)
                        if item_data and is_target_fashion_item(item_data):
                            items.append(item_data)
                            print(f"✅ Found: {item_data['brand']} - {item_data['title'][:50]}... - ¥{item_data['price_jpy']:,} (${item_data['price_usd']:.2f})")
                    
                    except Exception as e:
                        print(f"❌ Error parsing ZenMarket item: {e}")
                        continue
                
                # Rate limiting
                time.sleep(random.uniform(2, 4))
                
            else:
                print(f"❌ ZenMarket Mercari request failed: {response.status_code}")
                break
                
        except Exception as e:
            print(f"❌ Error searching ZenMarket Mercari for {keyword}: {e}")
            break
    
    return items

def extract_zenmarket_mercari_item(container):
    """Extract item data from ZenMarket Mercari listing"""
    try:
        # Extract title
        title_elem = (
            container.find('h3') or
            container.find('h4') or
            container.find('a', title=True) or
            container.find(class_=re.compile(r'title|name', re.I))
        )
        
        if not title_elem:
            return None
            
        title = title_elem.get('title') or title_elem.get_text(strip=True)
        
        # Extract ZenMarket URL
        link_elem = container.find('a', href=True)
        if not link_elem:
            return None
            
        zenmarket_url = link_elem['href']
        if not zenmarket_url.startswith('http'):
            zenmarket_url = f"https://zenmarket.jp{zenmarket_url}"
        
        # Extract Mercari item ID from ZenMarket URL
        mercari_id_match = re.search(r'/mercari/item/([^/?]+)', zenmarket_url)
        if not mercari_id_match:
            return None
        
        mercari_id = mercari_id_match.group(1)
        
        # Extract price
        price_elem = container.find(string=re.compile(r'[¥￥]\s*[\d,]+'))
        if not price_elem:
            price_elem = container.find(class_=re.compile(r'price', re.I))
        
        if not price_elem:
            return None
            
        price_text = price_elem.get_text(strip=True) if hasattr(price_elem, 'get_text') else str(price_elem)
        price_match = re.search(r'[¥￥]\s*([\d,]+)', price_text)
        
        if not price_match:
            return None
        
        price_jpy = int(price_match.group(1).replace(',', ''))
        price_usd = price_jpy / 150.0  # Approximate conversion
        
        # Filter by price (under $100)
        if price_usd > 100:
            return None
        
        # Extract image
        image_url = None
        img_elem = container.find('img')
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-src')
            if image_url and image_url.startswith('//'):
                image_url = f"https:{image_url}"
        
        # Detect brand from title
        detected_brand = detect_brand_in_title(title)
        if not detected_brand:
            return None
        
        # Create original Mercari URL (for reference)
        original_mercari_url = f"https://jp.mercari.com/item/{mercari_id}"
        
        return {
            'auction_id': f"mercari_{mercari_id}",
            'title': title,
            'brand': detected_brand,
            'price_jpy': price_jpy,
            'price_usd': price_usd,
            'zenmarket_url': zenmarket_url,
            'yahoo_url': original_mercari_url,  # Keep same format as Yahoo scraper
            'image_url': image_url,
            'source': 'Mercari (via ZenMarket)',
            'seller_id': 'mercari_seller',
            'deal_quality': calculate_mercari_deal_quality(price_usd, detected_brand, title),
            'priority': 0,  # Will be calculated later
            'auction_end_time': None
        }
        
    except Exception as e:
        print(f"❌ Error extracting ZenMarket Mercari item: {e}")
        return None

def is_target_fashion_item(item_data):
    """Check if item matches our target criteria"""
    title_lower = item_data['title'].lower()
    
    # Check for target brands
    target_brands = ['rick owens', 'junya watanabe', 'comme des garcons', 'cdg']
    if not any(brand in item_data['brand'].lower() for brand in target_brands):
        return False
    
    # Check for target clothing types
    clothing_types = [
        'jacket', 'shirt', 'pants', 'hoodie', 'sweater', 'blazer',
        'ジャケット', 'シャツ', 'パンツ', 'パーカー', 'セーター', 'ブレザー'
    ]
    
    if not any(clothing_type in title_lower for clothing_type in clothing_types):
        return False
    
    # Exclude women's items
    if 'femme' in title_lower or 'women' in title_lower or 'レディース' in title_lower:
        return False
    
    # Price check (already done in extraction, but double-check)
    if item_data['price_usd'] > 100:
        return False
    
    return True

def detect_brand_in_title(title):
    """Detect brand from title - reuse existing function"""
    title_lower = title.lower()
    
    brand_mapping = {
        'Rick Owens': ['rick owens', 'rick', 'drkshdw', 'リックオーウェンス'],
        'Junya Watanabe': ['junya watanabe', 'junya', 'ジュンヤワタナベ'],
        'Comme Des Garcons': ['comme des garcons', 'cdg', 'コムデギャルソン', 'ギャルソン']
    }
    
    for brand, variations in brand_mapping.items():
        for variation in variations:
            if variation in title_lower:
                return brand
    return None

def calculate_mercari_deal_quality(price_usd, brand, title):
    """Calculate deal quality for Mercari items"""
    # Simplified version of existing deal quality calculation
    title_lower = title.lower()
    
    base_quality = 0.3  # Mercari items start with decent quality
    
    # Brand bonus
    if 'rick owens' in brand.lower():
        base_quality += 0.3
    elif 'junya watanabe' in brand.lower():
        base_quality += 0.25
    elif 'comme des garcons' in brand.lower():
        base_quality += 0.2
    
    # Price bonus
    if price_usd <= 30:
        base_quality += 0.3
    elif price_usd <= 60:
        base_quality += 0.2
    elif price_usd <= 80:
        base_quality += 0.1
    
    # Archive/rare bonus
    if any(word in title_lower for word in ['archive', 'rare', 'vintage', 'fw', 'ss']):
        base_quality += 0.2
    
    return min(1.0, base_quality)

def run_zenmarket_mercari_scrape():
    """Main function to scrape ZenMarket Mercari and return items"""
    target_brands = ['Rick Owens', 'Junya Watanabe', 'Comme Des Garcons']
    
    all_items = []
    
    for brand in target_brands:
        print(f"🎯 Searching ZenMarket Mercari for {brand}")
        
        # Search for brand + clothing combinations
        clothing_types = ['jacket', 'shirt', 'pants', 'hoodie', 'sweater', 'blazer']
        
        # Search brand alone first
        brand_items = search_zenmarket_mercari(brand, max_pages=2)
        all_items.extend(brand_items)
        
        # Search brand + clothing combinations
        for clothing_type in clothing_types[:3]:  # Limit to first 3 clothing types per brand
            search_term = f"{brand} {clothing_type}"
            clothing_items = search_zenmarket_mercari(search_term, max_pages=1)
            all_items.extend(clothing_items)
            
            # Rate limiting between searches
            time.sleep(random.uniform(3, 5))
    
    # Remove duplicates and sort by price
    unique_items = {}
    for item in all_items:
        if item['auction_id'] not in unique_items:
            unique_items[item['auction_id']] = item
    
    final_items = list(unique_items.values())
    final_items.sort(key=lambda x: x['price_usd'])
    
    print(f"🔥 ZenMarket Mercari scrape found {len(final_items)} unique items under $100")
    
    return final_items

# Integration with existing yahoo_sniper.py:
def add_to_main_loop():
    """
    Add this to your main_loop() in yahoo_sniper.py:
    
    # After your existing Yahoo Auctions scraping
    try:
        print("\\n🛒 Starting ZenMarket Mercari scrape...")
        mercari_items = run_zenmarket_mercari_scrape()
        
        for item in mercari_items[:5]:  # Send top 5 Mercari finds
            send_to_discord_bot(item)
            time.sleep(2)  # Rate limit Discord
            
        print(f"✅ Sent {min(len(mercari_items), 5)} Mercari items to Discord")
        
    except Exception as e:
        print(f"❌ ZenMarket Mercari scrape error: {e}")
    """
    pass

if __name__ == "__main__":
    # Test the scraper
    print("🧪 Testing ZenMarket Mercari scraper...")
    items = run_zenmarket_mercari_scrape()
    
    if items:
        print(f"\\n✅ Test successful! Found {len(items)} items")
        for item in items[:3]:
            print(f"  - {item['brand']}: {item['title'][:60]}... - ¥{item['price_jpy']:,} (${item['price_usd']:.2f})")
    else:
        print("\\n❌ Test failed - no items found")