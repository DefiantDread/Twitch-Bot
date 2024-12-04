# tests/test_rewards.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from features.rewards.handlers import RewardHandlers
from features.rewards.base_handler import BaseRewardHandler

@pytest.fixture
def mock_ctx():
    ctx = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.name = "test_channel"
    ctx.channel.moderators = ["mod_user"]
    ctx.send = AsyncMock()
    return ctx

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.rewards = MagicMock()
    bot.get_channel = MagicMock()
    
    # Mock channel with moderators
    mock_channel = MagicMock()
    mock_channel.moderators = ["mod_user"]
    bot.get_channel.return_value = mock_channel
    
    # Mock analytics
    bot.analytics = MagicMock()
    bot.analytics.log_reward = AsyncMock()
    
    return bot

@pytest.mark.asyncio
async def test_reward_registration(mock_bot):
    """Test reward handler registration"""
    handlers = RewardHandlers(mock_bot)
    
    # Verify all rewards were registered
    registered_rewards = [args[0][0] for args in mock_bot.rewards.register_reward.call_args_list]
    expected_rewards = [
        'timeout_reward', 'emote_only', 'highlight_message',
        'channel_vip', 'hydrate', 'posture', 'stretch'
    ]
    
    for reward in expected_rewards:
        assert reward in registered_rewards

@pytest.mark.asyncio
async def test_timeout_reward(mock_bot, mock_ctx):
    """Test timeout reward handling"""
    handlers = RewardHandlers(mock_bot)

    # Test successful timeout
    await handlers.handle_timeout(mock_ctx, "redeemer", "target_user")

    assert mock_ctx.send.call_count == 1
    assert "timed out" in str(mock_ctx.send.call_args_list[0][0][0]).lower()

@pytest.mark.asyncio
async def test_timeout_reward_error_cases(mock_bot, mock_ctx):
    """Test timeout reward error handling"""
    handlers = RewardHandlers(mock_bot)

    # Test missing target
    with pytest.raises(ValueError, match="specify a user"):
        await handlers.handle_timeout(mock_ctx, "redeemer", None)

    # Test timeout on moderator
    mock_ctx.channel.moderators = ["mod_user"]
    with pytest.raises(ValueError, match="Cannot timeout moderators"):
        await handlers.handle_timeout(mock_ctx, "redeemer", "mod_user")

@pytest.mark.asyncio
async def test_emote_only_reward(mock_bot, mock_ctx):
    """Test emote-only mode reward"""
    handlers = RewardHandlers(mock_bot)

    await handlers.handle_emote_only(mock_ctx, "user", None)

    assert mock_ctx.send.call_count == 3
    assert "/emoteonly" in str(mock_ctx.send.call_args_list[0][0][0])
    assert "emote-only mode" in str(mock_ctx.send.call_args_list[1][0][0])

@pytest.mark.asyncio
async def test_base_reward_handler():
    """Test base reward handler functionality"""
    class TestHandler(BaseRewardHandler):
        def _setup_messages(self):
            self.messages = {
                'test': ['Test message for {user}!']
            }

        def _setup_handlers(self):
            self.handlers = {
                'test_reward': self.handle_test
            }

        async def handle_test(self, ctx, user, input_text):
            await self.send_random_message(ctx, 'test', user=user)

    mock_bot = MagicMock()
    mock_bot.analytics = MagicMock()
    mock_bot.analytics.log_reward = AsyncMock()  # Ensure this is awaitable

    handler = TestHandler(mock_bot)
    ctx = AsyncMock()

    await handler.handle_reward(ctx, 'test_reward', 'testuser', '')

    ctx.send.assert_called_once_with('Test message for testuser!')

@pytest.mark.asyncio
async def test_reward_error_handling(mock_bot, mock_ctx):
    """Test error handling in rewards"""
    handlers = RewardHandlers(mock_bot)

    # Force an error by passing None as target
    with pytest.raises(ValueError, match="You must specify a user to timeout."):
        await handlers.handle_timeout(mock_ctx, "user", None)

@pytest.mark.asyncio
async def test_input_validation():
    """Test reward input validation"""
    class TestHandler(BaseRewardHandler):
        def _setup_messages(self):
            self.messages = {}
        def _setup_handlers(self):
            self.handlers = {}
    
    handler = TestHandler(MagicMock())
    
    # Test valid input
    assert handler.validate_input("test") == "test"
    
    # Test empty input
    with pytest.raises(ValueError, match="provide valid input"):
        handler.validate_input("")
    
    # Test too long input
    long_input = "a" * 501
    with pytest.raises(ValueError, match="Input too long"):
        handler.validate_input(long_input)

@pytest.mark.asyncio
async def test_message_key_not_found(mock_bot, mock_ctx):
    """Test handling of missing message key"""
    class TestHandler(BaseRewardHandler):
        def _setup_messages(self):
            self.messages = {}
        def _setup_handlers(self):
            self.handlers = {}
    
    handler = TestHandler(mock_bot)
    await handler.send_random_message(mock_ctx, 'nonexistent_key')
    
    # Should send fallback message
    mock_ctx.send.assert_called_once_with("Action completed!")