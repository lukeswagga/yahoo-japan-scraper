#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Priority Calculator for Discord Auction Bot
Calculates priority scores for listings based on price, brand, scraper source, and deal quality
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PriorityCalculator:
    def __init__(self, brand_data: Dict[str, Any]):
        """
        Initialize priority calculator with brand data
        
        Args:
            brand_data: Dictionary containing brand information with tiers
        """
        self.brand_data = brand_data
        self._validate_brand_data()
    
    def _validate_brand_data(self):
        """Validate that brand data has required structure"""
        if not isinstance(self.brand_data, dict):
            logger.warning("⚠️ Brand data is not a dictionary, using default scoring")
            self.brand_data = {}
            return
        
        # Check if brand data has tier information
        has_tiers = any('tier' in str(brand_info).lower() for brand_info in self.brand_data.values())
        if not has_tiers:
            logger.warning("⚠️ Brand data doesn't contain tier information, using default scoring")
    
    def calculate_priority(self, listing_data: Dict[str, Any]) -> float:
        """
        Calculate priority score from 0.0 to 1.0 based on multiple factors
        
        Scoring breakdown:
        - Price tier: <$50 (0.4), $50-100 (0.3), $100-200 (0.2), >$200 (0.1)
        - Brand tier: tier 1 (0.3), tier 2 (0.25), tier 3 (0.2), tier 4 (0.15), tier 5 (0.1)
        - Scraper source: ending_soon (0.2), budget_steals (0.15), new_listings (0.1), buy_it_now (0.05)
        - Deal quality: existing deal_quality score (0-0.15)
        
        Args:
            listing_data: Dictionary containing listing information
            
        Returns:
            Priority score between 0.0 and 1.0
        """
        try:
            score = 0.0
            
            # Price scoring (0.1 to 0.4 points)
            price_score = self._calculate_price_score(listing_data)
            score += price_score
            
            # Brand tier scoring (0.1 to 0.3 points)
            brand_score = self._calculate_brand_score(listing_data)
            score += brand_score
            
            # Scraper source scoring (0.05 to 0.2 points)
            scraper_score = self._calculate_scraper_score(listing_data)
            score += scraper_score
            
            # Deal quality boost (0 to 0.15 points)
            quality_score = self._calculate_quality_score(listing_data)
            score += quality_score
            
            # Ensure score is between 0.0 and 1.0
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate priority score: {e}")
            return 0.5  # Default middle score on error
    
    def _calculate_price_score(self, listing_data: Dict[str, Any]) -> float:
        """Calculate score based on price tier"""
        try:
            price_usd = float(listing_data.get('price_usd', 999))
            
            if price_usd <= 50:
                return 0.4
            elif price_usd <= 100:
                return 0.3
            elif price_usd <= 200:
                return 0.2
            else:
                return 0.1
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid price_usd value: {listing_data.get('price_usd')}")
            return 0.2  # Default middle price score
    
    def _calculate_brand_score(self, listing_data: Dict[str, Any]) -> float:
        """Calculate score based on brand tier"""
        try:
            brand = listing_data.get('brand', 'Unknown')
            if brand == 'Unknown':
                return 0.1  # Default for unknown brands
            
            # Look for brand in brand_data
            brand_info = self.brand_data.get(brand, {})
            
            # Check if brand_info has tier information
            if isinstance(brand_info, dict) and 'tier' in brand_info:
                tier = brand_info['tier']
            else:
                # Try to find brand by variants
                tier = self._find_brand_tier_by_variants(brand)
            
            # Brand tier scoring
            brand_scores = {1: 0.3, 2: 0.25, 3: 0.2, 4: 0.15, 5: 0.1}
            return brand_scores.get(tier, 0.1)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to calculate brand score for {brand}: {e}")
            return 0.1
    
    def _find_brand_tier_by_variants(self, brand: str) -> int:
        """Find brand tier by checking variants in brand_data"""
        try:
            for brand_name, brand_info in self.brand_data.items():
                if isinstance(brand_info, dict) and 'variants' in brand_info:
                    variants = brand_info['variants']
                    if brand in variants:
                        return brand_info.get('tier', 5)
            return 5  # Default tier for unknown brands
        except Exception:
            return 5
    
    def _calculate_scraper_score(self, listing_data: Dict[str, Any]) -> float:
        """Calculate score based on scraper source"""
        try:
            scraper_source = listing_data.get('scraper_source', '').lower()
            
            if 'ending_soon' in scraper_source:
                return 0.2
            elif 'budget_steals' in scraper_source:
                return 0.15
            elif 'new_listings' in scraper_source:
                return 0.1
            elif 'buy_it_now' in scraper_source:
                return 0.05
            else:
                return 0.1  # Default score for unknown sources
        except Exception:
            return 0.1
    
    def _calculate_quality_score(self, listing_data: Dict[str, Any]) -> float:
        """Calculate score based on deal quality"""
        try:
            deal_quality = float(listing_data.get('deal_quality', 0))
            
            # Ensure deal_quality is between 0 and 1
            deal_quality = max(0.0, min(1.0, deal_quality))
            
            # Scale to 0-0.15 range
            return deal_quality * 0.15
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Invalid deal_quality value: {listing_data.get('deal_quality')}")
            return 0.0
    
    def get_priority_breakdown(self, listing_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Get detailed breakdown of priority calculation for debugging
        
        Returns:
            Dictionary with individual score components
        """
        try:
            return {
                'price_score': self._calculate_price_score(listing_data),
                'brand_score': self._calculate_brand_score(listing_data),
                'scraper_score': self._calculate_scraper_score(listing_data),
                'quality_score': self._calculate_quality_score(listing_data),
                'total_score': self.calculate_priority(listing_data)
            }
        except Exception as e:
            logger.error(f"❌ Failed to get priority breakdown: {e}")
            return {
                'price_score': 0.0,
                'brand_score': 0.0,
                'scraper_score': 0.0,
                'quality_score': 0.0,
                'total_score': 0.5
            }
    
    def load_brand_data_from_file(self, file_path: str) -> bool:
        """
        Load brand data from JSON file
        
        Args:
            file_path: Path to brands.json file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.brand_data = json.load(f)
            self._validate_brand_data()
            logger.info(f"✅ Loaded brand data from {file_path}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load brand data from {file_path}: {e}")
            return False
