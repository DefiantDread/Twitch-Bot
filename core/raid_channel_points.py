# core/raid_channel_points.py

import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class RaidReward:
    id: str
    name: str
    cost: int
    description: str
    cooldown: int  # seconds
    is_enabled: bool = True
    
@dataclass
class RewardEffect:
    multiplier: float
    duration: int  # seconds
    stack: bool = False

class RaidRewardManager:
    def __init__(self, bot):
        self.bot = bot
        self._active_effects: Dict[str, List[RewardEffect]] = {}
        self.rewards = self._setup_rewards()
        
    def _setup_rewards(self) -> Dict[str, RaidReward]:
        return {
            'boost_multiplier': RaidReward(
                id='raid_multiplier_boost',
                name='Boost Raid Multiplier',
                cost=5000,
                description='Increases raid multiplier by 0.2x for 60 seconds',
                cooldown=300
            ),
            'extend_time': RaidReward(
                id='raid_time_extension',
                name='Extend Raid Time',
                cost=3000,
                description='Adds 30 seconds to the current raid phase',
                cooldown=180
            ),
            'double_investment': RaidReward(
                id='double_investment',
                name='Double Investment Power',
                cost=8000,
                description='Next investment counts double towards raid progress',
                cooldown=600
            ),
            'instant_milestone': RaidReward(
                id='instant_milestone',
                name='Trigger Milestone',
                cost=10000,
                description='Instantly triggers next raid milestone if requirements are met',
                cooldown=900
            ),
            'bonus_plunder': RaidReward(
                id='bonus_plunder',
                name='Bonus Plunder',
                cost=7000,
                description='Adds 20% bonus plunder to final raid rewards',
                cooldown=600
            )
        }

    async def handle_reward_redemption(
        self,
        reward_id: str,
        user_id: str,
        raid_instance
    ) -> bool:
        """Handle channel point reward redemption"""
        try:
            if reward_id not in self.rewards:
                return False
                
            reward = self.rewards[reward_id]
            if not reward.is_enabled:
                return False

            # Handle specific rewards
            if reward_id == 'boost_multiplier':
                return await self._handle_multiplier_boost(raid_instance)
            elif reward_id == 'extend_time':
                return await self._handle_time_extension(raid_instance)
            elif reward_id == 'double_investment':
                return await self._handle_double_investment(user_id)
            elif reward_id == 'instant_milestone':
                return await self._handle_instant_milestone(raid_instance)
            elif reward_id == 'bonus_plunder':
                return await self._handle_bonus_plunder(raid_instance)
                
            return False

        except Exception as e:
            logger.error(f"Error handling reward redemption: {e}")
            return False

    async def _handle_multiplier_boost(self, raid_instance) -> bool:
        """Handle multiplier boost reward"""
        try:
            if raid_instance.state not in ['RECRUITING', 'MILESTONE']:
                return False
                
            effect = RewardEffect(
                multiplier=0.2,
                duration=60,
                stack=True
            )
            
            raid_instance.current_multiplier += effect.multiplier
            self._add_effect('multiplier_boost', effect)
            
            await self.bot.raid_messages.announce_reward_effect(
                f"Raid multiplier increased by 0.2x! "
                f"Current multiplier: {raid_instance.current_multiplier}x"
            )
            
            return True

        except Exception as e:
            logger.error(f"Error handling multiplier boost: {e}")
            return False

    async def _handle_time_extension(self, raid_instance) -> bool:
        """Handle time extension reward"""
        try:
            if raid_instance.state not in ['RECRUITING', 'MILESTONE']:
                return False
                
            # Add 30 seconds to current phase
            raid_instance.extend_time(30)
            
            await self.bot.raid_messages.announce_reward_effect(
                "Raid time extended by 30 seconds!"
            )
            
            return True

        except Exception as e:
            logger.error(f"Error handling time extension: {e}")
            return False

    async def _handle_double_investment(self, user_id: str) -> bool:
        """Handle double investment reward"""
        try:
            effect = RewardEffect(
                multiplier=2.0,
                duration=120,  # 2 minutes to use it
                stack=False
            )
            
            self._add_effect(f'double_investment_{user_id}', effect)
            
            await self.bot.raid_messages.announce_reward_effect(
                f"@{user_id} next investment will count double! "
                f"Valid for 2 minutes."
            )
            
            return True

        except Exception as e:
            logger.error(f"Error handling double investment: {e}")
            return False

    async def _handle_instant_milestone(self, raid_instance) -> bool:
        """Handle instant milestone reward"""
        try:
            if raid_instance.state not in ['RECRUITING']:
                return False
                
            milestone = raid_instance.check_milestone()
            if not milestone:
                return False
                
            raid_instance.trigger_milestone(milestone)
            
            await self.bot.raid_messages.announce_reward_effect(
                f"Raid milestone triggered! New multiplier: {raid_instance.current_multiplier}x"
            )
            
            return True

        except Exception as e:
            logger.error(f"Error handling instant milestone: {e}")
            return False

    async def _handle_bonus_plunder(self, raid_instance) -> bool:
        """Handle bonus plunder reward"""
        try:
            effect = RewardEffect(
                multiplier=1.2,
                duration=None,  # Lasts until raid end
                stack=False
            )
            
            self._add_effect('bonus_plunder', effect)
            
            await self.bot.raid_messages.announce_reward_effect(
                "20% bonus plunder will be added to final rewards!"
            )
            
            return True

        except Exception as e:
            logger.error(f"Error handling bonus plunder: {e}")
            return False

    def _add_effect(self, effect_id: str, effect: RewardEffect):
        """Add an active effect"""
        if effect_id not in self._active_effects:
            self._active_effects[effect_id] = []
            
        if effect.stack or not self._active_effects[effect_id]:
            self._active_effects[effect_id].append(effect)

    async def check_effects(self) -> None:
        """Check and clean up expired effects"""
        current_time = datetime.now()
        
        for effect_id, effects in list(self._active_effects.items()):
            # Remove expired effects
            self._active_effects[effect_id] = [
                effect for effect in effects
                if not effect.duration or (
                    hasattr(effect, 'start_time') and
                    current_time - effect.start_time < timedelta(seconds=effect.duration)
                )
            ]
            
            # Remove empty effect lists
            if not self._active_effects[effect_id]:
                del self._active_effects[effect_id]

    def get_active_effects(self) -> Dict[str, List[RewardEffect]]:
        """Get currently active effects"""
        return self._active_effects.copy()

    async def cleanup(self) -> None:
        """Clean up all effects"""
        self._active_effects.clear()