# src/collectors/builtin/docker.py

import os
import subprocess
import logging

from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class DockerCollector(BaseCollector):
    """
    Collecte des métriques Docker si disponible :
    - présence du binaire docker
    - démon en cours d'exécution
    - nombre de conteneurs / images
    """

    name = "docker"

    def _collect_metrics(self):
        metrics = []

        docker_bin = "/usr/bin/docker"
        if not os.path.exists(docker_bin):
            return metrics

        docker_running = False
        try:
            result = subprocess.run(
                [docker_bin, "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            docker_running = result.returncode == 0
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de l'exécution de 'docker info' : %s", exc)

        # Statut du démon Docker
        metrics.append(
            {
                "name": "docker.daemon_running",
                "value": bool(docker_running),
                "type": "boolean",
                "description": "Indique si le démon Docker est en cours d'exécution.",
                "is_critical": True,
            })

        if not docker_running:
            return metrics

        # Si le démon tourne, collecter des métriques supplémentaires
        try:
            # Tous les conteneurs (y compris stoppés)
            containers_result = subprocess.run(
                [docker_bin, "ps", "-a", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            total_containers = len(
                [l for l in containers_result.stdout.strip().split("\n") if l.strip()]
            )

            # Conteneurs en cours d'exécution
            running_result = subprocess.run(
                [docker_bin, "ps", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            running_containers = len(
                [l for l in running_result.stdout.strip().split("\n") if l.strip()]
            )

            # Images Docker
            images_result = subprocess.run(
                [docker_bin, "images", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            total_images = len(
                [l for l in images_result.stdout.strip().split("\n") if l.strip()]
            )

            # Conteneurs en pause
            paused_result = subprocess.run(
                [docker_bin, "ps", "--filter", "status=paused", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            paused_containers = len(
                [l for l in paused_result.stdout.strip().split("\n") if l.strip()]
            )

            metrics.extend([{"name": "docker.containers_total",
                             "value": int(total_containers),
                             "type": "numeric",
                             "description": "Nombre total de conteneurs Docker (y compris stoppés).",
                             "is_critical": True,
                             },
                            {"name": "docker.containers_running",
                             "value": int(running_containers),
                             "type": "numeric",
                             "description": "Nombre de conteneurs Docker en cours d'exécution.",
                             "is_critical": True,
                             },
                            {"name": "docker.images_total",
                             "value": int(total_images),
                             "type": "numeric",
                             "description": "Nombre total d'images Docker sur le système.",
                             "is_critical": False,
                             },
                            {"name": "docker.containers_paused",
                             "value": int(paused_containers),
                             "type": "numeric",
                             "description": "Nombre de conteneurs Docker actuellement en pause.",
                             "is_critical": False,
                             },
                            ])
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la collecte des métriques Docker : %s", exc)

        return metrics
