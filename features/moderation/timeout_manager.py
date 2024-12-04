# features/moderation/timeout_manager.py
import time
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class TimeoutManager:
    def __init__(self, cleanup_interval: int = 3600):
        self.timeout_users: Dict[str, float] = {}  # user -> timeout_end_time
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()

    def add_timeout(self, user: str, duration: int) -> None:
        """Add a user timeout"""
        self.timeout_users[user] = time.time() + duration
        self._cleanup_if_needed()

    def remove_timeout(self, user: str) -> None:
        """Remove a user's timeout"""
        self.timeout_users.pop(user, None)

    def get_remaining_timeout(self, user: str) -> Optional[int]:
        """Get remaining timeout duration in seconds"""
        if user not in self.timeout_users:
            return None
            
        remaining = self.timeout_users[user] - time.time()
        if remaining <= 0:
            self.remove_timeout(user)
            return None
            
        return int(remaining)

    def is_timeout(self, user: str) -> bool:
        """Check if a user is currently timed out"""
        remaining = self.get_remaining_timeout(user)
        return remaining is not None and remaining > 0

    def _cleanup_if_needed(self) -> None:
        """Clean up expired timeouts periodically"""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            expired = [
                user for user, end_time in self.timeout_users.items()
                if end_time <= current_time
            ]
            for user in expired:
                self.timeout_users.pop(user)
            
            if expired:
                logger.debug(f"Cleaned up {len(expired)} expired timeouts")
            self.last_cleanup = current_time