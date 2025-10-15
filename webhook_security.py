#!/usr/bin/env python3
"""
Secure webhook handler for Yahoo Japan auction bot
"""
import hashlib
import hmac
import time
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)

class WebhookSecurity:
    def __init__(self, secret_key: str, rate_limit_window: int = 3600, max_requests: int = 1000):
        self.secret_key = secret_key.encode()
        self.rate_limit_window = rate_limit_window
        self.max_requests = max_requests
        self.request_counts = {}  # In production, use Redis
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature using HMAC-SHA256"""
        try:
            expected_signature = hmac.new(
                self.secret_key,
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit"""
        current_time = time.time()
        window_start = current_time - self.rate_limit_window
        
        # Clean old entries
        self.request_counts = {
            ip: count for ip, count in self.request_counts.items()
            if self.request_counts.get(ip, {}).get('first_request', 0) > window_start
        }
        
        # Check current client
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {
                'count': 1,
                'first_request': current_time
            }
            return True
        
        client_data = self.request_counts[client_ip]
        if client_data['count'] >= self.max_requests:
            return False
        
        client_data['count'] += 1
        return True
    
    def validate_listing_data(self, data: dict) -> tuple[bool, str]:
        """Validate incoming listing data"""
        required_fields = ['auction_id', 'title', 'price', 'brand']
        
        if not isinstance(data, dict):
            return False, "Data must be a JSON object"
        
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        # Validate data types and ranges
        try:
            price = float(data.get('price', 0))
            if price < 0 or price > 1000000:  # $1M max
                return False, "Invalid price range"
        except (ValueError, TypeError):
            return False, "Invalid price format"
        
        # Validate auction_id format (should be numeric)
        auction_id = str(data.get('auction_id', ''))
        if not auction_id.isdigit() or len(auction_id) < 8:
            return False, "Invalid auction_id format"
        
        return True, "Valid"

def secure_webhook_required(secret_key: str):
    """Decorator for secure webhook endpoints"""
    security = WebhookSecurity(secret_key)
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get client IP
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            
            # Check rate limit
            if not security.check_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            # Verify signature
            signature = request.headers.get('X-Signature')
            if not signature:
                logger.warning(f"Missing signature from {client_ip}")
                return jsonify({"error": "Missing signature"}), 401
            
            if not security.verify_signature(request.data, signature):
                logger.warning(f"Invalid signature from {client_ip}")
                return jsonify({"error": "Invalid signature"}), 401
            
            # Validate data
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            
            data = request.get_json()
            is_valid, error_msg = security.validate_listing_data(data)
            
            if not is_valid:
                logger.warning(f"Invalid data from {client_ip}: {error_msg}")
                return jsonify({"error": error_msg}), 400
            
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    
    return decorator
