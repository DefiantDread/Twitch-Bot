import asyncio


class BasicRewards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_rewards()

    def setup_rewards(self):
        # Custom shoutout
        self.bot.rewards.register_reward(
            'shoutout_reward_id',
            self.handle_shoutout
        )
        
        # VIP status for stream
        self.bot.rewards.register_reward(
            'temp_vip_reward_id',
            self.handle_temp_vip
        )
        
        # Song request
        self.bot.rewards.register_reward(
            'song_request_id',
            self.handle_song_request
        )

    async def handle_shoutout(self, ctx, user, input_text):
        await ctx.send(f"Big shoutout to {user}! {input_text}")
        
    async def handle_temp_vip(self, ctx, user, _):
        await ctx.send(f"/vip {user}")
        await asyncio.sleep(3600)  # 1 hour
        await ctx.send(f"/unvip {user}")
        
    async def handle_song_request(self, ctx, user, song_name):
        await ctx.send(f"Song request from {user}: {song_name} has been added to the queue!")