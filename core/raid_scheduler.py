# core/raid_scheduler.py

import asyncio
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class ScheduleConfig:
    min_cooldown: int  # minimum seconds between raids
    max_cooldown: int  # maximum seconds between raids
    min_viewers: int   # minimum viewers required
    active_multiplier: float  # increase chance during high activity
    peak_hours: List[int]    # hours considered peak time
    enabled: bool = True

class RaidScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_raid_end: Optional[datetime] = None
        # Initialize with a time in the past instead of None
        self.last_raid_end = datetime.now(timezone.utc) - timedelta(hours=1)  # Set to 1 hour ago
        
        # Default configuration
        self.config = ScheduleConfig(
            min_cooldown=1800,    # 30 minutes
            max_cooldown=3600,    # 60 minutes
            min_viewers=2,
            active_multiplier=1.5,
            peak_hours=[19, 20, 21, 22]  # 7PM-10PM
        )
        
        # Activity tracking
        self.recent_activity = []
        self.max_activity_samples = 10

    async def start(self):
        """Start the raid scheduling system"""
        if self.is_running:
            return

        self.is_running = True
        self._task = asyncio.create_task(self._schedule_loop())
        logger.info("Raid scheduler started")

    async def stop(self):
        """Stop the raid scheduling system"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Raid scheduler stopped")

    async def _schedule_loop(self):
        """Main scheduling loop"""
        while self.is_running:
            try:
                if not self.config.enabled:
                    await asyncio.sleep(60)
                    continue

                # Check if we should start a raid
                if await self._should_start_raid():
                    await self._trigger_raid()
                
                # Update activity metrics
                await self._update_activity_metrics()
                
                # Wait before next check
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in raid scheduler: {e}")
                await asyncio.sleep(60)

    async def _should_start_raid(self) -> bool:
        """Determine if we should start a raid based on current conditions"""
        # Don't start if a raid is already active
        if self.bot.raid_manager.state != 'INACTIVE':
            return False

        # Check cooldown
        if self.last_raid_end:
            elapsed = (datetime.now(timezone.utc) - self.last_raid_end).total_seconds()
            if elapsed < self.config.min_cooldown:
                return False

        # Check viewer count
        viewer_count = await self.bot.get_viewer_count()
        if viewer_count < self.config.min_viewers:
            return False

        # If we're past max cooldown, force a raid
        if self.last_raid_end:
            if elapsed >= self.config.max_cooldown:
                return True

        # Calculate probability based on conditions
        if self.last_raid_end and elapsed >= self.config.min_cooldown:
            base_chance = self._calculate_base_chance()
            current_hour = datetime.now(timezone.utc).hour
            
            # Increase chance during peak hours
            if current_hour in self.config.peak_hours:
                base_chance *= 1.5
            
            # Increase chance with more viewers
            viewer_multiplier = min(viewer_count / 10, 2)
            base_chance *= viewer_multiplier
            
            # Increase chance during high activity
            activity_multiplier = self._get_activity_multiplier()
            base_chance *= activity_multiplier
            
            return random.random() < base_chance

        return False

    def _calculate_base_chance(self) -> float:
        """Calculate base probability for raid start"""
        elapsed = (datetime.now(timezone.utc) - self.last_raid_end).total_seconds()
        progress = (elapsed - self.config.min_cooldown) / (self.config.max_cooldown - self.config.min_cooldown)
        return min(0.1 + (progress * 0.4), 0.5)  # 10% to 50% chance

    async def _update_activity_metrics(self):
        """Update chat activity metrics"""
        try:
            # Get recent message count
            async with self.bot.db.session_scope() as session:
                result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM message_log
                        WHERE timestamp > :cutoff
                    """),
                    {'cutoff': datetime.now(timezone.utc) - timedelta(minutes=5)}
                )
                message_count = (await result.first())[0]
            
            self.recent_activity.append(message_count)
            if len(self.recent_activity) > self.max_activity_samples:
                self.recent_activity.pop(0)

        except Exception as e:
            logger.error(f"Error updating activity metrics: {e}")

    def _get_activity_multiplier(self) -> float:
        """Calculate activity multiplier based on recent chat activity"""
        if not self.recent_activity:
            return 1.0

        avg_activity = sum(self.recent_activity) / len(self.recent_activity)
        if avg_activity > 50:  # Very active
            return self.config.active_multiplier
        elif avg_activity > 20:  # Moderately active
            return 1.25
        return 1.0

    async def update_config(self, **kwargs) -> bool:
        """Update scheduler configuration"""
        try:
            for key, value in kwargs.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            logger.info(f"Scheduler config updated: {kwargs}")
            return True
        except Exception as e:
            logger.error(f"Error updating scheduler config: {e}")
            return False

    async def force_raid(self) -> bool:
        """Force start a raid (for mod commands)"""
        try:
            if not self.config.enabled:
                return False
            
            # Set last_raid_end to ensure validation passes
            if self.last_raid_end is None:
                self.last_raid_end = datetime.now(timezone.utc) - timedelta(hours=1)
                
            return await self.bot.raid_manager.start_raid()
        except Exception as e:
            logger.error(f"Error force starting raid: {e}")
            return False

    def update_last_raid(self):
        """Update the last raid end time"""
        self.last_raid_end = datetime.now(timezone.utc)

    async def get_next_raid_estimate(self) -> Dict:
        """Get estimated time until next raid"""
        if not self.config.enabled:
            return {"enabled": False}
            
        if not self.last_raid_end:
            return {"estimate": "Soon"}
            
        elapsed = (datetime.now(timezone.utc) - self.last_raid_end).total_seconds()
        min_remaining = max(0, self.config.min_cooldown - elapsed)
        max_remaining = max(0, self.config.max_cooldown - elapsed)
        
        return {
            "enabled": True,
            "min_time": min_remaining,
            "max_time": max_remaining,
            "peak_hours": self.config.peak_hours,
            "current_probability": self._calculate_base_chance()
        }