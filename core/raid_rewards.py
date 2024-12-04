# core/raid_rewards.py
import logging
import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text
from core.raid_states import RaidState


logger = logging.getLogger(__name__)

class RaidRewardManager:
    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    async def distribute_rewards(self, raid_instance):
        """Distribute rewards to raid participants."""
        # Log the raid state for debugging
        logger.debug(f"Raid state: {raid_instance.state}")

        # Check for valid raid state
        if raid_instance.state != RaidState.ACTIVE:
            logger.warning(f"Cannot distribute rewards. Invalid state: {raid_instance.state}")
            return False, f"Invalid state: {raid_instance.state}. Cannot distribute rewards."

        if not raid_instance.participants:
            logger.warning("No participants in the raid. Rewards cannot be distributed.")
            return False, "No participants in the raid. Rewards cannot be distributed."

        try:
            rewards = raid_instance.get_rewards()
            for user_id, reward in rewards.items():
                await self.bot.points_manager.add_points(
                    user_id,
                    reward,
                    f"Raid reward ({raid_instance.ship_type})"
                )
            return True, "Rewards distributed successfully."
        except Exception as e:
            logger.error(f"Error distributing rewards: {e}")
            return False, f"Error: {str(e)}"
        
    async def _record_raid_history(self, session, raid_instance) -> Optional[int]:
        """Record raid history and return raid_id"""
        try:
            result = await session.execute(
                text("""
                    INSERT INTO raid_history (
                        start_time, end_time, ship_type, viewer_count,
                        required_crew, final_crew, final_multiplier, total_plunder
                    ) VALUES (
                        :start_time, :end_time, :ship_type, :viewer_count,
                        :required_crew, :final_crew, :final_multiplier, :total_plunder
                    ) RETURNING id
                """),
                {
                    'start_time': raid_instance.start_time,
                    'end_time': datetime.now(timezone.utc),
                    'ship_type': raid_instance.ship_type,
                    'viewer_count': len(raid_instance.participants),
                    'required_crew': raid_instance.required_crew,
                    'final_crew': len(raid_instance.participants),
                    'final_multiplier': raid_instance.current_multiplier,
                    'total_plunder': sum(raid_instance.get_rewards().values())
                }
            )
            row = await result.first()
            return row[0] if row else None
            
        except Exception as e:
            logger.error(f"Error recording raid history: {e}")
            return None

    async def _record_participants(self, session, raid_id: int, raid_instance, rewards: Dict[str, int]):
        """Record all participant data"""
        for user_id, participant in raid_instance.participants.items():
            await session.execute(
                text("""
                    INSERT INTO raid_participants (
                        raid_id, user_id, initial_investment,
                        final_investment, reward
                    ) VALUES (
                        :raid_id, :user_id, :initial_investment,
                        :final_investment, :reward
                    )
                """),
                {
                    'raid_id': raid_id,
                    'user_id': user_id,
                    'initial_investment': participant.initial_investment,
                    'final_investment': participant.total_investment,
                    'reward': rewards[user_id]
                }
            )

    async def _update_player_stats(self, session, raid_instance, rewards: Dict[str, int]):
        """Update player raid statistics"""
        for user_id, reward in rewards.items():
            participant = raid_instance.participants[user_id]
            await session.execute(
                text("""
                    INSERT INTO player_raid_stats (
                        user_id, total_raids, successful_raids,
                        total_invested, total_plunder, biggest_reward
                    ) VALUES (
                        :user_id, 1, 1,
                        :investment, :reward, :reward
                    )
                    ON CONFLICT (user_id) DO UPDATE SET
                        total_raids = player_raid_stats.total_raids + 1,
                        successful_raids = player_raid_stats.successful_raids + 1,
                        total_invested = player_raid_stats.total_invested + :investment,
                        total_plunder = player_raid_stats.total_plunder + :reward,
                        biggest_reward = GREATEST(player_raid_stats.biggest_reward, :reward)
                """),
                {
                    'user_id': user_id,
                    'investment': participant.total_investment,
                    'reward': reward
                }
            )