#!/usr/bin/env python3
"""
Universal Product Arbitrage Analyzer
Scrapes Yahoo Japan/Zenmarket listings and finds similar sold items on eBay and Grailed
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from urllib.parse import quote, urljoin
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Product:
    title: str
    brand: str = ""
    model: str = ""
    category: str = ""
    size: str = ""
    color: str = ""
    condition: str = ""
    price_original: str = ""
    price_usd: float = 0.0
    images: List[str] = None
    platform: str = ""
    seller: str = ""
    url: str = ""
    
    def __post_init__(self):
        if self.images is None:
            self.images = []

@dataclass
class SoldListing:
    title: str
    sold_price: float
    sold_date: str
    condition: str
    size: str
    color: str
    url: str
    image_url: str
    platform: str
    seller: str = ""
    similarity_score: float = 0.0

class UniversalScraper:
    def __init__(self, headless=True):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Set up Selenium for JavaScript-heavy sites
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def extract_product_from_url(self, url: str) -> Optional[Product]:
        """Extract product information from any marketplace URL"""
        logger.info(f"Extracting product from: {url}")
        
        try:
            if "zenmarket.jp" in url:
                return self._extract_zenmarket(url)
            elif "page.auctions.yahoo.co.jp" in url:
                return self._extract_yahoo_auction(url)
            elif "buyee.jp" in url:
                return self._extract_buyee(url)
            elif "mercari.com" in url:
                return self._extract_mercari(url)
            else:
                return self._extract_generic(url)
        except Exception as e:
            logger.error(f"Failed to extract product from {url}: {str(e)}")
            return None
    
    def _extract_zenmarket(self, url: str) -> Optional[Product]:
        """Extract product from Zenmarket proxy"""
        self.driver.get(url)
        time.sleep(3)
        
        try:
            # Wait for page to load
            wait = WebDriverWait(self.driver, 10)
            
            # Extract title
            title_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".item-title, .product-title, h1")))
            title = title_elem.text.strip()
            
            # Extract price
            price_elem = self.driver.find_element(By.CSS_SELECTOR, ".price, .item-price, .product-price")
            price_text = price_elem.text
            
            # Extract images
            images = []
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, ".item-image img, .product-image img, .gallery img")
            for img in img_elements[:5]:  # Limit to 5 images
                src = img.get_attribute("src")
                if src and "http" in src:
                    images.append(src)
            
            # Parse price and convert to USD
            price_yen = self._extract_price_from_text(price_text)
            price_usd = price_yen / 150 if price_yen else 0  # Rough conversion
            
            # Extract additional info from title
            brand, model, size, color = self._parse_product_details(title)
            
            return Product(
                title=title,
                brand=brand,
                model=model,
                size=size,
                color=color,
                condition="Used",  # Default for Japanese marketplaces
                price_original=f"¥{price_yen:,.0f}" if price_yen else "Unknown",
                price_usd=price_usd,
                images=images,
                platform="Zenmarket",
                url=url
            )
            
        except Exception as e:
            logger.error(f"Failed to extract Zenmarket product: {str(e)}")
            return None
    
    def _extract_yahoo_auction(self, url: str) -> Optional[Product]:
        """Extract from Yahoo Japan Auctions"""
        self.driver.get(url)
        time.sleep(3)
        
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # Title
            title_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ProductTitle__text, .p-item-detail-title")))
            title = title_elem.text.strip()
            
            # Price
            price_elem = self.driver.find_element(By.CSS_SELECTOR, ".Price__value, .u-fs-18")
            price_text = price_elem.text
            
            # Images
            images = []
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, ".ProductImage img, .p-item-detail-image img")
            for img in img_elements[:5]:
                src = img.get_attribute("src")
                if src and "http" in src:
                    images.append(src)
            
            price_yen = self._extract_price_from_text(price_text)
            price_usd = price_yen / 150 if price_yen else 0
            
            brand, model, size, color = self._parse_product_details(title)
            
            return Product(
                title=title,
                brand=brand,
                model=model,
                size=size,
                color=color,
                condition="Used",
                price_original=f"¥{price_yen:,.0f}" if price_yen else "Unknown",
                price_usd=price_usd,
                images=images,
                platform="Yahoo Japan",
                url=url
            )
            
        except Exception as e:
            logger.error(f"Failed to extract Yahoo auction: {str(e)}")
            return None
    
    def _extract_generic(self, url: str) -> Optional[Product]:
        """Generic extraction for unknown sites"""
        response = self.session.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to find title
        title = ""
        for selector in ["h1", ".title", ".product-title", ".item-title", "title"]:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                break
        
        # Try to find price
        price_text = ""
        for selector in [".price", ".cost", ".amount", "[class*='price']"]:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                price_text = elem.text.strip()
                break
        
        # Extract images
        images = []
        img_elements = soup.select("img")
        for img in img_elements[:5]:
            src = img.get("src")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    src = urljoin(url, src)
                if "http" in src:
                    images.append(src)
        
        if not title:
            return None
            
        price_amount = self._extract_price_from_text(price_text)
        brand, model, size, color = self._parse_product_details(title)
        
        return Product(
            title=title,
            brand=brand,
            model=model,
            size=size,
            color=color,
            condition="Unknown",
            price_original=price_text,
            price_usd=price_amount if price_amount and price_amount < 10000 else price_amount/150 if price_amount else 0,
            images=images,
            platform="Unknown",
            url=url
        )
    
    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not text:
            return None
            
        # Remove common currency symbols and text
        cleaned = re.sub(r'[¥$€£,]', '', text)
        cleaned = re.sub(r'[^\d.]', '', cleaned)
        
        try:
            return float(cleaned)
        except:
            return None
    
    def _parse_product_details(self, title: str) -> tuple:
        """Parse brand, model, size, color from title"""
        title_lower = title.lower()
        
        # Common brands
        brands = ["maison margiela", "supreme", "off-white", "stone island", "nike", "adidas", 
                 "balenciaga", "gucci", "prada", "louis vuitton", "comme des garcons"]
        brand = ""
        for b in brands:
            if b in title_lower:
                brand = b.title()
                break
        
        # Size patterns
        size_match = re.search(r'\b(xs|s|m|l|xl|xxl|\d{1,2}(?:\.\d)?)\b', title_lower)
        size = size_match.group(1).upper() if size_match else ""
        
        # EU/US size patterns
        eu_size = re.search(r'\b(\d{2}(?:\.\d)?)\s*(?:eu|eur)\b', title_lower)
        us_size = re.search(r'\b(\d{1,2}(?:\.\d)?)\s*(?:us|usa)\b', title_lower)
        
        if eu_size:
            size = f"{eu_size.group(1)} EU"
        elif us_size:
            size = f"{us_size.group(1)} US"
        
        # Colors
        colors = ["black", "white", "red", "blue", "green", "yellow", "pink", "purple", "brown", "gray", "grey"]
        color = ""
        for c in colors:
            if c in title_lower:
                color = c.title()
                break
        
        # Model (everything after brand)
        model = ""
        if brand:
            brand_index = title_lower.find(brand.lower())
            if brand_index != -1:
                after_brand = title[brand_index + len(brand):].strip()
                model = after_brand.split()[0:3]  # First few words after brand
                model = " ".join(model)
        
        return brand, model, size, color

class EbayScraper:
    def __init__(self, session):
        self.session = session
        
    def search_sold_listings(self, product: Product, max_results=20) -> List[SoldListing]:
        """Search eBay sold listings for similar products"""
        logger.info(f"Searching eBay for: {product.brand} {product.model}")
        
        # Build search query
        query_parts = []
        if product.brand:
            query_parts.append(product.brand)
        if product.model:
            query_parts.append(product.model)
        if product.size:
            query_parts.append(product.size)
        
        query = " ".join(query_parts)
        
        # eBay sold listings URL
        url = f"https://www.ebay.com/sch/i.html?_nkw={quote(query)}&LH_Sold=1&LH_Complete=1"
        
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            listings = []
            items = soup.select('.s-item')[:max_results]
            
            for item in items:
                try:
                    title_elem = item.select_one('.s-item__title')
                    price_elem = item.select_one('.s-item__price')
                    link_elem = item.select_one('.s-item__link')
                    img_elem = item.select_one('.s-item__image img')
                    
                    if not all([title_elem, price_elem, link_elem]):
                        continue
                    
                    title = title_elem.text.strip()
                    price_text = price_elem.text.strip()
                    url = link_elem.get('href', '')
                    img_url = img_elem.get('src', '') if img_elem else ''
                    
                    # Extract price
                    price_match = re.search(r'\$?([\d,]+\.?\d*)', price_text)
                    if not price_match:
                        continue
                        
                    sold_price = float(price_match.group(1).replace(',', ''))
                    
                    # Calculate similarity
                    similarity = self._calculate_similarity(product, title)
                    
                    listing = SoldListing(
                        title=title,
                        sold_price=sold_price,
                        sold_date="2024-08-01",  # eBay doesn't show exact dates easily
                        condition="Used",
                        size=product.size,
                        color=product.color,
                        url=url,
                        image_url=img_url,
                        platform="eBay",
                        similarity_score=similarity
                    )
                    
                    listings.append(listing)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse eBay item: {str(e)}")
                    continue
            
            return sorted(listings, key=lambda x: x.similarity_score, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to search eBay: {str(e)}")
            return []
    
    def _calculate_similarity(self, product: Product, title: str) -> float:
        """Calculate similarity score between product and listing title"""
        score = 0.0
        title_lower = title.lower()
        
        if product.brand and product.brand.lower() in title_lower:
            score += 0.4
        
        if product.model and product.model.lower() in title_lower:
            score += 0.3
        
        if product.size and product.size.lower() in title_lower:
            score += 0.2
        
        if product.color and product.color.lower() in title_lower:
            score += 0.1
        
        return min(score, 1.0)

class GrailedScraper:
    def __init__(self, session):
        self.session = session
        
    def search_sold_listings(self, product: Product, max_results=20) -> List[SoldListing]:
        """Search Grailed sold listings (Note: Grailed requires more complex scraping)"""
        logger.info(f"Searching Grailed for: {product.brand} {product.model}")
        
        # Grailed search URL - they use a different structure
        query = f"{product.brand} {product.model}".strip()
        url = f"https://www.grailed.com/sold?q={quote(query)}"
        
        try:
            # Grailed requires headers to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers)
            
            # Note: Grailed uses heavy JavaScript, might need Selenium for full functionality
            # This is a simplified version
            
            soup = BeautifulSoup(response.content, 'html.parser')
            listings = []
            
            # Grailed has a complex structure, this is a basic attempt
            items = soup.select('[data-testid="listing-item"]')[:max_results]
            
            for item in items:
                try:
                    # This structure may need adjustment based on actual Grailed HTML
                    title_elem = item.select_one('.listing-title, .title')
                    price_elem = item.select_one('.price, .sold-price')
                    
                    if title_elem and price_elem:
                        title = title_elem.text.strip()
                        price_text = price_elem.text.strip()
                        
                        price_match = re.search(r'\$?([\d,]+)', price_text)
                        if price_match:
                            sold_price = float(price_match.group(1).replace(',', ''))
                            
                            similarity = self._calculate_similarity(product, title)
                            
                            listing = SoldListing(
                                title=title,
                                sold_price=sold_price,
                                sold_date="2024-07-15",
                                condition="Used",
                                size=product.size,
                                color=product.color,
                                url="https://grailed.com",  # Would need to extract actual URL
                                image_url="",
                                platform="Grailed",
                                similarity_score=similarity
                            )
                            
                            listings.append(listing)
                
                except Exception as e:
                    continue
            
            return sorted(listings, key=lambda x: x.similarity_score, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to search Grailed: {str(e)}")
            return []
    
    def _calculate_similarity(self, product: Product, title: str) -> float:
        """Same similarity calculation as eBay"""
        score = 0.0
        title_lower = title.lower()
        
        if product.brand and product.brand.lower() in title_lower:
            score += 0.4
        
        if product.model and product.model.lower() in title_lower:
            score += 0.3
        
        if product.size and product.size.lower() in title_lower:
            score += 0.2
        
        if product.color and product.color.lower() in title_lower:
            score += 0.1
        
        return min(score, 1.0)

class ArbitrageAnalyzer:
    def __init__(self):
        self.scraper = UniversalScraper()
        self.ebay = EbayScraper(self.scraper.session)
        self.grailed = GrailedScraper(self.scraper.session)
    
    def analyze_url(self, url: str, min_similarity=0.7) -> Dict:
        """Complete arbitrage analysis for a given URL"""
        logger.info(f"Starting arbitrage analysis for: {url}")
        
        # Step 1: Extract product from source URL
        product = self.scraper.extract_product_from_url(url)
        if not product:
            return {"error": "Could not extract product information from URL"}
        
        logger.info(f"Extracted product: {product.title}")
        
        # Step 2: Search for similar sold listings
        ebay_listings = self.ebay.search_sold_listings(product)
        grailed_listings = self.grailed.search_sold_listings(product)
        
        # Step 3: Filter by similarity
        all_listings = ebay_listings + grailed_listings
        filtered_listings = [l for l in all_listings if l.similarity_score >= min_similarity]
        
        # Step 4: Calculate arbitrage potential
        if not filtered_listings:
            return {
                "product": product,
                "matches": [],
                "arbitrage": {"error": "No similar listings found"}
            }
        
        avg_sold_price = sum(l.sold_price for l in filtered_listings) / len(filtered_listings)
        potential_profit = avg_sold_price - product.price_usd
        profit_margin = (potential_profit / product.price_usd * 100) if product.price_usd > 0 else 0
        
        arbitrage = {
            "avg_sold_price": round(avg_sold_price, 2),
            "source_price": product.price_usd,
            "potential_profit": round(potential_profit, 2),
            "profit_margin": round(profit_margin, 1),
            "matches_count": len(filtered_listings)
        }
        
        return {
            "product": product,
            "matches": filtered_listings[:10],  # Top 10 matches
            "arbitrage": arbitrage
        }
    
    def close(self):
        """Clean up resources"""
        self.scraper.driver.quit()

def main():
    """Example usage"""
    analyzer = ArbitrageAnalyzer()
    
    try:
        # Example URL - replace with any product URL
        test_url = "https://zenmarket.jp/en/auction.aspx?itemCode=h1196632725"
        
        print(f"Analyzing: {test_url}")
        result = analyzer.analyze_url(test_url)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        product = result["product"]
        matches = result["matches"]
        arbitrage = result["arbitrage"]
        
        print(f"\n=== PRODUCT ANALYSIS ===")
        print(f"Title: {product.title}")
        print(f"Brand: {product.brand}")
        print(f"Price: {product.price_original} (${product.price_usd:.2f})")
        print(f"Platform: {product.platform}")
        
        print(f"\n=== SIMILAR SOLD LISTINGS ===")
        for i, match in enumerate(matches[:5], 1):
            print(f"{i}. {match.title}")
            print(f"   Platform: {match.platform}")
            print(f"   Sold Price: ${match.sold_price:.2f}")
            print(f"   Similarity: {match.similarity_score:.1%}")
            print(f"   URL: {match.url}")
            print()
        
        print(f"=== ARBITRAGE ANALYSIS ===")
        if "error" not in arbitrage:
            print(f"Average Sold Price: ${arbitrage['avg_sold_price']:.2f}")
            print(f"Source Price: ${arbitrage['source_price']:.2f}")
            print(f"Potential Profit: ${arbitrage['potential_profit']:.2f}")
            print(f"Profit Margin: {arbitrage['profit_margin']:.1f}%")
            print(f"Based on {arbitrage['matches_count']} matches")
            
            if arbitrage['potential_profit'] > 50:
                print("🚨 HIGH ARBITRAGE OPPORTUNITY!")
            elif arbitrage['profit_margin'] < 20:
                print("⚠️  Low margin - consider fees and shipping")
        else:
            print(f"Error: {arbitrage['error']}")
    
    finally:
        analyzer.close()

if __name__ == "__main__":
    main()