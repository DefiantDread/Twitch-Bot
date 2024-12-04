# core/raid_messages.py

import logging
import random
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class MessageContext:
    ship_type: str
    crew_count: int
    required_crew: int
    multiplier: float
    total_investment: int = 0
    username: Optional[str] = None
    investment: Optional[int] = None
    plunder: Optional[int] = None
    time_remaining: Optional[int] = None

class RaidMessageHandler:
    def __init__(self, bot):
        self.bot = bot
        self._setup_message_templates()

    def _setup_message_templates(self):
        # Raid start messages
        self.raid_start_messages = [
            "🏴‍☠️ Through the spyglass: A {ship_type} flying {nation} colors spotted to the {direction}!",
            "⛵ Sail ho! A loaded {ship_type} has strayed from its escort in the {weather}!",
            "🌊 {weather} Perfect conditions - a {ship_type} lies at anchor, ripe for the taking!",
            "⚓ Opportunity strikes! A {ship_type} has run aground on the reefs!",
            "🗺️ Our scouts report a {ship_type} taking the long way around - easy pickings!"
        ]

        # Crew join messages
        self.crew_join_messages = [
            "🎯 {username} commits {investment} points to the raid! ({current}/{needed} crew)",
            "💰 {username} throws in {investment} points and joins the crew! ({current}/{needed})",
            "⚔️ {username} contributes {investment} points to the cause! ({current}/{needed})"
        ]

        # Milestone messages
        self.milestone_messages = [
            "⭐ The crew's reputation grows! Reward multiplier increased to {multiplier}x! {description}",
            "💎 Hidden cargo spotted aboard! Raid value now {multiplier}x! {description}",
            "🏆 Elite crew assembled! Rewards increased to {multiplier}x! {description}"
        ]

        # Progress messages
        self.progress_messages = [
            "⏳ {time_remaining} seconds remaining! Need {remaining_crew} more crew members!",
            "⌛ The {ship_type} won't wait forever! {time_remaining} seconds left to join!",
            "⏰ Time is running out! {time_remaining} seconds to join the raid!"
        ]

        # Launch messages
        self.launch_messages = [
            "🚀 The raid on the {ship_type} begins! {crew_size} brave souls against destiny!",
            "⚔️ All hands on deck! {crew_size} raiders move to engage the {ship_type}!",
            "🏃 The crew charges forward! {crew_size} raiders ready for glory!"
        ]

        # Success messages
        self.success_messages = [
            "💰 Victory! The {ship_type} yields {plunder} points of plunder! ({multiplier}x multiplier)",
            "🎉 A successful raid! {plunder} points claimed from the {ship_type}! ({multiplier}x multiplier)",
            "🏆 The crew triumphs! {plunder} points seized from the {ship_type}! ({multiplier}x multiplier)"
        ]

        # Investment increase messages
        self.investment_messages = [
            "💫 {username} seizes the moment with {amount} more points!",
            "✨ {username} increases their stake by {amount} points!",
            "🌟 {username} commits another {amount} points to the raid!"
        ]

        # Crew join messages
        self.crew_join_messages = [
            "🎯 {username} commits {investment} points to the raid! ({current}/{needed} crew)",
            "💰 {username} throws in {investment} points and joins the crew! ({current}/{needed})",
            "⚔️ {username} contributes {investment} points to the cause! ({current}/{needed})"
        ]

        # Failure messages
        self.raid_failure_messages = [
            "The {ship_type} slips away into the mist - not enough crew to attempt the raid!",
            "Without a full crew, we can't catch the {ship_type}. Better luck next time!",
            "The {ship_type} escapes - we needed more hands on deck!",
            "Raid cancelled - the {ship_type} was too well defended for our small crew.",
            "Our small crew couldn't manage the {ship_type}. All investments returned!"
        ]

        # Environment flavor
        self.weather_conditions = [
            "calm seas",
            "light fog",
            "gathering dusk",
            "morning mist",
            "cloudy skies"
        ]

        self.directions = [
            "north", "south", "east", "west",
            "northwest", "northeast", "southwest", "southeast"
        ]

        self.nations = [
            "Spanish", "Portuguese", "Dutch", "French",
            "English", "Venetian", "Imperial"
        ]

    async def announce_raid_start(self, raid_data: dict):
        """Announce the start of a new raid"""
        try:
            # Format message with raid_data
            message = random.choice(self.raid_start_messages).format(
                ship_type=raid_data['ship_type'],
                weather=random.choice(self.weather_conditions),
                direction=random.choice(self.directions),
                nation=random.choice(self.nations)
            )
            
            await self.bot.send_chat_message(message)
            
            # Follow up with crew requirements
            crew_message = (
                f"🏴‍☠️ Seeking {raid_data['required_crew']} brave souls! "
                f"Join with !raid <amount> (100-1000 points)"
            )
            await self.bot.send_chat_message(crew_message)

        except Exception as e:
            logger.error(f"Error announcing raid start: {e}")

    async def announce_raid_active(self, crew_count: int, ship_type: str):
        """Announce that raid is now active"""
        message = f"🚀 The raid on the {ship_type} begins! {crew_count} brave souls against destiny!"
        await self.bot.send_chat_message(message)


    async def announce_crew_joined(self, username: str, current: int, needed: int, investment: int = None):
        """Announce when a new crew member joins"""
        try:
            message = random.choice(self.crew_join_messages).format(
                username=username,
                investment=investment,
                current=current,
                needed=needed
            )
            await self.bot.send_chat_message(message)

            # If almost full crew, add urgency
            if current == needed - 1:
                await self.bot.send_chat_message(f"⚠️ One more crew member needed!")

        except Exception as e:
            logger.error(f"Error announcing crew join: {e}")

    async def announce_investment(self, context: MessageContext) -> None:
        """Announce when someone invests in the raid"""
        try:
            message = random.choice(self.investment_messages).format(
                username=username,
                amount=amount
            )
            await self.bot.send_chat_message(message)
            
            # Check and announce milestones
            if context.crew_count == context.required_crew - 1:
                await self.bot.send_message(
                    f"⚠️ One more crew member needed! Don't miss out on {context.multiplier}x rewards!"
                )

        except Exception as e:
            logger.error(f"Error announcing investment: {e}")

    async def announce_milestone(self, context: MessageContext) -> None:
        """Announce reaching a raid milestone"""
        try:
            message = random.choice(self.milestone_messages).format(**context.__dict__)
            await self.bot.send_message(message)
            
            # Announce investment window
            window_message = (
                f"💫 30-second bonus investment window! "
                f"Use !invest <amount> to increase your stake!"
            )
            await self.bot.send_message(window_message)

        except Exception as e:
            logger.error(f"Error announcing milestone: {e}")

    async def announce_progress(self, context: MessageContext) -> None:
        """Announce raid progress and time remaining"""
        try:
            remaining_crew = context.required_crew - context.crew_count
            
            message = random.choice(self.progress_messages).format(
                time_remaining=context.time_remaining,
                remaining_crew=remaining_crew,
                ship_type=context.ship_type
            )
            
            await self.bot.send_message(message)

        except Exception as e:
            logger.error(f"Error announcing progress: {e}")

    async def announce_raid_failure(self, data: dict) -> None:
        """Announce when a raid fails or is cancelled"""
        message = random.choice(self.raid_failure_messages).format(**data)
        await self.bot.send_chat_message(message)

    async def announce_time_remaining(self, time_remaining: int, raid_data: dict) -> None:
        """Announce remaining time in raid"""
        remaining_crew = raid_data['required_crew'] - raid_data['current_crew']
        message = (
            f"⏳ {time_remaining} seconds remaining! {raid_data['current_crew']}/{raid_data['required_crew']} crew members! "
            f"Need {remaining_crew} more to raid the {raid_data['ship_type']}!"
        )
        await self.bot.send_chat_message(message)

    async def announce_launch(self, context: MessageContext) -> None:
        """Announce raid launching"""
        try:
            message = random.choice(self.launch_messages).format(**context.__dict__)
            await self.bot.send_message(message)

        except Exception as e:
            logger.error(f"Error announcing launch: {e}")

    async def announce_success(self, context: MessageContext) -> None:
        """Announce successful raid completion"""
        try:
            message = random.choice(self.success_messages).format(plunder=total_plunder, **data)
            await self.bot.send_chat_message(message)

        except Exception as e:
            logger.error(f"Error announcing success: {e}")

    async def _announce_top_contributors(self, context: MessageContext) -> None:
        """Announce top contributors to the raid"""
        try:
            # Get top 3 contributors
            async with self.bot.db.session_scope() as session:
                result = await session.execute(
                    text("""
                        SELECT username, final_investment
                        FROM raid_participants rp
                        JOIN users u ON rp.user_id = u.twitch_id
                        WHERE raid_id = (
                            SELECT id FROM raid_history
                            WHERE end_time = (
                                SELECT MAX(end_time) FROM raid_history
                            )
                        )
                        ORDER BY final_investment DESC
                        LIMIT 3
                    """)
                )
                contributors = await result.fetchall()
                
                if contributors:
                    message = "🏅 Top Contributors: " + " | ".join(
                        f"{username} ({investment} points)"
                        for username, investment in contributors
                    )
                    await self.bot.send_message(message)

        except Exception as e:
            logger.error(f"Error announcing top contributors: {e}")

    async def announce_status(self, context: MessageContext) -> None:
        """Announce current raid status"""
        try:
            message = (
                f"📊 Raid Status: {context.ship_type} | "
                f"Crew: {context.crew_count}/{context.required_crew} | "
                f"Multiplier: {context.multiplier}x"
            )
            
            if context.time_remaining:
                message += f" | Time remaining: {context.time_remaining}s"
            
            await self.bot.send_message(message)

        except Exception as e:
            logger.error(f"Error announcing status: {e}")

    async def announce_error(self, message: str) -> None:
        """Announce error condition"""
        try:
            error_message = f"⚠️ {message}"
            await self.bot.send_message(error_message)
        except Exception as e:
            logger.error(f"Error announcing error: {e}")