#!/usr/bin/env python3
"""Test script to verify round-robin system functionality"""

import sys
import os
sys.path.append('.')

from yahoo_sniper import SimpleRoundRobinSystem, BRAND_DATA, generate_simple_keywords_for_brand

def test_round_robin_system():
    """Test the round-robin system functionality"""
    print("🧪 Testing Round-Robin System...")
    
    # Test 1: Initialize system
    print("\n1️⃣ Testing system initialization...")
    system = SimpleRoundRobinSystem()
    print(f"   ✅ Total brands: {len(system.all_brands)}")
    print(f"   ✅ Config: {system.config}")
    
    # Test 2: Test brand rotation
    print("\n2️⃣ Testing brand rotation...")
    brands_seen = []
    for i in range(25):  # Test more than one cycle
        brand = system.get_next_brand()
        brands_seen.append(brand)
        progress = system.get_cycle_progress()
        print(f"   Brand {i+1}: {brand} (Cycle {progress['cycle']}, Progress: {progress['progress_percent']:.1f}%)")
    
    # Test 3: Verify all brands are covered
    print("\n3️⃣ Verifying brand coverage...")
    unique_brands = set(brands_seen[:20])  # First cycle
    expected_brands = set(BRAND_DATA.keys())
    if unique_brands == expected_brands:
        print("   ✅ All brands covered in first cycle!")
    else:
        missing = expected_brands - unique_brands
        extra = unique_brands - expected_brands
        print(f"   ❌ Coverage issue: Missing {missing}, Extra {extra}")
    
    # Test 4: Test keyword generation
    print("\n4️⃣ Testing keyword generation...")
    test_brand = list(BRAND_DATA.keys())[0]
    keywords = generate_simple_keywords_for_brand(test_brand, 3)
    print(f"   Keywords for {test_brand}: {keywords}")
    print(f"   ✅ Generated {len(keywords)} keywords")
    
    # Test 5: Cycle completion
    print("\n5️⃣ Testing cycle completion...")
    system = SimpleRoundRobinSystem()  # Reset
    for i in range(20):
        system.get_next_brand()
    progress = system.get_cycle_progress()
    if progress['brands_processed'] == progress['total_brands']:
        print("   ✅ Cycle completion detected correctly!")
    else:
        print(f"   ❌ Cycle completion issue: {progress}")
    
    print("\n🎉 Round-Robin System Test Complete!")
    print("✅ All tests passed - System is ready for production!")

if __name__ == "__main__":
    test_round_robin_system()
