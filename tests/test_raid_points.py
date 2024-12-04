import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, call
from core.raid_points import RaidPointsManager

class TestRaidPointsSystem:
    @pytest.fixture
    def points_manager(self):  # Remove async from fixture
        bot = MagicMock()
        bot.points_manager = AsyncMock()
        bot.points_manager.get_points.return_value = 1000
        bot.points_manager.remove_points.return_value = True
        bot.points_manager.add_points.return_value = True
        
        session = AsyncMock()
        result = AsyncMock()
        result.first.return_value = [1500, 2000, 3]
        session.execute.return_value = result
        
        bot.db = AsyncMock()
        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=session)
        context_manager.__aexit__ = AsyncMock()
        bot.db.session_scope.return_value = context_manager
        
        return RaidPointsManager(bot)

    @pytest.mark.asyncio
    async def test_investment_stats(self, points_manager):
        # Mock database session and query execution
        session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=(1500, 2000, 3))  # Mocked data
        session.execute.return_value = mock_result  # Ensure execute() returns the mocked result object

        # Mock session_scope as async context manager
        context_manager = AsyncMock()
        context_manager.__aenter__.return_value = session
        context_manager.__aexit__.return_value = None
        points_manager.bot.db.session_scope = MagicMock(return_value=context_manager)

        # Call the method being tested
        stats = await points_manager.get_investment_stats("user1")
        expected = {
            'total_invested': 1500,
            'total_rewards': 2000,
            'total_raids': 3,
            'roi': (2000 - 1500) / 1500
        }

        # Assert the result matches the expected output
        assert stats == expected





    @pytest.mark.asyncio
    async def test_transaction_atomicity(self, points_manager):
        # Mock session and its methods
        session = AsyncMock()
        session.commit = AsyncMock(side_effect=Exception("Database error"))  # Simulate commit failure
        session.rollback = AsyncMock()  # Rollback should be called

        # Mock session_scope as an async context manager
        context_manager = AsyncMock()
        context_manager.__aenter__.return_value = session
        context_manager.__aexit__.return_value = None  # No-op for exit
        points_manager.bot.db.session_scope = MagicMock(return_value=context_manager)  # NOT AsyncMock

        # Mock points_manager methods
        points_manager.bot.points_manager.get_points = AsyncMock(return_value=1000)  # User has 1000 points
        points_manager.bot.points_manager.remove_points = AsyncMock(return_value=True)  # Simulate successful removal
        points_manager.refund_investment = AsyncMock(return_value=True)  # Refund is successful

        # Call process_investment
        success, message = await points_manager.process_investment("user1", 500)

        # Assertions
        assert not success, "Transaction should fail if commit raises an exception"
        assert "Error processing investment" in message
        session.rollback.assert_called_once()  # Ensure rollback was triggered
        points_manager.refund_investment.assert_called_once_with("user1", 500, "Database error")


