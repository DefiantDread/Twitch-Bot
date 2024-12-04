# core/raid_recovery.py

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from sqlalchemy import text

from .raid_errors import RaidError, RaidStateError, ErrorCode
from .raid_states import RaidState, RaidInstance

logger = logging.getLogger(__name__)

class RaidRecoveryManager:
    def __init__(self, bot):
        self.bot = bot
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3
        self.recovery_states = {
            RaidState.RECRUITING: self._recover_recruiting,
            RaidState.MILESTONE: self._recover_milestone,
            RaidState.LAUNCHING: self._recover_launching,
            RaidState.ACTIVE: self._recover_active
        }

    async def _handle_unknown_error(self, error: Exception, raid_instance=None) -> bool:
        """Handle unknown errors during raid operations"""
        logger.error(f"An unknown error occurred during raid recovery: {error}")
        try:
            if self.recovery_attempts > self.max_recovery_attempts:
                await self._force_reset("Max recovery attempts exceeded")
                return False

            if raid_instance:
                await self._cancel_raid(raid_instance, f"Unknown error: {str(error)}")
                
            return False

        except Exception as recovery_error:
            logger.error(f"Error handling unknown error: {recovery_error}")
            return False
        
    async def handle_error(self, error: Exception, raid_instance: Optional[RaidInstance] = None) -> bool:
        """Handle raid errors and attempt recovery"""
        try:
            logger.error(f"Raid error occurred: {str(error)}")
            self.recovery_attempts += 1

            if self.recovery_attempts > self.max_recovery_attempts:
                await self._force_reset("Max recovery attempts exceeded")
                return False

            if isinstance(error, RaidStateError):
                return await self._handle_state_error(error, raid_instance)
            elif isinstance(error, RaidError):
                return await self._handle_raid_error(error, raid_instance)
            else:
                return await self._handle_unknown_error(error, raid_instance)

        except Exception as recovery_error:
            logger.error(f"Error during recovery: {str(recovery_error)}")
            await self._force_reset("Recovery error")
            return False

    async def recover_from_crash(self) -> bool:
        """Recover raid state after bot crash/restart"""
        try:
            async with self.bot.db.session_scope() as session:
                # Find any incomplete raids
                result = await session.execute(
                    text("""
                        SELECT id, start_time, ship_type, required_crew
                        FROM raid_history
                        WHERE end_time IS NULL
                        AND start_time > :cutoff
                        ORDER BY start_time DESC
                        LIMIT 1
                    """),
                    {'cutoff': datetime.now(timezone.utc) - timedelta(hours=1)}
                )
                raid = await result.fetchone()

                if not raid:
                    return True  # No recovery needed

                # Get participants for the incomplete raid
                result = await session.execute(
                    text("""
                        SELECT user_id, initial_investment, final_investment
                        FROM raid_participants
                        WHERE raid_id = :raid_id
                    """),
                    {'raid_id': raid[0]}
                )
                participants = await result.fetchall()

                # Process refunds
                for participant in participants:
                    await self.bot.raid_points_manager.refund_investment(
                        participant[0],
                        participant[2],  # final_investment
                        "Raid recovery after crash"
                    )

                # Mark raid as failed
                await session.execute(
                    text("""
                        UPDATE raid_history
                        SET end_time = :now, status = 'failed'
                        WHERE id = :raid_id
                    """),
                    {
                        'now': datetime.now(timezone.utc),
                        'raid_id': raid[0]
                    }
                )

                return True

        except Exception as e:
            logger.error(f"Error during crash recovery: {e}")
            return False

    async def _handle_state_error(self, error: RaidStateError, raid_instance: Optional[RaidInstance]) -> bool:
        """Handle state-related errors"""
        if not raid_instance:
            return False

        try:
            current_state = raid_instance.state
            recovery_handler = self.recovery_states.get(current_state)
            
            if recovery_handler:
                return await recovery_handler(raid_instance)
            
            # If no handler for state, force reset
            await self._force_reset(f"No recovery handler for state {current_state}")
            return False

        except Exception as e:
            logger.error(f"Error in state recovery: {e}")
            return False

    async def _recover_recruiting(self, raid_instance: RaidInstance) -> bool:
        """Recover from error in recruiting state"""
        try:
            if await self._is_raid_expired(raid_instance):
                await self._cancel_raid(raid_instance, "Raid expired during recovery")
                return True

            # Check if we should transition to milestone
            milestone = raid_instance.check_milestone()
            if milestone:
                raid_instance.state = RaidState.MILESTONE
                
            return True

        except Exception as e:
            logger.error(f"Error recovering recruiting state: {e}")
            return False

    async def _recover_milestone(self, raid_instance: RaidInstance) -> bool:
        """Recover from error in milestone state"""
        try:
            if await self._is_raid_expired(raid_instance):
                await self._cancel_raid(raid_instance, "Raid expired during milestone")
                return True

            # Return to recruiting state
            raid_instance.state = RaidState.RECRUITING
            return True

        except Exception as e:
            logger.error(f"Error recovering milestone state: {e}")
            return False

    async def _recover_launching(self, raid_instance: RaidInstance) -> bool:
        """Recover from error during launch"""
        try:
            # Check if rewards were partially distributed
            distributed = await self._check_partial_distribution(raid_instance)
            
            if distributed:
                # Complete the distribution
                await self.bot.raid_rewards_manager.distribute_rewards(raid_instance)
            else:
                # Cancel and refund
                await self._cancel_raid(raid_instance, "Failed during launch")
                
            return True

        except Exception as e:
            logger.error(f"Error recovering launching state: {e}")
            return False

    async def _recover_active(self, raid_instance: RaidInstance) -> bool:
        """Recover from error during active state"""
        try:
            # Verify all rewards were distributed
            if not await self._verify_rewards(raid_instance):
                await self._cancel_raid(raid_instance, "Reward verification failed")
                return False

            raid_instance.state = RaidState.COMPLETED
            return True

        except Exception as e:
            logger.error(f"Error recovering active state: {e}")
            return False

    async def _cancel_raid(self, raid_instance: RaidInstance, reason: str) -> bool:
        """Cancel raid and process refunds"""
        try:
            refunds = {
                user_id: participant.total_investment
                for user_id, participant in raid_instance.participants.items()
            }
            
            success = await self.bot.raid_points_manager.batch_refund(refunds, reason)
            
            if success:
                raid_instance.state = RaidState.INACTIVE
                
            return success

        except Exception as e:
            logger.error(f"Error canceling raid: {e}")
            return False

    async def _force_reset(self, reason: str):
        """Force reset all raid state"""
        try:
            if hasattr(self.bot, 'raid_manager') and self.bot.raid_manager.current_raid:
                await self._cancel_raid(
                    self.bot.raid_manager.current_raid,
                    f"Force reset: {reason}"
                )
            
            if hasattr(self.bot, 'raid_manager'):
                self.bot.raid_manager.current_raid = None
                self.bot.raid_manager.state = 'INACTIVE'
            
            self.recovery_attempts = 0

        except Exception as e:
            logger.error(f"Error during force reset: {e}")

    async def _is_raid_expired(self, raid_instance: RaidInstance) -> bool:
        """Check if raid has exceeded time limit"""
        time_elapsed = (datetime.now(timezone.utc) - raid_instance.start_time).total_seconds()
        return time_elapsed > 300  # 5 minute limit

    async def _check_partial_distribution(self, raid_instance: RaidInstance) -> bool:
        """Check if rewards were partially distributed"""
        try:
            async with self.bot.db.session_scope() as session:
                result = await session.execute(
                    text("""
                        SELECT COUNT(*) FROM raid_participants
                        WHERE raid_id = (
                            SELECT id FROM raid_history
                            WHERE start_time = :start_time
                        )
                    """),
                    {'start_time': raid_instance.start_time}
                )
                count = (await result.first())[0]
                return count > 0

        except Exception as e:
            logger.error(f"Error checking partial distribution: {e}")
            return False

    async def _verify_rewards(self, raid_instance: RaidInstance) -> bool:
        """Verify all rewards were properly distributed"""
        try:
            rewards = raid_instance.get_rewards()
            
            for user_id, expected_reward in rewards.items():
                points_before = await self.bot.points_manager.get_points(user_id)
                participant = raid_instance.participants[user_id]
                
                # Expected points = current + reward - investment
                expected_points = (
                    points_before + 
                    expected_reward - 
                    participant.total_investment
                )
                
                current_points = await self.bot.points_manager.get_points(user_id)
                if current_points != expected_points:
                    return False
                    
            return True

        except Exception as e:
            logger.error(f"Error verifying rewards: {e}")
            return False