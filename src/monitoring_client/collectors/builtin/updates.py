import logging
import os
import subprocess

from monitoring_client.collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)

class PackageUpdatesCollector(BaseCollector):
    """
    Vérifie les mises à jour disponibles selon le gestionnaire de paquets :
    - APT (Debian/Ubuntu)
    - YUM / DNF (RedHat/CentOS/Fedora)
    """

    name = "package_updates"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self):
        metrics = []

        # Vérifier le gestionnaire de paquets et collecter les mises à jour disponibles
        if os.path.exists("/usr/bin/apt"):
            self._collect_apt(metrics)
        elif os.path.exists("/usr/bin/yum") or os.path.exists("/usr/bin/dnf"):
            cmd = "dnf" if os.path.exists("/usr/bin/dnf") else "yum"
            self._collect_yum_dnf(cmd, metrics)

        # Retour des métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics

    def _collect_apt(self, metrics):
        try:
            # Mises à jour disponibles
            update_check = subprocess.run(
                ["apt", "list", "--upgradeable"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            lines = [l for l in update_check.stdout.strip().split("\n") if l.strip() and "/" in l]
            updates_available = len(lines)

            # Mises à jour de sécurité (approx : recherche "security" dans la ligne)
            security_updates = len([l for l in update_check.stdout.split("\n") if "security" in l.lower()])

            metrics.extend(
                [
                    {
                        "name": "apt.updates_available",
                        "value": int(updates_available),
                        "type": "numeric",
                        "description": "Nombre de mises à jour disponibles pour les paquets APT.",
                        "is_critical": False,
                        "collector_name": self.name,  # Ajout du nom du collecteur
                        "editor_name": self.editor,  # Ajout du nom de l'éditeur
                    },
                    {
                        "name": "apt.security_updates",
                        "value": int(security_updates),
                        "type": "numeric",
                        "description": "Nombre de mises à jour de sécurité disponibles pour APT.",
                        "is_critical": True,
                        "collector_name": self.name,  # Ajout du nom du collecteur
                        "editor_name": self.editor,  # Ajout du nom de l'éditeur
                    },
                ]
            )

            # Version APT
            version_result = subprocess.run(
                ["apt", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            apt_version = version_result.stdout.strip().split("\n")[0] if version_result.returncode == 0 else "unknown"
            metrics.append(
                {
                    "name": "apt.version",
                    "value": apt_version,
                    "type": "string",
                    "description": "Version actuelle d'APT sur le système.",
                    "is_critical": False,
                    "collector_name": self.name,  # Ajout du nom du collecteur
                    "editor_name": self.editor,  # Ajout du nom de l'éditeur
                }
            )
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la collecte des mises à jour APT : %s", exc)

    def _collect_yum_dnf(self, cmd: str, metrics):
        try:
            result = subprocess.run(
                [cmd, "check-update", "--quiet"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            # Heuristique simple : lignes non vides et ne commençant pas par "Last"
            updates = len([l for l in result.stdout.split("\n") if l.strip() and not l.startswith("Last")])
            metrics.append(
                {
                    "name": f"{cmd}.updates_available",
                    "value": int(updates),
                    "type": "numeric",
                    "description": f"Nombre de mises à jour disponibles pour les paquets {cmd}.",
                    "is_critical": False,
                    "collector_name": self.name,  # Ajout du nom du collecteur
                    "editor_name": self.editor,  # Ajout du nom de l'éditeur
                }
            )

            version_result = subprocess.run(
                [cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            pkg_version = version_result.stdout.strip().split("\n")[0] if version_result.returncode == 0 else "unknown"
            metrics.append(
                {
                    "name": f"{cmd}.version",
                    "value": pkg_version,
                    "type": "string",
                    "description": f"Version actuelle de {cmd} sur le système.",
                    "is_critical": False,
                    "collector_name": self.name,  # Ajout du nom du collecteur
                    "editor_name": self.editor,  # Ajout du nom de l'éditeur
                }
            )
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la collecte des mises à jour via %s : %s", cmd, exc)
