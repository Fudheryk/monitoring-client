from __future__ import annotations

from typing import Any, Dict, List

import psutil

from monitoring_client.core.logger import get_logger
from monitoring_client.collectors.base_collector import BaseCollector, Metric

# Configuration du logger
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

    name = "network"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self) -> List[Metric]:
        """
        Collecte les métriques réseau pour chaque interface active.
        :return: Liste des métriques collectées.
        """
        metrics: List[Dict[str, Any]] = []

        try:
            # Collecte des statistiques des interfaces réseau et des compteurs IO
            stats = psutil.net_if_stats()
            counters = psutil.net_io_counters(pernic=True)
        except Exception as exc:
            logger.debug("Échec de la collecte réseau globale: %s", exc)
            return metrics

        # Traitement de chaque interface
        for iface, stat in stats.items():

            # Ignorer les interfaces virtuelles bruyantes (Docker bridges + veth pairs)
            if iface.startswith("br-") or iface.startswith("veth"):
                continue

            try:
                up = stat.isup
                metric_prefix = f"network.{iface}"

                # Statut de l'interface (up/down)
                metrics.append(
                    {
                        "name": f"{metric_prefix}.up",
                        "value": up,
                        "type": "boolean",
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Type de collecteur
                    }
                )

                # Vitesse de l'interface (si disponible)
                if stat.speed is not None and stat.speed >= 0:
                    metrics.append(
                        {
                            "name": f"{metric_prefix}.speed_mbps",
                            "value": stat.speed,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        }
                    )

                # Collecte des compteurs IO (envoyés/reçus, erreurs, drops)
                io = counters.get(iface)
                if io is None:
                    continue

                metrics.extend(
                    [
                        {
                            "name": f"{metric_prefix}.bytes_sent",
                            "value": io.bytes_sent,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.bytes_recv",
                            "value": io.bytes_recv,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.packets_sent",
                            "value": io.packets_sent,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.packets_recv",
                            "value": io.packets_recv,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.errin",
                            "value": io.errin,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.errout",
                            "value": io.errout,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.dropin",
                            "value": io.dropin,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                        {
                            "name": f"{metric_prefix}.dropout",
                            "value": io.dropout,
                            "type": "numeric",
                            "collector_name": self.name,  # Nom du collecteur
                            "editor_name": self.editor,  # Type de collecteur
                        },
                    ]
                )

            except Exception as exc:
                logger.debug("Échec de la collecte réseau pour l'interface %s: %s", iface, exc)

        # Retour des métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
