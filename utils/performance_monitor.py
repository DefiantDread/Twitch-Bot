# utils/performance_monitor.py
import time
import logging
import asyncio
import psutil
from datetime import datetime, timedelta, timezone
from collections import deque
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QueryMetrics:
    total_time: float
    count: int
    avg_time: float
    max_time: float
    min_time: float
    last_slow_query: Optional[datetime]

class PerformanceTracker:
    def __init__(self, history_size: int = 1000, alert_threshold_ms: int = 100):
        self.history_size = history_size
        self.alert_threshold_ms = alert_threshold_ms
        
        # Query performance tracking
        self.query_history: Dict[str, deque] = {}
        self.query_metrics: Dict[str, QueryMetrics] = {}
        
        # Resource tracking
        self.cpu_usage = deque(maxlen=history_size)
        self.memory_usage = deque(maxlen=history_size)
        self.io_counters = deque(maxlen=history_size)
        
        # Bottleneck detection
        self.bottleneck_points: List[Dict] = []
        self.process = psutil.Process()

    async def track_query(self, query_name: str, execution_time: float):
        """Record query execution time and check for bottlenecks"""
        if query_name not in self.query_history:
            self.query_history[query_name] = deque(maxlen=self.history_size)
        
        self.query_history[query_name].append(execution_time)
        await self._update_query_metrics(query_name)
        
        if execution_time > self.alert_threshold_ms:
            await self._record_bottleneck(query_name, execution_time)

    async def _update_query_metrics(self, query_name: str):
        """Update query performance metrics"""
        times = list(self.query_history[query_name])
        if not times:
            return

        self.query_metrics[query_name] = QueryMetrics(
            total_time=sum(times),
            count=len(times),
            avg_time=sum(times) / len(times),
            max_time=max(times),
            min_time=min(times),
            last_slow_query=datetime.now(timezone.utc) if times[-1] > self.alert_threshold_ms else None
        )

    async def _record_bottleneck(self, query_name: str, execution_time: float):
        """Record performance bottleneck with context"""
        bottleneck = {
            'timestamp': datetime.now(timezone.utc),
            'query_name': query_name,
            'execution_time': execution_time,
            'cpu_usage': self.process.cpu_percent(),
            'memory_usage': self.process.memory_info().rss / 1024 / 1024,
            'context': await self._get_system_context()
        }
        
        self.bottleneck_points.append(bottleneck)
        logger.warning(f"Performance bottleneck detected: {bottleneck}")

    async def _get_system_context(self) -> Dict:
        """Get system context for bottleneck analysis"""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_available': psutil.virtual_memory().available / 1024 / 1024,
            'disk_io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else None,
            'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else None
        }

    async def get_performance_report(self) -> Dict:
        """Generate comprehensive performance report"""
        return {
            'query_metrics': {
                name: {
                    'avg_time': metrics.avg_time,
                    'max_time': metrics.max_time,
                    'total_queries': metrics.count,
                    'slow_queries': sum(1 for t in self.query_history[name] if t > self.alert_threshold_ms)
                }
                for name, metrics in self.query_metrics.items()
            },
            'resource_usage': {
                'cpu_avg': sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
                'memory_avg': sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
            },
            'bottlenecks': self.bottleneck_points[-10:],  # Last 10 bottlenecks
            'system_health': await self._get_system_context()
        }

    async def analyze_trends(self) -> Dict:
        """Analyze performance trends and provide recommendations"""
        recommendations = []
        
        # Analyze query patterns
        for query_name, metrics in self.query_metrics.items():
            if metrics.avg_time > self.alert_threshold_ms / 2:
                recommendations.append({
                    'type': 'query_optimization',
                    'target': query_name,
                    'reason': f'High average execution time: {metrics.avg_time:.2f}ms',
                    'suggestion': 'Consider adding indexes or optimizing query structure'
                })

        # Analyze resource usage
        if any(cpu > 80 for cpu in self.cpu_usage):
            recommendations.append({
                'type': 'resource_optimization',
                'target': 'cpu',
                'reason': 'High CPU usage detected',
                'suggestion': 'Consider implementing caching or query optimization'
            })

        return {
            'recommendations': recommendations,
            'trend_analysis': {
                'performance_degradation': self._detect_degradation(),
                'resource_pressure': self._analyze_resource_pressure()
            }
        }

    def _detect_degradation(self) -> Dict:
        """Detect performance degradation patterns"""
        degradation = {}
        for query_name, history in self.query_history.items():
            if len(history) < 10:
                continue
            
            recent = list(history)[-10:]
            older = list(history)[:-10]
            if recent and older:
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older)
                if recent_avg > older_avg * 1.2:  # 20% degradation
                    degradation[query_name] = {
                        'recent_avg': recent_avg,
                        'historical_avg': older_avg,
                        'degradation_pct': ((recent_avg - older_avg) / older_avg) * 100
                    }
        
        return degradation

    def _analyze_resource_pressure(self) -> Dict:
        """Analyze resource usage patterns"""
        return {
            'cpu_pressure': any(cpu > 80 for cpu in self.cpu_usage),
            'memory_pressure': any(mem > 85 for mem in self.memory_usage),
            'sustained_high_load': self._check_sustained_load()
        }

    def _check_sustained_load(self) -> bool:
        """Check for sustained high resource usage"""
        if len(self.cpu_usage) < 10:
            return False
            
        recent_cpu = list(self.cpu_usage)[-10:]
        return sum(cpu > 70 for cpu in recent_cpu) >= 7  # 70% high load for 7 out of 10 samples