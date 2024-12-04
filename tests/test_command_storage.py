# tests/test_command_storage.py
import pytest
from sqlalchemy import text

@pytest.mark.asyncio
async def test_add_command(db):
    """Test storing and retrieving commands"""
    create_table = text('''
        CREATE TABLE IF NOT EXISTS commands (
            name TEXT PRIMARY KEY,
            response TEXT NOT NULL
        )
    ''')

    insert_command = text('INSERT INTO commands (name, response) VALUES (:name, :response)')
    select_command = text('SELECT response FROM commands WHERE name = :name')

    async with db.session_scope() as session:
        # Create commands table if it doesn't exist
        await session.execute(create_table)
        await session.commit()

        # Add command
        await session.execute(insert_command, 
            {'name': '!test', 'response': 'Test response'}
        )
        await session.commit()
        
        # Verify command exists
        result = await session.execute(select_command, 
            {'name': '!test'}
        )
        row = result.first()
        assert row[0] == 'Test response'

@pytest.mark.asyncio
async def test_update_command(db):
    """Test updating an existing command"""
    insert_command = text('INSERT INTO commands (name, response) VALUES (:name, :response)')
    update_command = text('UPDATE commands SET response = :response WHERE name = :name')
    select_command = text('SELECT response FROM commands WHERE name = :name')

    async with db.session_scope() as session:
        # Add initial command
        await session.execute(insert_command,
            {'name': '!test', 'response': 'Original response'}
        )
        await session.commit()
        
        # Update command
        await session.execute(update_command,
            {'name': '!test', 'response': 'Updated response'}
        )
        await session.commit()
        
        # Verify update
        result = await session.execute(select_command,
            {'name': '!test'}
        )
        row = result.first()
        assert row[0] == 'Updated response'

@pytest.mark.asyncio
async def test_delete_command(db):
    """Test deleting a command"""
    insert_command = text('INSERT INTO commands (name, response) VALUES (:name, :response)')
    delete_command = text('DELETE FROM commands WHERE name = :name')
    count_command = text('SELECT COUNT(*) FROM commands WHERE name = :name')

    async with db.session_scope() as session:
        # Add command
        await session.execute(insert_command,
            {'name': '!test', 'response': 'Test response'}
        )
        await session.commit()
        
        # Delete command
        await session.execute(delete_command,
            {'name': '!test'}
        )
        await session.commit()
        
        # Verify deletion
        result = await session.execute(count_command,
            {'name': '!test'}
        )
        row = result.first()
        assert row[0] == 0

@pytest.mark.asyncio
async def test_command_case_sensitivity(db):
    """Test command name case sensitivity handling"""
    insert_command = text('INSERT INTO commands (name, response) VALUES (:name, :response)')
    select_command = text('SELECT response FROM commands WHERE LOWER(name) = LOWER(:name)')

    async with db.session_scope() as session:
        # Add command with uppercase
        await session.execute(insert_command,
            {'name': '!TEST', 'response': 'Test response'}
        )
        await session.commit()
        
        # Should find command case-insensitively
        result = await session.execute(select_command,
            {'name': '!test'}
        )
        row = result.first()
        assert row[0] == 'Test response'