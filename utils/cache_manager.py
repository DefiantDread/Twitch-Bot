# utils/cache_manager.py
import time
import logging
from typing import Any, Dict, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, default_ttl: int = 300):  # 5 minutes default TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache if it exists and hasn't expired"""
        if key not in self.cache:
            return None

        cache_data = self.cache[key]
        if time.time() > cache_data['expires']:
            await self.delete(key)
            return None

        return cache_data['value']

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set item in cache with expiration"""
        async with self.lock:
            self.cache[key] = {
                'value': value,
                'expires': time.time() + (ttl or self.default_ttl)
            }

    async def delete(self, key: str) -> None:
        """Remove item from cache"""
        async with self.lock:
            self.cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cached items"""
        async with self.lock:
            self.cache.clear()

    async def cleanup(self) -> None:
        """Remove expired items from cache"""
        async with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, data in self.cache.items()
                if current_time > data['expires']
            ]
            for key in expired_keys:
                self.cache.pop(key)

def cached(ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Generate cache key from function name and arguments
            key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try to get from cache first
            cached_value = await self.cache_manager.get(key)
            if cached_value is not None:
                return cached_value

            # If not in cache, execute function
            result = await func(self, *args, **kwargs)
            
            # Store in cache
            await self.cache_manager.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator