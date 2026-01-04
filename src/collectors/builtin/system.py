"""
Collecteur système unifié.

Combine les informations statiques et les métriques dynamiques
pour éviter les doublons et simplifier la maintenance.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
from typing import Any, Dict, List

import psutil

from core.logger import get_logger

from ..base_collector import BaseCollector, Metric

logger = get_logger(__name__)


class SystemCollector(BaseCollector):
    """
    Collecteur builtin pour toutes les métriques système.

    Métriques statiques (collectées une fois) :
      - system.hostname
      - system.os
      - system.kernel_version
      - system.kernel_full_version
      - system.distribution
      - system.architecture
      - system.python_version
      - system.memory_total_gb

    Métriques dynamiques (collectées à chaque run) :
      - cpu.usage_percent
      - cpu.count
      - system.load_1m / 5m / 15m
      - memory.usage_percent
      - memory.available_gb
      - memory.total_bytes
      - memory.available_bytes
      - swap.usage_percent
      - swap.total_bytes
      - system.uptime_seconds
      - system.process_count
      - disk[<mountpoint>].usage_percent
      - disk[<mountpoint>].total_gb
      - disk[<mountpoint>].free_gb
      - temperature.<sensor>.current (si disponible)
    """

    name = "system"

    def _collect_metrics(self) -> List[Metric]:
        metrics: List[Dict[str, Any]] = []

        # === INFORMATIONS STATIQUES ===

        # Hostname
        try:
            metrics.append(
                {
                    "name": "system.hostname",
                    "value": platform.node(),
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte hostname: %s", exc)

        # OS
        try:
            metrics.append(
                {
                    "name": "system.os",
                    "value": platform.system(),
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte OS: %s", exc)

        # Kernel version (simple)
        try:
            metrics.append(
                {
                    "name": "system.kernel_version",
                    "value": platform.release(),
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte kernel version: %s", exc)

        # Kernel version (full via uname -r)
        try:
            kernel_full = (
                subprocess.check_output(["uname", "-r"], stderr=subprocess.DEVNULL)
                .decode("utf-8", errors="ignore")
                .strip()
            )

            metrics.append(
                {
                    "name": "system.kernel_full_version",
                    "value": kernel_full,
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte kernel full: %s", exc)

        # Distribution Linux
        try:
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        metrics.append(
                            {
                                "name": "system.distribution",
                                "value": distro,
                                "type": "string",
                            }
                        )
                        break
        except (FileNotFoundError, Exception) as exc:
            logger.debug("Échec lecture /etc/os-release: %s", exc)

        # Architecture
        try:
            metrics.append(
                {
                    "name": "system.architecture",
                    "value": platform.machine(),
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte architecture: %s", exc)

        # Python version
        try:
            metrics.append(
                {
                    "name": "system.python_version",
                    "value": platform.python_version(),
                    "type": "string",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte Python version: %s", exc)

        # === MÉTRIQUES DYNAMIQUES ===

        # CPU usage (instantané)
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            metrics.append(
                {
                    "name": "cpu.usage_percent",
                    "value": float(cpu_percent),
                    "type": "numeric",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte CPU usage: %s", exc)

        # CPU count
        try:
            cpu_count = psutil.cpu_count(logical=True)
            if cpu_count is not None:
                metrics.append(
                    {
                        "name": "cpu.count",
                        "value": int(cpu_count),
                        "type": "numeric",
                    }
                )
        except Exception as exc:
            logger.debug("Échec collecte CPU count: %s", exc)

        # Load average (Unix)
        try:
            if hasattr(os, "getloadavg"):
                load1, load5, load15 = os.getloadavg()
                metrics.extend(
                    [
                        {
                            "name": "system.load_1m",
                            "value": float(load1),
                            "type": "numeric",
                        },
                        {
                            "name": "system.load_5m",
                            "value": float(load5),
                            "type": "numeric",
                        },
                        {
                            "name": "system.load_15m",
                            "value": float(load15),
                            "type": "numeric",
                        },
                    ]
                )
        except Exception as exc:
            logger.debug("Échec collecte load average: %s", exc)

        # Memory (RAM)
        try:
            vm = psutil.virtual_memory()
            metrics.extend(
                [
                    {
                        "name": "memory.usage_percent",
                        "value": float(vm.percent),
                        "type": "numeric",
                    },
                    {
                        "name": "memory.total_bytes",
                        "value": int(vm.total),
                        "type": "numeric",
                    },
                    {
                        "name": "memory.available_bytes",
                        "value": int(vm.available),
                        "type": "numeric",
                    },
                    {
                        "name": "system.memory_total_gb",
                        "value": round(vm.total / (1024**3), 2),
                        "type": "numeric",
                    },
                    {
                        "name": "system.memory_available_gb",
                        "value": round(vm.available / (1024**3), 2),
                        "type": "numeric",
                    },
                ]
            )
        except Exception as exc:
            logger.debug("Échec collecte mémoire: %s", exc)

        # Swap
        try:
            sm = psutil.swap_memory()
            metrics.extend(
                [
                    {
                        "name": "swap.usage_percent",
                        "value": float(sm.percent),
                        "type": "numeric",
                    },
                    {
                        "name": "swap.total_bytes",
                        "value": int(sm.total),
                        "type": "numeric",
                    },
                ]
            )
        except Exception as exc:
            logger.debug("Échec collecte swap: %s", exc)

        # Uptime
        try:
            boot_ts = psutil.boot_time()
            uptime_sec = max(0.0, time.time() - boot_ts)
            metrics.append(
                {
                    "name": "system.uptime_seconds",
                    "value": float(uptime_sec),
                    "type": "numeric",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte uptime: %s", exc)

        # Process count
        try:
            process_count = len([pid for pid in os.listdir("/proc") if pid.isdigit()])
            metrics.append(
                {
                    "name": "system.process_count",
                    "value": int(process_count),
                    "type": "numeric",
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte process count: %s", exc)

        # === MÉTRIQUES DISQUE ===
        try:
            for partition in psutil.disk_partitions(all=False):
                mountpoint = partition.mountpoint
                
                # Filtrer les systèmes de fichiers spéciaux
                skip_fs_types = ['squashfs', 'tmpfs', 'devtmpfs', 'overlay', 'proc', 'sysfs', 'cgroup']
                if partition.fstype in skip_fs_types:
                    continue
                
                # Éviter les points de montage spéciaux
                if mountpoint.startswith(('/sys', '/proc', '/dev', '/run')):
                    continue
                
                try:
                    disk_usage = psutil.disk_usage(mountpoint)
                    
                    # Format : disk[<mountpoint>].usage_percent
                    metrics.extend([
                        {
                            "name": f"disk[{mountpoint}].usage_percent",
                            "value": float(disk_usage.percent),
                            "type": "numeric",
                        },
                        {
                            "name": f"disk[{mountpoint}].total_gb",
                            "value": round(disk_usage.total / (1024**3), 2),
                            "type": "numeric",
                        },
                        {
                            "name": f"disk[{mountpoint}].free_gb",
                            "value": round(disk_usage.free / (1024**3), 2),
                            "type": "numeric",
                        }
                    ])
                except (PermissionError, FileNotFoundError):
                    # Partition non accessible
                    continue
                except Exception as exc:
                    logger.debug("Erreur sur la partition %s: %s", mountpoint, exc)
                    
        except Exception as exc:
            logger.debug("Échec collecte disque: %s", exc)

        # === MÉTRIQUES TEMPÉRATURE ===
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for label, entries in temps.items():
                        for idx, temp in enumerate(entries):
                            sensor_name = f"{label}.{idx}"
                            metrics.append(
                                {
                                    "name": f"temperature.{sensor_name}.current",
                                    "value": float(temp.current),
                                    "type": "numeric",
                                }
                            )
        except Exception as exc:
            logger.debug("Échec collecte températures: %s", exc)

        return metrics
