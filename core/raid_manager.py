# core/raid_manager.py

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
import asyncio
import logging
import random
from database.models import RaidHistory, RaidParticipant, PlayerRaidStats
from sqlalchemy import select, text

from core.raid_errors import ErrorHandler, RaidError, ErrorCode, RaidStateError, ValidationError
from core.raid_validation import RaidValidator
from core.raid_recovery import RaidRecoveryManager

logger = logging.getLogger(__name__)

class RaidState(Enum):
    INACTIVE = "INACTIVE"
    RECRUITING = "RECRUITING"
    MILESTONE = "MILESTONE"
    LAUNCHING = "LAUNCHING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

class RaidManager:
    def __init__(self, bot):
        self.bot = bot
        self.state = RaidState.INACTIVE
        self.current_raid = None
        self.participants = {}
        self._lock = asyncio.Lock()
        self.validator = RaidValidator()
        self.recovery = RaidRecoveryManager(self)
        
        # Initialize raid-specific attributes
        self.raid_ship_type = None
        self.raid_required_crew = None
        self.raid_start_time = None
        self.raid_viewer_count = None
        self.raid_multiplier = None
        self._recruitment_task = None
        
        # Ship types based on viewer count
        self.ship_types = {
            'small': [
                "Merchant Sloop", "Fishing Vessel", "Supply Barge",
                "Coast Guard Cutter", "Pearl Diving Boat"
            ],
            'medium': [
                "Merchant Brig", "Spice Trader", "Wine Transport",
                "Silk Runner", "Colonial Supply Ship"
            ],
            'large': [
                "Trade Galleon", "East India Trader", "Royal Merchant",
                "Treasure Galleon", "Portuguese Carrack"
            ],
            'epic': [
                "Spanish Armada Ship", "Royal Treasury Fleet",
                "Imperial Gold Transport", "Sultan's Gift Fleet",
                "Portuguese Spice Armada"
            ]
        }

    async def start_raid(self) -> bool:
        """Initialize a new raid"""
        async with self._lock:
            try:
                logger.info(f"Starting raid - Current state: {self.state}")
                
                # Check current state
                if self.state != RaidState.INACTIVE:
                    logger.warning(f"Cannot start raid - current state is {self.state}")
                    return False

                viewer_count = await self.bot.get_viewer_count()
                logger.info(f"Current viewer count: {viewer_count}")
                
                if viewer_count is None or viewer_count <= 0:
                    logger.error("Viewer count is None or zero, cannot start raid.")
                    return False

                # Initialize raid data
                self.raid_start_time = datetime.now(timezone.utc)
                self.raid_ship_type = await self._select_ship_type(viewer_count)
                self.raid_required_crew = self._calculate_required_crew(viewer_count)
                self.raid_viewer_count = viewer_count
                self.raid_multiplier = 1.5
                
                logger.info(f"Raid initialized - Ship: {self.raid_ship_type}, Required crew: {self.raid_required_crew}")
                
                # Set state to recruiting and clear any old data
                self.state = RaidState.RECRUITING
                self.participants.clear()
                
                # Start recruitment timer
                if self._recruitment_task and not self._recruitment_task.done():
                    self._recruitment_task.cancel()
                    try:
                        await self._recruitment_task
                    except asyncio.CancelledError:
                        pass
                        
                self._recruitment_task = asyncio.create_task(self._recruitment_timer())
                
                # Announce raid start
                await self._announce_raid_start()
                logger.info("Raid started successfully")
                return True

            except Exception as e:
                logger.error(f"Error starting raid: {e}", exc_info=True)
                await self._reset_raid_data()
                return False
            
    async def _reset_raid_data(self):
        """Reset all raid-related data with task cleanup"""
        try:
            async with self._lock:
                logger.info("Starting raid data reset")
                
                # Cancel recruitment timer if it exists
                if self._recruitment_task and not self._recruitment_task.done():
                    logger.info("Cancelling recruitment task")
                    self._recruitment_task.cancel()
                    try:
                        await asyncio.wait_for(self._recruitment_task, timeout=2.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.warning("Recruitment task cancellation timed out")
                    self._recruitment_task = None

                # Force immediate state reset
                await self._force_reset()
                
                # Verify state
                if self.is_active:
                    logger.error("State verification failed after reset")
                    await self._force_reset()  # Try one more time
                
                logger.info("Raid data reset completed successfully")

        except Exception as e:
            logger.error(f"Error resetting raid data: {e}")
            # Force reset as last resort
            await self._force_reset()

    @property
    def is_active(self) -> bool:
        """Check if raid is currently active"""
        return (
            self.state != RaidState.INACTIVE and 
            self.state != RaidState.COMPLETED
        )

    async def join_raid(self, user_id: str, username: str, investment: int) -> tuple[bool, str]:
        """Handle a player joining the raid with validation"""
        if self.state != RaidState.RECRUITING:
            return False, "No raid is currently active"
        
        if self.raid_ship_type is None:
            return False, "No raid is currently active"

        async with self._lock:
            try:
                # Validate participant
                is_valid, error_code = self.validator.validate_participant(
                    user_id, 
                    self.participants,
                    self.state.name
                )
                
                if not is_valid:
                    return False, str(error_code.value if error_code else "Invalid participant")

                # Validate investment
                current_points = await self.bot.points_manager.get_points(user_id)
                is_valid, error_code = self.validator.validate_investment(
                    investment,
                    current_points
                )
                
                if not is_valid:
                    return False, str(error_code.value if error_code else "Invalid investment")

                # Add participant
                self.participants[user_id] = {
                    'username': username,
                    'initial_investment': investment,
                    'total_investment': investment
                }

                # Update points
                await self.bot.points_manager.remove_points(
                    user_id,
                    investment,
                    "Raid investment"
                )
                
                # Announce new crew member
                await self.bot.raid_messages.announce_crew_joined(
                    username=username,
                    current=len(self.participants),
                    needed=self.raid_required_crew,
                    investment=investment
                )

                await self._check_milestone()
                
                return True, "Successfully joined the raid!"

            except Exception as e:
                logger.error(f"Error joining raid: {e}")
                await self.recovery.handle_error(e)
                return False, "Error joining raid"
            
    async def _select_ship_type(self, viewer_count: int) -> str:
        """Select appropriate ship type based on viewer count"""
        if viewer_count <= 10:
            return random.choice(self.ship_types['small'])
        elif viewer_count <= 30:
            return random.choice(self.ship_types['medium'])
        elif viewer_count <= 100:
            return random.choice(self.ship_types['large'])
        else:
            return random.choice(self.ship_types['epic'])

    def _calculate_required_crew(self, viewer_count: int) -> int:
        """Calculate required participants based on viewer count"""
        if viewer_count < 10:
            return 2
        return max(2, int(viewer_count * 0.1))

    async def _recruitment_timer(self):
        """Handle recruitment phase timing"""
        try:
            # Announce at 60 seconds remaining
            await asyncio.sleep(60)
            if self.state == RaidState.RECRUITING:
                await self._announce_time_remaining(60)

            # Announce at 30 seconds remaining
            await asyncio.sleep(30)
            if self.state == RaidState.RECRUITING:
                await self._announce_time_remaining(30)

            # Final 30 seconds
            await asyncio.sleep(30)
            
            logger.info("Recruitment timer finished - initiating raid end")
            
            # Important: Use _end_raid instead of _complete_raid
            if self.state == RaidState.RECRUITING:
                async with self._lock:
                    await self._handle_raid_completion()

        except asyncio.CancelledError:
            logger.info("Recruitment timer cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in recruitment timer: {e}")
            await self._handle_raid_error()

    async def _handle_raid_completion(self):
        """Handle the raid completion process"""
        try:
            logger.info(f"Handling raid completion. Participants: {len(self.participants)}/{self.raid_required_crew}")
            
            if len(self.participants) >= self.raid_required_crew:
                # Successful raid
                logger.info("Raid successful - distributing rewards")
                
                # Transition states
                self.state = RaidState.LAUNCHING
                await self._announce_raid_launching()
                await asyncio.sleep(2)

                self.state = RaidState.ACTIVE
                total_plunder = await self._distribute_rewards()

                self.state = RaidState.COMPLETED
                await self._announce_raid_success({
                    'total_plunder': total_plunder,
                    'participants': len(self.participants),
                    'multiplier': self.raid_multiplier,
                    'ship_type': self.raid_ship_type
                })
            else:
                # Failed raid
                logger.info("Raid failed - insufficient participants")
                await self._handle_raid_error()

        except Exception as e:
            logger.error(f"Error in raid completion: {e}")
            await self._handle_raid_error()
        finally:
            # Always ensure we reset state
            logger.info("Resetting raid state after completion")
            await self._force_reset()

    async def _end_raid(self):
        """End the raid and handle rewards"""
        async with self._lock:
            try:
                logger.info(f"Ending raid with {len(self.participants)} participants (need {self.raid_required_crew})")
                
                # Cancel the recruitment timer first
                if self._recruitment_task and not self._recruitment_task.done():
                    self._recruitment_task.cancel()
                    try:
                        await asyncio.wait_for(self._recruitment_task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                    self._recruitment_task = None

                # Check if we have enough participants
                if len(self.participants) >= self.raid_required_crew:
                    logger.info("Sufficient participants - completing raid")
                    self.state = RaidState.LAUNCHING
                    await self._announce_raid_launching()
                    await asyncio.sleep(5)

                    # Move to active and distribute rewards
                    self.state = RaidState.ACTIVE
                    total_plunder = await self._distribute_rewards()
                    
                    # Announce success
                    await self._announce_raid_success({
                        'total_plunder': total_plunder,
                        'participants': len(self.participants),
                        'multiplier': self.raid_multiplier,
                        'ship_type': self.raid_ship_type
                    })

                    # Move to completed then inactive
                    self.state = RaidState.COMPLETED
                    await asyncio.sleep(2)
                else:
                    logger.info("Insufficient participants - cancelling raid")
                    await self._handle_raid_error()

            except Exception as e:
                logger.error(f"Error ending raid: {e}")
                await self._handle_raid_error()
            finally:
                # Force a state reset at the end
                logger.info("Forcing final state reset")
                self.state = RaidState.INACTIVE
                await self._force_reset()

    async def _force_reset(self):
        """Force reset all raid state"""
        try:
            logger.info("Performing force reset of raid state")
            
            # Cancel any existing recruitment timer
            if hasattr(self, '_recruitment_task') and self._recruitment_task:
                if not self._recruitment_task.done():
                    self._recruitment_task.cancel()
                self._recruitment_task = None

            # Reset all state variables
            self.state = RaidState.INACTIVE
            self.raid_ship_type = None
            self.raid_required_crew = None
            self.raid_start_time = None
            self.raid_viewer_count = None
            self.raid_multiplier = None
            self.participants.clear()
            
            logger.info("Force reset completed - state is now INACTIVE")
            
        except Exception as e:
            logger.error(f"Error during force reset: {e}")
            # Ensure critical state is reset even on error
            self.state = RaidState.INACTIVE
            self.participants.clear()

    async def _check_milestone(self):
        """Check for and handle raid milestones"""
        try:
            participant_count = len(self.participants)
            viewer_count = self.current_raid['viewer_count']
            
            new_multiplier = self._calculate_multiplier(participant_count, viewer_count)
            
            if new_multiplier > self.current_raid.get('multiplier', 1.5):
                is_valid, error_code = self.validator.validate_state_transition(
                    str(self.state),
                    'MILESTONE'
                )
                
                if is_valid:
                    self.current_raid['multiplier'] = new_multiplier
                    self.state = RaidState.MILESTONE
                    await self._announce_milestone(new_multiplier)
                    asyncio.create_task(self._milestone_timer())
                else:
                    logger.warning(f"Invalid state transition to milestone: {error_code}")

        except Exception as e:
            logger.error(f"Error checking milestone: {e}")
            await self.recovery.handle_error(e)
    
    async def _milestone_timer(self):
        """Handle milestone investment window"""
        await asyncio.sleep(30)  # 30 second investment window
        
        async with self._lock:
            if self.state == RaidState.MILESTONE:
                self.state = RaidState.RECRUITING
                await self._announce_recruitment_resumed()

    async def increase_investment(self, user_id: str, additional_amount: int) -> tuple[bool, str]:
        """Handle investment increase with validation"""
        async with self._lock:
            try:
                # Validate increase
                is_valid, error_code = self.validator.validate_investment_increase(
                    user_id,
                    additional_amount,
                    self.participants,
                    str(self.state)
                )
                if not is_valid:
                    return False, ErrorHandler.get_error_message(error_code)

                current_points = await self.bot.points_manager.get_points(user_id)
                is_valid, error_code = self.validator.validate_investment(
                    additional_amount,
                    current_points,
                    self.participants[user_id]['total_investment']
                )
                if not is_valid:
                    return False, ErrorHandler.get_error_message(error_code, {'current_points': current_points})

                # Update investment
                participant = self.participants[user_id]
                participant['total_investment'] += additional_amount

                # Update points
                await self.bot.points_manager.remove_points(
                    user_id,
                    additional_amount,
                    "Raid investment increase"
                )

                await self._announce_investment_increased(
                    participant['username'],
                    additional_amount
                )
                
                return True, f"Investment increased by {additional_amount} points!"

            except Exception as e:
                logger.error(f"Error increasing investment: {e}")
                await self.recovery.handle_error(e)
                return False, "Error increasing investment"

    async def _complete_raid(self):
        """Complete the raid with error handling and reward distribution"""
        try:
            async with self._lock:
                # Log current state for debugging
                logger.info(f"Starting raid completion. Current state: {self.state}")

                # Validate state transition
                is_valid, error_code = self.validator.validate_state_transition(
                    self.state,  # Current state
                    RaidState.LAUNCHING  # Target state
                )
                
                if not is_valid:
                    logger.error(f"Cannot complete raid: Invalid state transition from {self.state} to LAUNCHING")
                    await self._handle_raid_error()
                    return

                # Check if we have enough participants
                if len(self.participants) < self.raid_required_crew:
                    logger.info(f"Not enough participants ({len(self.participants)}/{self.raid_required_crew}). Handling as failed raid.")
                    await self._handle_raid_error()
                    return

                try:
                    # State transition
                    self.state = RaidState.LAUNCHING
                    await self._announce_raid_launching()
                    await asyncio.sleep(5)

                    self.state = RaidState.ACTIVE
                    # Calculate and distribute rewards
                    total_plunder = await self._distribute_rewards()
                    
                    # Announce success
                    await self._announce_raid_success({
                        'total_plunder': total_plunder,
                        'participants': len(self.participants),
                        'multiplier': self.raid_multiplier,
                        'ship_type': self.raid_ship_type
                    })

                    # Move to completed state
                    self.state = RaidState.COMPLETED
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error during raid completion: {e}")
                    await self._handle_raid_error()
                    return

                finally:
                    # Always ensure we reset
                    await self._reset_raid_data()

        except Exception as e:
            logger.error(f"Error in raid completion: {e}")
            await self._handle_raid_error()

    async def _distribute_rewards(self):
        """Handle reward distribution"""
        total_plunder = 0
        participant_rewards = []

        async with self.bot.db.session_scope() as session:
            # Create raid history record
            raid_record = RaidHistory(
                start_time=self.raid_start_time,
                end_time=datetime.now(timezone.utc),
                ship_type=self.raid_ship_type,
                viewer_count=self.raid_viewer_count,
                required_crew=self.raid_required_crew,
                final_crew=len(self.participants),
                final_multiplier=self.raid_multiplier,
                total_plunder=0
            )
            session.add(raid_record)
            await session.flush()

            # Process rewards for each participant
            for user_id, participant in self.participants.items():
                investment = participant['total_investment']
                reward = int(investment * self.raid_multiplier)
                total_plunder += reward
                
                # Record participation and prepare rewards
                participation = RaidParticipant(
                    raid_id=raid_record.id,
                    user_id=user_id,
                    initial_investment=participant['initial_investment'],
                    final_investment=investment,
                    reward=reward
                )
                session.add(participation)
                
                participant_rewards.append({
                    'user_id': user_id,
                    'username': participant['username'],
                    'reward': reward
                })

            # Update total plunder
            raid_record.total_plunder = total_plunder
            await session.commit()

        # Distribute rewards after successful database transaction
        for reward_info in participant_rewards:
            try:
                await self.bot.points_manager.add_points(
                    reward_info['user_id'],
                    reward_info['reward'],
                    f"Raid reward ({self.raid_ship_type})"
                )
            except Exception as e:
                logger.error(f"Error distributing reward to {reward_info['username']}: {e}")

        return total_plunder

    async def _handle_raid_error(self):
        """Handle raid errors and cleanup"""
        try:
            logger.info("Handling raid error and cleaning up")
            
            # Process refunds first
            if self.participants:
                for user_id, participant in self.participants.items():
                    try:
                        await self.bot.points_manager.add_points(
                            user_id,
                            participant['total_investment'],
                            "Raid cancelled - refund"
                        )
                        logger.info(f"Refunded {participant['total_investment']} points to {participant['username']}")
                    except Exception as refund_error:
                        logger.error(f"Error processing refund for {user_id}: {refund_error}")

            # Announce the error
            await self._announce_raid_error()
            
        except Exception as e:
            logger.error(f"Error in raid error handler: {e}")
        finally:
            # Always force reset state
            await self._force_reset()

    def reset_state(self):
        """Explicitly reset all raid state"""
        self.state = RaidState.INACTIVE
        self.current_raid = None
        self.participants.clear()
        logger.info("Raid state explicitly reset")


    def _calculate_multiplier(self, participant_count: int, viewer_count: int) -> float:
        """Calculate reward multiplier based on participation"""
        if viewer_count < 10:
            if participant_count >= 5:
                return 2.0
            elif participant_count >= 3:
                return 1.8
            return 1.5
        else:
            participation_rate = participant_count / viewer_count
            if participation_rate >= 0.5:
                return 2.5
            elif participation_rate >= 0.4:
                return 2.2
            elif participation_rate >= 0.3:
                return 2.0
            elif participation_rate >= 0.2:
                return 1.8
            return 1.5

    async def get_raid_status(self) -> Dict:
        """Get current raid status"""
        try:
            logger.info(f"Getting raid status - Current state: {self.state}, Ship type: {self.raid_ship_type}")
            
            # Check if raid is active based on state instead of current_raid object
            if self.state == RaidState.INACTIVE or not self.raid_ship_type:
                logger.info("No active raid found")
                return {'state': RaidState.INACTIVE}
            
            status = {
                'state': self.state,
                'ship_type': self.raid_ship_type,
                'current_crew': len(self.participants),
                'required_crew': self.raid_required_crew,
                'multiplier': self.raid_multiplier,
                'time_remaining': await self._get_time_remaining()
            }
            logger.info(f"Returning raid status: {status}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting raid status: {e}", exc_info=True)
            return {'state': RaidState.INACTIVE}

    async def _get_time_remaining(self) -> int:
        """Get seconds remaining in current phase"""
        if not self.raid_ship_type or self.state == RaidState.INACTIVE:
            return 0
        
        if self.state == RaidState.RECRUITING:
            elapsed = (datetime.now(timezone.utc) - self.raid_start_time).total_seconds()
            return max(0, 120 - int(elapsed))  # 120 seconds recruitment window
        
        if self.state == RaidState.MILESTONE:
            return 30  # 30-second milestone window
        
        return 0

    async def _get_time_remaining(self) -> int:
        """Get seconds remaining in current phase"""
        if not self.current_raid or self.state == RaidState.INACTIVE:
            return 0
        
        if self.state == RaidState.RECRUITING:
            elapsed = (datetime.now(timezone.utc) - self.current_raid['start_time']).total_seconds()
            return max(0, 120 - int(elapsed))  # 120 seconds recruitment window
        
        if self.state == RaidState.MILESTONE:
            # Find last milestone time and calculate remaining time in 30-second window
            return 30  # Simplified for now
        
        return 0

    async def get_player_stats(self, user_id: str) -> Dict:
        """Get player's raid statistics"""
        async with self.bot.db.session_scope() as session:
            stats = await session.execute(
                select(PlayerRaidStats).where(PlayerRaidStats.user_id == user_id)
            )
            stats = stats.scalar_one_or_none()
            
            if not stats:
                return {
                    'total_raids': 0,
                    'successful_raids': 0,
                    'total_invested': 0,
                    'total_plunder': 0,
                    'biggest_reward': 0
                }
            
            return {
                'total_raids': stats.total_raids,
                'successful_raids': stats.successful_raids,
                'total_invested': stats.total_invested,
                'total_plunder': stats.total_plunder,
                'biggest_reward': stats.biggest_reward
            }

    async def _announce_raid_start(self):
        """Announce the start of a new raid"""
        try:
            await self.bot.raid_messages.announce_raid_start({
                'ship_type': self.raid_ship_type,
                'required_crew': self.raid_required_crew,
                'viewer_count': self.raid_viewer_count
            })

        except Exception as e:
            logger.error(f"Error announcing raid start: {e}")

    async def _check_milestone(self) -> bool:
        """Check if a new milestone has been reached"""
        try:
            participant_count = len(self.participants)
            
            if not hasattr(self, 'milestones'):
                self._setup_milestones()

            for milestone in self.milestones:
                if (participant_count >= milestone['count'] and 
                    self.raid_multiplier < milestone['multiplier']):
                    self.raid_multiplier = milestone['multiplier']
                    await self._announce_milestone(milestone)
                    return True
            
            return False

        except Exception as e:
            logger.error(f"Error checking milestone: {e}")
            return False
        
    def _setup_milestones(self):
        """Setup raid milestones based on viewer count"""
        if self.raid_viewer_count < 10:
            self.milestones = [
                {'count': 3, 'multiplier': 1.8, 'description': "Crew growing stronger!"},
                {'count': 5, 'multiplier': 2.0, 'description': "Full crew assembled!"}
            ]
        else:
            participant_threshold = max(3, int(self.raid_viewer_count * 0.1))
            self.milestones = [
                {'count': participant_threshold, 'multiplier': 1.8, 
                 'description': "Initial crew assembled!"},
                {'count': int(participant_threshold * 1.5), 'multiplier': 2.0,
                 'description': "Strong crew formed!"},
                {'count': int(participant_threshold * 2), 'multiplier': 2.5,
                 'description': "Legendary crew ready!"}
            ]

    async def _announce_milestone(self, milestone: dict):
        """Announce reaching a new milestone"""
        try:
            await self.bot.raid_messages.announce_milestone(
                description=milestone['description'],
                multiplier=milestone['multiplier']
            )
        except Exception as e:
            logger.error(f"Error announcing milestone: {e}")

    async def _announce_recruitment_resumed(self):
        """Announce recruitment phase resuming after milestone"""
        await self.bot.raid_messages.announce_raid_start({
            'ship_type': self.raid_ship_type,
            'current_crew': len(self.participants),
            'required_crew': self.raid_required_crew
        })

    async def _announce_raid_launching(self) -> None:
        """Announce raid launching"""
        try:
            await self.bot.raid_messages.announce_raid_launching({
                'ship_type': self.raid_ship_type,
                'crew_size': len(self.participants),
                'multiplier': self.raid_multiplier
            })
        except Exception as e:
            logger.error(f"Error announcing raid launch: {e}")

    async def _announce_raid_success(self, data: dict) -> None:
        """Announce successful raid completion"""
        try:
            await self.bot.raid_messages.announce_raid_success(data)
        except Exception as e:
            logger.error(f"Error announcing raid success: {e}")
            # Fallback message
            try:
                await self.bot.send_chat_message(
                    f"Raid successful! Total plunder: {data['total_plunder']} points!"
                )
            except Exception as e2:
                logger.error(f"Error sending fallback success message: {e2}")

    async def _announce_raid_error(self) -> None:
        """Announce raid failure or error"""
        try:
            await self.bot.raid_messages.announce_raid_failure({
                'ship_type': self.raid_ship_type
            })
        except Exception as e:
            logger.error(f"Error announcing raid failure: {e}")
            # Fallback message if the fancy announcement fails
            try:
                await self.bot.send_chat_message("Raid cancelled! All investments have been refunded.")
            except Exception as e2:
                logger.error(f"Error sending fallback message: {e2}")

    async def _announce_time_remaining(self, time_remaining: int) -> None:
        """Announce remaining time in raid"""
        try:
            await self.bot.raid_messages.announce_time_remaining(
                time_remaining,
                {
                    'ship_type': self.raid_ship_type,
                    'current_crew': len(self.participants),
                    'required_crew': self.raid_required_crew
                }
            )
        except Exception as e:
            logger.error(f"Error announcing time remaining: {e}")

    async def _announce_player_joined(self, username: str):
        """Announce when a player joins the raid"""
        await self.bot.raid_messages.announce_crew_joined(
            username=username,
            current=len(self.participants),
            needed=self.raid_required_crew
        )

    async def _announce_investment_increased(self, username: str, amount: int):
        """Announce when a player increases their investment"""
        await self.bot.raid_messages.announce_investment_increase(
            username=username,
            amount=amount
        )