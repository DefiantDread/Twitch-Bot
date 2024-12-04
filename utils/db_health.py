# utils/db_health.py
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ConnectionHealthMonitor:
    def __init__(self, db_manager, check_interval: int = 60):
        self.db_manager = db_manager
        self.check_interval = check_interval
        self.last_check: Optional[datetime] = None
        self.is_running = False
        self.failed_checks = 0
        self.max_failures = 3

    async def start_monitoring(self):
        """Start connection health monitoring"""
        if self.is_running:
            return
            
        self.is_running = True
        while self.is_running:
            await self.check_connections()
            await asyncio.sleep(self.check_interval)

    async def stop_monitoring(self):
        """Stop connection health monitoring"""
        self.is_running = False

    async def check_connections(self) -> bool:
        """Check database connection health"""
        try:
            async with self.db_manager.session_scope() as session:
                await asyncio.to_thread(
                    session.execute, 
                    text('SELECT 1')
                )
            
            self.last_check = datetime.now(timezone.utc)
            self.failed_checks = 0
            logger.debug("Database connection health check passed")
            return True
            
        except Exception as e:
            self.failed_checks += 1
            logger.error(f"Database health check failed: {e}")
            
            if self.failed_checks >= self.max_failures:
                await self._handle_connection_failure()
            return False

    async def check_database(self) -> bool:
        """Public method to check database health"""
        return await self.check_connections()

    async def _handle_connection_failure(self):
        """Handle repeated connection failures"""
        logger.critical("Multiple database connection failures detected")
        try:
            # Dispose current pool and create new connections
            await asyncio.to_thread(self.db_manager.engine.dispose)
            
            # Create new engine with fresh connection pool
            self.db_manager._setup_engine()
            logger.info("Database connection pool has been reset")
            
        except Exception as e:
            logger.critical(f"Failed to recover database connections: {e}")