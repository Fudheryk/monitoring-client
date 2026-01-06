import logging
import os
import re
import subprocess

from collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)

class LogAnomaliesCollector(BaseCollector):
    """
    Analyse basique des logs système pour détecter :
    - erreurs
    - warnings
    - échecs d'authentification
    - erreurs dans journalctl sur la dernière heure
    """

    name = "log_anomalies"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self):
        """
        Collecte les métriques concernant les anomalies dans les logs système
        :return: liste des métriques collectées
        """
        metrics = []

        # Fichiers de logs à analyser
        log_files = ["/var/log/syslog", "/var/log/messages", "/var/log/kern.log"]
        errors_count = 0
        warnings_count = 0

        # Mots-clés pour la détection d'erreurs et d'avertissements
        error_keywords = ["error", "fail", "panic", "critical", "fatal"]
        warning_keywords = ["warn", "warning"]

        # Compilation des regex pour rechercher les erreurs et les avertissements
        error_regex = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, error_keywords)), re.IGNORECASE)
        warning_regex = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, warning_keywords)), re.IGNORECASE)

        # Analyse des logs système
        for log_file in log_files:
            if not os.path.exists(log_file):
                continue

            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-1000:]  # Dernières 1000 lignes
            except Exception as exc:
                logger.warning("Erreur lors de la lecture du fichier %s : %s", log_file, exc)
                continue

            # Comptage des erreurs et des avertissements
            for line in lines:
                if error_regex.search(line):
                    errors_count += 1
                elif warning_regex.search(line):
                    warnings_count += 1

        # Analyse du fichier d'authentification (auth.log)
        auth_failures = 0
        auth_log = "/var/log/auth.log"
        if os.path.exists(auth_log):
            try:
                with open(auth_log, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-500:]  # Dernières 500 lignes
                auth_failures = len(
                    [l for l in lines if "authentication failure" in l.lower() or "failed password" in l.lower()]
                )
            except Exception as exc:
                logger.warning("Erreur lors de la lecture de %s : %s", auth_log, exc)

        # Collecte des erreurs via journalctl (dernière heure, priorité err)
        journal_errors = 0
        try:
            result = subprocess.run(
                [
                    "journalctl",
                    "--since",
                    "1h",
                    "--priority",
                    "err",
                    "--quiet",
                    "--output=short",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            journal_errors = len(lines)
        except Exception as exc:
            logger.warning("Erreur lors de la collecte des erreurs via journalctl : %s", exc)

        # Ajout des métriques collectées
        metrics.extend(
            [
                {
                    "name": "logs.errors_count",
                    "value": int(errors_count),
                    "type": "numeric",
                    "description": (
                        "Nombre d'erreurs détectées dans les principaux logs système "
                        "(syslog/messages/kern.log, dernières 1000 lignes)."
                    ),
                    "is_critical": True,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "logs.warnings_count",
                    "value": int(warnings_count),
                    "type": "numeric",
                    "description": (
                        "Nombre d'avertissements détectés dans les principaux logs système "
                        "(syslog/messages/kern.log, dernières 1000 lignes)."
                    ),
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "logs.auth_failures",
                    "value": int(auth_failures),
                    "type": "numeric",
                    "description": ("Nombre d'échecs d'authentification récents " "(auth.log, dernières 500 lignes)."),
                    "is_critical": True,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
                {
                    "name": "logs.journal_errors_last_hour",
                    "value": int(journal_errors),
                    "type": "numeric",
                    "description": ("Nombre d'erreurs journalctl sur la dernière heure " "(priorité err)."),
                    "is_critical": False,
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Type de collecteur
                },
            ]
        )

        # Log du nombre total de métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
