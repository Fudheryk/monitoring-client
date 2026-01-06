from __future__ import annotations

import os
import platform
import subprocess
import time
from typing import Any, Dict, List

import psutil

from monitoring_client.core.logger import get_logger
from monitoring_client.collectors.base_collector import BaseCollector, Metric

# Configuration du logger
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

    name = "system"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                                "collector_name": self.name,
                                "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                        "collector_name": self.name,
                        "editor_name": self.editor,
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
                            "collector_name": self.name,
                            "editor_name": self.editor,
                        },
                        {
                            "name": "system.load_5m",
                            "value": float(load5),
                            "type": "numeric",
                            "collector_name": self.name,
                            "editor_name": self.editor,
                        },
                        {
                            "name": "system.load_15m",
                            "value": float(load15),
                            "type": "numeric",
                            "collector_name": self.name,
                            "editor_name": self.editor,
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
                        "collector_name": self.name,
                        "editor_name": self.editor,
                    },
                    {
                        "name": "memory.total_bytes",
                        "value": int(vm.total),
                        "type": "numeric",
                        "collector_name": self.name,
                        "editor_name": self.editor,
                    },
                    {
                        "name": "memory.available_bytes",
                        "value": int(vm.available),
                        "type": "numeric",
                        "collector_name": self.name,
                        "editor_name": self.editor,
                    },
                    {
                        "name": "system.memory_total_gb",
                        "value": round(vm.total / (1024**3), 2),
                        "type": "numeric",
                        "collector_name": self.name,
                        "editor_name": self.editor,
                    },
                    {
                        "name": "system.memory_available_gb",
                        "value": round(vm.available / (1024**3), 2),
                        "type": "numeric",
                        "collector_name": self.name,
                        "editor_name": self.editor,
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
                        "collector_name": self.name,
                        "editor_name": self.editor,
                    },
                    {
                        "name": "swap.total_bytes",
                        "value": int(sm.total),
                        "type": "numeric",
                        "collector_name": self.name,
                        "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
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
                    "collector_name": self.name,
                    "editor_name": self.editor,
                }
            )
        except Exception as exc:
            logger.debug("Échec collecte process count: %s", exc)

        # === MÉTRIQUES DISQUE (avec filtrage bind mounts et dédoublonnage) ===
        try:
            # Filtrage des partitions et dédoublonnage
            valid_partitions = self._filter_and_deduplicate_partitions()

            # Collecte des métriques pour les partitions uniques
            for partition in valid_partitions:
                mountpoint = partition.mountpoint
                try:
                    disk_usage = psutil.disk_usage(mountpoint)
                    metrics.extend(
                        [
                            {
                                "name": f"disk[{mountpoint}].usage_percent",
                                "value": round(disk_usage.percent, 1),
                                "type": "numeric",
                                "unit": "%",
                                "collector_name": self.name,
                                "editor_name": self.editor,
                            },
                            {
                                "name": f"disk[{mountpoint}].total_gb",
                                "value": round(disk_usage.total / (1024**3), 2),
                                "type": "numeric",
                                "unit": "GB",
                                "collector_name": self.name,
                                "editor_name": self.editor,
                            },
                            {
                                "name": f"disk[{mountpoint}].free_gb",
                                "value": round(disk_usage.free / (1024**3), 2),
                                "type": "numeric",
                                "unit": "GB",
                                "collector_name": self.name,
                                "editor_name": self.editor,
                            },
                        ]
                    )
                except (PermissionError, FileNotFoundError) as exc:
                    logger.debug("Cannot access disk usage for %s: %s", mountpoint, exc)
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
                                    "unit": "°C",
                                    "collector_name": self.name,
                                    "editor_name": self.editor,
                                }
                            )
        except Exception as exc:
            logger.debug("Échec collecte températures: %s", exc)

        # Retour des métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics

    @staticmethod
    def _is_bind_mount(mountpoint: str) -> bool:
        """
        Détecte un bind mount via /proc/self/mountinfo.
        Fallback safe si non disponible.
        """
        try:
            with open("/proc/self/mountinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 10:
                        continue

                    current_mount_point = parts[4]
                    root_source = parts[3]

                    if current_mount_point == mountpoint:
                        # bind mount si root != /
                        if root_source != "/":
                            return True

                        # ou option bind
                        options = " ".join(parts[5:]).lower()
                        if "bind" in options:
                            return True

        except (FileNotFoundError, PermissionError):
            # Non Linux ou permissions
            return False
        except Exception:
            return False

        return False

    def _filter_and_deduplicate_partitions(self):
        """
        Filtrer les partitions valides et supprimer les doublons.
        Cette méthode combine les étapes de filtrage des bind mounts,
        et de dédoublonnage des partitions.
        """
        skip_fs_types = {
            'squashfs', 'tmpfs', 'devtmpfs', 'overlay', 
            'proc', 'sysfs', 'cgroup', 'cgroup2',
            'devpts', 'securityfs', 'fusectl', 'debugfs'
        }
        skip_prefixes = ('/sys', '/proc', '/dev', '/run')
        
        valid_partitions = []
        
        for partition in psutil.disk_partitions(all=False):
            mountpoint = partition.mountpoint
            
            # Filtrer les systèmes de fichiers spéciaux
            if partition.fstype in skip_fs_types:
                continue
            
            # Éviter les points de montage spéciaux
            if mountpoint.startswith(skip_prefixes):
                continue
            
            # Détecter et filtrer les bind mounts
            opts = set((partition.opts or "").split(","))
            if "bind" in opts or "rbind" in opts:
                logger.debug("Ignoring bind mount: %s", mountpoint)
                continue
            
            # Détection des bind mounts via /proc/self/mountinfo
            if self._is_bind_mount(mountpoint):
                logger.debug("Ignoring bind mount (via /proc): %s", mountpoint)
                continue
            
            valid_partitions.append(partition)
        
        # Déduplique les partitions
        seen_devices = {}
        unique_partitions = []

        for partition in valid_partitions:
            try:
                stat_info = os.stat(partition.mountpoint)
                device_id = stat_info.st_dev
                
                if device_id in seen_devices:
                    existing = seen_devices[device_id]
                    if len(partition.mountpoint) < len(existing.mountpoint):
                        # Remplacer le plus long par le plus court
                        unique_partitions.remove(existing)
                        seen_devices[device_id] = partition
                        unique_partitions.append(partition)
                        logger.debug(
                            "Replacing %s with shorter %s (same device %s)",
                            existing.mountpoint, partition.mountpoint, device_id
                        )
                    else:
                        logger.debug(
                            "Skipping duplicate mountpoint %s (device %s already seen as %s)",
                            partition.mountpoint, device_id, existing.mountpoint
                        )
                else:
                    seen_devices[device_id] = partition
                    unique_partitions.append(partition)
            
            except (OSError, PermissionError) as exc:
                logger.debug("Cannot stat %s: %s", partition.mountpoint, exc)
                continue

        return unique_partitions
