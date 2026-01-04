from __future__ import annotations

from typing import Any, Dict, List

import psutil

from ..base_collector import BaseCollector, Metric
from core.logger import get_logger


logger = get_logger(__name__)


class NetworkCollector(BaseCollector):
    """
    Collecteur builtin pour les métriques réseau.

    Pour chaque interface active :
      - network.<iface>.up (boolean)
      - network.<iface>.speed_mbps (numeric, si dispo)
      - network.<iface>.bytes_sent
      - network.<iface>.bytes_recv
      - network.<iface>.packets_sent
      - network.<iface>.packets_recv
      - network.<iface>.errin
      - network.<iface>.errout
      - network.<iface>.dropin
      - network.<iface>.dropout
    """

    name = "network"

    def _collect_metrics(self) -> List[Metric]:
        metrics: List[Dict[str, Any]] = []

        try:
            stats = psutil.net_if_stats()
            counters = psutil.net_io_counters(pernic=True)
        except Exception as exc:
            logger.debug("Échec de la collecte réseau globale: %s", exc)
            return metrics

        for iface, stat in stats.items():

            # Ignore noisy virtual interfaces (Docker bridges + veth pairs)
            # Examples: br-*, veth*
            if iface.startswith("br-") or iface.startswith("veth"):
                continue
            try:
                up = stat.isup
                metric_prefix = f"network.{iface}"

                # up/down
                metrics.append(
                    {
                        "name": f"{metric_prefix}.up",
                        "value": up,
                        "type": "boolean",
                    }
                )

                # speed (peut être 0 sur certaines interfaces)
                if stat.speed is not None and stat.speed >= 0:
                    metrics.append(
                        {
                            "name": f"{metric_prefix}.speed_mbps",
                            "value": stat.speed,
                            "type": "numeric",
                        }
                    )

                # Compteurs IO (si dispo)
                io = counters.get(iface)
                if io is None:
                    continue

                metrics.extend(
                    [
                        {
                            "name": f"{metric_prefix}.bytes_sent",
                            "value": io.bytes_sent,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.bytes_recv",
                            "value": io.bytes_recv,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.packets_sent",
                            "value": io.packets_sent,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.packets_recv",
                            "value": io.packets_recv,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.errin",
                            "value": io.errin,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.errout",
                            "value": io.errout,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.dropin",
                            "value": io.dropin,
                            "type": "numeric",
                        },
                        {
                            "name": f"{metric_prefix}.dropout",
                            "value": io.dropout,
                            "type": "numeric",
                        },
                    ]
                )

            except Exception as exc:
                logger.debug(
                    "Échec de la collecte réseau pour l'interface %s: %s",
                    iface,
                    exc)

        return metrics
