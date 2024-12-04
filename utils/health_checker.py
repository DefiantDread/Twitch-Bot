# utils/health_checker.py
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, bot):
        self.bot = bot
        self.last_check = None
        self.health_status = {}
        self.is_running = False

    async def start_monitoring(self):
        """Start the health check monitoring loop"""
        if self.is_running:
            return
            
        self.is_running = True
        while self.is_running:
            await self.check_health()
            await asyncio.sleep(60)  # Check every minute

    async def stop_monitoring(self):
        """Stop the health check monitoring"""
        self.is_running = False

    async def check_health(self) -> Dict[str, bool]:
        """Run all health checks"""
        self.last_check = datetime.now(timezone.utc)
        self.health_status = {
            'database': await self.check_database(),
            'twitch_api': await self.check_twitch_api(),
            'bot_responsive': await self.check_bot_responsive()
        }
        return self.health_status

    async def check_database(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.bot.db.session_scope() as session:
                await asyncio.to_thread(session.execute, text('SELECT 1'))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def check_twitch_api(self) -> bool:
        """Check Twitch API status"""
        try:
            # Test a simple API call
            await self.bot.get_channel(self.bot.nick)
            return True
        except Exception as e:
            logger.error(f"Twitch API health check failed: {e}")
            return False

    async def check_bot_responsive(self) -> bool:
        """Check if bot is responsive"""
        try:
            current_time = datetime.now(timezone.utc)
            if self.last_check is None:
                return True
            
            # If last check was more than 2 minutes ago, consider unresponsive
            time_diff = (current_time - self.last_check).total_seconds()
            return time_diff < 120
        except Exception as e:
            logger.error(f"Bot responsiveness check failed: {e}")
            return False

    def get_status(self) -> Dict[str, Dict]:
        """Get current health status with details"""
        return {
            'status': all(self.health_status.values()),
            'last_check': self.last_check,
            'checks': self.health_status,
            'details': {
                'database': {
                    'healthy': self.health_status.get('database', False),
                    'connection': bool(self.bot.db.engine)
                },
                'twitch_api': {
                    'healthy': self.health_status.get('twitch_api', False),
                    'connected': bool(self.bot._connection)
                },
                'bot': {
                    'healthy': self.health_status.get('bot_responsive', False),
                    'uptime': (datetime.now(timezone.utc) - self.bot.start_time).total_seconds() if hasattr(self.bot, 'start_time') else None
                }
            }
        }