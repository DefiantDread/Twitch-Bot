# features/points/points_manager.py
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import logging
import asyncio

from sqlalchemy import text

logger = logging.getLogger(__name__)

class PointsManager:
    def __init__(self, bot):
        self.bot = bot
        self.points_per_minute = 10
        self.active_multiplier = 2.0
        self.subscriber_multiplier = 1.5
        self._lock = asyncio.Lock()

    async def setup(self):
        """Initialize database tables for points system."""
        async with self.bot.db.session_scope() as session:
            try:
                queries = [
                    text('''
                        CREATE TABLE IF NOT EXISTS user_points (
                            user_id TEXT PRIMARY KEY,
                            points INTEGER DEFAULT 0,
                            total_earned INTEGER DEFAULT 0,
                            last_updated TIMESTAMP,
                            streak_days INTEGER DEFAULT 0,
                            last_daily TIMESTAMP
                        )
                    '''),
                    text('''
                        CREATE TABLE IF NOT EXISTS points_transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT,
                            amount INTEGER,
                            reason TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES user_points(user_id)
                        )
                    '''),
                    text('''
                        CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            twitch_id TEXT UNIQUE,
                            username TEXT,
                            is_mod BOOLEAN DEFAULT FALSE,
                            is_subscriber BOOLEAN DEFAULT FALSE,
                            first_seen TIMESTAMP,
                            last_seen TIMESTAMP
                        )
                    ''')
                ]
                for query in queries:
                    await session.execute(query)
                logger.info("Tables initialized successfully.")
            except Exception as e:
                logger.error(f"Error initializing tables: {e}")
                raise

    async def add_points(self, user_id: str, amount: int, reason: str = None) -> bool:
        """Add points to a user's balance."""
        async with self._lock:
            async with self.bot.db.session_scope() as session:
                try:
                    now = datetime.now(timezone.utc)
                    await session.execute(
                        text("""
                            INSERT INTO user_points (user_id, points, total_earned, last_updated)
                            VALUES (:user_id, :amount, :amount, :now)
                            ON CONFLICT (user_id) DO UPDATE
                            SET points = user_points.points + :amount,
                                total_earned = user_points.total_earned + :amount,
                                last_updated = :now
                        """),
                        {'user_id': user_id, 'amount': amount, 'now': now}
                    )
                    await session.commit()
                    return True
                except Exception as e:
                    logger.error(f"Error adding points: {e}")
                    return False

    async def remove_points(self, user_id: str, amount: int, reason: str = None) -> bool:
        """Remove points from a user's balance."""
        async with self._lock:
            async with self.bot.db.session_scope() as session:
                try:
                    current_points = await self.get_points(user_id)
                    if current_points < amount:
                        return False

                    now = datetime.now(timezone.utc)
                    await session.execute(
                        text("""
                            UPDATE user_points
                            SET points = points - :amount,
                                last_updated = :now
                            WHERE user_id = :user_id
                        """),
                        {'user_id': user_id, 'amount': amount, 'now': now}
                    )
                    await session.commit()
                    return True
                except Exception as e:
                    logger.error(f"Error removing points: {e}")
                    return False

    async def get_points(self, user_id: str) -> int:
        """Get current points balance."""
        try:
            async with self.bot.db.session_scope() as session:
                query = text('SELECT points FROM user_points WHERE user_id = :user_id')
                result = await session.execute(query, {'user_id': user_id})
                points = result.scalar()
                return points if points is not None else 0
        except Exception as e:
            logger.error(f"Error fetching points for user_id {user_id}: {e}")
            return 0

    async def update_watch_time_points(self):
        """Update points for active viewers."""
        try:
            now = datetime.now(timezone.utc)
            inactive_threshold = now - timedelta(minutes=10)
            
            for user_id, activity in self.bot.user_tracker.active_users.items():
                try:
                    # Skip inactive users
                    if activity.last_seen <= inactive_threshold:
                        continue

                    # Calculate points for the user
                    points = self.points_per_minute
                    if activity.is_subscriber:
                        points *= self.subscriber_multiplier
                    if activity.message_count > 0:
                        points *= self.active_multiplier

                    # Round points before adding
                    await self.add_points(user_id, round(points))
                
                except Exception as user_error:
                    logger.error(
                        f"Error updating points for user_id {user_id}: {user_error} | "
                        f"Last Seen: {activity.last_seen}, Message Count: {activity.message_count}"
                    )
        
        except Exception as general_error:
            logger.error(f"Error in update_watch_time_points: {general_error}")
