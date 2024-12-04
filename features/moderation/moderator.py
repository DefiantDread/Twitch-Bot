# features/moderation/moderator.py
from sqlalchemy import text
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TimeoutInfo:
    user_id: str
    moderator: str
    reason: str
    duration: int
    timestamp: datetime

class ModerationManager:
    def __init__(self, bot):
        self.bot = bot
        self.timeout_history: Dict[str, List[TimeoutInfo]] = {}
        self.banned_phrases: List[str] = []
        self.user_warnings: Dict[str, int] = {}
        self.caps_threshold = 0.7
        self.spam_threshold = 3
        self.message_history: Dict[str, List[str]] = {}

    async def load_banned_phrases(self):
        """Load banned phrases from database"""
        try:
            async with self.bot.db.session_scope() as session:
                result = await session.execute(
                    text("SELECT phrase FROM banned_phrases WHERE enabled = TRUE")
                )
                # Use the result's scalars() method instead of fetchall()
                self.banned_phrases = [row[0] for row in result.all()]
                logger.info(f"Loaded {len(self.banned_phrases)} banned phrases")
        except Exception as e:
            logger.error(f"Error loading banned phrases: {e}")
            # Set empty list as fallback
            self.banned_phrases = []

    async def add_banned_phrase(self, phrase: str, moderator: str):
        """Add a new banned phrase"""
        try:
            async with self.bot.db.session_scope() as session:
                await session.execute(
                    text("""
                        INSERT INTO banned_phrases (phrase, enabled, created_by) 
                        VALUES (:phrase, TRUE, :moderator)
                    """),
                    {'phrase': phrase.lower(), 'moderator': moderator}
                )
                await session.commit()
                await self.load_banned_phrases()
                logger.info(f"Added banned phrase: {phrase} by {moderator}")
                return True
        except Exception as e:
            logger.error(f"Error adding banned phrase: {e}")
            return False

    async def remove_banned_phrase(self, phrase: str):
        """Remove a banned phrase"""
        try:
            async with self.bot.db.session_scope() as session:
                await session.execute(
                    text("UPDATE banned_phrases SET enabled = FALSE WHERE phrase = :phrase"),
                    {'phrase': phrase.lower()}
                )
                await session.commit()
                await self.load_banned_phrases()
                logger.info(f"Removed banned phrase: {phrase}")
                return True
        except Exception as e:
            logger.error(f"Error removing banned phrase: {e}")
            return False

    async def check_message(self, message) -> Optional[str]:
        """Check message against moderation rules"""
        if not message.content:
            return None
            
        content = message.content.lower()
        user_id = str(message.author.id)

        # Check banned phrases if any exist
        if self.banned_phrases and any(phrase in content for phrase in self.banned_phrases):
            return "banned phrase"

        # Check caps
        if len(message.content) > 10:
            caps_ratio = sum(1 for c in message.content if c.isupper()) / len(message.content)
            if caps_ratio > self.caps_threshold:
                return "excessive caps"

        # Check spam
        if user_id not in self.message_history:
            self.message_history[user_id] = []
        
        self.message_history[user_id].append(content)
        if len(self.message_history[user_id]) > self.spam_threshold:
            self.message_history[user_id].pop(0)
            
        if len(self.message_history[user_id]) == self.spam_threshold:
            if all(msg == content for msg in self.message_history[user_id]):
                return "spam"

        return None

    async def handle_message_moderation(self, message):
        """Handle message moderation"""
        try:
            if message.author.is_mod:
                return

            violation = await self.check_message(message)
            if violation:
                user_id = str(message.author.id)
                warning_count = await self.warn_user(user_id)
                
                # Escalating timeout durations
                duration = 300 * warning_count  # 5 minutes * warning count
                
                await message.delete()
                await self.timeout_user(
                    user_id,
                    "Bot",
                    duration,
                    f"AutoMod: {violation} (Warning #{warning_count})"
                )
                
                await message.channel.send(
                    f"@{message.author.name} message deleted for {violation}. "
                    f"Warning #{warning_count}. Timeout: {duration//60} minutes."
                )
        except Exception as e:
            logger.error(f"Error in message moderation: {e}")