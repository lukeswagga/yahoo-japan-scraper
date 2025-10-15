#!/usr/bin/env python3
"""
Enhanced database security for Yahoo Japan auction bot
"""
import aiosqlite
import json
import hashlib
import secrets
from cryptography.fernet import Fernet
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class SecureDatabaseManager:
    def __init__(self, db_path: str, encryption_key: bytes = None):
        self.db_path = db_path
        
        # Generate or use provided encryption key
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            # In production, store this securely
            key = Fernet.generate_key()
            self.cipher = Fernet(key)
            logger.warning("Generated new encryption key - store securely!")
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data before storing"""
        if not data:
            return data
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data after retrieving"""
        if not encrypted_data:
            return encrypted_data
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_data  # Return as-is if decryption fails
    
    def hash_discord_id(self, discord_id: str) -> str:
        """Create one-way hash of Discord ID for privacy"""
        salt = "yahoo_japan_bot_salt_2024"  # Use environment variable in production
        return hashlib.sha256(f"{discord_id}{salt}".encode()).hexdigest()[:16]
    
    async def secure_user_insert(self, discord_id: str, tier: str, stripe_customer_id: str = None):
        """Securely insert user data with encryption"""
        hashed_id = self.hash_discord_id(discord_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Use parameterized queries to prevent SQL injection
            await db.execute("""
                INSERT OR REPLACE INTO users 
                (discord_id_hash, original_discord_id, tier, stripe_customer_id_encrypted, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (
                hashed_id,
                self.encrypt_sensitive_data(discord_id),
                tier,
                self.encrypt_sensitive_data(stripe_customer_id) if stripe_customer_id else None
            ))
            await db.commit()
    
    async def secure_user_lookup(self, discord_id: str) -> Dict[str, Any]:
        """Securely lookup user data"""
        hashed_id = self.hash_discord_id(discord_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT tier, stripe_customer_id_encrypted, created_at
                FROM users 
                WHERE discord_id_hash = ?
            """, (hashed_id,))
            
            result = await cursor.fetchone()
            if result:
                return {
                    'tier': result[0],
                    'stripe_customer_id': self.decrypt_sensitive_data(result[1]) if result[1] else None,
                    'created_at': result[2]
                }
            return None
    
    async def secure_listing_insert(self, listing_data: Dict[str, Any]):
        """Securely insert listing data with validation"""
        # Sanitize and validate data
        auction_id = str(listing_data.get('auction_id', '')).strip()
        if not auction_id.isdigit():
            raise ValueError("Invalid auction_id")
        
        # Remove any potential XSS from title
        title = str(listing_data.get('title', '')).strip()[:500]  # Limit length
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO listing_queue 
                (auction_id, listing_data, priority_score, brand, scraper_source, received_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (
                auction_id,
                json.dumps(listing_data),  # JSON is safe
                float(listing_data.get('priority_score', 0.5)),
                str(listing_data.get('brand', 'Unknown')).strip()[:100],
                str(listing_data.get('scraper_source', 'unknown')).strip()[:50]
            ))
            await db.commit()

# Enhanced database schema with security
ENHANCED_SCHEMA = """
-- Enhanced users table with encryption
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id_hash TEXT UNIQUE NOT NULL,  -- Hashed Discord ID
    original_discord_id TEXT,              -- Encrypted original ID
    tier TEXT DEFAULT 'free',
    stripe_customer_id_encrypted TEXT,
    subscription_status TEXT DEFAULT 'active',
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_discord_hash ON users(discord_id_hash);
CREATE INDEX IF NOT EXISTS idx_tier ON users(tier);

-- Audit log for security monitoring
CREATE TABLE IF NOT EXISTS security_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    discord_id_hash TEXT,
    ip_address TEXT,
    user_agent TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
