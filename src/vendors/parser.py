from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.logger import get_logger, log_phase

from .validator import VendorDocument, VendorSchemaError, validate_vendor_document

logger = get_logger(__name__)


@dataclass
class VendorMetric:
    """
    Représentation interne d'une métrique vendor normalisée.

    Champs principaux :
      - vendor       : nom du vendor (ex: "acme.nginx")
      - group_name   : groupe fonctionnel (ex: "nginx")
      - name         : nom complet de la métrique (ex: "nginx.requests_per_sec")
      - command      : commande à exécuter (echo, script, etc.)
      - language     : langage associé à la commande (ex: "bash", "python")
      - type         : "numeric" | "boolean" | "string"
      - description  : description fonctionnelle fournie par le vendor
      - is_critical  : criticité suggérée par le vendor
      - source_file  : fichier vendor d'origine (Path)
      - raw_metric   : dict brut de la métrique (pour debug / logs)
    """

    vendor: str
    group_name: str
    name: str
    command: str
    language: str
    type: str
    description: str
    is_critical: bool
    source_file: Path
    raw_metric: Dict[str, Any]


class VendorParser:
    """
    Parser des fichiers vendor dans un dossier donné.

    Responsabilités :
      - Scanner le répertoire vendors (fichiers *.yaml, *.yml)
      - Charger le YAML
      - Valider via jsonschema (validator.py)
      - Normaliser en liste de VendorMetric
      - Gérer les erreurs fichier par fichier (warning, on continue)
    """

    def __init__(self, vendors_dir: Path) -> None:
        self.vendors_dir = vendors_dir

    # ---- Public API ----

    def parse_all(self) -> List[VendorMetric]:
        """
        Parcourt tous les fichiers vendor et renvoie une liste de VendorMetric.

        Fichiers invalides : warning et ignorés, mais on continue sur les autres.
        """
        log_phase(
            logger,
            "vendors.parse",
            f"Analyse des fichiers vendor dans {self.vendors_dir}",
        )

        metrics: List[VendorMetric] = []

        for path in self._discover_vendor_files():
            try:
                doc = self._load_yaml(path)
                validated = validate_vendor_document(doc, source=str(path))
                file_metrics = self._build_vendor_metrics(validated, path)
                metrics.extend(file_metrics)
                logger.info(
                    "Fichier vendor '%s' chargé (%d métriques).",
                    path,
                    len(file_metrics),
                )
            except VendorSchemaError as exc:
                logger.warning("Fichier vendor ignoré (schéma invalide): %s", exc)
            except Exception as exc:
                logger.warning(
                    "Erreur inattendue lors du traitement du fichier vendor '%s': %s",
                    path,
                    exc,
                )

        logger.info("Nombre total de métriques vendor chargées: %d", len(metrics))
        return metrics

    # ---- Internal helpers ----

    def _discover_vendor_files(self) -> List[Path]:
        """
        Retourne la liste des fichiers *.yaml / *.yml dans le dossier vendors.

        On ignore :
          - les dossiers
          - les fichiers terminant par .disabled ou .example
        """
        files: List[Path] = []

        if not self.vendors_dir.exists():
            logger.info(
                "Dossier vendors inexistant (%s), aucun fichier à charger.",
                self.vendors_dir,
            )
            return files

        if not self.vendors_dir.is_dir():
            logger.warning(
                "Chemin vendors n'est pas un dossier (%s), aucun fichier vendor chargé.",
                self.vendors_dir,
            )
            return files

        for entry in sorted(self.vendors_dir.iterdir()):
            if not entry.is_file():
                continue

            if entry.name.endswith((".yaml", ".yml")) and not entry.name.endswith((".disabled", ".example")):
                files.append(entry)

        logger.debug("Fichiers vendor détectés: %s", [str(f) for f in files])
        return files

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """
        Charge un fichier YAML et retourne un dict.

        Lève VendorSchemaError si le contenu n'est pas un mapping.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise VendorSchemaError(f"Impossible de lire le fichier {path}: {exc}") from exc

        try:
            data = yaml.safe_load(content)
        except Exception as exc:
            raise VendorSchemaError(f"YAML invalide dans {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise VendorSchemaError(
                f"Le contenu YAML doit être un objet (mapping) dans {path}, " f"trouvé {type(data)}."
            )

        return data

    def _build_vendor_metrics(self, document: VendorDocument, path: Path) -> List[VendorMetric]:
        """
        Construit les VendorMetric à partir d'un document validé.

        À ce stade :
          - le schéma JSON a déjà été validé (nom, vendor, type, etc.)
          - on peut donc indexer directement les champs requis
        """
        raw = document.data
        metadata: Dict[str, Any] = raw.get("metadata", {})
        metrics_raw: List[Dict[str, Any]] = raw.get("metrics", [])  # type: ignore[assignment]

        vendor_name: str = metadata.get("vendor", "")
        global_lang: str = metadata.get("language", "python")

        result: List[VendorMetric] = []

        for metric in metrics_raw:
            try:
                name: str = metric["name"]
                command: str = metric["command"]
                m_type: str = metric["type"]
                group_name: str = metric["group_name"]

                # Langage : spécifique à la métrique, sinon langage global, sinon python.
                lang: str = metric.get("language") or global_lang or "python"

                # Description et criticité viennent du vendor (obligatoires dans le schéma),
                description: str = metric.get("description", "")
                is_critical: bool = bool(metric.get("is_critical", False))

                vm = VendorMetric(
                    vendor=vendor_name,
                    group_name=group_name,
                    name=name,
                    command=command,
                    language=lang,
                    type=m_type,
                    description=description,
                    is_critical=is_critical,
                    source_file=path,
                    raw_metric=metric,
                )
                result.append(vm)
            except Exception as exc:
                logger.warning(
                    "Métrique ignorée dans '%s' (erreur de normalisation): %s / raw=%r",
                    path,
                    exc,
                    metric,
                )

        return result
