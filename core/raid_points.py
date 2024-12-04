# core/raid_points.py
import logging
import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RaidPointsManager:
    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.min_investment = 100
        self.max_investment = 1000
        self.max_total_investment = 2000

    async def process_investment(self, user_id: str, amount: int) -> Tuple[bool, str]:
        """Process initial raid investment with validation"""
        if not self._validate_investment_amount(amount):
            return False, f"Investment must be between {self.min_investment} and {self.max_investment} points"

        async with self._lock:
            async with self.bot.db.session_scope() as session:
                try:
                    current_points = await self.bot.points_manager.get_points(user_id)
                    if current_points < amount:
                        return False, f"Not enough points (You have: {current_points})"

                    # Remove points
                    success = await self.bot.points_manager.remove_points(
                        user_id, amount, "Raid investment"
                    )

                    if not success:
                        return False, "Failed to process investment"

                    # Simulate successful transaction
                    await session.commit()
                    return True, "Investment processed successfully"

                except Exception as e:
                    logger.error(f"Error processing investment: {e}")

                    # Rollback the transaction
                    await session.rollback()
                    
                    # Attempt refund if points were removed
                    await self.refund_investment(user_id, amount, str(e))
                    return False, f"Error processing investment: {str(e)}"

    async def get_investment_stats(self, user_id: str) -> Dict:
        """Get user's raid investment statistics."""
        try:
            async with self.bot.db.session_scope() as session:
                query = text("""
                    SELECT 
                        COALESCE(SUM(final_investment), 0) as total_invested,
                        COALESCE(SUM(reward), 0) as total_rewards,
                        COUNT(*) as total_raids
                    FROM raid_participants
                    WHERE user_id = :user_id
                """)
                result = await session.execute(query, {'user_id': user_id})
                row = await result.fetchone()  # Await here to fix the issue

                if not row:
                    return {
                        'total_invested': 0,
                        'total_rewards': 0,
                        'total_raids': 0,
                        'roi': 0
                    }

                total_invested, total_rewards, total_raids = row
                roi = ((total_rewards - total_invested) / total_invested) if total_invested > 0 else 0

                return {
                    'total_invested': total_invested,
                    'total_rewards': total_rewards,
                    'total_raids': total_raids,
                    'roi': roi
                }

        except Exception as e:
            logger.error(f"Error fetching investment stats: {e}")
            return {
                'total_invested': 0,
                'total_rewards': 0,
                'total_raids': 0,
                'roi': 0
            }


    def _validate_investment_amount(self, amount: int) -> bool:
        """Validate investment amount"""
        try:
            amount = int(amount)
            return self.min_investment <= amount <= self.max_investment
        except (TypeError, ValueError):
            return False

    async def refund_investment(self, user_id: str, amount: int, reason: str) -> bool:
        """Refund points in case of raid failure or cancellation"""
        try:
            return await self.bot.points_manager.add_points(
                user_id,
                amount,
                f"Raid refund: {reason}"
            )
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return False