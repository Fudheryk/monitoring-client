# src/collectors/builtin/__init__.py
from .databases import DatabasesCollector
from .docker import DockerCollector
from .firewall import FirewallCollector
from .log_anomalies import LogAnomaliesCollector
from .network import NetworkCollector
from .scheduled_tasks import ScheduledTasksCollector
from .security import SecurityCollector
from .services import ServicesCollector
from .system import SystemCollector
from .system_metrics import SystemMetricsCollector
from .updates import PackageUpdatesCollector

__all__ = [
    'DatabasesCollector',
    'DockerCollector',
    'FirewallCollector',
    'LogAnomaliesCollector',
    'NetworkCollector',
    'ScheduledTasksCollector',
    'SecurityCollector',
    'ServicesCollector',
    'SystemMetricsCollector',
    'SystemCollector',
    'PackageUpdatesCollector',
]
