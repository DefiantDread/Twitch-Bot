# features/rewards/stream_interaction.py
from features.rewards.base_handler import BaseRewardHandler

class StreamInteractionHandler(BaseRewardHandler):
    def _setup_messages(self) -> None:
        self.messages = {
            'hydrate': [
                "🚰 Time to hydrate! Take a sip of water!",
                "💧 Hydration check! Drink up!",
                "🌊 Stay hydrated! Water break!"
            ],
            'posture': [
                "🪑 Posture check! Sit up straight!",
                "💺 Fix that posture! Your back will thank you!",
                "🧘 Time to adjust your posture!"
            ],
            'stretch': [
                "🧘‍♂️ Time for a quick stretch break!",
                "💪 Let's stretch those muscles!",
                "🤸 Stand up and stretch!"
            ]
        }

    def _setup_handlers(self) -> None:
        self.handlers = {
            'hydrate_reward': self.handle_hydrate,
            'posture_reward': self.handle_posture,
            'stretch_reward': self.handle_stretch
        }

    async def handle_hydrate(self, ctx, user: str, _: str) -> None:
        await self.send_random_message(ctx, 'hydrate', user=user)
        await self.bot.analytics.log_reward('hydrate')

    async def handle_posture(self, ctx, user: str, _: str) -> None:
        await self.send_random_message(ctx, 'posture', user=user)
        await self.bot.analytics.log_reward('posture')

    async def handle_stretch(self, ctx, user: str, _: str) -> None:
        await self.send_random_message(ctx, 'stretch', user=user)
        await self.bot.analytics.log_reward('stretch')