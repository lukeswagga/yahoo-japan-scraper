#!/usr/bin/env python3
"""
Simple test script to verify Railway deployment
"""
from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "success",
        "message": "Railway deployment test successful",
        "service": "yahoo-japan-scraper"
    })

@app.route('/ping')
def ping():
    return jsonify({"status": "pong"})

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": "2025-01-21T12:00:00Z",
        "service": "yahoo-japan-scraper"
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    print(f"🌐 Starting test server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
