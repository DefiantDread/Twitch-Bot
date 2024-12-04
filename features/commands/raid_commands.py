"""Module responsible for raid commands."""
# features/commands/raid_commands.py
import logging
import asyncio
from datetime import timezone, datetime, timedelta
from twitchio.ext import commands
from core.raid_manager import RaidState
from utils.decorators import rate_limited

logger = logging.getLogger(__name__)

class RaidCommands(commands.Cog):
    """Class hosting all raid related commands."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='raid')
    @rate_limited(cooldown=5)
    async def raid_command(self, ctx, amount: str = None):
        """Join the current raid with an investment"""
        try:
            if not amount or not amount.isdigit():
                await ctx.send(f"@{ctx.author.name} Usage: !raid <amount> (100-1000 points)")
                return

            amount = int(amount)
            if amount < 100 or amount > 1000:
                await ctx.send(f"@{ctx.author.name} Investment must be between 100 and 1000 points!")
                return

            current_points = await self.bot.points_manager.get_points(str(ctx.author.id))
            if amount > current_points:
                await ctx.send(f"@{ctx.author.name} Not enough points! (You have: {current_points})")
                return

            success, message = await self.bot.raid_manager.join_raid(
                str(ctx.author.id),
                ctx.author.name,
                amount
            )

            if success:
                # Points are handled by the raid manager on success
                await ctx.send(f"@{ctx.author.name} {message}")
            else:
                await ctx.send(f"@{ctx.author.name} {message}")

        except Exception as e:
            logger.error(f"Error processing raid command: {e}")
            await ctx.send(f"@{ctx.author.name} Error joining raid!")

    @commands.command(name='invest')
    @rate_limited(cooldown=5)
    async def invest_command(self, ctx, amount: str = None):
        """Increase investment during raid milestone"""
        try:
            if not amount or not amount.isdigit():
                await ctx.send(f"@{ctx.author.name} Usage: !invest <amount>")
                return

            amount = int(amount)
            current_points = await self.bot.points_manager.get_points(str(ctx.author.id))
            if amount > current_points:
                await ctx.send(f"@{ctx.author.name} Not enough points! (You have: {current_points})")
                return

            success, message = await self.bot.raid_manager.increase_investment(
                str(ctx.author.id),
                amount
            )

            await ctx.send(f"@{ctx.author.name} {message}")

        except Exception as e:
            logger.error(f"Error processing invest command: {e}")
            await ctx.send(f"@{ctx.author.name} Error increasing investment!")

    @commands.command(name='crew')
    @rate_limited(cooldown=10)
    async def raid_status(self, ctx):
        """Check current raid status"""
        try:
            status = await self.bot.raid_manager.get_raid_status()
            
            # Check if no raid is active
            if status['state'] == RaidState.INACTIVE:
                await ctx.send("No raid is currently active!")
                return

            message = (
                f"Current Raid: {status['ship_type']} | "
                f"Crew: {status['current_crew']}/{status['required_crew']} | "
                f"Multiplier: {status['multiplier']}x"
            )
            
            if status['time_remaining'] > 0:
                message += f" | Time remaining: {status['time_remaining']}s"

            await ctx.send(message)

        except Exception as e:
            logger.error(f"Error in crew command: {e}", exc_info=True)
            await ctx.send("No raid is currently active!")  # Friendlier error message

    # Moderator commands
    @commands.command(name='forcereset')
    async def force_reset_command(self, ctx):
        """Force reset raid state (Mod only)"""
        if not ctx.author.is_mod:
            return

        try:
            logger.info("Force reset command initiated")
            
            # Try force reset with timeout
            try:
                await asyncio.wait_for(
                    self.bot.raid_manager._reset_raid_data(),
                    timeout=5.0
                )
                
                # Force immediate state reset if needed
                if self.bot.raid_manager.is_active:
                    await self.bot.raid_manager._force_reset()
                
                # Reset scheduler cooldown
                self.bot.raid_scheduler.last_raid_end = datetime.now(timezone.utc) - timedelta(hours=1)
                
                await ctx.send("Raid state has been forcefully reset.")
                logger.info("Force reset completed successfully")
                
            except asyncio.TimeoutError:
                logger.error("Force reset timed out")
                # Try one last force reset
                await self.bot.raid_manager._force_reset()
                await ctx.send("Reset timed out, but state has been force cleared.")
                
        except Exception as e:
            logger.error(f"Error in force reset: {e}")
            # Last resort reset
            try:
                await self.bot.raid_manager._force_reset()
                await ctx.send("Error occurred, but state has been force cleared.")
            except Exception:
                await ctx.send("Critical error resetting raid state!")

    @commands.command(name='forceraid')
    async def force_raid_command(self, ctx, viewers: str = "10"):
        """Force start a raid (Mod only)"""
        if not ctx.author.is_mod:
            return

        try:
            # Debug current state
            logger.debug(f"Force raid - Current state before start: {self.bot.raid_manager.state}")
            
            # Make sure system is cleaned up first
            await self.bot.raid_manager._reset_raid_data()
            
            # Convert viewer count parameter
            try:
                viewer_count = int(viewers)
                if viewer_count < 2:
                    viewer_count = 2
            except ValueError:
                viewer_count = 10
            
            # Create mock function for viewer count
            async def mock_viewer_count():
                return viewer_count
            
            # Store original and replace with mock
            original_get_viewers = self.bot.get_viewer_count
            self.bot.get_viewer_count = mock_viewer_count
            
            try:
                # Force reset scheduler cooldown
                self.bot.raid_scheduler.last_raid_end = datetime.now(timezone.utc) - timedelta(hours=1)
                
                # Start new raid
                success = await self.bot.raid_manager.start_raid()
                if success:
                    await ctx.send(f"Raid started successfully! (Test mode: {viewer_count} viewers)")
                else:
                    logger.debug(f"Force raid - State after failed start: {self.bot.raid_manager.state}")
                    await ctx.send("Couldn't start raid. One might already be active.")
            finally:
                self.bot.get_viewer_count = original_get_viewers
                
        except Exception as e:
            logger.error(f"Error forcing raid: {e}")
            await ctx.send("Error starting raid!")

    @commands.command(name='raidstate')
    async def raid_state_command(self, ctx):
        """Check current raid state (Mod only)"""
        if not ctx.author.is_mod:
            return
            
        try:
            state = self.bot.raid_manager.state
            is_active = self.bot.raid_manager.is_active
            participants = len(self.bot.raid_manager.participants)
            ship_type = self.bot.raid_manager.raid_ship_type
            
            status_msg = [
                f"Current raid state: {state}",
                f"Raid active: {is_active}",
                f"Participants: {participants}"
            ]
            
            if ship_type:
                status_msg.append(f"Ship Type: {ship_type}")
                
            await ctx.send(" | ".join(status_msg))
            
        except Exception as e:
            logger.error(f"Error getting raid state: {e}")
            await ctx.send("Error retrieving raid state!")

    @commands.command(name='raidstats')
    @rate_limited(cooldown=30)
    async def raid_stats_command(self, ctx):
        """View your raid statistics"""
        try:
            stats = await self.bot.raid_manager.get_player_stats(str(ctx.author.id))
            
            message = (
                f"@{ctx.author.name} Raid Stats | "
                f"Raids: {stats['total_raids']} | "
                f"Successful: {stats['successful_raids']} | "
                f"Total Plunder: {stats['total_plunder']} | "
                f"Biggest Haul: {stats['biggest_reward']}"
            )
            
            await ctx.send(message)

        except Exception as e:
            logger.error(f"Error processing raid stats command: {e}")
            await ctx.send(f"@{ctx.author.name} Error getting raid stats!")