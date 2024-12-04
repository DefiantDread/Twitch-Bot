# utils/query_profiler.py
import time
import logging
from functools import wraps
from typing import Optional

logger = logging.getLogger(__name__)

def profile_query(threshold_ms: Optional[int] = 100):
    """Decorator to profile query execution time"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                if threshold_ms and execution_time > threshold_ms:
                    logger.warning(
                        f"Slow query detected in {func.__name__}: "
                        f"{execution_time:.2f}ms (threshold: {threshold_ms}ms)"
                    )
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"Query error in {func.__name__}: {str(e)} "
                    f"after {execution_time:.2f}ms"
                )
                raise
        return wrapper
    return decorator