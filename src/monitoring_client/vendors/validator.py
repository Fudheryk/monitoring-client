from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict

import jsonschema

from monitoring_client.core.logger import get_logger

logger = get_logger(__name__)


class VendorSchemaError(Exception):
    """Erreur de validation du fichier vendor."""


# Noms autorisés pour vendor / métriques / group_name
_NAME_PATTERN = r"^[A-Za-z0-9_.-]+$"

# Langages supportés pour les commandes vendor
_ALLOWED_LANGUAGES = [
    "python",
    "bash",
    "python2",
    "java",
    "node",
    "nodejs",
    "sh",
]

# Schéma JSON des fichiers vendor.
# IMPORTANT :
#   - metadata.vendor     : requis, non vide, pattern simple
#   - metrics[*].name     : requis
#   - metrics[*].command  : requis (commande à exécuter)
#   - metrics[*].type     : requis ("numeric" / "boolean" / "string")
#   - metrics[*].group_name : requis
#   - metrics[*].description : requis (le backend en a besoin pour VendorMetricIn)
#   - metrics[*].is_critical : requis (le backend en a besoin pour VendorMetricIn)
_VENDOR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["metadata", "metrics"],
    "properties": {
        "metadata": {
            "type": "object",
            "required": ["vendor"],
            "properties": {
                "vendor": {
                    "type": "string",
                    "pattern": _NAME_PATTERN,
                },
                "language": {
                    "type": "string",
                    "enum": _ALLOWED_LANGUAGES,
                },
                "version": {
                    "type": "string",
                },
            },
            "additionalProperties": True,
        },
        "metrics": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                # On impose description + is_critical pour coller au schéma VendorMetricIn
                "required": ["name", "command", "type", "group_name", "description", "is_critical"],
                "properties": {
                    "name": {
                        "type": "string",
                        "pattern": _NAME_PATTERN,
                    },
                    "command": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "language": {
                        "type": "string",
                        "enum": _ALLOWED_LANGUAGES,
                    },
                    "type": {
                        "type": "string",
                        "enum": ["numeric", "boolean", "string"],
                    },
                    "group_name": {
                        "type": "string",
                        "pattern": _NAME_PATTERN,
                    },
                    "description": {
                        "type": "string",
                    },
                    "is_critical": {
                        "type": "boolean",
                    },
                },
                # Non tolérant aux propriétés supplémentaires
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


@dataclass
class VendorDocument:
    """
    Représente un document vendor validé.

    - data   : contenu YAML validé
    - source : chemin du fichier (pour logs / debug)
    """

    data: Dict[str, Any]
    source: str


def _normalize_metadata_aliases(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gère les alias / erreurs fréquentes sur le nom du bloc metadata.

    Exemple:
      - "yamlmetadata" (typo historique) -> "metadata"
    """
    if "metadata" in raw:
        return raw

    # Compatibilité : certains fichiers peuvent utiliser "yamlmetadata"
    if "yamlmetadata" in raw and "metadata" not in raw:
        raw["metadata"] = raw.pop("yamlmetadata")
        logger.debug("Alias 'yamlmetadata' détecté, normalisé en 'metadata' pour le fichier vendor.")

    return raw


def _normalize_language(lang: str) -> str:
    """
    Normalise certains alias de langage (ex: nodejs -> node).

    La validation du schéma s'appuie sur _ALLOWED_LANGUAGES, donc cette
    fonction est surtout utile pour homogénéiser.
    """
    if lang == "nodejs":
        return "node"
    return lang


def validate_vendor_document(raw: Dict[str, Any], source: str) -> VendorDocument:
    """
    Valide un document vendor brut contre le schéma interne.

    Étapes :
      1. Normalisation des alias de metadata (yamlmetadata → metadata).
      2. Validation jsonschema stricte (_VENDOR_SCHEMA).
      3. Normalisation légère (language global et par métrique).
      4. Vérification supplémentaire que vendor != "builtin".

    Lève VendorSchemaError si le document est invalide.
    """
    if not isinstance(raw, dict):
        raise VendorSchemaError(f"Document YAML racine invalide (dict attendu) dans {source}")

    raw = _normalize_metadata_aliases(raw)

    try:
        jsonschema.validate(instance=raw, schema=_VENDOR_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise VendorSchemaError(f"Fichier vendor invalide ({source}): {exc.message}") from exc

    # Normalisation légère post-validation
    metadata = raw.get("metadata", {})
    lang = metadata.get("language")
    if isinstance(lang, str):
        metadata["language"] = _normalize_language(lang)
        raw["metadata"] = metadata

    # Vérification : un fichier vendor ne doit pas utiliser vendor="builtin"
    vendor_name = (metadata.get("vendor") or "").strip().lower()
    if vendor_name == "builtin":
        raise VendorSchemaError(f"Fichier vendor invalide ({source}): 'vendor' ne doit pas être 'builtin'.")

    # Normaliser language au niveau métrique + revalider name/group_name par sécurité
    metrics = raw.get("metrics") or []
    for metric in metrics:
        m_lang = metric.get("language")
        if isinstance(m_lang, str):
            metric["language"] = _normalize_language(m_lang)

        # Double sécurité : pattern name / group_name
        for key in ("name", "group_name"):
            val = metric.get(key)
            if isinstance(val, str) and not re.match(_NAME_PATTERN, val):
                raise VendorSchemaError(f"Champ '{key}' invalide dans {source}: '{val}' ne respecte pas le pattern.")

    return VendorDocument(data=raw, source=source)
