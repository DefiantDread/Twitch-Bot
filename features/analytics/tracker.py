# features/analytics/tracker.py
import logging
import asyncio
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ViewerMetrics:
    timestamp: datetime
    viewer_count: int
    chatters: set
    messages: int = 0

class AnalyticsTracker:
    def __init__(self, bot, max_command_history=720, max_reward_history=720, cleanup_interval=60):
        self.bot = bot
        self.max_command_history = max_command_history
        self.max_reward_history = max_reward_history
        self.viewer_snapshots: deque = deque(maxlen=max_command_history)
        self.command_history = deque(maxlen=max_command_history)
        self.command_usage = Counter()
        self.reward_history = deque(maxlen=max_reward_history)
        self.reward_usage = Counter()
        self.hourly_stats = {}
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self.active_chatters: Dict[str, int] = {}
        self.hourly_peaks: Dict[str, int] = {}
        self.last_snapshot = None

    async def log_command(self, command: str):
        """Log a command to analytics."""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            hour_key = current_time.strftime('%Y-%m-%d-%H')
            if hour_key not in self.hourly_stats:
                self.hourly_stats[hour_key] = Counter()
            self.hourly_stats[hour_key][f"commands_{command}"] += 1
            self.command_history.append((current_time, command))
            self.command_usage[command] += 1

    async def log_reward(self, reward: str):
        """Log a reward redemption to analytics."""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            hour_key = current_time.strftime('%Y-%m-%d-%H')
            if hour_key not in self.hourly_stats:
                self.hourly_stats[hour_key] = Counter()
            self.hourly_stats[hour_key][f"rewards_{reward}"] += 1
            self.reward_history.append((current_time, reward))
            self.reward_usage[reward] += 1

    async def get_stream_summary(self) -> Dict:
        """Get current stream summary"""
        if not self.bot.stream_start_time:
            return None

        current_time = datetime.now(timezone.utc)
        duration = current_time - self.bot.stream_start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m"

        # Get current stats
        stats = await self.bot.user_tracker.get_session_stats()
        
        return {
            'duration': duration_str,
            'peak_viewers': max(v.viewer_count for v in self.viewer_snapshots) if self.viewer_snapshots else 0,
            'total_messages': stats['total_messages'],
            'unique_chatters': stats['active_users'],
            'top_commands': self.command_usage.most_common(5),
            'top_rewards': self.reward_usage.most_common(5)
        }

    async def get_stats(self, hours: Optional[int] = None) -> Dict:
        """Get analytics statistics, optionally filtering by time window."""
        async with self._lock:
            if hours:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                filtered_commands = [
                    command for timestamp, command in self.command_history if timestamp > cutoff
                ]
                filtered_rewards = [
                    reward for timestamp, reward in self.reward_history if timestamp > cutoff
                ]
                commands_usage = Counter(filtered_commands)
                rewards_usage = Counter(filtered_rewards)
            else:
                commands_usage = self.command_usage
                rewards_usage = self.reward_usage

            return {
                "commands": {
                    "total": sum(commands_usage.values()),
                    "unique": len(commands_usage),
                    "most_used": commands_usage.most_common(),
                },
                "rewards": {
                    "total": sum(rewards_usage.values()),
                    "unique": len(rewards_usage),
                    "most_used": rewards_usage.most_common(),
                }
            }

    async def update_session_stats(self, stats: Dict):
        """Update current session statistics"""
        async with self._lock:
            hour_key = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')
            if hour_key not in self.hourly_stats:
                self.hourly_stats[hour_key] = Counter()
            
            self.hourly_stats[hour_key].update({
                'messages': stats.get('total_messages', 0),
                'chatters': stats.get('active_users', 0),
                'first_time': stats.get('first_time_chatters', 0),
                'returning': stats.get('returning_users', 0)
            })

    async def take_viewer_snapshot(self, viewer_count: int):
        """Take a snapshot of current viewer count and active users"""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            
            # Create new snapshot
            snapshot = ViewerMetrics(
                timestamp=current_time,
                viewer_count=viewer_count,
                chatters=set(self.active_chatters.keys())
            )
            
            self.viewer_snapshots.append(snapshot)
            
            # Update hourly peaks
            hour_key = current_time.strftime('%Y-%m-%d-%H')
            current_peak = self.hourly_peaks.get(hour_key, 0)
            if viewer_count > current_peak:
                self.hourly_peaks[hour_key] = viewer_count
                
            self.last_snapshot = snapshot
            await self._cleanup_old_data()

    async def track_message(self, user_id: str, username: str):
        """Track chat message for user activity"""
        async with self._lock:
            self.active_chatters[user_id] = self.active_chatters.get(user_id, 0) + 1
            
            if self.last_snapshot:
                self.last_snapshot.messages += 1

    async def calculate_hourly_stats(self) -> Dict[str, Counter]:
        """Calculate hourly statistics based on viewer snapshots."""
        async with self._lock:
            hourly_stats = {}
            for snapshot in self.viewer_snapshots:
                hour_key = snapshot.timestamp.strftime('%Y-%m-%d-%H')
                if hour_key not in hourly_stats:
                    hourly_stats[hour_key] = Counter()
                hourly_stats[hour_key]['viewers'] += snapshot.viewer_count
                hourly_stats[hour_key]['messages'] += snapshot.messages
            return hourly_stats


    async def get_peak_hours(self, limit: int = 10) -> List[Dict]:
        """Get the most active hours based on hourly stats."""
        async with self._lock:
            # Sort hourly stats by total activity (commands + rewards)
            sorted_hours = sorted(
                self.hourly_stats.items(),
                key=lambda x: sum(x[1].values()),  # Sum of all counters
                reverse=True
            )

            return [
                {
                    "hour": datetime.strptime(hour, '%Y-%m-%d-%H').hour,
                    "total_activity": sum(counter.values())
                }
                for hour, counter in sorted_hours[:limit]
            ]


    async def get_most_active_chatters(self, limit: int = 10) -> List[Dict]:
        """Get most active chatters based on message count"""
        async with self._lock:
            # Sort users by message count
            top_chatters = sorted(
                self.active_chatters.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Get usernames for the top chatters
            result = []
            for user_id, message_count in top_chatters:
                try:
                    username = await self.bot.db.get_username(user_id)
                    result.append({
                        'user_id': user_id,
                        'username': username,
                        'messages': message_count
                    })
                except Exception as e:
                    logger.error(f"Error getting username for {user_id}: {e}")

            return result

    async def get_activity_analysis(self) -> Dict:
        """Get comprehensive activity analysis"""
        async with self._lock:
            current_time = datetime.now(timezone.utc)
            
            # Analyze recent snapshots
            recent_snapshots = [
                s for s in self.viewer_snapshots
                if (current_time - s.timestamp).total_seconds() <= 3600  # Last hour
            ]
            
            if not recent_snapshots:
                return {
                    'status': 'No recent data available',
                    'viewer_trend': 'stable',
                    'chat_activity': 'low'
                }

            # Calculate viewer trend
            viewer_counts = [s.viewer_count for s in recent_snapshots]
            current_avg = sum(viewer_counts[-10:]) / 10 if len(viewer_counts) >= 10 else 0
            previous_avg = sum(viewer_counts[-20:-10]) / 10 if len(viewer_counts) >= 20 else 0
            
            trend = 'stable'
            if current_avg > previous_avg * 1.1:  # 10% increase
                trend = 'increasing'
            elif current_avg < previous_avg * 0.9:  # 10% decrease
                trend = 'decreasing'

            # Calculate chat activity level
            messages_per_minute = sum(s.messages for s in recent_snapshots) / len(recent_snapshots)
            activity_level = 'low'
            if messages_per_minute > 30:
                activity_level = 'high'
            elif messages_per_minute > 10:
                activity_level = 'medium'

            return {
                'viewer_count': {
                    'current': viewer_counts[-1],
                    'average': round(sum(viewer_counts) / len(viewer_counts), 1),
                    'peak': max(viewer_counts),
                    'trend': trend
                },
                'chat_activity': {
                    'level': activity_level,
                    'messages_per_minute': round(messages_per_minute, 1),
                    'active_chatters': len(self.active_chatters)
                },
                'timestamp': current_time.isoformat()
            }

    async def _cleanup_if_needed(self):
        """Clean up old command history if necessary."""
        async with self._lock:
            # Define a cutoff for old data (e.g., 24 hours)
            current_time = datetime.now(timezone.utc)
            cutoff = current_time - timedelta(hours=24)

            # Filter out old commands
            self.command_history = deque(
                (timestamp, command) for timestamp, command in self.command_history if timestamp > cutoff
            )

    async def _cleanup_old_data(self):
        """Clean up old analytics data."""
        current_time = datetime.now(timezone.utc)  # Use timezone-aware current time
        cutoff = current_time - timedelta(days=7)  # Clean data older than 7 days

        # Clean up hourly stats
        self.hourly_stats = {
            key: value
            for key, value in self.hourly_stats.items()
            if datetime.strptime(key, '%Y-%m-%d-%H').replace(tzinfo=timezone.utc) > cutoff
        }

