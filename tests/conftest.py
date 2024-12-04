# tests/conftest.py
from contextlib import asynccontextmanager
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Base
from utils.rate_limiter import RateLimiter
from features.analytics.tracker import AnalyticsTracker

import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Base
import greenlet

@pytest.fixture
async def db():
    """Create test database with proper async setup"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        echo=False
    )
    
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    class TestDatabaseManager:
        def __init__(self):
            self.engine = engine
            self.Session = async_session
        
        @asynccontextmanager
        async def session_scope(self):
            """Provide a transactional scope around a series of operations."""
            session = self.Session()
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    yield TestDatabaseManager()
    
    # Cleanup
    await engine.dispose()

@pytest.fixture
def mock_bot(mock_db):
    """Create a mock bot instance for testing."""
    bot = MagicMock()
    bot.db = mock_db
    bot.rate_limiter = RateLimiter()
    bot.analytics = AnalyticsTracker(bot)

    # Mock context for command testing
    bot.ctx = AsyncMock()
    bot.ctx.send = AsyncMock()
    bot.ctx.author = MagicMock()
    bot.ctx.author.is_mod = False
    bot.ctx.author.name = "test_user"
    bot.ctx.author.id = "12345"

    return bot

# Add event loop fixture for Windows
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
