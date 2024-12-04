# utils/rate_limiter.py
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self.command_cooldowns: Dict[str, Dict[str, datetime]] = {}
        self.global_cooldowns: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def _get_now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def can_execute(
        self,
        command_name: str,
        user_id: str,
        cooldown: int = 3,
        global_cooldown: int = 1,
    ) -> Tuple[bool, Optional[float]]:
        if not command_name or not user_id:
            return True, None

        if cooldown <= 0 and global_cooldown <= 0:
            return True, None

        now = self._get_now()
        command_key = command_name.lower()

        async with self._lock:
            # Clean up old cooldowns first
            self._cleanup_old_cooldowns(now)

            # Check global cooldown first
            if global_cooldown > 0 and command_key in self.global_cooldowns:
                time_since_last = (now - self.global_cooldowns[command_key]).total_seconds()
                logger.debug(f"Global cooldown check: {time_since_last} < {global_cooldown}")
                if time_since_last < global_cooldown:
                    return False, global_cooldown - time_since_last

            # Check user-specific cooldown
            if cooldown > 0:
                if command_key in self.command_cooldowns and user_id in self.command_cooldowns[command_key]:
                    time_since_last = (now - self.command_cooldowns[command_key][user_id]).total_seconds()
                    logger.debug(f"User cooldown check: {time_since_last} < {cooldown}")
                    if time_since_last < cooldown:
                        return False, cooldown - time_since_last

            # If we get here, update cooldowns and allow execution
            if global_cooldown > 0:
                self.global_cooldowns[command_key] = now
            if cooldown > 0:
                if command_key not in self.command_cooldowns:
                    self.command_cooldowns[command_key] = {}
                self.command_cooldowns[command_key][user_id] = now

            return True, None

    async def reset_cooldown(self, command_name: str, user_id: Optional[str] = None) -> None:
        command_key = command_name.lower()
        
        async with self._lock:
            logger.debug(f"Resetting cooldown for command: {command_key}, user: {user_id}")
            logger.debug(f"Before reset - Global cooldowns: {self.global_cooldowns}")
            logger.debug(f"Before reset - Command cooldowns: {self.command_cooldowns}")
            
            # Always reset global cooldown for the command
            if command_key in self.global_cooldowns:
                del self.global_cooldowns[command_key]
            
            # Reset user-specific cooldown if user_id provided
            if user_id is not None:
                if command_key in self.command_cooldowns:
                    self.command_cooldowns[command_key].pop(user_id, None)
                    if not self.command_cooldowns[command_key]:
                        del self.command_cooldowns[command_key]
            else:
                # Reset all cooldowns for this command
                self.command_cooldowns.pop(command_key, None)

            logger.debug(f"After reset - Global cooldowns: {self.global_cooldowns}")
            logger.debug(f"After reset - Command cooldowns: {self.command_cooldowns}")

    def _cleanup_old_cooldowns(self, now: Optional[datetime] = None) -> None:
        if now is None:
            now = self._get_now()

        cutoff = now - timedelta(minutes=5)
        logger.debug(f"Cleaning up cooldowns before: {cutoff}")

        # Clean up global cooldowns
        expired_globals = [
            cmd for cmd, time in self.global_cooldowns.items()
            if time <= cutoff
        ]
        for cmd in expired_globals:
            del self.global_cooldowns[cmd]

        # Clean up user cooldowns
        for cmd in list(self.command_cooldowns.keys()):
            expired_users = [
                user for user, time in self.command_cooldowns[cmd].items()
                if time <= cutoff
            ]
            for user in expired_users:
                del self.command_cooldowns[cmd][user]
            
            if not self.command_cooldowns[cmd]:
                del self.command_cooldowns[cmd]