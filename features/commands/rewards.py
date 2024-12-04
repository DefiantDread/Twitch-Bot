class RewardCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_rewards()

    def setup_rewards(self):
        # Register reward handlers
        self.bot.reward_handler.register_reward(
            'reward_id_here',
            self.handle_timeout_reward
        )

    async def handle_timeout_reward(self, user, input):
        target = input.strip().lower()
        if target and not self.bot.get_user(target).is_mod:
            await self.bot.timeout(target, 60, "Channel point reward redemption")