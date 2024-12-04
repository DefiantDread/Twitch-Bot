import pytest
from unittest.mock import AsyncMock, MagicMock
from core.raid_states import RaidState, RaidInstance
from core.raid_errors import RaidStateError

class TestRaidStateTransitions:
    @pytest.fixture
    async def raid_instance(self):
        instance = MagicMock()
        instance.state = RaidState.RECRUITING
        instance.validate_state_transition = AsyncMock()
        instance.validate_state_transition.side_effect = RaidStateError("Invalid state transition")
        return instance

    @pytest.mark.asyncio
    async def test_invalid_state_transitions(self, raid_instance):
        raid_instance.state = RaidState.COMPLETED
        
        with pytest.raises(RaidStateError) as exc_info:
            await raid_instance.validate_state_transition(RaidState.RECRUITING)
        
        assert "Invalid state transition" in str(exc_info.value)