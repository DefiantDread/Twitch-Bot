import pytest
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database.models import Base

@pytest.fixture
async def db():
    """Create test database"""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    class TestDatabaseManager:
        def __init__(self):
            self.engine = engine
            self.session_maker = async_session

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create test tables
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

    yield TestDatabaseManager()
    await engine.dispose()

@pytest.mark.asyncio
async def test_command_storage(db):
    """Test storing and retrieving commands"""
    async with db.session_maker() as session:
        # Create command
        await session.execute(
            text('INSERT INTO commands (name, response) VALUES (:name, :response)'),
            {'name': '!test', 'response': 'Test response'}
        )
        await session.commit()
        
        # Retrieve command
        result = await session.execute(
            text('SELECT response FROM commands WHERE name = :name'),
            {'name': '!test'}
        )
        row = result.first()
        assert row[0] == 'Test response'

@pytest.mark.asyncio
async def test_user_data(db):
    """Test user data operations"""
    async with db.session_maker() as session:
        # Add user
        await session.execute(
            text('INSERT INTO users (twitch_id, username) VALUES (:id, :name)'),
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Get user
        result = await session.execute(
            text('SELECT username FROM users WHERE twitch_id = :id'),
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] == 'testuser'

@pytest.mark.asyncio
async def test_basic_concurrent_access(db):
    """Test simple concurrent operations"""
    async def add_user(user_id: str, username: str):
        async with db.session_maker() as session:
            await session.execute(
                text('INSERT INTO users (twitch_id, username) VALUES (:id, :name)'),
                {'id': user_id, 'name': username}
            )
            await session.commit()
    
    # Add users concurrently
    await asyncio.gather(
        add_user('1', 'user1'),
        add_user('2', 'user2'),
        add_user('3', 'user3')
    )
    
    # Verify all users were added
    async with db.session_maker() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM users'))
        row = result.first()
        assert row[0] == 3