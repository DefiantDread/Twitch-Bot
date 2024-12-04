# features/rewards/moderation.py
import asyncio
from features.rewards.base_handler import BaseRewardHandler

class ModerationRewardHandler(BaseRewardHandler):
    def _setup_messages(self) -> None:
        self.messages = {
            'timeout': [
                "⏰ {target} has been timed out for 60 seconds (Channel Points Redemption by {user})",
                "⚠️ {target} is taking a 60-second break (Redeemed by {user})"
            ],
            'emote_only': [
                "😄 Chat is now in emote-only mode for 30 seconds!",
                "🎭 Emotes only! Normal chat resumes in 30 seconds!"
            ]
        }

    def _setup_handlers(self) -> None:
        self.handlers = {
            'timeout_reward': self.handle_timeout,
            'emote_only_reward': self.handle_emote_only
        }

    async def handle_timeout(self, ctx, user: str, target: str) -> None:
        if not target:
            await ctx.send("Please specify a user to timeout!")
            return

        target = target.lower().strip()
        if await self.bot.timeout_manager.is_timeout(target):
            await ctx.send(f"@{target} is already timed out!")
            return

        await self.bot.timeout_manager.add_timeout(target, 60)
        await self.send_random_message(ctx, 'timeout', user=user, target=target)
        await self.bot.analytics.log_reward('timeout')

    async def handle_emote_only(self, ctx, user: str, _: str) -> None:
        await ctx.send("/emoteonly")
        await self.send_random_message(ctx, 'emote_only', user=user)
        await asyncio.sleep(30)
        await ctx.send("/emoteonlyoff")
        await self.bot.analytics.log_reward('emote_only')