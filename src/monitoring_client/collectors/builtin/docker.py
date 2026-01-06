import logging
import os
import subprocess

from monitoring_client.collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)

class DockerCollector(BaseCollector):
    """
    Collecte des métriques Docker si disponible :
    - présence du binaire docker
    - démon en cours d'exécution
    - nombre de conteneurs / images
    """

    name = "docker"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self):
        """
        Collecte les métriques liées à Docker (présence du binaire, état du démon, conteneurs, images).
        :return: liste des métriques collectées
        """
        metrics = []

        # Vérification de la présence du binaire Docker
        docker_bin = "/usr/bin/docker"
        if not os.path.exists(docker_bin):
            return metrics  # Si Docker n'est pas installé, on retourne les métriques vides

        docker_running = False
        try:
            # Vérification du statut du démon Docker
            result = subprocess.run(
                [docker_bin, "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            docker_running = result.returncode == 0
        except Exception as exc:  # Si une erreur se produit
            logger.warning("Erreur lors de l'exécution de 'docker info' : %s", exc)

        # Statut du démon Docker
        metrics.append(
            {
                "name": "docker.daemon_running",
                "value": bool(docker_running),
                "type": "boolean",
                "description": "Indique si le démon Docker est en cours d'exécution.",
                "is_critical": True,
                "collector_name": self.name,  # Nom du collecteur
                "editor_name": self.editor,  # Nom de l'éditeur
            }
        )

        if not docker_running:
            return metrics  # Si le démon Docker n'est pas en cours d'exécution, on retourne les métriques ici

        # Si le démon est en cours d'exécution, collecte des métriques supplémentaires
        try:
            # Nombre total de conteneurs Docker (y compris stoppés)
            containers_result = subprocess.run(
                [docker_bin, "ps", "-a", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            total_containers = len([l for l in containers_result.stdout.strip().split("\n") if l.strip()])

            # Nombre de conteneurs Docker en cours d'exécution
            running_result = subprocess.run(
                [docker_bin, "ps", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            running_containers = len([l for l in running_result.stdout.strip().split("\n") if l.strip()])

            # Nombre total d'images Docker sur le système
            images_result = subprocess.run(
                [docker_bin, "images", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            total_images = len([l for l in images_result.stdout.strip().split("\n") if l.strip()])

            # Nombre de conteneurs Docker actuellement en pause
            paused_result = subprocess.run(
                [docker_bin, "ps", "--filter", "status=paused", "--format", "{{.ID}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            paused_containers = len([l for l in paused_result.stdout.strip().split("\n") if l.strip()])

            # Ajout des métriques collectées
            metrics.extend(
                [
                    {
                        "name": "docker.containers_total",
                        "value": int(total_containers),
                        "type": "numeric",
                        "description": "Nombre total de conteneurs Docker (y compris stoppés).",
                        "is_critical": True,
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Nom de l'éditeur
                    },
                    {
                        "name": "docker.containers_running",
                        "value": int(running_containers),
                        "type": "numeric",
                        "description": "Nombre de conteneurs Docker en cours d'exécution.",
                        "is_critical": True,
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Nom de l'éditeur
                    },
                    {
                        "name": "docker.images_total",
                        "value": int(total_images),
                        "type": "numeric",
                        "description": "Nombre total d'images Docker sur le système.",
                        "is_critical": False,
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Nom de l'éditeur
                    },
                    {
                        "name": "docker.containers_paused",
                        "value": int(paused_containers),
                        "type": "numeric",
                        "description": "Nombre de conteneurs Docker actuellement en pause.",
                        "is_critical": False,
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Nom de l'éditeur
                    },
                ]
            )
        except Exception as exc:  # Erreur lors de la collecte des métriques Docker
            logger.warning("Erreur lors de la collecte des métriques Docker : %s", exc)

        # Retour des métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
