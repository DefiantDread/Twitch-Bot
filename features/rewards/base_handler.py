# features/rewards/base_handler.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable, Any
import logging
import random
import asyncio
from utils.decorators import error_boundary

logger = logging.getLogger(__name__)

class BaseRewardHandler(ABC):
    def __init__(self, bot):
        self.bot = bot
        self.messages: Dict[str, list[str]] = {}
        self.handlers: Dict[str, Callable] = {}
        self._setup_messages()
        self._setup_handlers()

    @abstractmethod
    def _setup_messages(self) -> None:
        """Set up message templates for this handler"""
        pass

    @abstractmethod
    def _setup_handlers(self) -> None:
        """Set up reward handlers"""
        pass

    async def handle_reward(self, ctx, reward_id: str, user: str, input_text: str) -> None:
        """Main reward handling method with error handling"""
        try:
            handler = self.handlers.get(reward_id)
            if not handler:
                logger.warning(f"No handler found for reward {reward_id}")
                await ctx.send(f"@{user} This reward is not configured.")
                return

            await handler(ctx, user, input_text)

            # Track analytics if available
            if hasattr(self.bot, 'analytics'):
                await self.bot.analytics.log_reward(reward_id)
        except Exception as e:
            logger.error(f"Error handling reward {reward_id}: {str(e)}")
            await self.handle_error(ctx, user, reward_id, e)

    async def handle_error(self, ctx, user: str, reward_id: str, error: Exception) -> None:
        """Handle errors during reward processing"""
        try:
            error_message = f"@{user} Sorry, there was an error processing your reward."
            if isinstance(error, ValueError):
                error_message = f"@{user} {str(error)}"
            await ctx.send(error_message)
        except Exception as e:
            logger.error(f"Error sending error message: {e}")

    async def send_random_message(self, ctx, message_key: str, **kwargs) -> None:
        """Send a random message from the specified template"""
        try:
            messages = self.messages.get(message_key)
            if not messages:
                logger.error(f"Message key '{message_key}' not found")
                await ctx.send("Action completed!")  # Fallback message
                return

            # Only send one message if the key exists
            message = random.choice(messages)
            await ctx.send(message.format(**kwargs))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            if not messages:  # Only send fallback if no messages were available
                await ctx.send("Action completed!")


    def validate_input(self, input_text: str, min_length: int = 0, max_length: int = 500) -> str:
        """Validate user input"""
        input_text = input_text.strip()
        if not input_text or len(input_text) < min_length:
            raise ValueError("Please provide valid input.")
        if len(input_text) > max_length:
            raise ValueError(f"Input too long (max {max_length} characters).")
        return input_text