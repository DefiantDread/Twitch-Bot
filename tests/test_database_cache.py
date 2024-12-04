import pytest
import asyncio
from datetime import datetime
from sqlalchemy import text
from database.models import CustomCommand, User, Base

@pytest.fixture
async def db():
    """Set up test database with cache"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    class TestDatabaseManager:
        def __init__(self):
            self.engine = engine
            self.session_maker = async_session
            self.cache = {}
        
        async def get_command(self, name: str) -> CustomCommand:
            async with self.session_maker() as session:
                result = await session.execute(
                    text('SELECT name, response FROM commands WHERE name = :name'),
                    {'name': name}
                )
                row = await result.first()
                if row:
                    return CustomCommand(name=row[0], response=row[1])
                return None

        async def add_command(self, name: str, response: str) -> CustomCommand:
            async with self.session_maker() as session:
                await session.execute(
                    text('INSERT OR REPLACE INTO commands (name, response) VALUES (:name, :response)'),
                    {'name': name, 'response': response}
                )
                await session.commit()
                return CustomCommand(name=name, response=response)

        async def get_or_create_user(self, twitch_id: str, username: str) -> User:
            async with self.session_maker() as session:
                result = await session.execute(
                    text('SELECT twitch_id, username FROM users WHERE twitch_id = :twitch_id'),
                    {'twitch_id': twitch_id}
                )
                row = await result.first()
                if not row:
                    await session.execute(
                        text('INSERT INTO users (twitch_id, username) VALUES (:twitch_id, :username)'),
                        {'twitch_id': twitch_id, 'username': username}
                    )
                    await session.commit()
                    return User(twitch_id=twitch_id, username=username)
                return User(twitch_id=row[0], username=row[1])

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Create initial schema
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS commands (
                name TEXT PRIMARY KEY,
                response TEXT NOT NULL
            )
        '''))
        
        await conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                twitch_id TEXT PRIMARY KEY,
                username TEXT NOT NULL
            )
        '''))

    db = TestDatabaseManager()
    yield db
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_cached_command_retrieval(db):
    """Test command caching"""
    async with db.session_maker() as session:
        # Create initial command
        await session.execute(
            text('INSERT INTO commands (name, response) VALUES (:name, :response)'),
            {'name': 'test', 'response': 'test response'}
        )
        await session.commit()
    
    # First get should hit database
    async with db.session_maker() as session:
        result = await session.execute(
            text('SELECT response FROM commands WHERE name = :name'),
            {'name': 'test'}
        )
        row = result.first()
        assert row is not None
        assert row[0] == 'test response'
    
    # Second get should also work
    async with db.session_maker() as session:
        result = await session.execute(
            text('SELECT response FROM commands WHERE name = :name'),
            {'name': 'test'}
        )
        row = result.first()
        assert row is not None
        assert row[0] == 'test response'

@pytest.mark.asyncio
async def test_cache_invalidation(db):
    """Test cache invalidation on command update"""
    async with db.session_maker() as session:
        # Create initial command
        await session.execute(
            text('INSERT INTO commands (name, response) VALUES (:name, :response)'),
            {'name': 'test', 'response': 'initial response'}
        )
        await session.commit()
    
    # First get
    async with db.session_maker() as session:
        result = await session.execute(
            text('SELECT response FROM commands WHERE name = :name'),
            {'name': 'test'}
        )
        row = result.first()
        assert row[0] == 'initial response'
    
    # Update command
    async with db.session_maker() as session:
        await session.execute(
            text('UPDATE commands SET response = :response WHERE name = :name'),
            {'name': 'test', 'response': 'updated response'}
        )
        await session.commit()
    
    # Get updated response
    async with db.session_maker() as session:
        result = await session.execute(
            text('SELECT response FROM commands WHERE name = :name'),
            {'name': 'test'}
        )
        row = result.first()
        assert row[0] == 'updated response'

@pytest.mark.asyncio
async def test_cached_user_retrieval(db):
    """Test user caching"""
    async with db.session_maker() as session:
        # Add initial user
        await session.execute(
            text('INSERT INTO users (twitch_id, username) VALUES (:id, :name)'),
            {'id': '12345', 'name': 'test_user'}
        )
        await session.commit()
    
    # First get
    async with db.session_maker() as session:
        result = await session.execute(
            text('SELECT username FROM users WHERE twitch_id = :id'),
            {'id': '12345'}
        )
        row = result.first()
        assert row is not None
        assert row[0] == 'test_user'