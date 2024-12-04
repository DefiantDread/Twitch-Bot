# utils/monitoring.py
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import psutil
import statistics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self, bot, history_size: int = 1000):
        self.bot = bot
        self.is_running = False
        self.history_size = history_size
        
        # Performance metrics storage
        self.command_timings: Dict[str, deque] = {}
        self.db_query_times: deque = deque(maxlen=history_size)
        self.event_processing_times: deque = deque(maxlen=history_size)
        self.memory_usage: deque = deque(maxlen=history_size)
        self.cpu_usage: deque = deque(maxlen=history_size)
        
        # Process info for resource monitoring
        self.process = psutil.Process()

    async def start_monitoring(self):
        """Start the monitoring loop"""
        if self.is_running:
            return
            
        self.is_running = True
        while self.is_running:
            await self.collect_metrics()
            await asyncio.sleep(5)  # Collect metrics every 5 seconds

    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_running = False

    async def collect_metrics(self):
        """Collect current performance metrics"""
        try:
            # Resource usage
            self.memory_usage.append(self.process.memory_info().rss / 1024 / 1024)  # MB
            self.cpu_usage.append(self.process.cpu_percent())
            
            # Log if resource usage is high
            if self.memory_usage[-1] > 500:  # Warning if over 500MB
                logger.warning(f"High memory usage: {self.memory_usage[-1]:.2f}MB")
            if self.cpu_usage[-1] > 70:  # Warning if over 70%
                logger.warning(f"High CPU usage: {self.cpu_usage[-1]}%")
                
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

    async def record_command_timing(self, command_name: str, execution_time: float):
        """Record command execution time"""
        if command_name not in self.command_timings:
            self.command_timings[command_name] = deque(maxlen=self.history_size)
        self.command_timings[command_name].append(execution_time)

    async def record_db_query(self, query_time: float):
        """Record database query execution time"""
        self.db_query_times.append(query_time)
        if query_time > 1.0:  # Warning if query takes more than 1 second
            logger.warning(f"Slow database query detected: {query_time:.2f}s")

    async def record_event_processing(self, event_name: str, processing_time: float):
        """Record event processing time"""
        self.event_processing_times.append(processing_time)
        if processing_time > 0.5:  # Warning if event processing takes more than 0.5 seconds
            logger.warning(f"Slow event processing detected ({event_name}): {processing_time:.2f}s")

    def get_metrics(self) -> Dict:
        """Get current performance metrics summary"""
        return {
            'memory_usage': {
                'current': self.memory_usage[-1] if self.memory_usage else 0,
                'average': statistics.mean(self.memory_usage) if self.memory_usage else 0,
                'peak': max(self.memory_usage) if self.memory_usage else 0
            },
            'cpu_usage': {
                'current': self.cpu_usage[-1] if self.cpu_usage else 0,
                'average': statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                'peak': max(self.cpu_usage) if self.cpu_usage else 0
            },
            'command_performance': {
                name: {
                    'average': statistics.mean(times) if times else 0,
                    'max': max(times) if times else 0,
                    'count': len(times)
                } for name, times in self.command_timings.items()
            },
            'database_performance': {
                'average_query_time': statistics.mean(self.db_query_times) if self.db_query_times else 0,
                'max_query_time': max(self.db_query_times) if self.db_query_times else 0,
                'total_queries': len(self.db_query_times)
            },
            'event_processing': {
                'average_time': statistics.mean(self.event_processing_times) if self.event_processing_times else 0,
                'max_time': max(self.event_processing_times) if self.event_processing_times else 0,
                'total_events': len(self.event_processing_times)
            }
        }

class TimingContext:
    """Context manager for timing operations"""
    def __init__(self, monitor, operation_type: str, name: str):
        self.monitor = monitor
        self.operation_type = operation_type
        self.name = name
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.monotonic()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.monotonic() - self.start_time
        if self.operation_type == 'command':
            await self.monitor.record_command_timing(self.name, duration)
        elif self.operation_type == 'db_query':
            await self.monitor.record_db_query(duration)
        elif self.operation_type == 'event':
            await self.monitor.record_event_processing(self.name, duration)