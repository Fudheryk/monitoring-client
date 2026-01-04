# src/collectors/builtin/services.py

import logging
import re
import subprocess

from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class ServicesCollector(BaseCollector):
    """
    Collecte le statut des services systemd :
    - un booléen par service (actif/en cours d'exécution)
    - compteur global de services actifs / en échec
    """

    name = "services"

    _metric_name_safe_re = re.compile(r"[^a-zA-Z0-9._-]")

    def _collect_metrics(self):
        metrics = []

        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "list-units",
                    "--type=service",
                    "--no-legend",
                    "--no-pager",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
        except FileNotFoundError:  # systemd absent
            logger.info("systemctl introuvable, aucun service systemd à collecter.")
            return metrics
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de l'exécution de systemctl list-units : %s", exc)
            return metrics

        lines = result.stdout.strip().split("\n")
        active_count = 0
        failed_count = 0

        for line in lines:
            if not line.strip():
                continue

            parts = line.split()
            if len(parts) < 4:
                continue

            service_name = parts[0]  # ex: ssh.service
            load_state = parts[1]
            active_state = parts[2]
            sub_state = parts[3]

            is_active = active_state == "active" and sub_state == "running"
            is_failed = active_state == "failed"

            if is_active:
                active_count += 1
            if is_failed:
                failed_count += 1

            # Sanitize pour respecter ^[a-zA-Z0-9._-]+$
            safe_service_name = self._metric_name_safe_re.sub("_", service_name)

            metrics.append(
                {
                    "name": f"{safe_service_name}.service",
                    "value": bool(is_active),
                    "type": "boolean",
                    "description": f"Indique si le service {service_name} est actif (running).",
                    # par défaut, on considère les services comme critiques
                    # pour l'instant
                    "is_critical": True,
                }
            )

        # Statistiques globales
        metrics.append(
            {
                "name": "services.active_count",
                "value": int(active_count),
                "type": "numeric",
                "description": "Nombre total de services actifs (running).",
                "is_critical": True,
            }
        )
        metrics.append(
            {
                "name": "services.failed_count",
                "value": int(failed_count),
                "type": "numeric",
                "description": "Nombre total de services en échec.",
                "is_critical": True,
            }
        )

        return metrics
