"""Module providing base commands."""
# features/commands/base.py

from datetime import datetime, timezone
from twitchio.ext import commands
from utils.decorators import rate_limited

class BaseCommands(commands.Cog):
    """Class responsible for base commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='uptime')
    @rate_limited(cooldown=10)
    async def uptime(self, ctx):
        """Show stream uptime"""
        if not self.bot.stream_start_time:
            await ctx.send("Stream is not live!")
            return

        duration = datetime.now(timezone.utc) - self.bot.stream_start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f"Stream has been live for {hours}h {minutes}m {seconds}s")

    @commands.command(name='commands')
    @rate_limited(cooldown=5)
    async def show_commands(self, ctx):
        """Show available commands"""
        command_names = [command.name for command in self.bot.commands.values()]
        await ctx.send(f"Available commands: {', !'.join(sorted(command_names))}")


    @commands.command(name='ping')
    async def ping(self, ctx):
        """Simple ping command to check if bot is responsive"""
        await ctx.send("Pong! 🏓 Bot is running.")
