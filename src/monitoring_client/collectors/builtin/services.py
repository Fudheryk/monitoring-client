import logging
import re
import subprocess

from monitoring_client.collectors.base_collector import BaseCollector

# Configuration du logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # DEBUG pour voir en détail ce qui est collecté / filtré


class ServicesCollector(BaseCollector):
    """
    Collecte le statut des services systemd :
    - une métrique booléenne par service (actif/en cours d'exécution)
    - compteurs globaux services actifs / services en échec

    Spécificité demandée :
    - Ne remonter QUE tty1 pour les getty (donc ignorer tty2..tty6..ttyN).
    - Si tty1 n'existe pas, ne remonter AUCUN tty (pas de getty@ttyX).
    """

    name = "services"     # Identifiant du collecteur
    editor = "builtin"    # Type de collecteur

    _metric_name_safe_re = re.compile(r"[^a-zA-Z0-9._-]")

    # Regex: extrait le nom du service depuis une ligne systemctl list-units
    # Exemple de ligne typique:
    # getty@tty1.service loaded active running Getty on tty1
    _service_name_regex = re.compile(r"^(?:●?\s*)(\S+\.service)\s+.*$")

    # Regex: identifie les getty tty (tty1, tty2, ..., tty63...)
    _getty_tty_regex = re.compile(r"^getty@tty\d+\.service$")

    def _collect_metrics(self):
        metrics = []

        # 1) On récupère la liste des unités systemd de type service
        try:
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
        except FileNotFoundError:
            # systemd absent / systemctl non présent
            logger.error("systemctl non trouvé, impossible de collecter les services.")
            return metrics
        except Exception as exc:
            logger.error(f"Erreur lors de l'exécution de systemctl list-units : {exc}")
            return metrics

        # Nettoyage des lignes
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        active_count = 0
        failed_count = 0

        # 2) Détection préalable : est-ce que getty@tty1.service existe ?
        #    - S'il existe => on ne garde QUE celui-ci pour les TTY.
        #    - S'il n'existe pas => on ne garde AUCUN getty@ttyX.
        tty1_present = False
        for line in lines:
            match = self._service_name_regex.match(line)
            if not match:
                continue
            service_name = match.group(1)
            if service_name == "getty@tty1.service":
                tty1_present = True
                break

        logger.debug(f"Présence de getty@tty1.service: {tty1_present}")

        def keep_service(service_name: str) -> bool:
            """
            Politique de filtrage des services.

            - Tout ce qui n'est pas un getty tty => gardé.
            - Pour les getty tty :
              - si tty1 est présent => on ne garde que getty@tty1.service
              - sinon => on ne garde aucun getty@ttyX
            """
            if not self._getty_tty_regex.match(service_name):
                return True

            # service getty@ttyX
            if tty1_present:
                return service_name == "getty@tty1.service"
            return False

        # 3) Parcours des services et construction des métriques
        for line in lines:
            match = self._service_name_regex.match(line)
            if not match:
                logger.warning(f"Nom de service invalide dans la ligne: {line}. Ignoré.")
                continue

            service_name = match.group(1)

            # systemctl list-units renvoie des colonnes:
            # UNIT LOAD ACTIVE SUB DESCRIPTION...
            parts = line.split()
            if len(parts) < 4:
                continue

            active_state = parts[2]  # active/inactive/failed/...
            sub_state = parts[3]     # running/dead/exited/...

            # Gestion "not-found" (systemctl peut mettre une puce '●' en début de ligne)
            # Ton code original traitait ça en remplaçant par un service générique.
            # On garde la même logique, mais on applique ensuite le filtre.
            if line.startswith("●"):
                logger.warning(f"Ligne indique un service non trouvé: {line}")
                service_name = "_unknown_service"
                active_state = "inactive"
                sub_state = "dead"

            # Filtre des services transitoires / dynamiques "run-*"
            # (souvent créés à la volée pour exécuter une tâche puis disparaître).
            # Exemple vu chez toi: run-plesk-deferred-aca-1768583362.service
            # On les ignore pour éviter le bruit (noms qui changent, NO DATA, etc.).
            if service_name.startswith("run-") and service_name.endswith(".service"):
                logger.debug(f"Service transitoire ignoré (run-*): {service_name}")
                continue

            # Appliquer le filtrage demandé (ne garder que tty1)
            if not keep_service(service_name):
                logger.debug(f"Service filtré (TTY != tty1): {service_name}")
                continue

            # Déterminer si le service est actif ou en échec
            is_active = (active_state == "active")
            is_failed = (active_state == "failed")

            if is_active:
                active_count += 1
            if is_failed:
                failed_count += 1

            # Nettoyage du nom de la métrique
            safe_service_name = self._metric_name_safe_re.sub("_", service_name)

            logger.debug(
                f"Service retenu: {service_name} -> metric={safe_service_name} "
                f"(active_state={active_state}, sub_state={sub_state}, is_active={is_active})"
            )

            # Ajout de la métrique par service
            metrics.append(
                {
                    "name": safe_service_name,
                    "value": bool(is_active),
                    "type": "boolean",
                    "collector_name": self.name,
                    "editor_name": self.editor,
                }
            )

        # 4) Ajout des métriques globales
        metrics.append(
            {
                "name": "services.active_count",
                "value": int(active_count),
                "type": "numeric",
                "collector_name": self.name,
                "editor_name": self.editor,
            }
        )
        metrics.append(
            {
                "name": "services.failed_count",
                "value": int(failed_count),
                "type": "numeric",
                "collector_name": self.name,
                "editor_name": self.editor,
            }
        )

        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics
