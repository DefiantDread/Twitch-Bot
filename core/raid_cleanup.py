# core/raid_cleanup.py

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)

class RaidCleanupManager:
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.cleanup_interval = 300  # 5 minutes
        self.raid_timeout = 300      # 5 minutes
        self.history_retention = 30   # days
        
        # Success criteria for auto-completion
        self.min_participants = 2
        self.min_investment = 500

    async def start(self):
        """Start the cleanup system"""
        if self.is_running:
            return

        self.is_running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Raid cleanup system started")

    async def stop(self):
        """Stop the cleanup system"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Raid cleanup system stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.is_running:
            try:
                # Check for abandoned raids
                await self._cleanup_abandoned_raids()
                
                # Clean up old raid history
                await self._cleanup_raid_history()
                
                # Optimize database tables
                await self._optimize_tables()
                
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)

    async def _cleanup_abandoned_raids(self):
        """Clean up abandoned or stuck raids"""
        try:
            current_raid = self.bot.raid_manager.current_raid
            if not current_raid:
                return

            elapsed = (datetime.now(timezone.utc) - current_raid.start_time).total_seconds()
            
            # Handle different abandoned states
            if elapsed > self.raid_timeout:
                if len(current_raid.participants) >= self.min_participants:
                    # Auto-complete raid if it has enough participation
                    logger.info("Auto-completing timed out raid with sufficient participation")
                    await self._auto_complete_raid(current_raid)
                else:
                    # Cancel and refund raid if insufficient participation
                    logger.info("Canceling timed out raid with insufficient participation")
                    await self._cancel_raid(current_raid, "Raid timed out")

        except Exception as e:
            logger.error(f"Error cleaning up abandoned raids: {e}")

    async def _cleanup_raid_history(self):
        """Clean up old raid history records"""
        try:
            async with self.bot.db.session_scope() as session:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.history_retention)
                
                # Archive old raids to history table
                await session.execute(
                    text("""
                        INSERT INTO raid_history_archive
                        SELECT *
                        FROM raid_history
                        WHERE end_time < :cutoff
                    """),
                    {'cutoff': cutoff}
                )
                
                # Remove old raids from main table
                await session.execute(
                    text("""
                        DELETE FROM raid_history
                        WHERE end_time < :cutoff
                    """),
                    {'cutoff': cutoff}
                )
                
                # Clean up related tables
                await session.execute(
                    text("""
                        DELETE FROM raid_participants
                        WHERE raid_id NOT IN (
                            SELECT id FROM raid_history
                        )
                    """)
                )
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error cleaning up raid history: {e}")

    async def _optimize_tables(self):
        """Optimize database tables periodically"""
        try:
            async with self.bot.db.session_scope() as session:
                # Update statistics for better query planning
                await session.execute(text("ANALYZE raid_history"))
                await session.execute(text("ANALYZE raid_participants"))
                await session.execute(text("ANALYZE player_raid_stats"))
                
                # Remove duplicate entries if any
                await session.execute(
                    text("""
                        DELETE FROM player_raid_stats
                        WHERE rowid NOT IN (
                            SELECT MIN(rowid)
                            FROM player_raid_stats
                            GROUP BY user_id
                        )
                    """)
                )
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error optimizing tables: {e}")

    async def _auto_complete_raid(self, raid_instance) -> bool:
        """Auto-complete a raid that has sufficient participation"""
        try:
            # Calculate rewards
            rewards = raid_instance.get_rewards()
            
            # Distribute rewards
            success = await self.bot.raid_rewards_manager.distribute_rewards(raid_instance)
            if not success:
                await self._cancel_raid(raid_instance, "Failed to distribute rewards")
                return False
            
            # Update raid record
            async with self.bot.db.session_scope() as session:
                await session.execute(
                    text("""
                        UPDATE raid_history
                        SET end_time = :end_time,
                            status = 'auto_completed',
                            total_plunder = :total_plunder
                        WHERE start_time = :start_time
                    """),
                    {
                        'end_time': datetime.now(timezone.utc),
                        'total_plunder': sum(rewards.values()),
                        'start_time': raid_instance.start_time
                    }
                )
                await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error auto-completing raid: {e}")
            return False

    async def _cancel_raid(self, raid_instance, reason: str) -> bool:
        """Cancel a raid and refund participants"""
        try:
            # Process refunds
            refunds = {
                user_id: participant.total_investment
                for user_id, participant in raid_instance.participants.items()
            }
            
            success = await self.bot.raid_points_manager.batch_refund(refunds, reason)
            if not success:
                logger.error("Failed to process refunds for canceled raid")
                return False
            
            # Update raid record
            async with self.bot.db.session_scope() as session:
                await session.execute(
                    text("""
                        UPDATE raid_history
                        SET end_time = :end_time,
                            status = 'canceled',
                            notes = :reason
                        WHERE start_time = :start_time
                    """),
                    {
                        'end_time': datetime.now(timezone.utc),
                        'reason': reason,
                        'start_time': raid_instance.start_time
                    }
                )
                await session.commit()
            
            # Reset raid state
            self.bot.raid_manager.current_raid = None
            self.bot.raid_manager.state = 'INACTIVE'
            
            return True
            
        except Exception as e:
            logger.error(f"Error canceling raid: {e}")
            return False

    async def get_cleanup_stats(self) -> Dict:
        """Get statistics about cleanup operations"""
        try:
            async with self.bot.db.session_scope() as session:
                # Get counts of different raid outcomes
                result = await session.execute(
                    text("""
                        SELECT 
                            status,
                            COUNT(*) as count,
                            AVG(total_plunder) as avg_plunder
                        FROM raid_history
                        WHERE end_time > :cutoff
                        GROUP BY status
                    """),
                    {'cutoff': datetime.now(timezone.utc) - timedelta(days=7)}
                )
                stats = await result.fetchall()
                
                return {
                    'raid_outcomes': {
                        row[0]: {
                            'count': row[1],
                            'avg_plunder': row[2]
                        } for row in stats
                    },
                    'last_cleanup': datetime.now(timezone.utc),
                    'history_retention_days': self.history_retention
                }
                
        except Exception as e:
            logger.error(f"Error getting cleanup stats: {e}")
            return {}