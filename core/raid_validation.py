# core/raid_validation.py

from asyncio.log import logger
from typing import Optional, Tuple, Dict
from datetime import datetime, timezone
from .raid_errors import ErrorCode, ValidationError, RaidStateError

class RaidValidator:
    """Validates raid operations and state transitions"""

    @staticmethod
    def validate_raid_start(current_state: str, last_raid_end: Optional[datetime],
                          viewer_count: int) -> Tuple[bool, Optional[ErrorCode]]:
        """Validate if a raid can be started"""
        # Debug the incoming state
        logger.debug(f"Validating raid start - Current state: {current_state}, Type: {type(current_state)}")
        
        # Convert RaidState enum to string if needed
        if hasattr(current_state, 'name'):
            current_state = current_state.name
            
        # Case-insensitive comparison
        if current_state.upper() != 'INACTIVE':
            logger.debug(f"Raid validation failed - State is {current_state}, expected INACTIVE")
            return False, ErrorCode.RAID_ALREADY_ACTIVE

        if last_raid_end:
            cooldown = 1800  # 30 minutes
            elapsed = (datetime.now(timezone.utc) - last_raid_end).total_seconds()
            if elapsed < cooldown:
                return False, ErrorCode.COOLDOWN_ACTIVE

        if viewer_count < 2:
            return False, ErrorCode.INVALID_STATE_TRANSITION

        return True, None

    @staticmethod
    def validate_investment(amount: int, current_points: int, 
                          existing_investment: Optional[int] = None) -> Tuple[bool, Optional[ErrorCode]]:
        """Validate investment amount"""
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return False, ErrorCode.INVALID_AMOUNT

        if amount < 100:
            return False, ErrorCode.INVESTMENT_TOO_LOW
            
        if amount > 1000:
            return False, ErrorCode.INVESTMENT_TOO_HIGH

        if existing_investment and (existing_investment + amount) > 2000:
            return False, ErrorCode.INVESTMENT_TOO_HIGH

        if amount > current_points:
            return False, ErrorCode.INSUFFICIENT_POINTS

        return True, None

    @staticmethod
    def validate_participant(user_id: str, participants: dict,
                           state: str) -> Tuple[bool, ErrorCode]:
        """Validate participant actions"""
        if not user_id:
            return False, ErrorCode.INVALID_USER

        if user_id in participants:
            return False, ErrorCode.ALREADY_PARTICIPATING

        if state not in ['RECRUITING', 'MILESTONE']:
            return False, ErrorCode.RAID_NOT_ACTIVE

        return True, None

    @staticmethod
    def validate_state_transition(current_state: str, new_state: str) -> Tuple[bool, Optional[ErrorCode]]:
        """Validate state transitions"""
        # Map of valid state transitions
        valid_transitions = {
            'RECRUITING': ['MILESTONE', 'LAUNCHING', 'INACTIVE'],
            'MILESTONE': ['RECRUITING', 'LAUNCHING'],
            'LAUNCHING': ['ACTIVE', 'INACTIVE'],
            'ACTIVE': ['COMPLETED', 'INACTIVE'],
            'COMPLETED': ['INACTIVE'],
            'INACTIVE': ['RECRUITING']
        }

        # Convert enum to string if needed
        if hasattr(current_state, 'name'):
            current_state = current_state.name
        
        if hasattr(new_state, 'name'):
            new_state = new_state.name

        # Ensure states are uppercase for comparison
        current_state = current_state.upper()
        new_state = new_state.upper()

        logger.info(f"Validating state transition: {current_state} -> {new_state}")

        if current_state not in valid_transitions:
            logger.error(f"Invalid current state: {current_state}")
            return False, ErrorCode.INVALID_STATE_TRANSITION

        if new_state not in valid_transitions[current_state]:
            logger.error(f"Invalid transition from {current_state} to {new_state}")
            return False, ErrorCode.INVALID_STATE_TRANSITION

        return True, None

    @staticmethod
    def validate_investment_increase(user_id: str, amount: int,
                                  participants: Dict, state: str) -> Tuple[bool, Optional[ErrorCode]]:
        """Validate investment increase"""
        if state != 'MILESTONE':
            return False, ErrorCode.INVESTMENT_WINDOW_CLOSED

        if user_id not in participants:
            return False, ErrorCode.NOT_PARTICIPATING

        current_investment = participants[user_id]['total_investment']
        if current_investment + amount > 2000:
            return False, ErrorCode.INVESTMENT_TOO_HIGH

        return True, None