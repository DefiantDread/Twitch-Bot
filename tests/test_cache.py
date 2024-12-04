# tests/test_cache.py
import pytest
import asyncio
import time
from utils.cache_manager import CacheManager, cached

@pytest.mark.asyncio
async def test_cache_basic_operations():
    """Test basic cache operations"""
    cache = CacheManager(default_ttl=60)
    
    # Test set and get
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value"
    
    # Test delete
    await cache.delete("test_key")
    value = await cache.get("test_key")
    assert value is None

@pytest.mark.asyncio
async def test_cache_expiration():
    """Test cache expiration"""
    cache = CacheManager(default_ttl=1)  # 1 second TTL
    
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value"
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    value = await cache.get("test_key")
    assert value is None

@pytest.mark.asyncio
async def test_cache_cleanup():
    """Test cache cleanup"""
    cache = CacheManager(default_ttl=1)
    
    # Add some items
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    
    assert len(cache.cache) == 2
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    await cache.cleanup()
    
    assert len(cache.cache) == 0

# Test the cached decorator
class MockDB:
    def __init__(self):
        self.cache_manager = CacheManager()
        self.call_count = 0

    @cached(ttl=1)
    async def expensive_operation(self, key):
        self.call_count += 1
        return f"result_{key}"

@pytest.mark.asyncio
async def test_cached_decorator():
    """Test the cached decorator"""
    db = MockDB()
    
    # First call should hit the database
    result1 = await db.expensive_operation("test")
    assert result1 == "result_test"
    assert db.call_count == 1
    
    # Second call should use cache
    result2 = await db.expensive_operation("test")
    assert result2 == "result_test"
    assert db.call_count == 1
    
    # Wait for cache expiration
    await asyncio.sleep(1.1)
    
    # This call should hit the database again
    result3 = await db.expensive_operation("test")
    assert result3 == "result_test"
    assert db.call_count == 2