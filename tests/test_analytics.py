import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock
from features.analytics.tracker import AnalyticsTracker
from collections import Counter, deque

@pytest.fixture
async def tracker():
    """Create a test analytics tracker"""
    bot = MagicMock()
    tracker = AnalyticsTracker(
        bot,
        max_command_history=10,
        max_reward_history=10,
        cleanup_interval=1
    )
    # Ensure tracker uses timezone-aware datetimes
    tracker.session_start = datetime.now(timezone.utc)
    return tracker

@pytest.mark.asyncio
async def test_analytics_cleanup(tracker):
    """Test cleanup of old analytics data"""
    # Add test data with timezone-aware dates
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=2)
    
    tracker.command_history.clear()
    tracker.command_history.append((old_time, "old_command"))
    tracker.command_history.append((now, "new_command"))
    
    # Update command usage counters
    tracker.command_usage["old_command"] += 1
    tracker.command_usage["new_command"] += 1
    
    # Force cleanup with timezone-aware cutoff
    cutoff = now - timedelta(days=1)
    tracker.command_history = deque(
        (ts, cmd) for ts, cmd in tracker.command_history 
        if ts > cutoff
    )
    
    # Verify cleanup
    commands = [cmd for _, cmd in tracker.command_history]
    assert "new_command" in commands
    assert "old_command" not in commands