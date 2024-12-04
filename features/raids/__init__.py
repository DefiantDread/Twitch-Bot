# features/raids/__init__.py

import logging
import asyncio
from typing import Optional
from .raid_manager import RaidManager, RaidState
from .message_handler import RaidMessageHandler
from .commands import RaidCommands
from .database import RaidDatabaseManager
from .scheduler import RaidScheduler

logger = logging.getLogger(__name__)

class RaidSystem:
    def __init__(self, bot):
        self.bot = bot
        self.db = None  # RaidDatabaseManager instance
        self.manager = None  # RaidManager instance
        self.messages = None  # RaidMessageHandler instance
        self.scheduler = None  # RaidScheduler instance
        
    async def initialize(self):
        """Initialize the raid system and all its components"""
        try:
            logger.info("Initializing raid system...")
            
            # Initialize components in order of dependency
            self.db = RaidDatabaseManager(self.bot.db)
            await self.db.initialize_tables()
            
            self.messages = RaidMessageHandler()
            self.manager = RaidManager(self.bot)
            self.scheduler = RaidScheduler(
                bot=self.bot,
                raid_manager=self.manager,
                message_handler=self.messages
            )

            # Register commands
            if 'RaidCommands' not in self.bot.cogs:
                self.bot.add_cog(RaidCommands(self.bot))
            
            # Setup event handlers
            self.bot.event_handler.add_handler(
                'channel_points_used',
                self._handle_points_redemption
            )
            
            # Start scheduler
            await self.scheduler.start()
            
            logger.info("Raid system initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing raid system: {e}")
            return False

    async def cleanup(self):
        """Cleanup raid system on shutdown"""
        try:
            logger.info("Cleaning up raid system...")
            
            if self.scheduler:
                await self.scheduler.stop()
            
            # Handle any active raids
            if self.manager and self.manager.state != RaidState.INACTIVE:
                await self.manager._cleanup_active_raid()
            
            logger.info("Raid system cleanup completed")

        except Exception as e:
            logger.error(f"Error during raid system cleanup: {e}")

    async def _handle_points_redemption(self, user_id: str, reward_id: str):
        """Handle channel point redemptions related to raids"""
        # Future implementation for channel point integration
        pass

    @property
    def active_raid(self) -> Optional[dict]:
        """Get current raid status if active"""
        if self.manager:
            return self.manager.get_raid_status()
        return None

def setup(bot):
    """Setup function for loading the raid system"""
    raid_system = RaidSystem(bot)
    
    # Store reference to raid system in bot
    bot.raid_system = raid_system
    
    # Schedule initialization
    asyncio.create_task(raid_system.initialize())
    
    return raid_system