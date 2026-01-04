# src/collectors/builtin/system_metrics.py

import logging
import os

import psutil

from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class SystemMetricsCollector(BaseCollector):
    """
    Collecte des métriques système détaillées :
    - mémoire (Go + pourcentage)
    - swap
    - CPU (usage, count, load avg)
    - réseau global
    - partitions disque (découverte automatique)
    - températures (si disponibles)
    """

    name = "system_metrics"

    def _collect_metrics(self):
        """Collecte toutes les métriques système."""
        metrics = []

        self._collect_memory_metrics(metrics)
        self._collect_cpu_metrics(metrics)
        self._collect_network_metrics(metrics)
        self._collect_disk_metrics(metrics)
        self._collect_temperature_metrics(metrics)

        return metrics

    def _collect_memory_metrics(self, metrics):
        """Collecte les métriques de mémoire et swap."""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            metrics.extend(
                [
                    {
                        "name": "memory.usage_percent",
                        "value": round(float(mem.percent), 2),
                        "type": "numeric",
                        "description": "Pourcentage de mémoire utilisée.",
                        "is_critical": True,
                    },
                    {
                        "name": "memory.total_gb",
                        "value": round(mem.total / (1024**3), 2),
                        "type": "numeric",
                        "description": "Mémoire totale disponible (en Go).",
                        "is_critical": False,
                    },
                    {
                        "name": "memory.available_gb",
                        "value": round(mem.available / (1024**3), 2),
                        "type": "numeric",
                        "description": "Mémoire disponible (en Go).",
                        "is_critical": False,
                    },
                    {
                        "name": "swap.usage_percent",
                        "value": round(float(swap.percent), 2),
                        "type": "numeric",
                        "description": "Pourcentage de mémoire swap utilisée.",
                        "is_critical": True,
                    },
                    {
                        "name": "swap.total_gb",
                        "value": round(swap.total / (1024**3), 2),
                        "type": "numeric",
                        "description": "Mémoire swap totale (en Go).",
                        "is_critical": False,
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Erreur lors de la collecte mémoire/swap : %s", exc)

    def _collect_cpu_metrics(self, metrics):
        """Collecte les métriques CPU et charge système."""
        try:
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(interval=1.0)
            load1, load5, load15 = os.getloadavg()

            metrics.extend(
                [
                    {
                        "name": "cpu.usage_percent",
                        "value": round(float(cpu_percent), 2),
                        "type": "numeric",
                        "description": "Pourcentage d'utilisation de la CPU.",
                        "is_critical": True,
                    },
                    {
                        "name": "cpu.count",
                        "value": int(cpu_count),
                        "type": "numeric",
                        "description": "Nombre de cœurs de processeur (logiques).",
                        "is_critical": False,
                    },
                    {
                        "name": "cpu.load_1min",
                        "value": round(float(load1), 2),
                        "type": "numeric",
                        "description": "Charge moyenne CPU sur 1 minute.",
                        "is_critical": False,
                    },
                    {
                        "name": "cpu.load_5min",
                        "value": round(float(load5), 2),
                        "type": "numeric",
                        "description": "Charge moyenne CPU sur 5 minutes.",
                        "is_critical": False,
                    },
                    {
                        "name": "cpu.load_15min",
                        "value": round(float(load15), 2),
                        "type": "numeric",
                        "description": "Charge moyenne CPU sur 15 minutes.",
                        "is_critical": False,
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Erreur lors de la collecte des métriques CPU : %s", exc)

    def _collect_network_metrics(self, metrics):
        """Collecte les métriques réseau globales."""
        try:
            net_io = psutil.net_io_counters()
            net_connections = len(psutil.net_connections())

            metrics.extend(
                [
                    {
                        "name": "network.total_bytes_sent",
                        "value": int(net_io.bytes_sent),
                        "type": "numeric",
                        "description": "Nombre total de bytes envoyés sur le réseau.",
                        "is_critical": False,
                    },
                    {
                        "name": "network.total_bytes_recv",
                        "value": int(net_io.bytes_recv),
                        "type": "numeric",
                        "description": "Nombre total de bytes reçus sur le réseau.",
                        "is_critical": False,
                    },
                    {
                        "name": "network.total_packets_sent",
                        "value": int(net_io.packets_sent),
                        "type": "numeric",
                        "description": "Nombre total de paquets envoyés sur le réseau.",
                        "is_critical": False,
                    },
                    {
                        "name": "network.total_packets_recv",
                        "value": int(net_io.packets_recv),
                        "type": "numeric",
                        "description": "Nombre total de paquets reçus sur le réseau.",
                        "is_critical": False,
                    },
                    {
                        "name": "network.connections_count",
                        "value": int(net_connections),
                        "type": "numeric",
                        "description": "Nombre de connexions réseau (tous états).",
                        "is_critical": False,
                    },
                ]
            )
        except Exception as exc:
            logger.warning("Erreur lors de la collecte des métriques réseau : %s", exc)

    def _collect_disk_metrics(self, metrics):
        """
        Collecte les métriques disque pour toutes les partitions montées.
        Découverte automatique avec filtrage des systèmes de fichiers spéciaux.
        """
        try:
            for partition in psutil.disk_partitions(all=False):
                mountpoint = partition.mountpoint

                # Filtrer les systèmes de fichiers spéciaux/inutiles pour la
                # surveillance
                skip_fs_types = ['squashfs', 'tmpfs', 'devtmpfs', 'overlay', 'proc', 'sysfs', 'cgroup']
                if partition.fstype in skip_fs_types:
                    continue

                # Éviter les points de montage spéciaux
                if mountpoint.startswith(('/sys', '/proc', '/dev', '/run')):
                    continue

                try:
                    disk_usage = psutil.disk_usage(mountpoint)

                    # Déterminer la criticité (partitions système importantes)
                    is_critical = mountpoint in ["/", "/var", "/home", "/opt"]

                    # IMPORTANT :
                    # On respecte le format attendu par le catalogue :
                    #   disk[<mountpoint>].usage_percent
                    #   disk[<mountpoint>].total_gb
                    #   disk[<mountpoint>].free_gb
                    base_name = f"disk[{mountpoint}]"

                    metrics.extend(
                        [
                            {
                                "name": f"{base_name}.usage_percent",
                                "value": round(float(disk_usage.percent), 2),
                                "type": "numeric",
                                "description": (
                                    f"Pourcentage d'utilisation de la partition " f"{mountpoint} ({partition.fstype})."
                                ),
                                "is_critical": is_critical,
                            },
                            {
                                "name": f"{base_name}.total_gb",
                                "value": round(disk_usage.total / (1024**3), 2),
                                "type": "numeric",
                                "description": (f"Capacité totale de la partition {mountpoint} (en Go)."),
                                "is_critical": False,
                            },
                            {
                                "name": f"{base_name}.free_gb",
                                "value": round(disk_usage.free / (1024**3), 2),
                                "type": "numeric",
                                "description": (f"Espace libre sur la partition {mountpoint} (en Go)."),
                                "is_critical": False,
                            },
                        ]
                    )

                except (PermissionError, FileNotFoundError):
                    # Partition non accessible - on ignore silencieusement
                    continue
                except Exception as exc:
                    logger.warning("Erreur sur la partition %s : %s", mountpoint, exc)
                    continue

        except Exception as exc:
            logger.warning("Erreur lors de la collecte des métriques disque : %s", exc)

    def _collect_temperature_metrics(self, metrics):
        """Collecte les métriques de température si disponibles."""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if not temps:
                    return

                for label, entries in temps.items():
                    for idx, temp in enumerate(entries):
                        sensor_name = f"{label}.{idx}"
                        metrics.append(
                            {
                                "name": f"temperature.{sensor_name}.current",
                                "value": float(temp.current),
                                "type": "numeric",
                                "description": f"Température actuelle du capteur {sensor_name}.",
                                "is_critical": True,
                            }
                        )
        except Exception as exc:
            logger.warning("Erreur lors de la collecte des températures système : %s", exc)
