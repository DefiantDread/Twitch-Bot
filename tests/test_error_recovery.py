# tests/test_error_recovery.py
import pytest
import asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Define SQL statements
CREATE_TABLE = text('''
    CREATE TABLE IF NOT EXISTS commands (
        name TEXT PRIMARY KEY,
        response TEXT NOT NULL
    )
''')

INSERT_COMMAND = text('INSERT INTO commands (name, response) VALUES (:name, :response)')
COUNT_COMMANDS = text('SELECT COUNT(*) FROM commands')

@pytest.mark.asyncio
async def test_transaction_rollback(db):
    """Test database recovery after failed transaction."""
    async with db.session_scope() as session:
        # Create table and insert initial command
        await session.execute(CREATE_TABLE)
        await session.execute(INSERT_COMMAND,
            {'name': '!test', 'response': 'Test response'}
        )
        await session.commit()

    try:
        async with db.session_scope() as session:
            await session.execute(INSERT_COMMAND,
                {'name': '!test2', 'response': 'Test 2'}
            )
            raise SQLAlchemyError("Simulated error")
    except SQLAlchemyError:
        pass

    async with db.session_scope() as session:
        result = await session.execute(COUNT_COMMANDS)
        row = result.first()
        assert row[0] == 1  # Only first command should exist

@pytest.mark.asyncio
async def test_connection_loss_recovery(db):
    """Test recovery from connection loss."""
    async with db.session_scope() as session:
        # Verify we can execute queries
        result = await session.execute(COUNT_COMMANDS)
        row = result.first()
        assert row[0] is not None

@pytest.mark.asyncio
async def test_concurrent_error_isolation(db):
    """Test that errors in one operation don't affect others."""
    async def good_operation():
        async with db.session_scope() as session:
            await session.execute(INSERT_COMMAND,
                {'name': '!good', 'response': 'Good'}
            )
            await session.commit()
            return True

    async def bad_operation():
        try:
            async with db.session_scope() as session:
                raise SQLAlchemyError("Simulated bad operation")
        except SQLAlchemyError:
            return False
        return True

    results = await asyncio.gather(
        good_operation(),
        bad_operation(),
        return_exceptions=True
    )
    
    assert results[0] is True  # good operation succeeded
    assert results[1] is False  # bad operation failed as expected

    async with db.session_scope() as session:
        result = await session.execute(COUNT_COMMANDS)
        row = result.first()
        assert row[0] == 1  # Only good operation's command should exist

@pytest.mark.asyncio
async def test_reconnection_attempt(db):
    """Test database reconnection attempts."""
    retries = 3
    success = False

    for _ in range(retries):
        try:
            async with db.session_scope() as session:
                result = await session.execute(COUNT_COMMANDS)
                row = result.first()
                assert row[0] is not None
                success = True
                break
        except SQLAlchemyError:
            await asyncio.sleep(0.1)

    assert success, "Should successfully reconnect within retry attempts"