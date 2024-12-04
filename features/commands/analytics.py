# features/commands/analytics.py
from twitchio.ext import commands
from datetime import datetime, timedelta, timezone
from utils.decorators import rate_limited
import logging

logger = logging.getLogger(__name__)

class AnalyticsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='stats')
    @rate_limited(cooldown=30)
    async def show_stats(self, ctx):
        """Show current stream statistics"""
        try:
            if not self.bot.stream_start_time:
                await ctx.send("Stream is not live!")
                return

            # Calculate stream duration
            duration = datetime.now(timezone.utc) - self.bot.stream_start_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m"

            # Get stream stats
            session_stats = await self.bot.user_tracker.get_session_stats()
            
            await ctx.send(
                f"Stream Stats 📊 Duration: {duration_str} | "
                f"Messages: {session_stats['total_messages']} | "
                f"Unique chatters: {session_stats['active_users']} | "
                f"First-time chatters: {session_stats['first_time_chatters']}"
            )

        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await ctx.send("Error retrieving stream statistics!")

    @commands.command(name='topcommands')
    @rate_limited(cooldown=30)
    async def show_top_commands(self, ctx):
        """Show most used commands"""
        if not ctx.author.is_mod:
            return
            
        try:
            stats = await self.bot.analytics.get_stream_summary()
            if not stats or not stats['top_commands']:
                await ctx.send("No command statistics available!")
                return
                
            top_cmds = " | ".join(
                f"!{cmd}: {count}" 
                for cmd, count in stats['top_commands']
            )
            await ctx.send(f"Most Used Commands 📈 {top_cmds}")
        except Exception as e:
            logger.error(f"Error showing top commands: {e}")
            await ctx.send("Error retrieving command statistics!")

    @commands.command(name='toprewards')
    @rate_limited(cooldown=30)
    async def show_top_rewards(self, ctx):
        """Show most redeemed channel point rewards"""
        if not ctx.author.is_mod:
            return
            
        try:
            stats = await self.bot.analytics.get_stream_summary()
            if not stats or not stats['top_rewards']:
                await ctx.send("No reward statistics available!")
                return
                
            top_rewards = " | ".join(
                f"{reward}: {count}" 
                for reward, count in stats['top_rewards']
            )
            await ctx.send(f"Most Used Rewards 🎁 {top_rewards}")
        except Exception as e:
            logger.error(f"Error showing top rewards: {e}")
            await ctx.send("Error retrieving reward statistics!")

    @commands.command(name='weeklystats')
    @rate_limited(cooldown=60)
    async def show_weekly_stats(self, ctx):
        """Show statistics for the past 7 days"""
        if not ctx.author.is_mod:
            return
            
        try:
            stats = await self.bot.analytics.get_historical_stats(days=7)
            hours = round(stats['avg_duration'] / 3600, 1)
            
            await ctx.send(
                f"Weekly Stats 📅 Streams: {stats['streams']} | "
                f"Avg. viewers: {round(stats['avg_viewers'])} | "
                f"Avg. duration: {hours}h | "
                f"Total messages: {stats['total_messages']}"
            )
        except Exception as e:
            logger.error(f"Error showing weekly stats: {e}")
            await ctx.send("Error retrieving weekly statistics!")

    @commands.command(name='chatters')
    @rate_limited(cooldown=30)
    async def show_chatter_stats(self, ctx):
        """Show current stream chatter statistics"""
        if not ctx.author.is_mod:
            return
            
        try:
            stats = await self.bot.analytics.get_stream_summary()
            if not stats:
                await ctx.send("No stream statistics available!")
                return
                
            messages_per_chatter = round(
                stats['total_messages'] / stats['unique_chatters']
                if stats['unique_chatters'] > 0 else 0,
                1
            )
            
            await ctx.send(
                f"Chat Stats 💬 Unique chatters: {stats['unique_chatters']} | "
                f"Messages per chatter: {messages_per_chatter} | "
                f"Total messages: {stats['total_messages']}"
            )
        except Exception as e:
            logger.error(f"Error showing chatter stats: {e}")
            await ctx.send("Error retrieving chat statistics!")

    @commands.command(name='streamtime')
    @rate_limited(cooldown=15)
    async def show_stream_time(self, ctx):
        """Show current stream duration and stats"""
        try:
            stats = await self.bot.analytics.get_stream_summary()
            if not stats:
                await ctx.send("Stream is not live!")
                return
                
            await ctx.send(
                f"Stream Time ⏱️ {stats['duration']} | "
                f"Current viewers: {stats['peak_viewers']} | "
                f"Total messages: {stats['total_messages']}"
            )
        except Exception as e:
            logger.error(f"Error showing stream time: {e}")
            await ctx.send("Error retrieving stream time!")

    @commands.command(name='analyze')
    @rate_limited(cooldown=60)
    async def analyze_stats(self, ctx, timeframe: str = "day"):
        """Analyze stats for a specific timeframe (day/week/month)"""
        if not ctx.author.is_mod:
            return
            
        try:
            days = {
                "day": 1,
                "week": 7,
                "month": 30
            }.get(timeframe.lower(), 7)
            
            stats = await self.bot.analytics.get_historical_stats(days=days)
            if not stats['streams']:
                await ctx.send(f"No statistics available for the past {timeframe}!")
                return
                
            await ctx.send(
                f"{timeframe.capitalize()} Analysis 📊 "
                f"Streams: {stats['streams']} | "
                f"Avg. viewers: {round(stats['avg_viewers'])} | "
                f"Avg. duration: {round(stats['avg_duration']/3600, 1)}h | "
                f"Messages: {stats['total_messages']}"
            )
        except Exception as e:
            logger.error(f"Error analyzing stats: {e}")
            await ctx.send("Error analyzing statistics!")