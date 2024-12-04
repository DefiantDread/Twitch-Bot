# tests/test_rate_limiting.py
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from utils.rate_limiter import RateLimiter

@pytest.mark.asyncio
async def test_basic_rate_limiting():
    """Test basic rate limiting functionality"""
    limiter = RateLimiter()
    
    # First attempt should succeed
    can_execute, wait_time = await limiter.can_execute("test_command", "user1", cooldown=1)
    assert can_execute is True
    assert wait_time is None
    
    # Immediate second attempt should fail
    can_execute, wait_time = await limiter.can_execute("test_command", "user1", cooldown=1)
    assert can_execute is False
    assert wait_time > 0

    # Wait for cooldown
    await asyncio.sleep(1)

    # Third attempt should succeed
    can_execute, wait_time = await limiter.can_execute("test_command", "user1", cooldown=1)
    assert can_execute is True
    assert wait_time is None

@pytest.mark.asyncio
async def test_different_users():
    """Test rate limiting across different users"""
    limiter = RateLimiter()
    
    # First user triggers cooldown
    await limiter.can_execute("test_command", "user1", cooldown=3, global_cooldown=0)
    
    # Second user should still be able to execute (no global cooldown)
    can_execute, _ = await limiter.can_execute("test_command", "user2", cooldown=3, global_cooldown=0)
    assert can_execute is True

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test rate limiting under concurrent load"""
    limiter = RateLimiter()
    
    async def make_request(user_id):
        return await limiter.can_execute(
            "test_command", 
            f"user{user_id}", 
            cooldown=3, 
            global_cooldown=0
        )
    
    # Make multiple concurrent requests with different users
    results = await asyncio.gather(
        *[make_request(i) for i in range(10)]
    )
    
    # Each first attempt per user should succeed when no global cooldown
    assert all(can_execute for can_execute, _ in results)

@pytest.mark.asyncio
async def test_edge_cases():
    """Test edge cases and invalid inputs"""
    limiter = RateLimiter()
    
    # Test with empty command name
    can_execute, _ = await limiter.can_execute("", "user1")
    assert can_execute is True
    
    # Test with empty user id
    can_execute, _ = await limiter.can_execute("test_command", "")
    assert can_execute is True
    
    # Test with zero cooldown
    can_execute, _ = await limiter.can_execute(
        "test_command",
        "user1",
        cooldown=0,
        global_cooldown=0
    )
    assert can_execute is True

@pytest.mark.asyncio
async def test_cooldown_cleanup():
    """Test cleanup of old cooldowns"""
    limiter = RateLimiter()
    
    # Add some cooldowns
    await limiter.can_execute("test_command", "user1", cooldown=5)
    
    # Manually set old time
    old_time = datetime.now(timezone.utc) - timedelta(minutes=6)
    limiter.command_cooldowns["test_command"]["user1"] = old_time
    limiter.global_cooldowns["test_command"] = old_time
    
    # Trigger cleanup by making a new request
    await limiter.can_execute("other_command", "user2", cooldown=5)
    
    # Verify old cooldowns were cleaned up
    assert "test_command" not in limiter.command_cooldowns, "Old user cooldown not cleaned"
    assert "test_command" not in limiter.global_cooldowns, "Old global cooldown not cleaned"

@pytest.mark.asyncio
async def test_case_insensitivity():
    """Test case-insensitive command handling"""
    limiter = RateLimiter()
    
    # Set cooldown with uppercase command
    await limiter.can_execute("TEST_COMMAND", "user1")
    
    # Check with lowercase command
    can_execute, wait_time = await limiter.can_execute("test_command", "user1")
    assert can_execute is False
    assert wait_time > 0

@pytest.mark.asyncio
async def test_reset_cooldown():
    """Test cooldown reset functionality."""
    limiter = RateLimiter()
    command_name = "test_command"
    user_id = "user1"
    
    # First execution should succeed
    can_execute1, wait1 = await limiter.can_execute(command_name, user_id, cooldown=5, global_cooldown=0)
    assert can_execute1 is True, "First execution should succeed"
    assert wait1 is None, "First execution should have no wait time"
    
    # Verify cooldown is set
    assert command_name in limiter.command_cooldowns, "Command cooldown not set"
    assert user_id in limiter.command_cooldowns[command_name], "User cooldown not set"
    
    # Second execution should fail (on cooldown)
    can_execute2, wait2 = await limiter.can_execute(command_name, user_id, cooldown=5, global_cooldown=0)
    assert can_execute2 is False, "Should be on cooldown"
    assert wait2 > 0, "Should have wait time"
    
    # Reset the cooldown
    await limiter.reset_cooldown(command_name, user_id)
    
    # Verify cooldown is cleared
    assert command_name not in limiter.command_cooldowns or user_id not in limiter.command_cooldowns.get(command_name, {}), "Cooldown not properly reset"
    
    # Should be able to execute again after reset
    can_execute3, wait3 = await limiter.can_execute(command_name, user_id, cooldown=5, global_cooldown=0)
    assert can_execute3 is True, "Should work after cooldown reset"
    assert wait3 is None, "Should have no wait time after reset"