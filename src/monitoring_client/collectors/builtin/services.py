import logging
import re
import subprocess

from monitoring_client.collectors.base_collector import BaseCollector

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
# Laisse DEBUG ici si tu veux diagnostiquer (sinon INFO en prod)
logger.setLevel(logging.DEBUG)


class ServicesCollector(BaseCollector):
    """
    Collecte le statut des services systemd :
    - une métrique booléenne par service (actif/en cours d'exécution)
    - compteurs globaux services actifs / services en échec

    Spécificité demandée :
    - Ne remonter QUE tty1 pour les getty (donc ignorer tty2..tty6..ttyN).
    - Si tty1 n'existe pas, ne remonter AUCUN tty (pas de getty@ttyX).

    Important (fix Debian) :
    - Le caractère "●" dans `systemctl list-units` n'est PAS un indicateur fiable de "not-found".
      C'est juste un marqueur d'unités "problématiques" selon la sortie.
    - Le vrai indicateur "not-found" est dans la colonne LOAD (2e colonne).
      Donc on ne renomme JAMAIS un service en "_unknown_service".
      On ignore simplement les unités dont LOAD == "not-found".
    """

    name = "services"
    editor = "builtin"

    # Remplace tout caractère non autorisé par "_" pour avoir des noms de métriques stables
    _metric_name_safe_re = re.compile(r"[^a-zA-Z0-9._-]")

    # Extrait le nom d'un service depuis une ligne de `systemctl list-units`.
    # Exemple de ligne possible (selon distro):
    #   getty@tty1.service loaded active running Getty on tty1
    #   ● syslog.service not-found inactive dead syslog.service
    #
    # On accepte un éventuel "●" (avec espaces) puis on capture <xxx.service>
    _service_name_regex = re.compile(r"^(?:●?\s*)(\S+\.service)\s+.*$")

    # Identifie les getty tty (tty1, tty2, ..., tty63...)
    _getty_tty_regex = re.compile(r"^getty@tty\d+\.service$")

    def _collect_metrics(self):
        metrics = []

        # ---------------------------------------------------------------------
        # 1) Récupération des services via systemctl
        # ---------------------------------------------------------------------
        try:
            # --plain : évite certains glyphes/formatages suivant la distro
            # (réduit les surprises de parsing, tout en gardant une sortie textuelle simple)
            result = subprocess.run(
                [
                    "systemctl",
                    "list-units",
                    "--all",
                    "--type=service",
                    "--no-legend",
                    "--no-pager",
                    "--plain",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
        except FileNotFoundError:
            logger.error("systemctl non trouvé, impossible de collecter les services.")
            return metrics
        except Exception as exc:
            logger.error(f"Erreur lors de l'exécution de systemctl list-units : {exc}")
            return metrics

        # Nettoyage des lignes
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        active_count = 0
        failed_count = 0

        # ---------------------------------------------------------------------
        # 2) Détection préalable : getty@tty1 existe ?
        #    - Si oui => on garde uniquement getty@tty1.service
        #    - Si non => on ne remonte aucun getty@ttyX
        # ---------------------------------------------------------------------
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

            if tty1_present:
                return service_name == "getty@tty1.service"
            return False

        # ---------------------------------------------------------------------
        # 3) Parcours des services et construction des métriques
        # ---------------------------------------------------------------------
        for line in lines:
            match = self._service_name_regex.match(line)
            if not match:
                # On log en debug plutôt qu'en warning si tu veux réduire le bruit,
                # mais je conserve ton warning d'origine.
                logger.warning(f"Nom de service invalide dans la ligne: {line}. Ignoré.")
                continue

            service_name = match.group(1)

            # systemctl list-units renvoie des colonnes:
            # UNIT LOAD ACTIVE SUB DESCRIPTION...
            parts = line.split()
            if len(parts) < 4:
                logger.debug(f"Ligne systemctl trop courte (ignorée): {line}")
                continue

            # Très important : LOAD est la 2e colonne (parts[1])
            # C'est ici qu'on trouve "loaded" / "not-found" / etc.
            load_state = parts[1]
            active_state = parts[2]  # active/inactive/failed/...
            sub_state = parts[3]     # running/dead/exited/...

            # Fix Debian : ignorer les unités fantômes / paquets absents / alias
            # (ne surtout PAS renommer en _unknown_service, sinon on crée des doublons)
            if load_state == "not-found":
                logger.debug(f"Service not-found ignoré: {service_name} ({line})")
                continue

            # Filtre des services transitoires "run-*"
            # Ces unités ont des noms changeants et génèrent du bruit dans la supervision.
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
                f"(load_state={load_state}, active_state={active_state}, sub_state={sub_state}, "
                f"is_active={is_active}, is_failed={is_failed})"
            )

            # Ajout de la métrique par service (booléen)
            metrics.append(
                {
                    "name": safe_service_name,
                    "value": bool(is_active),
                    "type": "boolean",
                    "collector_name": self.name,
                    "editor_name": self.editor,
                }
            )

        # ---------------------------------------------------------------------
        # 4) Ajout des métriques globales
        # ---------------------------------------------------------------------
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
