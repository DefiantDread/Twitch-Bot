# tests/test_stream_analytics.py
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from features.analytics.tracker import AnalyticsTracker
from collections import Counter
from datetime import datetime, timedelta, timezone

@pytest.fixture
async def tracker():
    """Create a test analytics tracker"""
    bot = MagicMock()
    return AnalyticsTracker(
        bot,
        max_command_history=10,
        max_reward_history=10,
        cleanup_interval=1
    )

@pytest.mark.asyncio
async def test_command_logging(tracker):
    """Test basic command logging functionality"""
    # Log some commands
    await tracker.log_command("test_command")
    await tracker.log_command("test_command")
    await tracker.log_command("other_command")
    
    # Get stats
    stats = await tracker.get_stats()
    
    assert stats['commands']['total'] == 3
    assert stats['commands']['unique'] == 2
    most_used = dict(stats['commands']['most_used'])
    assert most_used['test_command'] == 2

@pytest.mark.asyncio
async def test_reward_logging(tracker):
    """Test reward logging functionality"""
    # Log some rewards
    await tracker.log_reward("test_reward")
    await tracker.log_reward("test_reward")
    await tracker.log_reward("other_reward")
    
    # Get stats
    stats = await tracker.get_stats()
    
    assert stats['rewards']['total'] == 3
    assert stats['rewards']['unique'] == 2
    most_used = dict(stats['rewards']['most_used'])
    assert most_used['test_reward'] == 2

@pytest.mark.asyncio
async def test_hourly_stats_tracking(tracker):
    """Test hourly statistics tracking"""
    current_time = datetime.now(timezone.utc)
    hour_key = current_time.strftime('%Y-%m-%d-%H')
    
    # Log activities
    await tracker.log_command("test_command")
    await tracker.log_reward("test_reward")
    
    # Verify hourly stats
    assert tracker.hourly_stats[hour_key]['commands_test_command'] == 1
    assert tracker.hourly_stats[hour_key]['rewards_test_reward'] == 1

@pytest.mark.asyncio
async def test_stats_with_time_window(tracker):
    """Test getting stats within a specific time window."""
    # Log some historical commands
    old_time = datetime.now(timezone.utc) - timedelta(hours=3)
    tracker.command_history.append((old_time, "old_command"))
    tracker.command_usage["old_command"] += 1

    current_time = datetime.now(timezone.utc)
    await tracker.log_command("new_command")

    # Get stats for last hour
    stats = await tracker.get_stats(hours=1)

    assert stats["commands"]["total"] == 1  # Only the new command
    assert stats["commands"]["unique"] == 1
    assert len(stats["commands"]["most_used"]) == 1
    assert stats["commands"]["most_used"][0][0] == "new_command"

@pytest.mark.asyncio
async def test_cleanup_old_data(tracker):
    """Test cleanup of old analytics data"""
    old_time = datetime.now(timezone.utc) - timedelta(days=8)
    old_key = old_time.strftime('%Y-%m-%d-%H')
    tracker.hourly_stats[old_key] = Counter({"test": 1})

    current_time = datetime.now(timezone.utc)
    current_key = current_time.strftime('%Y-%m-%d-%H')
    tracker.hourly_stats[current_key] = Counter({"test": 1})

    # Trigger cleanup
    await tracker._cleanup_old_data()

    assert old_key not in tracker.hourly_stats
    assert current_key in tracker.hourly_stats

@pytest.mark.asyncio
async def test_concurrent_logging(tracker):
    """Test concurrent logging of analytics data"""
    # Simulate concurrent logging
    tasks = []
    for _ in range(10):
        tasks.append(tracker.log_command("concurrent_command"))
    
    await asyncio.gather(*tasks)
    
    stats = await tracker.get_stats()
    assert stats['commands']['total'] == 10

@pytest.mark.asyncio
async def test_analytics_error_handling(tracker):
    """Test error handling in analytics tracking"""
    # Force an error by setting invalid data
    tracker.command_history = None
    
    # Should handle error gracefully
    stats = await tracker.get_stats()
    assert isinstance(stats, dict)
    assert stats == {
        'commands': {'total': 0, 'unique': 0, 'most_used': []},
        'rewards': {'total': 0, 'unique': 0, 'most_used': []}
    }

@pytest.mark.asyncio
async def test_hourly_stats_cleanup(tracker):
    """Test cleanup of old hourly stats."""
    old_time = datetime.now(timezone.utc) - timedelta(days=8)
    old_key = old_time.strftime('%Y-%m-%d-%H')
    tracker.hourly_stats[old_key] = Counter({"test": 1})

    current_time = datetime.now(timezone.utc)
    current_key = current_time.strftime('%Y-%m-%d-%H')
    tracker.hourly_stats[current_key] = Counter({"test": 1})

    # Trigger cleanup
    await tracker._cleanup_old_data()

    assert old_key not in tracker.hourly_stats
    assert current_key in tracker.hourly_stats

@pytest.mark.asyncio
async def test_most_active_hours(tracker):
    """Test analysis of most active hours."""
    base_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for hour in range(24):
        time = base_time + timedelta(hours=hour)
        hour_key = time.strftime('%Y-%m-%d-%H')
        tracker.hourly_stats[hour_key] = Counter({
            "commands_test": hour + 1  # More activity in later hours
        })

    active_hours = await tracker.get_peak_hours()

    assert len(active_hours) > 0
    assert active_hours[0]["hour"] == 23  # Latest hour has highest activity
