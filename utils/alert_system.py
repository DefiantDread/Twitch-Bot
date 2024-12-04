# utils/alert_system.py
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class AlertThreshold:
    warning: float
    critical: float
    cooldown: int  # seconds between repeated alerts

class AlertManager:
    def __init__(self, bot):
        self.bot = bot
        self.alert_history: Dict[str, datetime] = {}
        self.alert_handlers: List[Callable] = []
        self.is_running = False
        
        # Define default thresholds
        self.thresholds = {
            'query_time': AlertThreshold(warning=100, critical=500, cooldown=300),
            'cpu_usage': AlertThreshold(warning=70, critical=90, cooldown=600),
            'memory_usage': AlertThreshold(warning=80, critical=95, cooldown=600),
            'error_rate': AlertThreshold(warning=5, critical=15, cooldown=300),
            'connection_pool': AlertThreshold(warning=80, critical=95, cooldown=300),
        }

    async def start_monitoring(self):
        """Start alert monitoring"""
        if self.is_running:
            return
            
        self.is_running = True
        while self.is_running:
            await self.check_all_metrics()
            await asyncio.sleep(60)  # Check every minute

    async def check_all_metrics(self):
        """Check all monitored metrics"""
        try:
            # Get current metrics
            performance_metrics = await self.bot.db.get_performance_metrics()
            pool_status = await self.bot.db.get_pool_status()

            # Check query performance
            for query_name, metrics in performance_metrics['query_metrics'].items():
                if await self._should_alert('query_time', query_name):
                    if metrics['avg_time'] > self.thresholds['query_time'].critical:
                        await self.trigger_alert(
                            'query_performance',
                            f"Critical query performance: {query_name} ({metrics['avg_time']:.2f}ms)",
                            AlertSeverity.CRITICAL,
                            metrics
                        )
                    elif metrics['avg_time'] > self.thresholds['query_time'].warning:
                        await self.trigger_alert(
                            'query_performance',
                            f"Slow query detected: {query_name} ({metrics['avg_time']:.2f}ms)",
                            AlertSeverity.WARNING,
                            metrics
                        )

            # Check resource usage
            cpu_usage = performance_metrics['resource_usage']['cpu_avg']
            if cpu_usage > self.thresholds['cpu_usage'].critical:
                await self.trigger_alert(
                    'cpu_usage',
                    f"Critical CPU usage: {cpu_usage:.1f}%",
                    AlertSeverity.CRITICAL,
                    {'cpu_usage': cpu_usage}
                )
            elif cpu_usage > self.thresholds['cpu_usage'].warning:
                await self.trigger_alert(
                    'cpu_usage',
                    f"High CPU usage: {cpu_usage:.1f}%",
                    AlertSeverity.WARNING,
                    {'cpu_usage': cpu_usage}
                )

            # Check connection pool
            pool_usage = (pool_status['checkedout'] / pool_status['size']) * 100
            if pool_usage > self.thresholds['connection_pool'].critical:
                await self.trigger_alert(
                    'connection_pool',
                    f"Critical connection pool usage: {pool_usage:.1f}%",
                    AlertSeverity.CRITICAL,
                    pool_status
                )
            elif pool_usage > self.thresholds['connection_pool'].warning:
                await self.trigger_alert(
                    'connection_pool',
                    f"High connection pool usage: {pool_usage:.1f}%",
                    AlertSeverity.WARNING,
                    pool_status
                )

        except Exception as e:
            logger.error(f"Error in alert monitoring: {e}")

    async def trigger_alert(self, alert_type: str, message: str, 
                          severity: AlertSeverity, context: Dict):
        """Trigger an alert with given severity and context"""
        if not await self._should_alert(alert_type, message):
            return

        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now(timezone.utc),
            'context': context
        }

        # Log alert
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.critical
        }[severity]
        
        log_method(f"Alert: {message}")

        # Notify all handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}")

        # Update alert history
        self.alert_history[f"{alert_type}:{message}"] = datetime.now(timezone.utc)

    async def _should_alert(self, alert_type: str, key: str) -> bool:
        """Check if we should trigger an alert based on cooldown"""
        history_key = f"{alert_type}:{key}"
        if history_key not in self.alert_history:
            return True

        last_alert = self.alert_history[history_key]
        cooldown = self.thresholds[alert_type].cooldown
        return (datetime.now(timezone.utc) - last_alert).total_seconds() > cooldown

    def add_alert_handler(self, handler: Callable):
        """Add a new alert handler"""
        self.alert_handlers.append(handler)

    async def stop_monitoring(self):
        """Stop alert monitoring"""
        self.is_running = False