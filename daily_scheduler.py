"""
Daily Scheduler for Discord Auction Bot

Handles scheduled tasks like daily digest and counter resets.
"""

import schedule
import time
import asyncio
import threading
import logging
from datetime import datetime, timezone
from notification_tiers import tier_manager

logger = logging.getLogger(__name__)

class DailyScheduler:
    """Manages daily scheduled tasks"""
    
    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
            
        self.running = True
        
        # Schedule daily digest at 9 AM UTC
        schedule.every().day.at("09:00").do(self._run_daily_digest)
        
        # Schedule daily counter reset at midnight UTC
        schedule.every().day.at("00:00").do(self._reset_daily_counters)
        
        # Start scheduler in background thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Daily scheduler started - Daily digest at 9 AM, counter reset at midnight UTC")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        schedule.clear()
        logger.info("Daily scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _run_daily_digest(self):
        """Run the daily digest task"""
        try:
            logger.info("Running daily digest task")
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the daily digest
                loop.run_until_complete(tier_manager.send_daily_digest())
                logger.info("Daily digest completed successfully")
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error running daily digest: {e}")
    
    def _reset_daily_counters(self):
        """Reset daily notification counters for all users"""
        try:
            logger.info("Resetting daily notification counters")
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Reset counters for all active users
                loop.run_until_complete(self._reset_all_counters())
                logger.info("Daily counter reset completed successfully")
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}")
    
    async def _reset_all_counters(self):
        """Reset daily counters for all users"""
        try:
            from database_manager import db_manager
            
            # Get all active users
            users = db_manager.execute_query(
                'SELECT user_id FROM user_subscriptions WHERE status = %s'
                if db_manager.use_postgres else
                'SELECT user_id FROM user_subscriptions WHERE status = ?',
                ('active',),
                fetch_all=True
            )
            
            if users:
                reset_time = datetime.now(timezone.utc)
                for user_row in users:
                    user_id = user_row['user_id'] if isinstance(user_row, dict) else user_row[0]
                    await tier_manager.set_daily_count(user_id, 0, reset_time)
                
                logger.info(f"Reset daily counters for {len(users)} users")
            else:
                logger.info("No active users found for counter reset")
                
        except Exception as e:
            logger.error(f"Error resetting all counters: {e}")
    
    def run_daily_digest_now(self):
        """Manually trigger daily digest (for admin commands)"""
        try:
            logger.info("Manually triggering daily digest")
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                success = loop.run_until_complete(tier_manager.send_daily_digest())
                if success:
                    logger.info("Manual daily digest completed successfully")
                else:
                    logger.error("Manual daily digest failed")
                return success
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Error running manual daily digest: {e}")
            return False

# Global scheduler instance
daily_scheduler = DailyScheduler()
