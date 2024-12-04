from twitchio.ext import commands
from utils.decorators import rate_limited
import logging

logger = logging.getLogger(__name__)

class RaidCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='raid')
    @rate_limited(cooldown=5)
    async def join_raid(self, ctx, amount: str = None):
        """Join the current raid with an investment"""
        try:
            if not amount or not amount.isdigit():
                await ctx.send(f"@{ctx.author.name} Usage: !raid <amount> (100-1000 points)")
                return

            amount = int(amount)
            current_points = await self.bot.points_manager.get_points(str(ctx.author.id))
            
            if amount > current_points:
                await ctx.send(f"@{ctx.author.name} You don't have enough points! (You have: {current_points})")
                return

            success, message = await self.bot.raid_manager.join_raid(
                str(ctx.author.id),
                ctx.author.name,
                amount
            )

            await ctx.send(f"@{ctx.author.name} {message}")

        except Exception as e:
            logger.error(f"Error in raid command: {e}")
            await ctx.send(f"@{ctx.author.name} Error joining raid!")

    @commands.command(name='invest')
    @rate_limited(cooldown=5)
    async def increase_investment(self, ctx, amount: str = None):
        """Increase your investment during milestone windows"""
        try:
            if not amount or not amount.isdigit():
                await ctx.send(f"@{ctx.author.name} Usage: !invest <amount>")
                return

            amount = int(amount)
            current_points = await self.bot.points_manager.get_points(str(ctx.author.id))
            
            if amount > current_points:
                await ctx.send(f"@{ctx.author.name} You don't have enough points! (You have: {current_points})")
                return

            success, message = await self.bot.raid_manager.increase_investment(
                str(ctx.author.id),
                amount
            )

            await ctx.send(f"@{ctx.author.name} {message}")

        except Exception as e:
            logger.error(f"Error in invest command: {e}")
            await ctx.send(f"@{ctx.author.name} Error increasing investment!")

    @commands.command(name='crew')
    @rate_limited(cooldown=10)
    async def raid_status(self, ctx):
        """Check current raid status"""
        try:
            status = await self.bot.raid_manager.get_raid_status()
            
            if status['state'] == 'INACTIVE':
                await ctx.send("No raid currently active!")
                return

            message = (
                f"Current Raid Status: {status['ship_type']} | "
                f"Crew: {status['participant_count']}/{status['required_crew']} | "
                f"Current Multiplier: {status['current_multiplier']}x"
            )

            if status['next_milestone']:
                message += f" | Next milestone: {status['next_milestone'].participant_count} crew"

            await ctx.send(message)

        except Exception as e:
            logger.error(f"Error in crew command: {e}")
            await ctx.send("Error getting raid status!")

    @commands.command(name='bounty')
    @rate_limited(cooldown=30)
    async def raid_stats(self, ctx):
        """View your raid statistics"""
        try:
            stats = await self.bot.raid_manager.get_player_stats(str(ctx.author.id))
            
            message = (
                f"@{ctx.author.name} Raid Stats | "
                f"Total Raids: {stats['total_raids']} | "
                f"Successful: {stats['successful_raids']} | "
                f"Total Plunder: {stats['total_plunder']} points"
            )

            await ctx.send(message)

        except Exception as e:
            logger.error(f"Error in bounty command: {e}")
            await ctx.send(f"@{ctx.author.name} Error getting raid stats!")