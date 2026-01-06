from __future__ import annotations

"""collectors/loader.py

Loader des collecteurs builtin.

"""

from typing import List

from monitoring_client.core.logger import get_logger, log_phase

from monitoring_client.collectors.base_collector import BaseCollector, Metric
from monitoring_client.collectors.builtin.databases import DatabasesCollector
from monitoring_client.collectors.builtin.docker import DockerCollector
from monitoring_client.collectors.builtin.firewall import FirewallCollector
from monitoring_client.collectors.builtin.log_anomalies import LogAnomaliesCollector
from monitoring_client.collectors.builtin.network import NetworkCollector
from monitoring_client.collectors.builtin.scheduled_tasks import ScheduledTasksCollector
from monitoring_client.collectors.builtin.security import SecurityCollector
from monitoring_client.collectors.builtin.services import ServicesCollector
from monitoring_client.collectors.builtin.system import SystemCollector
from monitoring_client.collectors.builtin.updates import PackageUpdatesCollector

logger = get_logger(__name__)


def get_builtin_collectors() -> List[BaseCollector]:
    """
    Retourne la liste des collecteurs builtin actifs.

    Cette liste est immuable du point de vue de l'utilisateur final : il ne
    peut pas ajouter/supprimer des collecteurs builtin, seulement des vendors.
    """
    # Si plus tard tu veux activer / désactiver certains collectors via config,
    # tu pourras filtrer ici.
    return [
        # Contexte système (hostname, os, uptime, load, etc.)
        SystemCollector(),
        # Réseau / firewall
        NetworkCollector(),
        FirewallCollector(),
        # Packages & updates
        PackageUpdatesCollector(),
        # Services / sécurité / tâches
        ServicesCollector(),
        SecurityCollector(),
        ScheduledTasksCollector(),
        LogAnomaliesCollector(),
        # Runtime / DB
        DockerCollector(),
        DatabasesCollector(),
    ]


def run_builtin_collectors() -> List[Metric]:
    """
    Exécute tous les collecteurs builtin et concatène leurs métriques.

    Retour :
      - Liste de métriques (dicts) prêtes à être intégrées dans le payload.
    """
    log_phase(logger, "collectors.builtin.run", "Exécution de tous les collecteurs builtin")

    all_metrics: List[Metric] = []
    collectors = get_builtin_collectors()

    for collector in collectors:
        metrics = collector.collect()
        if not metrics:
            logger.debug("Aucune métrique retournée par le collecteur '%s'", collector.name)
        all_metrics.extend(metrics)

    logger.info("Nombre total de métriques builtin collectées: %d", len(all_metrics))
    return all_metrics
