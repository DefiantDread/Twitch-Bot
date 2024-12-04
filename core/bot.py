# core/bot.py
from asyncio.log import logger
import logging
import asyncio
from sqlalchemy import text
from twitchio.ext import commands
from datetime import datetime, timezone
from config.config import Config
from core.raid_manager import RaidManager
from core.raid_messages import RaidMessageHandler
from core.raid_recovery import RaidRecoveryManager
from core.raid_scheduler import RaidScheduler
from core.rewards import RewardManager
from database.manager import DatabaseManager
from features.analytics.tracker import AnalyticsTracker
from features.commands.analytics import AnalyticsCommands
from features.commands.mod_commands import ModCommands
from features.commands.raid_commands import RaidCommands
from features.moderation.timeout_manager import TimeoutManager
from features.points.points_manager import PointsManager
from features.points.commands import PointsCommands
from features.rewards.handlers import RewardHandlers
from features.rewards.moderation import ModerationRewardHandler
from features.rewards.stream_interaction import StreamInteractionHandler
from utils.decorators import error_boundary
from utils.rate_limiter import RateLimiter
from utils.health_checker import HealthChecker
from utils.monitoring import PerformanceMonitor, TimingContext
from utils.alert_system import AlertManager
from features.tracking.user_tracker import UserTracker
from features.moderation.moderator import ModerationManager
from features.commands.base import BaseCommands

class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=Config.BOT_TOKEN,
            prefix=Config.BOT_PREFIX,
            initial_channels=[Config.CHANNEL_NAME]
        )
        
        # Store channel name for easy access
        self.channel_name = Config.CHANNEL_NAME
        
        # Initialize raid system components
        self.raid_messages = RaidMessageHandler(self)
        self.raid_manager = RaidManager(self)
        self.raid_recovery = RaidRecoveryManager(self)
        self.raid_scheduler = RaidScheduler(self)

        # Add to existing background_tasks setup
        self._raid_check_task = None  # For periodic raid spawning

        # Store prefix for easy access
        self.command_prefix = Config.BOT_PREFIX

        # Initialize monitoring and analytics components
        self.monitor = PerformanceMonitor(self)
        self.timeout_manager = TimeoutManager()
        self.analytics = AnalyticsTracker(self)
        self.health_checker = HealthChecker(self)

        # Initialize user and raid tracking
        self.user_tracker = UserTracker(self)
        self.moderation = ModerationManager(self)
        self.points_manager = PointsManager(self)

        # Initialize rewards and moderation
        self.rewards = RewardManager(self)
        self.reward_handler = RewardHandlers(self)
        self.moderation_rewards = ModerationRewardHandler(self)
        self.stream_interaction = StreamInteractionHandler(self)

        # Initialize rate limiter and alert manager
        self.rate_limiter = RateLimiter()
        self.alert_manager = AlertManager(self)

        # Initialize database manager
        self.db = DatabaseManager()

        # Set up logging
        self.logger = logging.getLogger('bot')

        # Track bot state information
        self.start_time = datetime.now(timezone.utc)
        self.stream_start_time = None
        self.messages_count = 0
        self.background_tasks = set()

        # Initialize cogs
        self._register_cogs()
        self._register_reward_handlers()
        self.setup_alert_handlers()

        # Start background monitoring
        self._start_background_tasks()

    @property
    def prefix(self):
        """Return the command prefix"""
        return self.command_prefix
    
    def _register_cogs(self):
        """Register all cogs"""
        try:
            if 'BaseCommands' not in self.cogs:
                self.add_cog(BaseCommands(self))
            if 'AnalyticsCommands' not in self.cogs:
                self.add_cog(AnalyticsCommands(self))
            if 'PointsCommands' not in self.cogs:
                self.add_cog(PointsCommands(self))
            if 'RaidCommands' not in self.cogs:
                self.add_cog(RaidCommands(self))
            if 'ModCommands' not in self.cogs:
                self.add_cog(ModCommands(self))
                
        except Exception as e:
            self.logger.error(f"Error registering cogs: {e}")

    async def event_message(self, message):
        if message.echo:
            return

        try:
            # Process commands if message starts with prefix
            if message.content.startswith(self.prefix):
                await self.handle_commands(message)
            
            # Track user activity
            await self.user_tracker.track_user_message(message)
            
            # Update analytics
            self.messages_count += 1
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def handle_commands(self, message):
        """Process commands"""
        try:
            ctx = await self.get_context(message)
            await self.invoke(ctx)
        except Exception as e:
            logger.error(f"Error handling command: {e}")

    async def event_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot is ready! Username: {self.nick}")
        
        # Load moderation settings
        await self.moderation.load_banned_phrases()
        await self.points_manager.setup()
        
        # Add commands
        if not self.cogs:
            self.add_cog(BaseCommands(self))
            self.add_cog(AnalyticsCommands(self))
            self.add_cog(PointsCommands(self))
            self.add_cog(RaidCommands(self))
            self.add_cog(ModCommands(self))

    async def get_viewer_count(self) -> int:
        try:
            channel = await self.fetch_channel(Config.CHANNEL_NAME)
            if hasattr(channel, 'viewer_count'):
                return channel.viewer_count
            else:
                logger.error("Viewer count attribute not available.")
                return 0
        except Exception as e:
            logger.error(f"Error getting viewer count: {e}")
            return 0    

    def _register_reward_handlers(self):
        """Register all reward handlers with their respective IDs"""
        handlers = {
            **self.stream_interaction.handlers,
            **self.moderation_rewards.handlers
        }
        
        for reward_id, handler in handlers.items():
            self.rewards.register_reward(reward_id, handler)

    def _start_background_tasks(self):
        """Initialize background tasks"""
        tasks = [
            self._update_watch_time(),
            self._cleanup_inactive_users(),
            self._update_analytics()
        ]
        
        for task in tasks:
            task_obj = asyncio.create_task(task)
            self.background_tasks.add(task_obj)
            task_obj.add_done_callback(self.background_tasks.discard)

    async def _update_watch_time(self):
        """Background task to update user watch time"""
        while True:
            try:
                await self.user_tracker.update_watch_time()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                # This is expected if the task is canceled, e.g., during shutdown
                logger.info("Watch time update task was cancelled.")
                raise
            except (RuntimeError, ValueError) as e:
                # Handle specific, known errors that might occur
                logger.error("Known error in watch time update task: %s", e, exc_info=True)
                # Optionally, you might want to implement a retry mechanism here
            except Exception as e:
                # Catch any unexpected exceptions, log them
                logger.error("Unexpected error in watch time update task: %s", e, exc_info=True)
                # Wait before retrying to avoid a fast crash-restart loop
                await asyncio.sleep(5)

    async def _cleanup_inactive_users(self):
        """Background task to cleanup inactive users"""
        try:
            while True:
                await self.user_tracker.cleanup_inactive_users()
                await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error("Error in user cleanup task: %s", e)

    async def _update_analytics(self):
        """Background task to update analytics"""
        try:
            while True:
                stats = await self.user_tracker.get_session_stats()
                await self.analytics.update_session_stats(stats)
                await asyncio.sleep(300)  # Update every 5 minutes
        except Exception as e:
            logger.error("Error in analytics update task: %s", e)

    async def event_stream_start(self):
        """Called when the stream starts."""
        self.stream_start_time = datetime.now(timezone.utc)
        task = asyncio.create_task(self._periodic_stats_update())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def event_stream_end(self):
        """Called when the stream ends."""
        if self.stream_start_time:
            duration = int((datetime.now(timezone.utc) - self.stream_start_time).total_seconds() / 60)
            try:
                # Update final stream stats
                async with self.db.session_scope() as session:
                    # Use text() for the query to ensure async compatibility
                    result = await session.execute(
                        text("""
                            SELECT * FROM stream_stats 
                            ORDER BY id DESC LIMIT 1
                        """)
                    )
                    stats = result.first()
                    
                    if stats:
                        await session.execute(
                            text("""
                                UPDATE stream_stats 
                                SET stream_duration = :duration, 
                                    messages_sent = :messages_count
                                WHERE id = :id
                            """),
                            {
                                'duration': duration,
                                'messages_count': self.messages_count,
                                'id': stats[0]  # Assuming id is the first column
                            }
                        )
                        await session.commit()
                        
            except Exception as e:
                self.logger.error(f"Failed to update final stream stats: {e}")

    async def _periodic_stats_update(self):
        """Background task to periodically update stream stats"""
        try:
            while True:
                await self.db.stream_stats_manager.flush()
                await asyncio.sleep(30)  # Update every 30 seconds
        except asyncio.CancelledError:
            # Make sure we save stats one last time if the task is cancelled
            await self.db.stream_stats_manager.flush()

    def setup_alert_handlers(self):
        """Setup default alert handlers"""
        # Add Discord webhook handler if configured
        if hasattr(Config, 'DISCORD_WEBHOOK_URL'):
            self.alert_manager.add_alert_handler(self.discord_alert_handler)
        
        # Add Twitch chat handler for important alerts
        self.alert_manager.add_alert_handler(self.chat_alert_handler)

    async def discord_alert_handler(self, alert):
        """Send important alerts to Discord"""
        if alert['severity'].value in ['warning', 'critical']:
            # Implementation of Discord webhook...
            pass

    async def chat_alert_handler(self, alert):
        """Send critical alerts to Twitch chat"""
        if alert['severity'].value == 'critical':
            await self.get_channel(Config.CHANNEL_NAME).send(
                f"⚠️ Bot Health Alert: {alert['message']}"
            )

    async def send_chat_message(self, message: str):
        """Send a message to the channel"""
        try:
            channel = self.get_channel(self.channel_name)
            if channel:
                await channel.send(message)
            else:
                logger.error(f"Could not find channel: {self.channel_name}")
        except Exception as e:
            logger.error(f"Error sending chat message: {e}", exc_info=True)

    def handle_signal(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(self.close())

    async def close(self):
        """Cleanup when shutting down"""
        try:
            logger.info("Bot shutting down, cleaning up...")
            
            # Cancel background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if self.background_tasks:
                done, pending = await asyncio.wait(self.background_tasks, timeout=5)
                for task in pending:
                    logger.warning(f"Task {task} did not complete in time")

            # Ensure raid system is properly cleaned up
            if hasattr(self, 'raid_manager'):
                try:
                    await self.raid_manager._reset_raid_data()
                except Exception as e:
                    logger.error(f"Error cleaning up raid manager: {e}")
            
            # Final analytics update
            try:
                stats = await self.user_tracker.get_session_stats()
                await self.analytics.update_session_stats(stats)
            except Exception as e:
                logger.error(f"Error updating final stats: {e}")
            
            # Close database connections
            try:
                await self.db.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            await super().close()
            