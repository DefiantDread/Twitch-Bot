# utils/error_tracker.py
import logging
from datetime import datetime, timezone
import traceback
from typing import Dict, List
import asyncio
from collections import deque

logger = logging.getLogger(__name__)

class ErrorTracker:
    def __init__(self, max_errors: int = 1000):
        self.errors: deque = deque(maxlen=max_errors)
        self.error_counts: Dict[str, int] = {}
        self.lock = asyncio.Lock()

    async def report(self, error: Exception, context: Dict = None) -> None:
        """Report an error with optional context"""
        async with self.lock:
            error_type = type(error).__name__
            error_entry = {
                'type': error_type,
                'message': str(error),
                'timestamp': datetime.now(timezone.utc),
                'context': context or {},
                'traceback': traceback.format_exc()
            }
            
            self.errors.append(error_entry)
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

    async def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get most recent errors"""
        async with self.lock:
            return list(self.errors)[-limit:]

    async def get_error_summary(self) -> Dict:
        """Get error statistics"""
        async with self.lock:
            return {
                'total_errors': len(self.errors),
                'error_counts': dict(self.error_counts),
                'recent_errors': await self.get_recent_errors(5)
            }