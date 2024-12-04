import pytest
import asyncio
from datetime import datetime
from unittest.mock import Base, MagicMock, AsyncMock
from sqlalchemy import text
from database.models import User, StreamStats

class MockDatabaseManager:
    def __init__(self, engine, session_maker):
        self.engine = engine
        self.session_maker = session_maker
        self.user_batch_manager = MagicMock()
        self.user_batch_manager.flush = AsyncMock()
        self.stream_stats_manager = MagicMock()
        self.stream_stats_manager.update_viewer_count = AsyncMock()
        self.stream_stats_manager.increment_messages = AsyncMock()
        self.stream_stats_manager.flush = AsyncMock()

    async def get_or_create_user(self, twitch_id: str, username: str) -> User:
        async with self.session_maker() as session:
            user = await session.execute(
                text('SELECT * FROM users WHERE twitch_id = :twitch_id'),
                {'twitch_id': twitch_id}
            )
            user = user.first()
            if not user:
                user = User(twitch_id=twitch_id, username=username)
                session.add(user)
                await session.commit()
            return user

    async def add_command(self, name: str, response: str):
        async with self.session_maker() as session:
            await session.execute(
                text('INSERT INTO commands (name, response) VALUES (:name, :response)'),
                {'name': name, 'response': response}
            )
            await session.commit()
            return True

@pytest.fixture
async def db():
    """Create test database"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    manager = MockDatabaseManager(engine, async_session)
    yield manager
    
    await engine.dispose()