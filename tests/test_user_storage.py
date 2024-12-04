# tests/test_user_storage.py
import pytest
from sqlalchemy import text
from datetime import datetime, timezone

# Define SQL statements
CREATE_TABLE = text('''
    CREATE TABLE IF NOT EXISTS users (
        twitch_id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        is_mod BOOLEAN DEFAULT FALSE,
        is_subscriber BOOLEAN DEFAULT FALSE,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

INSERT_USER = text('INSERT INTO users (twitch_id, username) VALUES (:id, :name)')
SELECT_USERNAME = text('SELECT username FROM users WHERE twitch_id = :id')

UPDATE_MOD_STATUS = text('UPDATE users SET is_mod = TRUE WHERE twitch_id = :id')
SELECT_MOD_STATUS = text('SELECT is_mod FROM users WHERE twitch_id = :id')

UPDATE_SUB_STATUS = text('UPDATE users SET is_subscriber = TRUE WHERE twitch_id = :id')
SELECT_SUB_STATUS = text('SELECT is_subscriber FROM users WHERE twitch_id = :id')

UPDATE_LAST_SEEN = text('UPDATE users SET last_seen = :timestamp WHERE twitch_id = :id')
SELECT_LAST_SEEN = text('SELECT last_seen FROM users WHERE twitch_id = :id')

UPSERT_USER = text('''
    INSERT INTO users (twitch_id, username) 
    VALUES (:id, :name)
    ON CONFLICT (twitch_id) DO UPDATE SET 
        username = :name,
        last_seen = CURRENT_TIMESTAMP
''')

@pytest.mark.asyncio
async def test_add_user(db):
    """Test adding a new user"""
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Add user
        await session.execute(INSERT_USER,
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Verify user exists
        result = await session.execute(SELECT_USERNAME,
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] == 'testuser'

@pytest.mark.asyncio
async def test_update_mod_status(db):
    """Test updating moderator status"""
    async with db.session_scope() as session:
        # Add user
        await session.execute(INSERT_USER,
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Make user mod
        await session.execute(UPDATE_MOD_STATUS,
            {'id': '12345'}
        )
        await session.commit()
        
        # Verify mod status
        result = await session.execute(SELECT_MOD_STATUS,
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] == 1  # SQLite represents TRUE as 1

@pytest.mark.asyncio
async def test_update_subscriber_status(db):
    """Test updating subscriber status"""
    async with db.session_scope() as session:
        # Add user
        await session.execute(INSERT_USER,
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Make user subscriber
        await session.execute(UPDATE_SUB_STATUS,
            {'id': '12345'}
        )
        await session.commit()
        
        # Verify subscriber status
        result = await session.execute(SELECT_SUB_STATUS,
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] == 1  # SQLite represents TRUE as 1

@pytest.mark.asyncio
async def test_update_last_seen(db):
    """Test updating user's last seen timestamp"""
    async with db.session_scope() as session:
        # Add user
        await session.execute(INSERT_USER,
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Update last seen
        current_time = datetime.now(timezone.utc)
        await session.execute(UPDATE_LAST_SEEN,
            {'id': '12345', 'timestamp': current_time}
        )
        await session.commit()
        
        # Verify last seen was updated
        result = await session.execute(SELECT_LAST_SEEN,
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] is not None

@pytest.mark.asyncio
async def test_get_or_create_user(db):
    """Test get or create user functionality"""
    async with db.session_scope() as session:
        # First time - should create
        await session.execute(UPSERT_USER,
            {'id': '12345', 'name': 'testuser'}
        )
        await session.commit()
        
        # Second time - should update
        await session.execute(UPSERT_USER,
            {'id': '12345', 'name': 'testuser_updated'}
        )
        await session.commit()
        
        # Verify final state
        result = await session.execute(SELECT_USERNAME,
            {'id': '12345'}
        )
        row = result.first()
        assert row[0] == 'testuser_updated'