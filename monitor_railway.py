#!/usr/bin/env python3
"""Monitor Railway deployment status"""

import requests
import time
import json
from datetime import datetime

RAILWAY_URL = "https://discord-auction-bot-production.up.railway.app"

def check_railway_status():
    """Check Railway deployment status"""
    try:
        # Check main endpoint
        response = requests.get(RAILWAY_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service: {data.get('service', 'Unknown')}")
            print(f"✅ Status: {data.get('status', 'Unknown')}")
            return True
        else:
            print(f"❌ Service returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking service: {e}")
        return False

def check_health():
    """Check health endpoint"""
    try:
        response = requests.get(f"{RAILWAY_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health: {data.get('status', 'Unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking health: {e}")
        return False

def monitor_deployment():
    """Monitor the deployment"""
    print("🔍 Monitoring Railway Deployment...")
    print(f"🌐 URL: {RAILWAY_URL}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # Check status
    status_ok = check_railway_status()
    health_ok = check_health()
    
    if status_ok and health_ok:
        print("\n🎉 Railway deployment is healthy and running!")
        print("🔄 Round-robin scraper should be active")
    else:
        print("\n⚠️ Railway deployment may have issues")
    
    print("-" * 50)

if __name__ == "__main__":
    monitor_deployment()
