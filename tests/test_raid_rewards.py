import pytest
from unittest.mock import MagicMock, AsyncMock, call
from core.raid_rewards import RaidRewardManager
from core.raid_states import RaidState

class TestRaidRewardDistribution:
    @pytest.fixture
    def mock_bot(self):  # Remove async
        bot = MagicMock()
        bot.points_manager = AsyncMock()
        bot.points_manager.add_points.return_value = True
        
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        
        bot.db = AsyncMock()
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock()
        bot.db.session_scope.return_value = context_manager
        
        return bot

    @pytest.fixture
    def raid_instance(self):  # Renamed from sample_raid_instance
        instance = MagicMock()
        instance.ship_type = "Merchant Vessel"
        instance.current_multiplier = 1.5
        instance.state = RaidState.ACTIVE
        instance.start_time = "2023-01-01"
        
        rewards = {
            "user1": 750,  # 500 * 1.5
            "user2": 1125, # 750 * 1.5
            "user3": 1500  # 1000 * 1.5
        }
        instance.get_rewards = MagicMock(return_value=rewards)
        
        instance.participants = {
            "user1": MagicMock(total_investment=500, initial_investment=500),
            "user2": MagicMock(total_investment=750, initial_investment=750),
            "user3": MagicMock(total_investment=1000, initial_investment=1000)
        }
        
        return instance

    @pytest.mark.asyncio
    async def test_basic_reward_distribution(self, mock_bot, raid_instance):
        reward_manager = RaidRewardManager(mock_bot)
        success, _ = await reward_manager.distribute_rewards(raid_instance)

        assert success, "Reward distribution should be successful"
        assert mock_bot.points_manager.add_points.call_count == len(raid_instance.participants)

        expected_calls = [
            call("user1", 750, f"Raid reward ({raid_instance.ship_type})"),
            call("user2", 1125, f"Raid reward ({raid_instance.ship_type})"),
            call("user3", 1500, f"Raid reward ({raid_instance.ship_type})")
        ]
        mock_bot.points_manager.add_points.assert_has_calls(expected_calls, any_order=True)

    @pytest.mark.asyncio
    async def test_empty_raid_handling(self, mock_bot):
        # Create an empty raid instance
        empty_raid = MagicMock()
        empty_raid.participants = {}  # No participants
        empty_raid.state = RaidState.ACTIVE
        empty_raid.get_rewards = MagicMock(return_value={})
        empty_raid.ship_type = "Empty Ship"

        reward_manager = RaidRewardManager(mock_bot)
        success, message = await reward_manager.distribute_rewards(empty_raid)

        # Assert that the distribution fails
        assert not success, "Reward distribution should fail for empty raids"
        assert "No participants" in str(message), f"Unexpected error message: {message}"

    @pytest.mark.asyncio
    async def test_invalid_state_distribution(self, mock_bot, raid_instance):
        raid_instance.state = RaidState.RECRUITING  # Set an invalid state

        reward_manager = RaidRewardManager(mock_bot)
        success, message = await reward_manager.distribute_rewards(raid_instance)

        # Assertions
        assert not success, "Reward distribution should fail for invalid raid state."
        assert "Invalid state" in message, f"Unexpected message: {message}"


    @pytest.mark.asyncio
    async def test_multiplier_reward_calculation(self, mock_bot, raid_instance):
        raid_instance.current_multiplier = 2.0
        rewards = {
            "user1": 1000,  # 500 * 2.0
            "user2": 1500,  # 750 * 2.0
            "user3": 2000   # 1000 * 2.0
        }
        raid_instance.get_rewards = MagicMock(return_value=rewards)
        
        reward_manager = RaidRewardManager(mock_bot)
        success, _ = await reward_manager.distribute_rewards(raid_instance)
        
        assert success
        reward_amounts = [args[1] for args, _ in mock_bot.points_manager.add_points.call_args_list]
        assert max(reward_amounts) == 2000