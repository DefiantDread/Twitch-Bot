# features/rewards/handlers.py
from typing import Dict, Optional
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RewardStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REFUNDED = "refunded"

@dataclass
class RewardResult:
    status: RewardStatus
    message: str
    cooldown: Optional[int] = None
    metadata: Optional[Dict] = None

class RewardHandlers:
    def __init__(self, bot):
        self.bot = bot
        self.active_rewards: Dict[str, datetime] = {}
        self.handlers = {}  # Initialize as empty
        self.setup_rewards()
        
    def setup_rewards(self):
        """Register all reward handlers with proper validation and error handling"""
        self.handlers = {
            'timeout_reward': self.handle_timeout,
            'highlight_message': self.handle_highlight,
            'emote_only': self.handle_emote_only,
            'channel_vip': self.handle_vip,
            'hydrate': self.handle_hydrate,
            'posture': self.handle_posture,
            'stretch': self.handle_stretch,
            'song_request': self.handle_song_request,
            'custom_shoutout': self.handle_shoutout,
            'follower_only': self.handle_follower_mode,
            'subscriber_only': self.handle_subscriber_mode,
            'custom_alert': self.handle_custom_alert
        }

        # Register rewards with the bot
        for reward_name in self.handlers.keys():
            self.bot.rewards.register_reward(reward_name, self.handlers[reward_name])

    async def handle_highlight(self, user: str, input_text: str) -> RewardResult:
        """Handle highlight message reward"""
        try:
            # Validate the input
            input_text = input_text.strip()
            if not input_text:
                raise ValueError("Message cannot be empty.")
            
            # Simulate sending a highlighted message (replace with actual implementation)
            # Example: Sending to a stream overlay or chat
            await self.bot.overlay_manager.display_highlight(user, input_text)

            return RewardResult(
                status=RewardStatus.SUCCESS,
                message=f"Highlighted message from {user}: {input_text}",
                cooldown=30  # Example cooldown of 30 seconds
            )
        except Exception as e:
            logger.error(f"Error handling highlight message: {e}")
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} Failed to process the highlight message."
            )

    async def handle_redemption(self, reward_data: Dict) -> RewardResult:
        """Main reward handling with comprehensive error handling and user feedback"""
        try:
            reward_id = reward_data['reward']['id']
            user = reward_data['user']['login']
            input_text = reward_data.get('user_input', '')
            
            # Check if reward is on cooldown
            if await self._check_cooldown(reward_id):
                remaining_time = int((self.active_rewards[reward_id] - datetime.now(timezone.utc)).total_seconds())
                return RewardResult(
                    status=RewardStatus.FAILED,
                    message=f"@{user} This reward is on cooldown for {remaining_time} seconds!"
                )
            
            handler = self.handlers.get(reward_id)
            if not handler:
                logger.error(f"No handler found for reward ID: {reward_id}")
                return RewardResult(
                    status=RewardStatus.FAILED,
                    message=f"@{user} This reward is not properly configured."
                )
                
            # Execute reward handler
            result = await handler(user, input_text)
            
            # Track analytics
            await self.bot.analytics.log_reward(reward_id, result.status == RewardStatus.SUCCESS)
            
            # Set cooldown if specified
            if result.cooldown:
                await self._set_cooldown(reward_id, result.cooldown)
                
            return result
            
        except Exception as e:
            logger.error(f"Error handling reward redemption: {e}")
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} There was an error processing your reward. Please try again later."
            )
        
    async def handle_vip(self, user: str, _input_text: str) -> RewardResult:
        """Handle VIP reward"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} has been granted VIP status!",
            cooldown=300  # Example cooldown of 5 minutes
        )
    
    async def handle_shoutout(self, user: str, _input_text: str) -> RewardResult:
        """Handle shoutout reward"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} has requested a shoutout.",
            cooldown=300  # Example cooldown of 5 minutes
        )
    
    async def handle_song_request(self, user: str, _input_text: str) -> RewardResult:
        """Handle song request reward"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} has requested a song.",
            cooldown=300  # Example cooldown of 5 minutes
        )

    async def handle_hydrate(self, user: str, _input_text: str) -> RewardResult:
        """Handle hydrate reminder"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} reminded everyone to hydrate!",
            cooldown=60  # Example cooldown of 1 minute
        )

    async def handle_posture(self, user: str, _input_text: str) -> RewardResult:
        """Handle posture reminder"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} reminded everyone to check their posture!",
            cooldown=60
        )

    async def handle_stretch(self, user: str, _input_text: str) -> RewardResult:
        """Handle stretch reminder"""
        return RewardResult(
            status=RewardStatus.SUCCESS,
            message=f"@{user} reminded everyone to stretch!",
            cooldown=60
        )

    async def handle_follower_mode(self, user: str, duration: str) -> RewardResult:
        """Handle follower-only mode activation"""
        try:
            # Convert duration to minutes, default to 5 minutes if not specified
            minutes = int(duration) if duration.strip() else 5
            minutes = min(max(1, minutes), 60)  # Limit between 1-60 minutes
            
            channel = self.bot.get_channel(self.bot.channel_name)
            await channel.followers_only(duration=minutes * 60)
            
            return RewardResult(
                status=RewardStatus.SUCCESS,
                message=f"Chat is now in follower-only mode for {minutes} minutes!",
                cooldown=minutes * 60 + 300  # Duration + 5 minute buffer
            )
        except Exception as e:
            logger.error(f"Error setting follower mode: {e}")
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} Failed to enable follower-only mode."
            )

    async def handle_subscriber_mode(self, user: str, duration: str) -> RewardResult:
        """Handle subscriber-only mode activation"""
        try:
            minutes = int(duration) if duration.strip() else 5
            minutes = min(max(1, minutes), 60)
            
            channel = self.bot.get_channel(self.bot.channel_name)
            await channel.subscribers_only()
            
            # Schedule mode disable
            asyncio.create_task(self._schedule_mode_disable(
                channel.subscribers_only_off,
                minutes * 60
            ))
            
            return RewardResult(
                status=RewardStatus.SUCCESS,
                message=f"Chat is now in subscriber-only mode for {minutes} minutes!",
                cooldown=minutes * 60 + 300
            )
        except Exception as e:
            logger.error(f"Error setting subscriber mode: {e}")
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} Failed to enable subscriber-only mode."
            )

    async def handle_custom_alert(self, user: str, alert_text: str) -> RewardResult:
        """Handle custom on-stream alert"""
        if not alert_text or len(alert_text.strip()) < 1:
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} Please provide alert text!"
            )
            
        try:
            # Sanitize alert text
            alert_text = alert_text.strip()[:200]  # Limit length
            
            # Send to overlay system (implementation needed)
            await self.bot.overlay_manager.show_alert(user, alert_text)
            
            return RewardResult(
                status=RewardStatus.SUCCESS,
                message=f"Alert from {user} displayed on stream!",
                cooldown=30,
                metadata={"alert_text": alert_text}
            )
        except Exception as e:
            logger.error(f"Error displaying alert: {e}")
            return RewardResult(
                status=RewardStatus.FAILED,
                message=f"@{user} Failed to display alert. Please try again later."
            )

    async def _schedule_mode_disable(self, disable_func, delay: int):
        """Schedule a chat mode to be disabled after delay"""
        await asyncio.sleep(delay)
        try:
            await disable_func()
        except Exception as e:
            logger.error(f"Error disabling chat mode: {e}")

    async def _check_cooldown(self, reward_id: str) -> bool:
        """Check if a reward is currently on cooldown"""
        if reward_id not in self.active_rewards:
            return False
            
        if datetime.now(timezone.utc) >= self.active_rewards[reward_id]:
            del self.active_rewards[reward_id]
            return False
            
        return True

    async def _set_cooldown(self, reward_id: str, seconds: int):
        """Set a cooldown for a reward"""
        self.active_rewards[reward_id] = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    async def handle_timeout(self, ctx, redeemer: str, target_user: Optional[str]) -> None:
        """Handle timeout reward"""
        if not target_user:
            raise ValueError("You must specify a user to timeout.")
        if target_user in ctx.channel.moderators:
            raise ValueError("Cannot timeout moderators.")
        if target_user in self.active_rewards:
            raise ValueError(f"{target_user} is already timed out.")

        self.active_rewards[target_user] = datetime.now(timezone.utc) + timedelta(minutes=5)
        await ctx.send(f"{target_user} has been timed out for 5 minutes by {redeemer}.")
        await self.bot.analytics.log_reward("timeout_reward", ctx.channel.name, redeemer)


    
    async def handle_emote_only(self, ctx, redeemer: str, _input_text: Optional[str]) -> None:
        """Handle emote-only mode reward"""
        try:
            await ctx.send("/emoteonly")
            await ctx.send("The emote-only mode has been activated!")
            await asyncio.sleep(5)  # Simulate the delay for the mode
            await ctx.send("/emoteonlyoff")
        except Exception as e:
            logger.error(f"Error activating emote-only mode: {e}")
            await ctx.send("Failed to activate emote-only mode.")