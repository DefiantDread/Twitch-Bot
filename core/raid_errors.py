# core/raid_errors.py

from enum import Enum
from typing import Optional

class RaidError(Exception):
    """Base class for raid-related errors"""
    pass

class RaidStateError(RaidError):
    """Error for invalid state transitions"""
    pass

class InvestmentError(RaidError):
    """Error for invalid investments"""
    pass

class ParticipationError(RaidError):
    """Error for participation-related issues"""
    pass

class ValidationError(RaidError):
    """Error for validation failures"""
    pass

class ErrorCode(Enum):
    # State Errors
    RAID_ALREADY_ACTIVE = "A raid is already in progress"
    RAID_NOT_ACTIVE = "No raid is currently active"
    INVALID_STATE_TRANSITION = "Invalid raid state transition"
    
    # Investment Errors
    INSUFFICIENT_POINTS = "Not enough points for investment"
    INVESTMENT_TOO_LOW = "Investment amount too low"
    INVESTMENT_TOO_HIGH = "Investment amount too high"
    INVESTMENT_WINDOW_CLOSED = "Investment window is closed"
    
    # Participation Errors
    ALREADY_PARTICIPATING = "Already participating in raid"
    NOT_PARTICIPATING = "Not participating in this raid"
    RAID_FULL = "Raid party is full"
    
    # Validation Errors
    INVALID_AMOUNT = "Invalid amount specified"
    INVALID_USER = "Invalid user"
    COOLDOWN_ACTIVE = "Cooldown still active"

class ErrorHandler:
    """Handles raid-related errors and provides appropriate messages"""
    
    @staticmethod
    def get_error_message(error_code: ErrorCode, context: Optional[dict] = None) -> str:
        """Get user-friendly error message"""
        base_message = error_code.value
        
        if context:
            if error_code == ErrorCode.INSUFFICIENT_POINTS:
                return f"{base_message} (You have: {context.get('current_points', 0)} points)"
            elif error_code == ErrorCode.INVESTMENT_TOO_LOW:
                return f"{base_message} (Minimum: {context.get('min_amount', 100)} points)"
            elif error_code == ErrorCode.INVESTMENT_TOO_HIGH:
                return f"{base_message} (Maximum: {context.get('max_amount', 1000)} points)"
            elif error_code == ErrorCode.COOLDOWN_ACTIVE:
                return f"{base_message} ({context.get('time_remaining', 0)} seconds remaining)"
        
        return base_message

    @staticmethod
    def format_error(error: RaidError) -> str:
        """Format error for logging"""
        return f"{error.__class__.__name__}: {str(error)}"