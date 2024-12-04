# features/rewards/rewards.py
from typing import Dict, Optional, Callable, Any
import logging
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RewardDefinition:
    id: str
    name: str
    cost: int
    handler: Callable
    cooldown: int = 0
    enabled: bool = True
    user_input_required: bool = False
    mod_bypass: bool = False

class ChannelRewards:
    def __init__(self, bot):
        self.bot = bot
        self.rewards: Dict[str, RewardDefinition] = {}
        self.cooldowns: Dict[str, datetime] = {}
        self.setup_base_rewards()

    def setup_base_rewards(self):
        """Set up default channel point rewards"""
        self.register_reward(
            RewardDefinition(
                id="timeout_user",
                name="Timeout User",
                cost=1000,
                handler=self.handle_timeout,
                cooldown=300,
                user_input_required=True
            )
        )

        self.register_reward(
            RewardDefinition(
                id="highlight_message",
                name="Highlight Message",
                cost=500,
                handler=self.handle_highlight,
                user_input_required=True
            )
        )

        self.register_reward(
            RewardDefinition(
                id="emote_only",
                name="Emote Only Mode",
                cost=2000,
                handler=self.handle_emote_mode,
                cooldown=600
            )
        )

    def register_reward(self, reward: RewardDefinition):
        """Register a new channel point reward"""
        self.rewards[reward.id] = reward
        logger.info(f"Registered reward: {reward.name}")

    async def handle_redemption(self, ctx: Any, reward_id: str, user: str, input_text: Optional[str] = None) -> bool:
        """Handle a reward redemption"""
        try:
            reward = self.rewards.get(reward_id)
            if not reward:
                logger.warning(f"Unknown reward redeemed: {reward_id}")
                return False

            if not reward.enabled:
                await ctx.send(f"@{user} This reward is currently disabled.")
                return False

            if reward.user_input_required and not input_text:
                await ctx.send(f"@{user} This reward requires input text.")
                return False

            # Check cooldown
            if not await self._check_cooldown(reward):
                remaining = await self._get_cooldown_remaining(reward)
                await ctx.send(f"@{user} This reward is on cooldown for {remaining} seconds.")
                return False

            # Execute reward handler
            success = await reward.handler(ctx, user, input_text)
            if success:
                await self._set_cooldown(reward)
                # Track analytics
                await self.bot.analytics.log_reward(reward_id)
                
            return success

        except Exception as e:
            logger.error(f"Error handling reward redemption: {e}")
            await ctx.send(f"@{user} There was an error processing your reward.")
            return False

    # Base reward handlers
    async def handle_timeout(self, ctx: Any, user: str, input_text: str) -> bool:
        """Handle timeout reward"""
        try:
            target = input_text.strip().lower()
            if not target:
                await ctx.send(f"@{user} Please specify a user to timeout!")
                return False

            # Check if target is mod
            channel = self.bot.get_channel(ctx.channel.name)
            if target in channel.moderators:
                await ctx.send(f"@{user} You cannot timeout moderators!")
                return False

            # Execute timeout
            await ctx.channel.timeout(target, 300, f"Channel Points Redemption by {user}")
            await ctx.send(f"@{target} has been timed out for 5 minutes (Redeemed by {user})")
            return True

        except Exception as e:
            logger.error(f"Error in timeout reward: {e}")
            return False

    async def handle_highlight(self, ctx: Any, user: str, input_text: str) -> bool:
        """Handle message highlight reward"""
        try:
            highlighted_message = f"📢 HIGHLIGHTED MESSAGE FROM {user}: {input_text} 📢"
            await ctx.send(highlighted_message)
            return True

        except Exception as e:
            logger.error(f"Error in highlight reward: {e}")
            return False

    async def handle_emote_mode(self, ctx: Any, user: str, _: Optional[str]) -> bool:
        """Handle emote-only mode reward"""
        try:
            await ctx.channel.emote_only()
            await ctx.send(f"Chat is now in emote-only mode for 5 minutes! (Redeemed by {user})")
            
            # Schedule emote-only mode disable
            await asyncio.sleep(300)
            await ctx.channel.emote_only(False)
            await ctx.send("Emote-only mode has been disabled.")
            return True

        except Exception as e:
            logger.error(f"Error in emote-only mode reward: {e}")
            return False

    async def _check_cooldown(self, reward: RewardDefinition) -> bool:
        """Check if a reward is on cooldown"""
        if reward.cooldown == 0:
            return True

        if reward.id not in self.cooldowns:
            return True

        return (datetime.now(timezone.utc) - self.cooldowns[reward.id]).total_seconds() >= reward.cooldown

    async def _set_cooldown(self, reward: RewardDefinition):
        """Set cooldown for a reward"""
        if reward.cooldown > 0:
            self.cooldowns[reward.id] = datetime.now(timezone.utc)

    async def _get_cooldown_remaining(self, reward: RewardDefinition) -> int:
        """Get remaining cooldown time in seconds"""
        if reward.id not in self.cooldowns:
            return 0

        elapsed = (datetime.now(timezone.utc) - self.cooldowns[reward.id]).total_seconds()
        remaining = reward.cooldown - elapsed
        return max(0, int(remaining))