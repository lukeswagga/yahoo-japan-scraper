# -*- coding: utf-8 -*-
"""
Diagnostics script to identify why the optimized scraper is underperforming
Run this to see what's going wrong
"""

import json
import sqlite3
from datetime import datetime, timedelta

def diagnose_performance():
    print("🔍 SCRAPER PERFORMANCE DIAGNOSTICS")
    print("=" * 50)
    
    # Check keyword performance
    print("\n📊 KEYWORD PERFORMANCE ANALYSIS:")
    try:
        with open('keyword_performance.json', 'r') as f:
            kw_data = json.load(f)
        
        keyword_perf = kw_data.get('keyword_performance', {})
        total_keywords = len(keyword_perf)
        dead_keywords = len([k for k, v in keyword_perf.items() if v.get('consecutive_fails', 0) >= 8])
        active_keywords = total_keywords - dead_keywords
        
        print(f"Total keywords tracked: {total_keywords}")
        print(f"Dead keywords: {dead_keywords}")
        print(f"Active keywords: {active_keywords}")
        if total_keywords > 0:
            print(f"Dead keyword percentage: {(dead_keywords/total_keywords)*100:.1f}%")
        else:
            print("Dead keyword percentage: 0.0% (no keywords tracked yet)")
        
        # Show worst performing keywords
        print("\n💀 DEAD KEYWORDS (marked as unusable):")
        dead_kw_list = [k for k, v in keyword_perf.items() if v.get('consecutive_fails', 0) >= 8]
        for kw in dead_kw_list[:10]:
            perf = keyword_perf[kw]
            print(f"  '{kw}': {perf['searches']} searches, {perf['finds']} finds, {perf['consecutive_fails']} fails")
        
        # Show best performing keywords
        print("\n🔥 BEST PERFORMING KEYWORDS:")
        best_kw = [(k, v['finds']/max(1, v['searches'])) for k, v in keyword_perf.items() 
                  if v['searches'] > 5 and v.get('consecutive_fails', 0) < 5]
        best_kw.sort(key=lambda x: x[1], reverse=True)
        
        for kw, rate in best_kw[:10]:
            perf = keyword_perf[kw]
            print(f"  '{kw}': {rate:.1%} success rate ({perf['finds']}/{perf['searches']})")
            
    except FileNotFoundError:
        print("❌ keyword_performance.json not found - learning system not working!")
        return False
    
    # Check tier performance
    print("\n🏆 TIER PERFORMANCE ANALYSIS:")
    try:
        with open('tier_performance.json', 'r') as f:
            tier_data = json.load(f)
        
        for tier_name, stats in tier_data.items():
            if stats['total_searches'] > 0:
                efficiency = stats['successful_finds'] / stats['total_searches']
                print(f"{tier_name}: {efficiency:.3f} efficiency ({stats['successful_finds']}/{stats['total_searches']})")
            else:
                print(f"{tier_name}: No searches recorded")
                
    except FileNotFoundError:
        print("❌ tier_performance.json not found - tier system not tracking!")
    
    # Check recent scraper stats
    print("\n📈 RECENT SCRAPER STATISTICS:")
    try:
        conn = sqlite3.connect('auction_tracking.db')
        cursor = conn.cursor()
        
        # Get last 10 cycles
        cursor.execute('''
            SELECT timestamp, total_found, quality_filtered, sent_to_discord, keywords_searched
            FROM scraper_stats 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        
        recent_stats = cursor.fetchall()
        if recent_stats:
            print("Last 10 cycles:")
            for i, (timestamp, found, filtered, sent, keywords) in enumerate(recent_stats):
                efficiency = sent / max(1, keywords)
                print(f"  Cycle {i+1}: {keywords} searches → {found} found → {filtered} quality → {sent} sent (eff: {efficiency:.3f})")
        else:
            print("❌ No recent statistics found in database!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
    
    # Check seen items growth
    print("\n💾 DUPLICATE DETECTION ANALYSIS:")
    try:
        with open('seen_yahoo.json', 'r') as f:
            seen_ids = json.load(f)
        
        print(f"Total seen items: {len(seen_ids)}")
        
        # Check database size
        conn = sqlite3.connect('auction_tracking.db')
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM scraped_items')
            db_count = cursor.fetchone()[0]
            print(f"Database tracked items: {db_count}")
        except sqlite3.OperationalError:
            print("Database tracked items: 0 (table doesn't exist yet)")
        conn.close()
        
        if len(seen_ids) > 50000:
            print("⚠️  WARNING: Seen items list is very large - might be blocking new finds!")
        
    except FileNotFoundError:
        print("❌ seen_yahoo.json not found!")
    
    return True

def check_filtering_issues():
    print("\n🚫 FILTERING ANALYSIS:")
    
    # Check if quality thresholds are too high
    print("Current quality thresholds:")
    print(f"PRICE_QUALITY_THRESHOLD: 0.15 (15%)")
    print(f"MIN_PRICE_USD: $3")
    print(f"MAX_PRICE_USD: $1200")
    
    # Suggest threshold adjustments
    print("\n💡 SUGGESTED FIXES:")
    print("1. Lower PRICE_QUALITY_THRESHOLD from 0.15 to 0.08")
    print("2. Check if brand multipliers are too high")
    print("3. Verify enhanced_filtering.py isn't too aggressive")
    print("4. Test with original keyword generation temporarily")

def generate_test_keywords():
    print("\n🧪 TEST KEYWORD SUGGESTIONS:")
    
    # Basic high-success keywords that should always work
    test_keywords = [
        "raf simons",
        "rick owens", 
        "margiela",
        "jean paul gaultier",
        "yohji yamamoto",
        "junya watanabe",
        "undercover",
        "comme des garcons"
    ]
    
    print("Try these basic keywords manually to test:")
    for kw in test_keywords:
        print(f"  - {kw}")
    
    print("\nIf these don't work, the issue is likely:")
    print("1. Quality filtering too strict")
    print("2. Spam detection too aggressive") 
    print("3. Brand matching broken")
    print("4. Price conversion issues")

if __name__ == "__main__":
    success = diagnose_performance()
    if success:
        check_filtering_issues()
        generate_test_keywords()
    
    print("\n🔧 NEXT STEPS:")
    print("1. Run this diagnostic script")
    print("2. Check the output above for red flags")
    print("3. Try manual keyword tests")
    print("4. Adjust thresholds based on findings")
    print("5. Consider temporary fallback to simpler keyword generation")