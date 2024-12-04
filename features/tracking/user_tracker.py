# features/tracking/user_tracker.py
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class UserActivity:
    first_seen: datetime
    last_seen: datetime
    message_count: int = 0
    time_watched: int = 0  # in minutes
    last_message: Optional[str] = None
    is_subscriber: bool = False
    is_moderator: bool = False
    custom_badges: List[str] = None

    def __post_init__(self):
        if self.custom_badges is None:
            self.custom_badges = []

class UserTracker:
    def __init__(self, bot):
        self.bot = bot
        self.active_users: Dict[str, UserActivity] = {}
        self.session_start = datetime.now(timezone.utc)
        self.first_time_chatters: set = set()
        self.returning_users: set = set()
        self._lock = asyncio.Lock()

    async def track_user_message(self, message) -> bool:
        """Track a user's message and return whether they're a first-time chatter"""
        user_id = str(message.author.id)
        username = message.author.name
        is_first_time = False

        async with self._lock:
            try:
                # Check if user exists in database
                is_first_time = await self._is_first_time_chatter(user_id)
                
                # Update or create activity record
                if user_id not in self.active_users:
                    self.active_users[user_id] = UserActivity(
                        first_seen=datetime.now(timezone.utc),
                        last_seen=datetime.now(timezone.utc),
                        is_subscriber=message.author.is_subscriber,
                        is_moderator=message.author.is_mod
                    )
                    if is_first_time:
                        self.first_time_chatters.add(user_id)
                    else:
                        self.returning_users.add(user_id)

                # Update activity
                activity = self.active_users[user_id]
                activity.last_seen = datetime.now(timezone.utc)
                activity.message_count += 1
                activity.last_message = message.content
                activity.is_subscriber = message.author.is_subscriber
                activity.is_moderator = message.author.is_mod

                # Update database
                await self._update_user_db(user_id, username, activity)
                
                return is_first_time
                
            except Exception as e:
                logger.error(f"Error tracking user message: {e}")
                return False

    async def _is_first_time_chatter(self, user_id: str) -> bool:
        """Check if this is a user's first time chatting"""
        try:
            async with self.bot.db.session_scope() as session:
                stmt = text("SELECT first_seen FROM users WHERE twitch_id = :user_id")
                result = await session.execute(stmt, {'user_id': user_id})
                row = result.first()
                return row is None
        except Exception as e:
            logger.error(f"Error checking first time chatter: {e}")
            return False

    async def _update_user_db(self, user_id: str, username: str, activity: UserActivity):
        """Update user information in database"""
        try:
            async with self.bot.db.session_scope() as session:
                stmt = text("""
                    INSERT INTO users (
                        twitch_id, username, first_seen, last_seen, 
                        is_subscriber, is_moderator
                    ) VALUES (
                        :user_id, :username, :first_seen, :last_seen,
                        :is_subscriber, :is_moderator
                    )
                    ON CONFLICT (twitch_id) DO UPDATE SET
                        username = :username,
                        last_seen = :last_seen,
                        is_subscriber = :is_subscriber,
                        is_moderator = :is_moderator
                """)
                
                await session.execute(stmt, {
                    'user_id': user_id,
                    'username': username,
                    'first_seen': activity.first_seen,
                    'last_seen': activity.last_seen,
                    'is_subscriber': activity.is_subscriber,
                    'is_moderator': activity.is_moderator
                })
        except Exception as e:
            logger.error(f"Error updating user database: {e}")

    async def update_watch_time(self):
        """Update watch time for active users"""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            for user_id, activity in self.active_users.items():
                if (current_time - activity.last_seen) < timedelta(minutes=10):
                    activity.time_watched += 1

    async def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """Get comprehensive stats for a user"""
        try:
            async with self.bot.db.session_scope() as session:
                stmt = text("""
                    SELECT 
                        username, first_seen, last_seen,
                        is_subscriber, is_moderator
                    FROM users 
                    WHERE twitch_id = :user_id
                """)
                result = await session.execute(stmt, {'user_id': user_id})
                row = result.first()
                
                if not row:
                    return None

                activity = self.active_users.get(user_id)
                
                return {
                    'username': row[0],
                    'first_seen': row[1],
                    'last_seen': row[2],
                    'is_subscriber': row[3],
                    'is_moderator': row[4],
                    'message_count': activity.message_count if activity else 0,
                    'time_watched': activity.time_watched if activity else 0
                }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None

    async def cleanup_inactive_users(self):
        """Remove users who haven't been active for a while"""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            inactive_threshold = timedelta(minutes=30)
            
            inactive_users = [
                user_id for user_id, activity in self.active_users.items()
                if (current_time - activity.last_seen) > inactive_threshold
            ]
            
            for user_id in inactive_users:
                del self.active_users[user_id]

    async def get_session_stats(self) -> Dict:
        """Get statistics for the current session"""
        return {
            'first_time_chatters': len(self.first_time_chatters),
            'returning_users': len(self.returning_users),
            'active_users': len(self.active_users),
            'total_messages': sum(u.message_count for u in self.active_users.values()),
            'subscribers': sum(1 for u in self.active_users.values() if u.is_subscriber),
            'session_duration': int((datetime.now(timezone.utc) - self.session_start).total_seconds() / 60)
        }