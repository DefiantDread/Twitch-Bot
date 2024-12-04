# features/commands/mod_commands.py
import logging
from typing import Optional
from twitchio.ext import commands
from utils.decorators import error_boundary

logger = logging.getLogger(__name__)

class ModCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='timeout', aliases=['to'])
    async def timeout_user(self, ctx, username: Optional[str] = None, duration: int = 300, *, reason: str = "No reason provided"):
        """Timeout a user from chat"""
        if not ctx.author.is_mod:
            return
            
        if not username:
            await ctx.send("Usage: !timeout <username> [duration] [reason]")
            return
            
        try:
            await ctx.channel.timeout(username, duration, reason)
            await ctx.send(f"User {username} has been timed out for {duration} seconds. Reason: {reason}")
        except Exception as e:
            logger.error(f"Failed to timeout user: {e}")
            await ctx.send(f"Failed to timeout user {username}")

    @commands.command(name='ban')
    async def ban_user(self, ctx, username: Optional[str] = None, *, reason: str = "No reason provided"):
        """Ban a user from chat"""
        if not ctx.author.is_mod:
            return
            
        if not username:
            await ctx.send("Usage: !ban <username> [reason]")
            return
            
        try:
            await ctx.channel.ban(username, reason)
            await ctx.send(f"User {username} has been banned. Reason: {reason}")
        except Exception as e:
            logger.error(f"Failed to ban user: {e}")
            await ctx.send(f"Failed to ban user {username}")

    @commands.command(name='unban')
    async def unban_user(self, ctx, username: Optional[str] = None):
        """Unban a user from chat"""
        if not ctx.author.is_mod:
            return
            
        if not username:
            await ctx.send("Usage: !unban <username>")
            return
            
        try:
            await ctx.channel.unban(username)
            await ctx.send(f"User {username} has been unbanned")
        except Exception as e:
            logger.error(f"Failed to unban user: {e}")
            await ctx.send(f"Failed to unban user {username}")

    @commands.command(name='clear')
    async def clear_chat(self, ctx):
        """Clear all messages from chat"""
        if not ctx.author.is_mod:
            return
            
        try:
            await ctx.channel.clear()
            await ctx.send("Chat has been cleared")
        except Exception as e:
            logger.error(f"Failed to clear chat: {e}")
            await ctx.send("Failed to clear chat")

    @commands.command(name='followers', aliases=['followersonly'])
    async def followers_only(self, ctx, duration: Optional[int] = None):
        """Enable/disable followers-only mode"""
        if not ctx.author.is_mod:
            return
            
        try:
            if duration is None:
                await ctx.channel.followers_only(False)
                await ctx.send("Followers-only mode disabled")
            else:
                await ctx.channel.followers_only(duration=duration)
                await ctx.send(f"Followers-only mode enabled ({duration} seconds)")
        except Exception as e:
            logger.error(f"Failed to change followers-only mode: {e}")
            await ctx.send("Failed to change followers-only mode")

    @commands.command(name='slow', aliases=['slowmode'])
    async def slow_mode(self, ctx, duration: Optional[int] = None):
        """Enable/disable slow mode"""
        if not ctx.author.is_mod:
            return
            
        try:
            if duration is None:
                await ctx.channel.slow(False)
                await ctx.send("Slow mode disabled")
            else:
                await ctx.channel.slow(duration)
                await ctx.send(f"Slow mode enabled ({duration} seconds)")
        except Exception as e:
            logger.error(f"Failed to change slow mode: {e}")
            await ctx.send("Failed to change slow mode")

    @commands.command(name='subscribers', aliases=['subscribersonly', 'subonly'])
    async def subscribers_only(self, ctx):
        """Toggle subscribers-only mode"""
        if not ctx.author.is_mod:
            return
            
        try:
            # Toggle the mode
            current_mode = getattr(ctx.channel, '_subscribers', False)
            if current_mode:
                await ctx.channel.subscribers_only(False)
                await ctx.send("Subscribers-only mode disabled")
            else:
                await ctx.channel.subscribers_only(True)
                await ctx.send("Subscribers-only mode enabled")
        except Exception as e:
            logger.error(f"Failed to toggle subscribers-only mode: {e}")
            await ctx.send("Failed to change subscribers-only mode")

    @commands.command(name='emoteonly')
    async def emote_only(self, ctx):
        """Toggle emote-only mode"""
        if not ctx.author.is_mod:
            return
            
        try:
            current_mode = getattr(ctx.channel, '_emote_only', False)
            if current_mode:
                await ctx.channel.emote_only(False)
                await ctx.send("Emote-only mode disabled")
            else:
                await ctx.channel.emote_only(True)
                await ctx.send("Emote-only mode enabled")
        except Exception as e:
            logger.error(f"Failed to toggle emote-only mode: {e}")
            await ctx.send("Failed to change emote-only mode")