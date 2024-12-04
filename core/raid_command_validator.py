# core/raid_command_validator.py

from datetime import datetime, timezone
from typing import Tuple, Optional
from core.raid_errors import ErrorCode, ValidationError
from utils.rate_limiter import RateLimiter
import logging

logger = logging.getLogger(__name__)

class RaidCommandValidator:
    def __init__(self, bot):
        self.bot = bot
        self.rate_limiter = bot.rate_limiter
        
        # Command cooldowns in seconds
        self.cooldowns = {
            'raid': 5,      # Joining a raid
            'invest': 5,    # Additional investment
            'crew': 10,     # Checking raid status
            'stats': 30     # Checking raid stats
        }
        
        # Global cooldowns in seconds
        self.global_cooldowns = {
            'raid': 1,
            'invest': 1,
            'crew': 2,
            'stats': 5
        }

    async def validate_command(
        self,
        command: str,
        user_id: str,
        raid_state: str,
        **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """Validate command execution with rate limiting and state checks"""
        try:
            # Check rate limits first
            can_execute, wait_time = await self.rate_limiter.can_execute(
                command,
                user_id,
                self.cooldowns.get(command, 3),
                self.global_cooldowns.get(command, 1)
            )
            
            if not can_execute:
                return False, f"Please wait {wait_time:.1f} seconds before using this command again."

            # Validate command based on raid state
            state_valid, error_msg = self._validate_state(command, raid_state)
            if not state_valid:
                return False, error_msg

            # Command-specific validation
            if command == 'raid':
                return await self._validate_raid_join(user_id, **kwargs)
            elif command == 'invest':
                return await self._validate_investment(user_id, **kwargs)
            
            return True, None

        except Exception as e:
            logger.error(f"Error validating command {command}: {e}")
            return False, "Error validating command"

    def _validate_state(self, command: str, raid_state: str) -> Tuple[bool, Optional[str]]:
        """Validate command against current raid state"""
        valid_states = {
            'raid': ['RECRUITING', 'MILESTONE'],
            'invest': ['MILESTONE'],
            'crew': ['RECRUITING', 'MILESTONE', 'LAUNCHING', 'ACTIVE'],
            'stats': None  # Can be used in any state
        }

        if command not in valid_states:
            return False, "Invalid command"

        required_states = valid_states[command]
        if required_states is None:
            return True, None

        if raid_state not in required_states:
            state_msg = "No raid is active" if raid_state == "INACTIVE" else f"Cannot use this command in {raid_state.lower()} state"
            return False, state_msg

        return True, None

    async def _validate_raid_join(self, user_id: str, amount: Optional[int] = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate raid join command"""
        try:
            # Validate user isn't already in raid
            if await self._is_user_in_raid(user_id):
                return False, "You are already participating in this raid"

            # Validate investment amount
            if not amount:
                return False, "Please specify an investment amount"

            try:
                amount = int(amount)
            except ValueError:
                return False, "Investment amount must be a number"

            if amount < 100 or amount > 1000:
                return False, "Investment must be between 100 and 1000 points"

            # Check user has enough points
            current_points = await self.bot.points_manager.get_points(user_id)
            if current_points < amount:
                return False, f"Not enough points (You have: {current_points})"

            return True, None

        except Exception as e:
            logger.error(f"Error validating raid join: {e}")
            return False, "Error validating raid join"

    async def _validate_investment(self, user_id: str, amount: Optional[int] = None, **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate additional investment command"""
        try:
            # Validate user is in raid
            if not await self._is_user_in_raid(user_id):
                return False, "You are not participating in this raid"

            # Validate investment amount
            if not amount:
                return False, "Please specify an investment amount"

            try:
                amount = int(amount)
            except ValueError:
                return False, "Investment amount must be a number"

            # Get current investment
            current_investment = await self._get_current_investment(user_id)
            if current_investment + amount > 2000:
                return False, f"Total investment cannot exceed 2000 points"

            # Check user has enough points
            current_points = await self.bot.points_manager.get_points(user_id)
            if current_points < amount:
                return False, f"Not enough points (You have: {current_points})"

            return True, None

        except Exception as e:
            logger.error(f"Error validating investment: {e}")
            return False, "Error validating investment"

    async def _is_user_in_raid(self, user_id: str) -> bool:
        """Check if user is participating in current raid"""
        return user_id in self.bot.raid_manager.current_raid.participants if self.bot.raid_manager.current_raid else False

    async def _get_current_investment(self, user_id: str) -> int:
        """Get user's current raid investment"""
        if not self.bot.raid_manager.current_raid:
            return 0
        participant = self.bot.raid_manager.current_raid.participants.get(user_id)
        return participant.total_investment if participant else 0

    async def reset_command_cooldown(self, command: str, user_id: str):
        """Reset cooldown for a command"""
        await self.rate_limiter.reset_cooldown(command, user_id)