"""
Collecteur système unifié.

Combine les informations statiques et les métriques dynamiques
pour éviter les doublons et simplifier la maintenance.

CORRECTIFS APPLIQUÉS :
- Filtrage des bind mounts systemd (ReadWritePaths)
- Dédoublonnage par device (évite les métriques redondantes)
- Détection robuste via /proc/self/mountinfo (fallback)
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

        # === MÉTRIQUES DISQUE (avec filtrage bind mounts et dédoublonnage) ===
        try:
            # Étape 1 : Filtrage de base des partitions
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
                
                # ✅ CORRECTIF 1 : Filtrer les bind mounts via partition.opts
                # Détecte les bind mounts systemd (ReadWritePaths, ProtectSystem)
                opts = set((partition.opts or "").split(","))
                if "bind" in opts or "rbind" in opts:
                    logger.debug("Ignoring bind mount: %s", mountpoint)
                    continue
                
                # ✅ CORRECTIF 2 : Fallback robuste via /proc/self/mountinfo
                # Plus fiable si partition.opts est vide ou incomplet
                if self._is_bind_mount(mountpoint):
                    logger.debug("Ignoring bind mount (via /proc): %s", mountpoint)
                    continue
                
                valid_partitions.append(partition)
            
            # Étape 2 : Dédoublonnage par device
            # Si plusieurs mountpoints pointent vers le même device (ex: / et /var),
            # ne garder que le plus court (racine logique du filesystem)
            seen_devices = {}
            unique_partitions = []
            
            for partition in valid_partitions:
                try:
                    stat_info = os.stat(partition.mountpoint)
                    device_id = stat_info.st_dev
                    
                    if device_id in seen_devices:
                        # Device déjà vu : garder le mountpoint le plus court
                        existing = seen_devices[device_id]
                        if len(partition.mountpoint) < len(existing.mountpoint):
                            # Remplacer par le plus court
                            unique_partitions.remove(existing)
                            seen_devices[device_id] = partition
                            unique_partitions.append(partition)
                            logger.debug(
                                "Replacing %s with shorter %s (same device %s)",
                                existing.mountpoint, partition.mountpoint, device_id
                            )
                        else:
                            # Ignorer ce doublon (plus long)
                            logger.debug(
                                "Skipping duplicate mountpoint %s (device %s already seen as %s)",
                                partition.mountpoint, device_id, existing.mountpoint
                            )
                    else:
                        # Nouveau device
                        seen_devices[device_id] = partition
                        unique_partitions.append(partition)
                
                except (OSError, PermissionError) as exc:
                    # Si stat() échoue, ignorer ce mountpoint
                    logger.debug("Cannot stat %s: %s", partition.mountpoint, exc)
                    continue
            
            # Étape 3 : Collecte des métriques pour les partitions uniques
            for partition in unique_partitions:
                mountpoint = partition.mountpoint
                
                try:
                    disk_usage = psutil.disk_usage(mountpoint)
                    
                    # Format : disk[<mountpoint>].usage_percent
                    metrics.extend([
                        {
                            "name": f"disk[{mountpoint}].usage_percent",
                            "value": round(disk_usage.percent, 1),
                            "type": "numeric",
                            "unit": "%",
                        },
                        {
                            "name": f"disk[{mountpoint}].total_gb",
                            "value": round(disk_usage.total / (1024**3), 2),
                            "type": "numeric",
                            "unit": "GB",
                        },
                        {
                            "name": f"disk[{mountpoint}].free_gb",
                            "value": round(disk_usage.free / (1024**3), 2),
                            "type": "numeric",
                            "unit": "GB",
                        }
                    ])
                
                except (PermissionError, FileNotFoundError) as exc:
                    # Partition non accessible
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
                                }
                            )
        except Exception as exc:
            logger.debug("Échec collecte températures: %s", exc)

        return metrics

    @staticmethod
    def _is_bind_mount(mountpoint: str) -> bool:
        """
        Détecte les bind mounts via /proc/self/mountinfo.
        
        Plus robuste que partition.opts sur Linux, car :
        - partition.opts peut être vide selon le backend psutil
        - /proc/self/mountinfo est la source de vérité du kernel
        
        Cette méthode détecte spécifiquement les bind mounts créés par systemd
        via ReadWritePaths, ProtectSystem=strict, etc.
        
        Args:
            mountpoint: Chemin du point de montage à vérifier
        
        Returns:
            True si c'est un bind mount, False sinon
        
        Note:
            Graceful fallback si /proc/self/mountinfo n'existe pas
            (non-Linux, permissions restreintes, etc.)
        """
        try:
            with open("/proc/self/mountinfo", "r", encoding="utf-8") as f:
                for line in f:
                    # Format /proc/self/mountinfo (man proc(5)) :
                    # 36 35 98:0 /mnt1 /mnt2 rw,noatime master:1 - ext3 /dev/root rw,errors=continue
                    # Champs : mount_id parent_id major:minor root mount_point options...
                    parts = line.split()
                    if len(parts) < 10:
                        continue
                    
                    # Champ 4 = mount_point
                    # Champ 3 = root (source dans le filesystem parent)
                    current_mount_point = parts[4]
                    root_source = parts[3]
                    
                    if current_mount_point == mountpoint:
                        # Bind mount détecté si :
                        # - root != "/" (pas la racine du filesystem)
                        # - OU si "bind" apparaît dans les options (champ 5)
                        
                        # Méthode 1 : Vérifier root source
                        if root_source != "/":
                            # Si root pointe vers un sous-répertoire du FS parent,
                            # c'est probablement un bind mount
                            logger.debug(
                                "Detected bind mount %s (root=%s)", 
                                mountpoint, root_source
                            )
                            return True
                        
                        # Méthode 2 : Chercher "bind" dans les options (champ 6+)
                        # Les options peuvent contenir "shared:N", "master:N", "bind", etc.
                        options_str = " ".join(parts[5:])
                        if "bind" in options_str.lower():
                            logger.debug(
                                "Detected bind mount %s (options=%s)", 
                                mountpoint, options_str
                            )
                            return True
        
        except (FileNotFoundError, PermissionError) as exc:
            # /proc/self/mountinfo indisponible (non-Linux ou permissions)
            logger.debug("Cannot read /proc/self/mountinfo: %s", exc)
        except Exception as exc:
            # Autre erreur (parsing, encoding, etc.)
            logger.debug("Error parsing /proc/self/mountinfo: %s", exc)
        
        return False
