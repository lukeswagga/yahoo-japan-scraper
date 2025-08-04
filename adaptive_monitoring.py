"""
Complete Adaptive monitoring system for Yahoo auction scraper
This provides intelligent keyword management and performance optimization
"""

import json
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import os

class AdaptivePerformanceMonitor:
    def __init__(self, performance_file="adaptive_performance.json"):
        self.performance_file = performance_file
        
        self.keyword_performance = defaultdict(lambda: {
            'searches': 0,
            'finds': 0,
            'last_find': None,
            'avg_response_time': 0.0,
            'consecutive_failures': 0,
            'success_streak': 0,
            'quality_score': 0.5,
            'total_quality_sum': 0.0,
            'peak_performance_hour': None
        })
        
        self.brand_performance = defaultdict(lambda: {
            'total_finds': 0,
            'avg_deal_quality': 0.0,
            'preferred_keywords': [],
            'dead_keywords': [],
            'last_successful_search': None,
            'peak_activity_hours': [],
            'best_price_range': {'min': 0, 'max': 1000},
            'success_rate_by_hour': {}
        })
        
        self.time_performance = defaultdict(lambda: {
            'finds_per_hour': [],
            'avg_finds': 0.0,
            'best_hours': [],
            'worst_hours': []
        })
        
        self.recent_performance = deque(maxlen=50)
        self.session_start = datetime.now()
        
        self.load_performance_data()
    
    def load_performance_data(self):
        try:
            with open(self.performance_file, 'r') as f:
                data = json.load(f)
                
            if 'keyword_performance' in data:
                for k, v in data['keyword_performance'].items():
                    self.keyword_performance[k].update(v)
            
            if 'brand_performance' in data:
                for k, v in data['brand_performance'].items():
                    self.brand_performance[k].update(v)
            
            if 'time_performance' in data:
                for k, v in data['time_performance'].items():
                    self.time_performance[k].update(v)
                    
            print("📊 Loaded previous performance data")
                    
        except FileNotFoundError:
            print("📊 No previous performance data found, starting fresh")
    
    def save_performance_data(self):
        data = {
            'keyword_performance': dict(self.keyword_performance),
            'brand_performance': dict(self.brand_performance),
            'time_performance': dict(self.time_performance),
            'last_updated': datetime.now().isoformat(),
            'session_start': self.session_start.isoformat()
        }
        
        with open(self.performance_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_search_result(self, keyword, brand, listings_found, response_time, avg_quality=0.0):
        """Record comprehensive search results for learning"""
        current_hour = datetime.now().hour
        
        kw_perf = self.keyword_performance[keyword]
        brand_perf = self.brand_performance[brand]
        
        kw_perf['searches'] += 1
        kw_perf['finds'] += listings_found
        kw_perf['avg_response_time'] = (kw_perf['avg_response_time'] + response_time) / 2
        
        if listings_found > 0:
            kw_perf['consecutive_failures'] = 0
            kw_perf['success_streak'] += 1
            kw_perf['last_find'] = datetime.now().isoformat()
            kw_perf['quality_score'] = min(1.0, kw_perf['quality_score'] + 0.1)
            kw_perf['peak_performance_hour'] = current_hour
            
            if avg_quality > 0:
                kw_perf['total_quality_sum'] += avg_quality * listings_found
            
            brand_perf['total_finds'] += listings_found
            brand_perf['last_successful_search'] = datetime.now().isoformat()
            
            if keyword not in brand_perf['preferred_keywords']:
                brand_perf['preferred_keywords'].append(keyword)
            
            if keyword in brand_perf['dead_keywords']:
                brand_perf['dead_keywords'].remove(keyword)
            
            if current_hour not in brand_perf['success_rate_by_hour']:
                brand_perf['success_rate_by_hour'][current_hour] = {'searches': 0, 'finds': 0}
            
            brand_perf['success_rate_by_hour'][current_hour]['searches'] += 1
            brand_perf['success_rate_by_hour'][current_hour]['finds'] += listings_found
            
            if avg_quality > 0:
                current_avg = brand_perf['avg_deal_quality']
                total_finds = brand_perf['total_finds']
                new_avg = ((current_avg * (total_finds - listings_found)) + (avg_quality * listings_found)) / total_finds
                brand_perf['avg_deal_quality'] = new_avg
                
        else:
            kw_perf['consecutive_failures'] += 1
            kw_perf['success_streak'] = 0
            kw_perf['quality_score'] = max(0.1, kw_perf['quality_score'] - 0.05)
            
            if kw_perf['consecutive_failures'] >= 8:
                if keyword not in brand_perf['dead_keywords']:
                    brand_perf['dead_keywords'].append(keyword)
                    print(f"💀 Marking keyword as dead: {keyword} (brand: {brand})")
        
        self.time_performance[current_hour]['finds_per_hour'].append(listings_found)
        
        self.recent_performance.append({
            'keyword': keyword,
            'brand': brand,
            'finds': listings_found,
            'quality': avg_quality,
            'response_time': response_time,
            'timestamp': datetime.now().isoformat(),
            'hour': current_hour
        })
    
    def get_optimized_keywords_for_brand(self, brand, max_keywords=5):
        """Get optimized keywords based on historical performance"""
        brand_perf = self.brand_performance[brand]
        
        preferred = brand_perf.get('preferred_keywords', [])
        dead = brand_perf.get('dead_keywords', [])
        
        optimized_keywords = []
        
        for keyword in preferred:
            if keyword not in dead:
                kw_perf = self.keyword_performance[keyword]
                if kw_perf['consecutive_failures'] < 5 and kw_perf['searches'] > 0:
                    success_rate = kw_perf['finds'] / kw_perf['searches']
                    quality_score = kw_perf['quality_score']
                    combined_score = (success_rate * 0.7) + (quality_score * 0.3)
                    optimized_keywords.append((keyword, combined_score))
        
        optimized_keywords.sort(key=lambda x: x[1], reverse=True)
        top_keywords = [kw for kw, score in optimized_keywords[:max_keywords]]
        
        if len(top_keywords) < max_keywords:
            fallback_keywords = self._generate_smart_fallbacks(brand, max_keywords - len(top_keywords))
            top_keywords.extend(fallback_keywords)
        
        return top_keywords[:max_keywords]
    
    def _generate_smart_fallbacks(self, brand, count):
        """Generate intelligent fallback keywords"""
        from yahoo_sniper import BRAND_DATA
        
        if brand not in BRAND_DATA:
            return [brand.lower()]
        
        brand_variants = BRAND_DATA[brand]['variants']
        primary_variant = brand_variants[0] if brand_variants else brand
        
        current_hour = datetime.now().hour
        is_peak_hour = current_hour in self.get_best_hours_for_brand(brand)
        
        if is_peak_hour:
            fallback = [
                primary_variant,
                f"{primary_variant} archive",
                f"{primary_variant} rare",
                f"{primary_variant} jacket",
                f"{primary_variant} shirt",
                f"{primary_variant} vintage"
            ]
        else:
            fallback = [
                primary_variant,
                f"{primary_variant} jacket",
                f"{primary_variant} archive",
                f"{primary_variant} shirt"
            ]
        
        return fallback[:count]
    
    def should_skip_keyword(self, keyword):
        """Determine if a keyword should be skipped based on recent performance"""
        kw_perf = self.keyword_performance[keyword]
        
        if kw_perf['consecutive_failures'] >= 10:
            return True
        
        if kw_perf['searches'] > 15 and (kw_perf['finds'] / kw_perf['searches']) < 0.01:
            return True
        
        if kw_perf['avg_response_time'] > 15.0:
            return True
        
        return False
    
    def get_best_hours_for_brand(self, brand):
        """Get the best hours to search for a specific brand"""
        brand_perf = self.brand_performance[brand]
        hour_data = brand_perf.get('success_rate_by_hour', {})
        
        if not hour_data:
            return list(range(24))
        
        hour_scores = {}
        for hour_str, data in hour_data.items():
            if data['searches'] > 0:
                success_rate = data['finds'] / data['searches']
                hour_scores[int(hour_str)] = success_rate
        
        if not hour_scores:
            return list(range(24))
        
        sorted_hours = sorted(hour_scores.items(), key=lambda x: x[1], reverse=True)
        best_hours = [hour for hour, rate in sorted_hours[:12] if rate > 0.05]
        
        return best_hours if best_hours else list(range(24))
    
    def get_performance_insights(self):
        """Get comprehensive performance insights"""
        insights = {
            'total_keywords_tracked': len(self.keyword_performance),
            'active_keywords': len([k for k, v in self.keyword_performance.items() if v['consecutive_failures'] < 5]),
            'dead_keywords': len([k for k, v in self.keyword_performance.items() if v['consecutive_failures'] >= 8]),
            'hot_keywords': len([k for k, v in self.keyword_performance.items() if v['success_streak'] >= 3]),
            'best_performing_keywords': [],
            'worst_performing_keywords': [],
            'brand_insights': {},
            'time_insights': {},
            'session_performance': self._get_session_performance()
        }
        
        keyword_scores = []
        for keyword, perf in self.keyword_performance.items():
            if perf['searches'] > 2:
                success_rate = perf['finds'] / perf['searches']
                quality_avg = perf['total_quality_sum'] / max(1, perf['finds'])
                combined_score = (success_rate * 0.6) + (quality_avg * 0.4)
                keyword_scores.append((keyword, combined_score, success_rate, quality_avg))
        
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        insights['best_performing_keywords'] = keyword_scores[:10]
        insights['worst_performing_keywords'] = keyword_scores[-5:]
        
        for brand, perf in self.brand_performance.items():
            insights['brand_insights'][brand] = {
                'total_finds': perf['total_finds'],
                'avg_quality': perf['avg_deal_quality'],
                'preferred_keywords_count': len(perf['preferred_keywords']),
                'dead_keywords_count': len(perf['dead_keywords']),
                'last_success': perf['last_successful_search'],
                'best_hours': self.get_best_hours_for_brand(brand)[:3]
            }
        
        current_hour = datetime.now().hour
        for hour, data in self.time_performance.items():
            if data['finds_per_hour']:
                avg_finds = statistics.mean(data['finds_per_hour'])
                insights['time_insights'][hour] = {
                    'avg_finds': avg_finds,
                    'total_sessions': len(data['finds_per_hour']),
                    'is_current_hour': hour == current_hour
                }
        
        return insights
    
    def _get_session_performance(self):
        """Get performance data for current session"""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        recent_finds = [entry['finds'] for entry in self.recent_performance if entry['finds'] > 0]
        recent_response_times = [entry['response_time'] for entry in self.recent_performance]
        
        return {
            'session_duration_minutes': session_duration / 60,
            'total_recent_finds': sum(recent_finds),
            'avg_finds_per_search': statistics.mean(recent_finds) if recent_finds else 0,
            'avg_response_time': statistics.mean(recent_response_times) if recent_response_times else 0,
            'searches_this_session': len(self.recent_performance)
        }
    
    def optimize_tier_allocation(self, tiered_system):
        """Dynamically adjust tier allocations based on performance"""
        current_time = datetime.now()
        
        brand_scores = {}
        for brand, perf in self.brand_performance.items():
            recent_activity_score = 0
            quality_score = perf['avg_deal_quality']
            total_finds_score = min(perf['total_finds'] / 10, 1.0)
            
            if perf['last_successful_search']:
                try:
                    last_find = datetime.fromisoformat(perf['last_successful_search'])
                    hours_since = (current_time - last_find).total_seconds() / 3600
                    
                    if hours_since < 6:
                        recent_activity_score = 1.0
                    elif hours_since < 24:
                        recent_activity_score = 0.7
                    elif hours_since < 72:
                        recent_activity_score = 0.4
                    else:
                        recent_activity_score = 0.1
                except:
                    recent_activity_score = 0.1
            
            preferred_keywords_score = min(len(perf['preferred_keywords']) / 5, 1.0)
            dead_keywords_penalty = min(len(perf['dead_keywords']) / 10, 0.5)
            
            final_score = (
                (recent_activity_score * 0.3) +
                (quality_score * 0.25) +
                (total_finds_score * 0.25) +
                (preferred_keywords_score * 0.2) -
                dead_keywords_penalty
            )
            
            brand_scores[brand] = max(0.0, final_score)
        
        sorted_brands = sorted(brand_scores.items(), key=lambda x: x[1], reverse=True)
        
        new_tier_1_premium = [brand for brand, score in sorted_brands[:2] if score > 0.7]
        new_tier_1_high = [brand for brand, score in sorted_brands[2:4] if score > 0.6]
        new_tier_2 = [brand for brand, score in sorted_brands[4:8] if score > 0.4]
        new_tier_3 = [brand for brand, score in sorted_brands[8:12] if score > 0.3]
        new_tier_4 = [brand for brand, score in sorted_brands[12:15] if score > 0.2]
        new_tier_5 = [brand for brand, score in sorted_brands[15:] if score > 0.1]
        
        print(f"\n🔄 DYNAMIC TIER REBALANCING BASED ON PERFORMANCE:")
        print(f"Tier 1 Premium (score >0.7): {new_tier_1_premium}")
        print(f"Tier 1 High (score >0.6): {new_tier_1_high}")
        print(f"Tier 2 (score >0.4): {new_tier_2}")
        print(f"Tier 3 (score >0.3): {new_tier_3}")
        
        if new_tier_1_premium:
            tiered_system.tier_config['tier_1_premium']['brands'] = new_tier_1_premium
        if new_tier_1_high:
            tiered_system.tier_config['tier_1_high']['brands'] = new_tier_1_high
        if new_tier_2:
            tiered_system.tier_config['tier_2']['brands'] = new_tier_2
        if new_tier_3:
            tiered_system.tier_config['tier_3']['brands'] = new_tier_3
        if new_tier_4:
            tiered_system.tier_config['tier_4']['brands'] = new_tier_4
        if new_tier_5:
            tiered_system.tier_config['tier_5_minimal']['brands'] = new_tier_5

class SmartKeywordRotator:
    """Intelligent keyword rotation system"""
    
    def __init__(self, performance_monitor):
        self.performance_monitor = performance_monitor
        self.keyword_pools = {
            'proven_high_performance': [],
            'proven_medium_performance': [],
            'experimental_new': [],
            'recovery_testing': [],
            'time_sensitive': []
        }
        self.rotation_cycle = 0
        self.last_rotation_time = datetime.now()
    
    def categorize_keywords_by_performance(self, brand):
        """Categorize keywords based on their performance metrics"""
        self.keyword_pools = {pool: [] for pool in self.keyword_pools.keys()}
        
        brand_perf = self.performance_monitor.brand_performance[brand]
        current_hour = datetime.now().hour
        
        for keyword in brand_perf.get('preferred_keywords', []):
            kw_perf = self.performance_monitor.keyword_performance[keyword]
            
            if kw_perf['searches'] == 0:
                self.keyword_pools['experimental_new'].append(keyword)
                continue
            
            success_rate = kw_perf['finds'] / kw_perf['searches']
            quality = kw_perf['quality_score']
            failures = kw_perf['consecutive_failures']
            
            if kw_perf.get('peak_performance_hour') == current_hour:
                self.keyword_pools['time_sensitive'].append(keyword)
            elif success_rate > 0.15 and quality > 0.7 and failures < 2:
                self.keyword_pools['proven_high_performance'].append(keyword)
            elif success_rate > 0.08 and quality > 0.5 and failures < 4:
                self.keyword_pools['proven_medium_performance'].append(keyword)
            elif failures >= 5 and failures < 10:
                self.keyword_pools['recovery_testing'].append(keyword)
            else:
                self.keyword_pools['experimental_new'].append(keyword)
    
    def get_rotation_keywords(self, brand, tier_config):
        """Get keywords for current rotation cycle"""
        self.categorize_keywords_by_performance(brand)
        max_keywords = tier_config['max_keywords']
        
        rotation_keywords = []
        cycle_type = self.rotation_cycle % 5
        
        if cycle_type == 0:
            rotation_keywords.extend(self.keyword_pools['proven_high_performance'][:max_keywords//2])
            rotation_keywords.extend(self.keyword_pools['time_sensitive'][:max_keywords//2])
        elif cycle_type == 1:
            rotation_keywords.extend(self.keyword_pools['proven_high_performance'][:max_keywords//3])
            rotation_keywords.extend(self.keyword_pools['proven_medium_performance'][:max_keywords//3])
            rotation_keywords.extend(self.keyword_pools['experimental_new'][:max_keywords//3])
        elif cycle_type == 2:
            rotation_keywords.extend(self.keyword_pools['proven_medium_performance'][:max_keywords])
        elif cycle_type == 3:
            rotation_keywords.extend(self.keyword_pools['proven_high_performance'][:max_keywords//2])
            rotation_keywords.extend(self.keyword_pools['experimental_new'][:max_keywords//2])
        else:
            if self.keyword_pools['recovery_testing']:
                rotation_keywords.extend(self.keyword_pools['recovery_testing'][:max_keywords//3])
                print(f"🔄 Testing recovery keywords for {brand}")
            rotation_keywords.extend(self.keyword_pools['proven_high_performance'][:max_keywords*2//3])
        
        if not rotation_keywords:
            from yahoo_sniper import BRAND_DATA
            brand_variants = BRAND_DATA.get(brand, {}).get('variants', [brand])
            rotation_keywords = [brand_variants[0]] if brand_variants else [brand]
        
        return rotation_keywords[:max_keywords]
    
    def next_rotation(self):
        """Move to next rotation cycle"""
        self.rotation_cycle += 1
        self.last_rotation_time = datetime.now()
        
        cycle_types = ['balanced_time_sensitive', 'experimental_focus', 'conservative_proven', 'discovery_mode', 'recovery_testing']
        current_type = cycle_types[self.rotation_cycle % 5]
        print(f"🔄 Keyword Rotation {self.rotation_cycle}: {current_type}")

class RealTimeOptimizer:
    """Real-time optimization based on current session performance"""
    
    def __init__(self):
        self.session_stats = {
            'searches_this_session': 0,
            'finds_this_session': 0,
            'errors_this_session': 0,
            'start_time': datetime.now(),
            'best_keywords_this_session': [],
            'worst_keywords_this_session': [],
            'quality_sum': 0.0,
            'response_times': []
        }
        
        self.current_efficiency = 0.0
        self.target_efficiency = 0.12
        self.performance_window = deque(maxlen=10)
        
    def update_session_stats(self, keyword, finds, errors, quality=0.0, response_time=0.0):
        """Update comprehensive session statistics"""
        self.session_stats['searches_this_session'] += 1
        self.session_stats['finds_this_session'] += finds
        self.session_stats['errors_this_session'] += errors
        self.session_stats['quality_sum'] += quality * finds
        self.session_stats['response_times'].append(response_time)
        
        if finds > 0:
            self.session_stats['best_keywords_this_session'].append((keyword, finds, quality))
        elif finds == 0:
            self.session_stats['worst_keywords_this_session'].append(keyword)
        
        self.current_efficiency = self.session_stats['finds_this_session'] / max(1, self.session_stats['searches_this_session'])
        
        self.performance_window.append({
            'efficiency': finds / max(1, self.session_stats['searches_this_session']),
            'finds': finds,
            'timestamp': datetime.now()
        })
    
    def should_intensify_search(self):
        """Determine if we should increase search intensity"""
        if len(self.performance_window) < 5:
            return False
        
        recent_efficiency = statistics.mean([entry['efficiency'] for entry in list(self.performance_window)[-5:]])
        return recent_efficiency > self.target_efficiency * 1.5
    
    def should_reduce_search(self):
        """Determine if we should reduce search intensity"""
        error_rate = self.session_stats['errors_this_session'] / max(1, self.session_stats['searches_this_session'])
        
        if error_rate > 0.4:
            return True
        
        if len(self.performance_window) >= 10:
            recent_efficiency = statistics.mean([entry['efficiency'] for entry in list(self.performance_window)[-10:]])
            if recent_efficiency < 0.03:
                return True
        
        avg_response_time = statistics.mean(self.session_stats['response_times'][-10:]) if len(self.session_stats['response_times']) >= 10 else 0
        if avg_response_time > 12.0:
            return True
        
        return False
    
    def get_session_recommendations(self):
        """Get actionable recommendations for optimizing current session"""
        recommendations = []
        
        session_duration = (datetime.now() - self.session_stats['start_time']).total_seconds() / 60
        
        if self.current_efficiency < 0.05 and session_duration > 15:
            recommendations.append("🚨 Switch to emergency mode - use only proven keywords")
        elif self.current_efficiency > 0.25:
            recommendations.append("🚀 High efficiency detected - increase page depth and keyword count")
        
        error_rate = self.session_stats['errors_this_session'] / max(1, self.session_stats['searches_this_session'])
        if error_rate > 0.3:
            recommendations.append("⚠️ High error rate - increase delays between requests")
        
        if len(self.session_stats['response_times']) > 5:
            avg_response = statistics.mean(self.session_stats['response_times'][-5:])
            if avg_response > 10:
                recommendations.append("🐌 Slow response times - reduce concurrent requests")
        
        if len(self.session_stats['best_keywords_this_session']) > 0:
            best_performers = sorted(self.session_stats['best_keywords_this_session'], 
                                   key=lambda x: x[1] * x[2], reverse=True)[:3]
            if best_performers:
                best_kw = best_performers[0][0]
                recommendations.append(f"🎯 Focus on variations of top performer: '{best_kw}'")
        
        if len(self.session_stats['worst_keywords_this_session']) > 5:
            recommendations.append("💀 Consider marking consistently failing keywords as dead")
        
        return recommendations
    
    def should_trigger_emergency_mode(self):
        """Determine if emergency mode should be activated"""
        session_time_minutes = (datetime.now() - self.session_stats['start_time']).total_seconds() / 60
        
        if session_time_minutes > 30 and self.current_efficiency < 0.02:
            return True
        
        if len(self.performance_window) >= 10:
            recent_finds = [entry['finds'] for entry in list(self.performance_window)[-10:]]
            if sum(recent_finds) == 0:
                return True
        
        return False

class IntelligentPageScraper:
    """Determines optimal page depth based on content quality and performance"""
    
    def __init__(self):
        self.page_quality_history = {}
        self.max_pages_global = 5
        
    def should_continue_pagination(self, keyword, current_page, items_found_this_page, quality_items_this_page, brand):
        """Advanced pagination decision making"""
        
        if current_page >= self.max_pages_global:
            return False
        
        if items_found_this_page < 8:
            print(f"🔚 Page {current_page} for '{keyword}' has few items ({items_found_this_page}), stopping")
            return False
        
        if quality_items_this_page == 0 and current_page > 1:
            print(f"🔚 No quality items on page {current_page} for '{keyword}', stopping")
            return False
        
        quality_ratio = quality_items_this_page / max(1, items_found_this_page)
        
        brand_threshold = 0.03
        if brand.lower() in ['raf_simons', 'rick_owens', 'maison_margiela']:
            brand_threshold = 0.02
        
        if quality_ratio < brand_threshold and current_page > 1:
            print(f"🔚 Low quality ratio ({quality_ratio:.1%}) on page {current_page} for '{keyword}', stopping")
            return False
        
        cache_key = f"{keyword}_{brand}_page_{current_page}"
        self.page_quality_history[cache_key] = {
            'total_items': items_found_this_page,
            'quality_items': quality_items_this_page,
            'quality_ratio': quality_ratio,
            'timestamp': datetime.now().isoformat(),
            'brand': brand
        }
        
        return True
    
    def get_optimal_pages_for_keyword(self, keyword, brand):
        """Get recommended page depth based on historical performance"""
        relevant_history = {k: v for k, v in self.page_quality_history.items() 
                          if keyword in k and brand in k}
        
        if not relevant_history:
            premium_brands = ['raf_simons', 'rick_owens', 'maison_margiela', 'jean_paul_gaultier']
            if brand.lower() in premium_brands:
                return 3
            else:
                return 2
        
        max_productive_page = 1
        for cache_key, data in relevant_history.items():
            if data['quality_ratio'] > 0.03:
                try:
                    page_num = int(cache_key.split('_page_')[1])
                    max_productive_page = max(max_productive_page, page_num)
                except:
                    continue
        
        recommended_pages = min(max_productive_page + 1, self.max_pages_global)
        return recommended_pages

def create_optimized_search_strategy(brand_data, performance_monitor, keyword_rotator, real_time_optimizer):
    """Factory function to create the complete optimized search strategy"""
    
    class OptimizedSearchStrategy:
        def __init__(self):
            self.performance_monitor = performance_monitor
            self.keyword_rotator = keyword_rotator
            self.real_time_optimizer = real_time_optimizer
            self.page_scraper = IntelligentPageScraper()
            self.emergency_keywords_cache = []
        
        def get_search_plan_for_brand(self, brand, tier_config):
            """Generate complete search plan for a brand"""
            
            if self.real_time_optimizer.should_reduce_search():
                keywords = self.performance_monitor.get_optimized_keywords_for_brand(brand, 2)
                max_pages = 1
                delay = tier_config['delay'] + 2
                print(f"🐌 CONSERVATION MODE: Reducing search intensity for {brand}")
                
            elif self.real_time_optimizer.should_intensify_search():
                keywords = self.performance_monitor.get_optimized_keywords_for_brand(brand, tier_config['max_keywords'] + 2)
                max_pages = min(tier_config['max_pages'] + 1, 4)
                delay = max(1, tier_config['delay'] - 1)
                print(f"🚀 BOOST MODE: Intensifying search for {brand}")
                
            else:
                keywords = self.keyword_rotator.get_rotation_keywords(brand, tier_config)
                max_pages = tier_config['max_pages']
                delay = tier_config['delay']
            
            filtered_keywords = [kw for kw in keywords if not self.performance_monitor.should_skip_keyword(kw)]
            
            if not filtered_keywords:
                fallback_keywords = self.performance_monitor._generate_smart_fallbacks(brand, 2)
                filtered_keywords = fallback_keywords
            
            return {
                'keywords': filtered_keywords,
                'max_pages': max_pages,
                'delay': delay,
                'max_listings': tier_config.get('max_listings', 5)
            }
        
        def should_trigger_emergency_mode(self):
            """Comprehensive emergency mode trigger logic"""
            return self.real_time_optimizer.should_trigger_emergency_mode()
        
        def get_emergency_keywords(self):
            """Get the most reliable keywords for emergency situations"""
            if self.emergency_keywords_cache:
                return self.emergency_keywords_cache
            
            all_keywords = []
            for keyword, perf in self.performance_monitor.keyword_performance.items():
                if perf['searches'] > 3:
                    success_rate = perf['finds'] / perf['searches']
                    if success_rate > 0.12 and perf['consecutive_failures'] < 3:
                        all_keywords.append((keyword, success_rate, perf['quality_score']))
            
            all_keywords.sort(key=lambda x: x[1] * x[2], reverse=True)
            
            self.emergency_keywords_cache = [kw for kw, rate, quality in all_keywords[:15]]
            
            if not self.emergency_keywords_cache:
                self.emergency_keywords_cache = [
                    "raf simons", "rick owens", "margiela", "jean paul gaultier",
                    "raf simons archive", "rick owens jacket", "margiela jacket",
                    "yohji yamamoto", "junya watanabe", "undercover"
                ]
            
            return self.emergency_keywords_cache
        
        def analyze_search_performance(self, tier_results):
            """Analyze performance and provide insights"""
            total_searches = sum(tier['searches'] for tier in tier_results.values())
            total_finds = sum(tier['finds'] for tier in tier_results.values())
            
            if total_searches > 0:
                overall_efficiency = total_finds / total_searches
                
                insights = {
                    'overall_efficiency': overall_efficiency,
                    'total_searches': total_searches,
                    'total_finds': total_finds,
                    'tier_performance': {},
                    'recommendations': []
                }
                
                for tier_name, results in tier_results.items():
                    tier_efficiency = results['finds'] / max(1, results['searches'])
                    insights['tier_performance'][tier_name] = {
                        'efficiency': tier_efficiency,
                        'searches': results['searches'],
                        'finds': results['finds']
                    }
                
                if overall_efficiency < 0.05:
                    insights['recommendations'].append("Consider emergency mode or keyword optimization")
                elif overall_efficiency > 0.2:
                    insights['recommendations'].append("High performance - consider expanding search scope")
                
                return insights
            
            return None
    
    return OptimizedSearchStrategy()

class PerformanceReporter:
    """Generate detailed performance reports"""
    
    def __init__(self, performance_monitor):
        self.performance_monitor = performance_monitor
    
    def generate_daily_report(self):
        """Generate comprehensive daily performance report"""
        insights = self.performance_monitor.get_performance_insights()
        
        report = {
            'report_date': datetime.now().isoformat(),
            'summary': {
                'total_keywords': insights['total_keywords_tracked'],
                'active_keywords': insights['active_keywords'],
                'dead_keywords': insights['dead_keywords'],
                'hot_keywords': insights['hot_keywords']
            },
            'top_performers': insights['best_performing_keywords'][:5],
            'brand_analysis': insights['brand_insights'],
            'time_analysis': insights['time_insights'],
            'session_summary': insights['session_performance']
        }
        
        report_filename = f"performance_report_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Daily performance report saved: {report_filename}")
        return report
    
    def print_live_dashboard(self, cycle_number):
        """Print live performance dashboard"""
        insights = self.performance_monitor.get_performance_insights()
        session_perf = insights['session_performance']
        
        print(f"\n📊 LIVE PERFORMANCE DASHBOARD - CYCLE {cycle_number}")
        print(f"⏱️  Session: {session_perf['session_duration_minutes']:.1f} min")
        print(f"🔍 Searches: {session_perf['searches_this_session']}")
        print(f"📊 Total finds: {session_perf['total_recent_finds']}")
        print(f"⚡ Efficiency: {self.performance_monitor.current_efficiency:.3f}")
        print(f"📈 Active keywords: {insights['active_keywords']}")
        print(f"💀 Dead keywords: {insights['dead_keywords']}")
        print(f"🔥 Hot keywords: {insights['hot_keywords']}")
        
        if insights['best_performing_keywords']:
            top_3 = insights['best_performing_keywords'][:3]
            print(f"🏆 Top performers: {[f'{kw}({rate:.1%})' for kw, score, rate, quality in top_3]}")

# Global instances for import
BRAND_DATA = {}