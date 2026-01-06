import logging
import os
import subprocess

from monitoring_client.collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)

class ScheduledTasksCollector(BaseCollector):
    """
    Collecte des informations sur les tâches planifiées :
    - présence de cron / anacron
    - nombre de jobs cron
    - nombre de timers systemd
    """

    name = "scheduled_tasks"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self):
        """
        Collecte les métriques liées aux tâches planifiées.
        :return: Liste des métriques collectées.
        """
        metrics = []

        # Vérification de la disponibilité de cron
        cron_active = os.path.exists("/etc/cron.d") or os.path.exists("/var/spool/cron")

        # Nombre de jobs cron (dans /etc/crontab uniquement, comme le prototype)
        cron_jobs = 0
        if os.path.exists("/etc/crontab"):
            try:
                with open("/etc/crontab", "r", encoding="utf-8", errors="ignore") as f:
                    cron_jobs = len(
                        [line for line in f.readlines() if line.strip() and not line.lstrip().startswith("#")]
                    )
            except Exception as exc:
                logger.warning("Erreur lors de la lecture de /etc/crontab : %s", exc)

        # Vérification de la disponibilité d'Anacron
        anacron_active = os.path.exists("/usr/sbin/anacron")

        # Nombre de timers systemd
        timers_count = 0
        try:
            result = subprocess.run(
                ["systemctl", "list-timers", "--all", "--no-pager"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            lines = result.stdout.strip().splitlines()
            # On ignore la première ligne d'entête si présente
            if len(lines) > 1:
                timers_count = len([l for l in lines[1:] if l.strip()])
        except Exception as exc:
            logger.warning("Erreur lors de la récupération des timers systemd : %s", exc)

        # Ajout des métriques collectées
        metrics.extend(
            [
                {
                    "name": "cron.available",
                    "value": bool(cron_active),
                    "type": "boolean",
                    "description": "Indique si le service cron est disponible",
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "cron.jobs_count",
                    "value": int(cron_jobs),
                    "type": "numeric",
                    "description": "Nombre de tâches cron programmées (via /etc/crontab)",
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "anacron.available",
                    "value": bool(anacron_active),
                    "type": "boolean",
                    "description": "Indique si le service Anacron est disponible",
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "systemd_timers.count",
                    "value": int(timers_count),
                    "type": "numeric",
                    "description": "Nombre de timers systemd (tous états confondus)",
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
            ]
        )

        # Retour des métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
