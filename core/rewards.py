from twitchio.ext import commands
import asyncio

class RewardManager:
    def __init__(self, bot):
        self.bot = bot
        self.registered_rewards = {}

    async def handle_redemption(self, ctx, reward_id, user, input_text):
        if reward_id in self.registered_rewards:
            await self.registered_rewards[reward_id](ctx, user, input_text)

    def register_reward(self, reward_id, handler):
        self.registered_rewards[reward_id] = handler