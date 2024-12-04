# database/manager.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import logging
import asyncio

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    twitch_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    is_mod = Column(Boolean, default=False)
    is_subscriber = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class StreamStats(Base):
    __tablename__ = 'stream_stats'
    id = Column(Integer, primary_key=True)
    peak_viewers = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)

class StreamStatsManager:
    def __init__(self, session_maker):
        self.session_maker = session_maker
        self.viewer_count = 0
        self.messages = 0
        self.current_stats = None

    async def flush(self):
        async with self.session_maker() as session:
            stmt = select(StreamStats).order_by(StreamStats.id.desc()).limit(1)
            result = await session.execute(stmt)
            stats = result.scalar_one_or_none()
            
            if not stats:
                stats = StreamStats(peak_viewers=self.viewer_count, messages_sent=self.messages)
                session.add(stats)
            else:
                stats.peak_viewers = max(stats.peak_viewers, self.viewer_count)
                stats.messages_sent += self.messages
            
            self.current_stats = stats
            await session.commit()
            self.viewer_count = 0
            self.messages = 0


class DatabaseManager:
    def __init__(self, connection_url: Optional[str] = None, testing: bool = False):
        self.connection_url = connection_url or 'sqlite+aiosqlite:///bot.db'
        self.engine = None
        self.Session = None
        self.testing = testing
        self.stats = {'connections_created': 0, 'connections_used': 0, 'errors': 0}
        self._setup_engine()
        self.stream_stats_manager = StreamStatsManager(self.session_scope)

    def _setup_engine(self) -> None:
        try:
            self.engine = create_async_engine(
                self.connection_url,
                echo=False,
                future=True
            )
            self.Session = sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("Database engine initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up database engine: {e}")
            raise

    @asynccontextmanager
    async def session_scope(self):
        """Provide a transactional scope for database operations."""
        session = self.Session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            self.stats['errors'] += 1
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            await session.close()

    async def check_connection_health(self) -> bool:
        """Check database connection health"""
        try:
            async with self.session_scope() as session:
                await session.execute(text('SELECT 1'))
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.stats['errors'] += 1
            return False

    async def close(self) -> None:
        """Close database connections"""
        try:
            if self.engine:
                await self.engine.dispose()
            logger.info("Database connections closed successfully")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
            raise

    async def get_pool_status(self) -> Dict[str, Any]:
        return {
            'active': bool(self.engine and self.Session),
            'stats': self.stats.copy()
        }
    
    async def get_or_create_user(self, twitch_id: str, username: str) -> User:
        """Fetch or create a user by Twitch ID."""
        async with self.session_scope() as session:
            stmt = select(User).where(User.twitch_id == twitch_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(twitch_id=twitch_id, username=username)
                session.add(user)
                await session.commit()
            return user
        
async def initialize_database(db_url: str):
    """Initialize database asynchronously"""
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        # Create users table
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitch_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                is_mod BOOLEAN DEFAULT FALSE,
                is_subscriber BOOLEAN DEFAULT FALSE,
                is_moderator BOOLEAN DEFAULT FALSE,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))
        
        # Create raid system tables
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS raid_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                ship_type TEXT NOT NULL,
                viewer_count INTEGER NOT NULL,
                required_crew INTEGER NOT NULL,
                final_crew INTEGER NOT NULL,
                final_multiplier REAL NOT NULL,
                total_plunder INTEGER NOT NULL,
                status TEXT
            )
        '''))

        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS raid_participants (
                raid_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                initial_investment INTEGER NOT NULL,
                final_investment INTEGER NOT NULL,
                reward INTEGER NOT NULL,
                PRIMARY KEY (raid_id, user_id),
                FOREIGN KEY (raid_id) REFERENCES raid_history(id),
                FOREIGN KEY (user_id) REFERENCES users(twitch_id)
            )
        '''))

        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS player_raid_stats (
                user_id TEXT PRIMARY KEY,
                total_raids INTEGER DEFAULT 0,
                successful_raids INTEGER DEFAULT 0,
                total_invested INTEGER DEFAULT 0,
                total_plunder INTEGER DEFAULT 0,
                biggest_reward INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(twitch_id)
            )
        '''))

        # Create other required tables
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS banned_phrases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase TEXT UNIQUE NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
        '''))
        
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS stream_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stream_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                peak_viewers INTEGER DEFAULT 0,
                stream_duration INTEGER DEFAULT 0,
                messages_sent INTEGER DEFAULT 0
            )
        '''))

        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id TEXT PRIMARY KEY,
                points INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                last_updated TIMESTAMP,
                streak_days INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(twitch_id)
            )
        '''))
        
        # Create indexes for better query performance
        await conn.execute(text('CREATE INDEX IF NOT EXISTS idx_raid_history_time ON raid_history(start_time)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS idx_raid_participants_user ON raid_participants(user_id)'))
        await conn.execute(text('CREATE INDEX IF NOT EXISTS idx_player_stats_plunder ON player_raid_stats(total_plunder)'))

    await engine.dispose()
    logger.info("Database tables created successfully.")