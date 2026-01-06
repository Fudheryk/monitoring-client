import logging
import re
import subprocess
from collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Niveau de log réglé sur DEBUG pour plus de détails

class ServicesCollector(BaseCollector):
    """
    Collecte le statut des services systemd :
    - un booléen par service (actif/en cours d'exécution)
    - compteur global de services actifs / en échec
    """

    name = "services"  # Identifiant du collecteur
    editor = "builtin"  # Type de collecteur, ici "builtin"

    _metric_name_safe_re = re.compile(r"[^a-zA-Z0-9._-]")

    def _collect_metrics(self):
        metrics = []

        try:
            # Exécution de la commande systemctl pour lister tous les services
            result = subprocess.run(
                [
                    "systemctl",
                    "list-units",
                    "--all",
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
            logger.error("systemctl non trouvé, impossible d'exécuter la commande.")
            return metrics
        except Exception as exc:  # Erreur générique
            logger.error(f"Erreur lors de l'exécution de systemctl list-units : {exc}")
            return metrics

        # Debug: afficher toute la sortie de systemctl
        lines = result.stdout.strip().split("\n")
        active_count = 0
        failed_count = 0

        service_name_regex = re.compile(r"^(?:●?\s*)(\S+\.service)\s+.*$")

        # Dans la boucle de traitement des services
        for line in lines:
            line = line.strip()  # Enlever les espaces autour de la ligne
            if not line:
                continue

            # Utilisation de la regex pour capturer le nom du service
            match = service_name_regex.match(line)
            if match:
                service_name = match.group(1)  # Le nom du service trouvé
            else:
                logger.warning(f"Nom de service invalide trouvé dans la ligne: {line}. Service ignoré.")
                continue

            # On extrait les autres informations
            parts = line.split()
            if len(parts) < 4:
                continue

            active_state = parts[2]  # Statut du service
            sub_state = parts[3]  # Sous-état du service

            # Log: afficher chaque ligne analysée
            logger.debug(f"Ligne analysée: {line}")
            logger.debug(f"Nom du service: {service_name}, État: {active_state}, Sous-état: {sub_state}")

            # Si le service est marqué comme "not-found" (indiqué par un nom commençant par '●'),
            # on le conserve mais on le traite comme inactif
            if service_name.startswith('●'):
                logger.warning(f"Ligne : {line} indique un service non trouvé.")
                logger.warning(f"Service non trouvé, mais conservé: {service_name}")
                service_name = "_unknown_service"  # Remplacer le nom par un nom générique pour ceux non trouvés
                active_state = "inactive"  # Les services non trouvés sont considérés comme inactifs
                sub_state = "dead"  # Marquer comme mort si non trouvé

            # Déterminer si le service est actif ou en échec
            is_active = active_state == "active" and sub_state == "running"
            is_failed = active_state == "failed"

            if is_active:
                active_count += 1  # Incrémenter le compteur des services actifs
            if is_failed:
                failed_count += 1  # Incrémenter le compteur des services en échec

            # Sanitize du nom de service pour respecter les caractères valides dans les noms
            safe_service_name = self._metric_name_safe_re.sub("_", service_name)

            # Log pour vérifier que les informations sont bien incluses
            logger.debug(f"Inclusion des informations dans la métrique: {safe_service_name}, {self.name}, {self.editor}")

            # Ajout de la métrique pour chaque service
            metrics.append(
                {
                    "name": f"{safe_service_name}",  # Nom du service nettoyé
                    "value": bool(is_active),  # Valeur booléenne (True si actif, False si inactif)
                    "type": "boolean",  # Type de la métrique
                    "collector_name": self.name,  # Nom du collecteur (via self)
                    "editor_name": self.editor,  # Type de collecteur (via self)
                }
            )

        # Ajout des statistiques globales
        metrics.append(
            {
                "name": "services.active_count",
                "value": int(active_count),
                "type": "numeric",
                "collector_name": self.name,  # Directement via self
                "editor_name": self.editor,  # Directement via self
            }
        )
        metrics.append(
            {
                "name": "services.failed_count",
                "value": int(failed_count),
                "type": "numeric",
                "collector_name": self.name,  # Directement via self
                "editor_name": self.editor,  # Directement via self
            }
        )

        # Log pour afficher le nombre total de métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
