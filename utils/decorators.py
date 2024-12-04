# utils/decorators.py
import functools
import logging
from typing import Type, Union, Callable
import traceback
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def error_boundary(error_types: Union[Type[Exception], tuple] = Exception,
                  retries: int = 0,
                  log_message: str = "Error in {func_name}"):
    """
    Decorator that creates an error boundary around async functions.
    Handles errors, logging, and optional retries.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = retries + 1
            last_error = None

            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except error_types as e:
                    last_error = e
                    error_details = {
                        'function': func.__name__,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'timestamp': datetime.now(timezone.utc),
                        'attempt': attempt + 1,
                        'traceback': traceback.format_exc()
                    }
                    
                    logger.error(
                        log_message.format(func_name=func.__name__),
                        extra=error_details
                    )
                    
                    if attempt < attempts - 1:
                        logger.info(f"Retrying {func.__name__} (attempt {attempt + 2}/{attempts})")
                    else:
                        logger.error(f"All retries failed for {func.__name__}")
            
            # If we get here, all retries failed
            raise last_error
    
        return wrapper
    return decorator

def rate_limited(cooldown: int = 3, global_cooldown: int = 1, mod_bypass: bool = True):
    """
    Decorator to apply rate limiting to commands.
    cooldown: per-user cooldown in seconds
    global_cooldown: global cooldown in seconds
    mod_bypass: whether moderators bypass cooldowns
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            # Mods bypass cooldown if enabled
            if mod_bypass and ctx.author.is_mod:
                return await func(self, ctx, *args, **kwargs)

            can_execute, wait_time = await self.bot.rate_limiter.can_execute(
                func.__name__,
                str(ctx.author.id),
                cooldown,
                global_cooldown
            )

            if not can_execute:
                await ctx.send(f"@{ctx.author.name} Please wait {wait_time:.1f} seconds before using this command again.")
                return

            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator