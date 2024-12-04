# tests/test_command_usage.py
import pytest
from sqlalchemy import text
from datetime import datetime, timedelta, timezone

# Define SQL statements
CREATE_TABLE = text('''
    CREATE TABLE IF NOT EXISTS command_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success BOOLEAN DEFAULT TRUE
    )
''')

INSERT_COMMAND = text('INSERT INTO command_usage (command_name, user_id) VALUES (:command, :user_id)')
INSERT_COMMAND_WITH_TIME = text('''
    INSERT INTO command_usage (command_name, user_id, timestamp) 
    VALUES (:command, :user_id, :timestamp)
''')
INSERT_COMMAND_WITH_SUCCESS = text('''
    INSERT INTO command_usage (command_name, user_id, success) 
    VALUES (:command, :user_id, :success)
''')

COUNT_ALL = text('SELECT COUNT(*) FROM command_usage')
COUNT_BY_USER = text('SELECT COUNT(*) FROM command_usage WHERE user_id = :user_id')
COUNT_RECENT = text('SELECT COUNT(*) FROM command_usage WHERE timestamp > :since')
GET_SUCCESS_STATS = text('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
    FROM command_usage 
    WHERE command_name = :command
''')
GET_USAGE_RANKING = text('''
    SELECT command_name, COUNT(*) as usage_count
    FROM command_usage
    GROUP BY command_name
    ORDER BY usage_count DESC
''')

@pytest.mark.asyncio
async def test_log_command_usage(db):
    """Test logging command usage"""
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Log command usage
        await session.execute(INSERT_COMMAND, 
            {'command': '!test', 'user_id': '12345'}
        )
        await session.commit()
        
        # Verify usage was logged
        result = await session.execute(COUNT_ALL)
        row = result.first()
        assert row[0] == 1

@pytest.mark.asyncio
async def test_get_user_command_count(db):
    """Test getting command usage count for a user"""
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Log multiple uses
        for _ in range(3):
            await session.execute(INSERT_COMMAND,
                {'command': '!test', 'user_id': '12345'}
            )
        await session.commit()
        
        # Get count for user
        result = await session.execute(COUNT_BY_USER,
            {'user_id': '12345'}
        )
        row = result.first()
        assert row[0] == 3

@pytest.mark.asyncio
async def test_get_recent_command_usage(db):
    """Test getting recent command usage"""
    current_time = datetime.now(timezone.utc)
    
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Add some usage data with timestamps
        await session.execute(INSERT_COMMAND_WITH_TIME,
            {
                'command': '!test', 
                'user_id': '12345',
                'timestamp': current_time - timedelta(minutes=5)
            }
        )
        await session.commit()
        
        # Get recent usage (last 10 minutes)
        result = await session.execute(COUNT_RECENT,
            {'since': current_time - timedelta(minutes=10)}
        )
        row = result.first()
        assert row[0] == 1

@pytest.mark.asyncio
async def test_command_success_tracking(db):
    """Test tracking command execution success/failure"""
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Log successful usage
        await session.execute(INSERT_COMMAND_WITH_SUCCESS,
            {'command': '!test', 'user_id': '12345', 'success': True}
        )
        
        # Log failed usage
        await session.execute(INSERT_COMMAND_WITH_SUCCESS,
            {'command': '!test', 'user_id': '12345', 'success': False}
        )
        await session.commit()
        
        # Get success rate
        result = await session.execute(GET_SUCCESS_STATS,
            {'command': '!test'}
        )
        row = result.first()
        assert row[0] == 2  # total
        assert row[1] == 1  # successes

@pytest.mark.asyncio
async def test_most_used_commands(db):
    """Test getting most frequently used commands"""
    async with db.session_scope() as session:
        # Create table
        await session.execute(CREATE_TABLE)
        await session.commit()

        # Log varying usage
        for _ in range(3):
            await session.execute(INSERT_COMMAND,
                {'command': '!test', 'user_id': '12345'}
            )
        
        await session.execute(INSERT_COMMAND,
            {'command': '!other', 'user_id': '12345'}
        )
        await session.commit()
        
        # Get command usage ranking
        result = await session.execute(GET_USAGE_RANKING)
        rows = result.fetchall()
        assert rows[0][0] == '!test'  # Most used command
        assert rows[0][1] == 3        # Used 3 times
        assert rows[1][0] == '!other' # Second most used
        assert rows[1][1] == 1        # Used once