#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json
import time
import random
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import List, Optional
import logging
from datetime import datetime
import re
import base64
import subprocess
import sys


# Try to import optional packages
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False



@dataclass
class Product:
    title: str
    brand: str
    price: str
    original_price: str
    url: str
    image_url: str
    size: str
    condition: str

class SimpleTheRealRealScraper:
    def __init__(self, email: str = None, password: str = None):
        self.base_url = "https://www.therealreal.com"
        self.conversation_log = []
        self.email = email
        self.password = password
        self.is_logged_in = False
        
        # Create session
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper()
            print("☁️ Using CloudScraper")
        else:
            self.session = requests.Session()
            print("📡 Using requests with enhanced headers")
        
        # Target brands and garments
        self.brands = [
            "Junya Watanabe",
            "Comme Des Garçons", 
            "CDG",
            "Rick Owens"
        ]
        
        self.garments = [
            "Jackets",
            "Shirts", 
            "Pants",
            "Hoodies",
            "Sweaters",
            "Blazers"
        ]
        
        self.setup_session()
        self.setup_logging()
    
    def load_seen_items(self):
        """Load previously seen items from file"""
        try:
            with open('seen_items.json', 'r') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def save_seen_items(self, seen_urls):
        """Save seen items to file"""
        with open('seen_items.json', 'w') as f:
            json.dump(list(seen_urls), f)
    
    def setup_session(self):
        """Setup session with rotating headers"""
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.session.headers.update(headers)
    

    
    def setup_logging(self):
        # Use a single persistent log file
        log_filename = 'therealreal_scraper.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, mode='a'),  # Append mode
                logging.StreamHandler()
            ],
            force=True  # Override any existing loggers
        )
        self.logger = logging.getLogger(__name__)
    
    def log_conversation(self, action: str, data: any = None):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'data': data
        }
        self.conversation_log.append(entry)
        self.logger.info(f"Action: {action}")
    
    def random_delay(self, min_delay: float = 3, max_delay: float = 7):
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def make_request(self, url: str, retries: int = 3) -> Optional[requests.Response]:
        for attempt in range(retries):
            try:
                self.log_conversation(f"Making request to: {url}")
                
                # Add some randomness between attempts
                if attempt > 0:
                    self.random_delay(5, 10)
                
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    self.logger.info(f"✅ Successfully fetched: {url}")
                    return response
                else:
                    self.logger.warning(f"⚠️ Status {response.status_code} for: {url}")
                    
            except Exception as e:
                self.logger.error(f"❌ Request failed (attempt {attempt + 1}/{retries}): {str(e)}")
                if attempt == retries - 1:
                    return None
                
        return None
    
    def get_search_url(self, brand: str, max_price: int = 100, page: int = 1) -> str:
        """Generate search URL for TheRealReal"""
        params = {
            'keywords': brand,
            'price_max': str(max_price),
            'sort': 'newest',  # Sort by newest listings first
            'department': 'men',
            'page': str(page)
        }
        
        return f"{self.base_url}/shop?{urlencode(params)}"
    
    def extract_price_value(self, price_text: str) -> float:
        if not price_text:
            return 0
        
        price_match = re.search(r'\$?([\d,]+)(?:\.\d{2})?', price_text.replace(',', ''))
        if price_match:
            return float(price_match.group(1))
        return 0
    
    def parse_product_card(self, card_soup) -> Optional[Product]:
        try:
            # Get all text from the card for comprehensive analysis
            all_card_text = card_soup.get_text(separator=' ', strip=True)
            
            # Extract title - try multiple approaches
            title = "Unknown Product"
            
            # Strategy 1: Look for title in various elements
            title_selectors = [
                'h1', 'h2', 'h3', 'h4', 'h5', 
                'a[href*="/products/"]',
                '[class*="title"]', '[class*="name"]', '[class*="product"]'
            ]
            
            for selector in title_selectors:
                elem = card_soup.select_one(selector)
                if elem and elem.get_text(strip=True):
                    candidate_title = elem.get_text(strip=True)
                    # Make sure it's not just a price or short text
                    if len(candidate_title) > 5 and '$' not in candidate_title:
                        title = candidate_title
                        break
            
            # Extract brand from title or URL
            brand = "Unknown"
            title_lower = title.lower()
            for target_brand in self.brands:
                if target_brand.lower() in title_lower:
                    brand = target_brand
                    break
            
            # Enhanced price extraction
            price_selectors = [
                '[class*="price"]', '[class*="cost"]', 'span:contains("$")',
                '.price', '.current-price', '[data-testid*="price"]'
            ]
            
            price = "N/A"
            for selector in price_selectors:
                price_elem = card_soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    if '$' in price_text:
                        price = price_text
                        break
            
            # If no price found with selectors, search for any text with $
            if price == "N/A":
                price_elem = card_soup.find(string=re.compile(r'\$\d+'))
                if price_elem:
                    price = price_elem.strip()
            
            # Enhanced URL extraction
            url_selectors = [
                'a[href*="/products/"]', 'a[class*="product"]', 'a[class*="item"]', 
                'a[href*="/p/"]', 'a[data-testid*="product"]'
            ]
            
            url = "N/A"
            for selector in url_selectors:
                link_elem = card_soup.select_one(selector)
                if link_elem and link_elem.get('href'):
                    url = link_elem['href']
                    if not url.startswith('http'):
                        url = self.base_url + url
                    break
            
            # Enhanced image extraction
            image_selectors = [
                'img[src*="product"]', 'img[class*="product"]', 'img[data-testid*="image"]',
                'img[alt*="product"]', 'picture img', '.product-image img'
            ]
            
            image_url = "N/A"
            for selector in image_selectors:
                img_elem = card_soup.select_one(selector)
                if img_elem and img_elem.get('src'):
                    image_url = img_elem['src']
                    # Handle relative URLs and data URLs
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/') and not image_url.startswith('//'):
                        image_url = self.base_url + image_url
                    elif image_url.startswith('data:'):
                        # Skip data URLs
                        continue
                    break
            
            # Try to get higher quality image
            if image_url != "N/A":
                # Look for srcset or data-src for higher quality
                img_elem = card_soup.select_one('img')
                if img_elem:
                    srcset = img_elem.get('srcset')
                    data_src = img_elem.get('data-src')
                    if srcset:
                        # Parse srcset and get largest image
                        sources = srcset.split(',')
                        if sources:
                            largest = sources[-1].strip().split()[0]
                            if largest.startswith('http') or largest.startswith('//'):
                                image_url = largest if largest.startswith('http') else 'https:' + largest
                    elif data_src and (data_src.startswith('http') or data_src.startswith('//')):
                        image_url = data_src if data_src.startswith('http') else 'https:' + data_src
            
            # Enhanced size extraction
            size_patterns = [
                r'size[:\s]+([a-zA-Z0-9]+)',
                r'([XS|S|M|L|XL|XXL|XXXL])\b',
                r'(\d{1,2})\s*(?:inch|"|\')',
                r'US\s*(\d+)',
                r'EU\s*(\d+)'
            ]
            
            size = "N/A"
            full_text = card_soup.get_text().lower()
            for pattern in size_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    size = match.group(1)
                    break
            
            # Enhanced condition extraction
            condition_keywords = ['excellent', 'very good', 'good', 'fair', 'new', 'mint']
            condition = "N/A"
            for keyword in condition_keywords:
                if keyword in full_text:
                    condition = keyword.title()
                    break
            
            # Check if item is sold - look for sold indicators
            sold_indicators = ['sold', 'unavailable', 'out of stock', 'see similar']
            if any(indicator in all_card_text.lower() for indicator in sold_indicators):
                return None  # Skip sold items
            
            return Product(
                title=title,
                brand=brand,
                price=price,
                original_price=price,
                url=url,
                image_url=image_url,
                size=size,
                condition=condition
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing product: {e}")
            return None
    
    def scrape_search_results(self, url: str, max_products: int = 50) -> List[Product]:
        response = self.make_request(url)
        if not response:
            self.logger.error(f"Failed to get response for: {url}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        products = []
        
        # Debug: Log page info
        page_title = soup.title.string if soup.title else 'No title'
        self.logger.info(f"Scraping page: {page_title}")
        
        # Enhanced product card selectors
        selectors = [
            '.product-card',
            '.item-card',
            '.listing-item',
            '[data-testid*="product"]',
            '[class*="ProductCard"]',
            '[class*="product-item"]',
            '[class*="Product_card"]',
            '[class*="ProductTile"]',
            '.product-tile',
            '.search-result',
            '[class*="search-result"]',
            'article[class*="product"]',
            'div[class*="product"][class*="card"]'
        ]
        
        product_cards = []
        used_selector = None
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards and len(cards) > 2:  # Need at least 3 cards to be valid
                product_cards = cards
                used_selector = selector
                self.logger.info(f"Found {len(cards)} items with selector: {selector}")
                break
        
        if not product_cards:
            # More aggressive fallback - look for any container with price
            all_containers = soup.find_all(['div', 'article', 'li'])
            potential_cards = []
            for container in all_containers:
                if container.find(string=re.compile(r'\$\d+')):
                    potential_cards.append(container)
            
            if potential_cards:
                product_cards = potential_cards
                used_selector = "price-containing divs"
                self.logger.info(f"Fallback: Found {len(potential_cards)} containers with prices")
        
        # Debug: Show some of the HTML structure if no products found
        if not product_cards:
            self.logger.warning("No product cards found. Analyzing page structure...")
            
            # Check if we're on a search results page
            if 'search' in url.lower() or 'shop' in url.lower():
                # Look for common "no results" indicators
                no_results_indicators = [
                    'no results', 'no products', 'no items', '0 results',
                    'try different', 'broaden your search'
                ]
                page_text = soup.get_text().lower()
                for indicator in no_results_indicators:
                    if indicator in page_text:
                        self.logger.info(f"Page indicates no results: '{indicator}' found")
                        return []
                
                # Log some structure for debugging
                body_classes = soup.body.get('class') if soup.body else []
                self.logger.warning(f"Body classes: {body_classes}")
                
                # Count elements with product-like classes
                product_like = soup.find_all(class_=re.compile(r'product|item|listing', re.I))
                self.logger.warning(f"Elements with product-like classes: {len(product_like)}")
                
                # Show price mentions
                price_mentions = soup.find_all(string=re.compile(r'\$\d+'))
                self.logger.warning(f"Price mentions found: {len(price_mentions)}")
        
        # Process each product card
        processed_count = 0
        for i, card in enumerate(product_cards):
            if processed_count >= max_products:
                self.logger.info(f"Reached max products limit ({max_products})")
                break
            
            # Skip sold items early
            card_text = card.get_text().lower()
            if any(sold_word in card_text for sold_word in ['sold', 'unavailable', 'see similar only']):
                continue
                
            try:
                product = self.parse_product_card(card)
                if product and product.price != "N/A":
                    price_value = self.extract_price_value(product.price)
                    if 0 < price_value <= 100:  # Valid price range
                        products.append(product)
                        processed_count += 1
                        self.log_conversation(f"Found product", {
                            'title': product.title,
                            'price': product.price
                        })
            except Exception as e:
                self.logger.error(f"Error processing card {i}: {e}")
                continue
        
        return products
    
    def scrape_brand(self, brand: str) -> List[Product]:
        self.log_conversation(f"Starting scrape for brand: {brand}")
        all_products = []
        
        # Search for brand
        search_url = self.get_search_url(brand)
        products = self.scrape_search_results(search_url)
        all_products.extend(products)
        
        self.random_delay(5, 10)
        
        return all_products
    
    def remove_duplicates(self, products: List[Product]) -> List[Product]:
        seen_urls = set()
        unique_products = []
        
        for product in products:
            if product.url not in seen_urls:
                seen_urls.add(product.url)
                unique_products.append(product)
        
        return unique_products
    
    def save_results(self, products: List[Product], filename: str = None):
        if not filename:
            filename = f"therealreal_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        results = {
            'scrape_date': datetime.now().isoformat(),
            'total_products': len(products),
            'products': [
                {
                    'title': p.title,
                    'brand': p.brand,
                    'price': p.price,
                    'original_price': p.original_price,
                    'url': p.url,
                    'image_url': p.image_url,
                    'size': p.size,
                    'condition': p.condition
                }
                for p in products
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Results saved to {filename}")
        return filename
    
    def send_to_discord(self, products: List[Product]):
        """Send products to Discord with rich embeds and brand names"""
        discord_webhook_url = "https://discord.com/api/webhooks/1407279132148240405/MrpynyFEiLYaxu4I1s0Ac0w-Ued4ZueeOIgG7ZwgEH--YZIXqelqUfld225nDwK4kekX"
        
        if not products:
            return
            
        try:
            for i, product in enumerate(products, 1):
                brand = product.brand if product.brand != "Unknown" else "Designer"
                
                embed = {
                    "title": product.title,
                    "url": product.url if product.url.startswith('http') else None,
                    "color": 0x2F3136,
                    "fields": [
                        {"name": "💰 Price", "value": product.price, "inline": True},
                        {"name": "🏷️ Brand", "value": brand, "inline": True}
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": f"TheRealReal • Item {i}/{len(products)}"}
                }
                
                if product.size not in ["N/A", "", "Unknown"]:
                    embed["fields"].append({"name": "📏 Size", "value": product.size, "inline": True})
                    
                if product.condition not in ["N/A", "", "Unknown"]:
                    embed["fields"].append({"name": "✨ Condition", "value": product.condition, "inline": True})
                
                if (product.image_url and product.image_url != "N/A" and 
                    product.image_url.startswith('http')):
                    embed["image"] = {"url": product.image_url}
                
                payload = {
                    "content": f"🔥 **{brand.upper()}** 🔥",
                    "embeds": [embed]
                }
                
                response = requests.post(discord_webhook_url, json=payload, timeout=10)
                
                if response.status_code == 204:
                    self.logger.info(f"✅ Sent: {product.title[:50]}...")
                else:
                    self.logger.error(f"❌ Discord failed: {response.status_code}")
                    
                time.sleep(0.5)
                
        except Exception as e:
            self.logger.error(f"Error sending to Discord: {e}")
    
    def run_scraper(self) -> List[Product]:
        self.log_conversation("Starting scraper")
        seen_urls = self.load_seen_items()
        all_products = []
        new_products = []
        
        for brand in self.brands:
            try:
                self.logger.info(f"Scraping brand: {brand}")
                brand_products = self.scrape_brand(brand)
                all_products.extend(brand_products)
                self.random_delay(10, 20)
            except Exception as e:
                self.logger.error(f"Error scraping {brand}: {str(e)}")
                continue
        
        # Filter out duplicates
        for product in all_products:
            if product.url not in seen_urls:
                new_products.append(product)
                seen_urls.add(product.url)
        
        if new_products:
            self.logger.info(f"Found {len(new_products)} new products")
            self.save_results(new_products)
            self.send_to_discord(new_products)
            self.save_seen_items(seen_urls)
        else:
            self.logger.info("No new products found")
        
        return new_products

def main():
    """Main function to run the scraper"""
    try:
        print("🚀 Starting TheRealReal Scraper...")
        print("=" * 50)
        
        scraper = SimpleTheRealRealScraper()
        products = scraper.run_scraper()
        
        print(f"\n{'='*50}")
        print(f"SCRAPING COMPLETE - FOUND {len(products)} PRODUCTS")
        print(f"{'='*50}")
        
        if len(products) == 0:
            print("\n❌ No products found. Check the log file for debug info.")
            print("Common issues:")
            print("- Site blocking requests (try using a VPN)")
            print("- Page structure changed")
            print("- Login required for search results")
            return
        
        # Show ALL products
        for i, product in enumerate(products, 1):
            print(f"\n🛍️  PRODUCT {i}")
            print(f"    Title: {product.title}")
            print(f"    Brand: {product.brand}")
            print(f"    Price: {product.price}")
            print(f"    Size: {product.size}")
            print(f"    Condition: {product.condition}")
            print(f"    URL: {product.url}")
            if product.image_url != "N/A":
                print(f"    Image: {product.image_url}")
            print("-" * 50)
        
        # Summary by brand
        print(f"\n📊 SUMMARY BY BRAND:")
        brand_count = {}
        total_value = 0
        
        for product in products:
            brand = product.brand
            brand_count[brand] = brand_count.get(brand, 0) + 1
            
            # Extract price value for total
            price_match = re.search(r'\$(\d+)', product.price)
            if price_match:
                total_value += int(price_match.group(1))
        
        for brand, count in sorted(brand_count.items()):
            print(f"    {brand}: {count} items")
        
        print(f"\n💰 Total retail value: ~${total_value}")
        print(f"📁 Results saved to JSON file")
        
        # Discord status
        print(f"✅ Products sent to Discord webhook automatically")
    
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Error during scraping: {str(e)}")

# Railway deployment functions
def run_as_service():
    """Run continuously with 5-minute intervals for local use"""
    import schedule
    
    def job():
        print(f"\n🔄 Running scrape at {datetime.now()}")
        try:
            scraper = SimpleTheRealRealScraper()
            products = scraper.run_scraper()
            print(f"✅ Found {len(products)} new products")
        except Exception as e:
            print(f"❌ Error during scrape: {e}")
    
    # Run every 5 minutes
    schedule.every(5).minutes.do(job)
    job()  # Run immediately
    
    print("🕐 Scheduled to run every 5 minutes")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")

def create_railway_requirements():
    """Create requirements.txt for Railway deployment"""
    requirements = """requests==2.31.0
beautifulsoup4==4.12.2
cloudscraper==1.2.71
schedule==1.2.0
"""
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    print("✅ Created requirements.txt for Railway")

def create_railway_config():
    """Create railway configuration files"""
    
    # Procfile for Railway
    procfile = "web: python therealreal_scraper.py --service\n"
    with open('Procfile', 'w') as f:
        f.write(procfile)
    
    # Environment example
    env_example = """# Discord webhook URL (get from Discord channel settings)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url

# Optional: Run as continuous service
RUN_AS_SERVICE=true

# Port for Railway (automatically set)
PORT=8000
"""
    
    with open('.env.example', 'w') as f:
        f.write(env_example)
    
    print("✅ Created Procfile and .env.example for Railway")

if __name__ == "__main__":
    import sys
    
    # Check for service mode (for Railway deployment)
    if len(sys.argv) > 1 and sys.argv[1] == '--service':
        run_as_service()
    elif len(sys.argv) > 1 and sys.argv[1] == '--setup-railway':
        create_railway_requirements()
        create_railway_config()
    else:
        main()