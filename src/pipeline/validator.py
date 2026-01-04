from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.logger import get_logger, log_phase


logger = get_logger(__name__)

MetricDict = Dict[str, Any]
PayloadDict = Dict[str, Any]

# Noms de métriques autorisés : alphanumérique + . - _
_METRIC_NAME_REGEX = re.compile(r"^[a-zA-Z0-9._\-\[\]/]+$")

# Types logiques supportés dans le payload final
_ALLOWED_TYPES = {"numeric", "boolean", "string"}


@dataclass
class ValidationError:
    """
    Représente une erreur de validation dans le payload.

    Attributs :
      - path    : chemin logique de la donnée (ex: "metrics[10].name")
      - message : description de l'erreur
    """

    path: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"path": self.path, "message": self.message}


class PayloadValidator:
    """
    Validation de cohérence et de conformité du payload final.

    Règles :
      - Noms de métriques : ^[a-zA-Z0-9._-]+$
      - Types supportés : "numeric", "boolean", "string"
      - Valeur cohérente avec le type :
          * numeric : int ou float (bool interdit)
          * boolean : bool
          * string  : str
      - Collecte de toutes les erreurs (pas d'arrêt au 1er échec)

    IMPORTANT :
      - Ce validateur ne fait PAS la différence builtin/vendor.
        Il valide uniquement la forme :
          * métadonnées racine (metadata/machine/metrics)
          * cohérence (name/type/value)
        La distinction BuiltinMetricIn / VendorMetricIn (présence
        obligatoire de vendor/group_name/description/is_critical pour
        les vendors) est gérée côté backend.
    """

    def validate_metric_name(self, name: Any) -> bool:
        """
        Valide un nom de métrique selon la regex ^[a-zA-Z0-9._-]+$.

        Retourne True si valide, False sinon.
        """
        if not isinstance(name, str):
            return False
        if not name:
            return False
        return bool(_METRIC_NAME_REGEX.match(name))

    def validate_metric_type(self, value: Any, expected_type: Any) -> bool:
        """
        Valide la cohérence entre la valeur et le type attendu.

        expected_type doit être une chaîne parmi {"numeric", "boolean", "string"}.

        Règles :
          - "numeric" : value est int ou float (mais pas bool)
          - "boolean" : value est bool
          - "string"  : value est str
        """
        if not isinstance(expected_type, str):
            return False

        etype = expected_type.strip().lower()
        if etype not in _ALLOWED_TYPES:
            return False

        if etype == "numeric":
            # exclure explicitement bool (bool hérite de int en Python)
            if isinstance(value, bool):
                return False
            return isinstance(value, (int, float))

        if etype == "boolean":
            return isinstance(value, bool)

        if etype == "string":
            return isinstance(value, str)

        # Par sécurité (devrait être unreachable)
        return False

    def validate_payload(self, payload: PayloadDict) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Valide le payload complet avant envoi.

        Vérifications principales :
          - présence des blocs "metadata", "machine", "metrics"
          - "metrics" est une liste
          - pour chaque métrique :
              * présence de "name", "type", "value"
              * type ∈ {"numeric", "boolean", "string"}
              * nom valide (regex)
              * valeur cohérente avec le type

        NOTE :
          - On ne vérifie pas ici les champs spécifiques aux vendors
            (vendor/group_name/description/is_critical). C'est le backend
            qui applique ce niveau de validation sur AgentMetricIn.
        """
        log_phase(logger, "pipeline.validate", "Validation du payload avant envoi")

        errors: List[ValidationError] = []

        # --- Vérification racine ---
        if not isinstance(payload, dict):
            errors.append(
                ValidationError(
                    path="$",
                    message=(
                        "Payload racine invalide, dict attendu, "
                        f"trouvé {type(payload)}."
                    ),
                )
            )
            return False, [e.to_dict() for e in errors]

        # Blocs de base
        for key in ("metadata", "machine", "metrics"):
            if key not in payload:
                errors.append(
                    ValidationError(
                        path="$",
                        message=f"Champ obligatoire manquant au niveau racine: '{key}'.",
                    )
                )

        metrics = payload.get("metrics")
        if not isinstance(metrics, list):
            errors.append(
                ValidationError(
                    path="$.metrics",
                    message=(
                        "Le champ 'metrics' doit être une liste, "
                        f"trouvé {type(metrics)}."
                    ),
                )
            )
            # On continue malgré tout, mais sans itérer si ce n'est pas une liste
            metrics = []

        # --- Validation métriques ---
        for idx, metric in enumerate(metrics):
            path_prefix = f"$.metrics[{idx}]"

            if not isinstance(metric, dict):
                errors.append(
                    ValidationError(
                        path=path_prefix,
                        message=(
                            "Métrique invalide, dict attendu, "
                            f"trouvé {type(metric)}."
                        ),
                    )
                )
                continue

            # Nom
            name = metric.get("name")
            if name is None:
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.name",
                        message="Champ 'name' manquant pour une métrique.",
                    )
                )
            elif not self.validate_metric_name(name):
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.name",
                        message=(
                            f"Nom de métrique invalide: {name!r} "
                            "(autorisé: alphanumérique + . + - + _)."
                        ),
                    )
                )

            # Type
            m_type = metric.get("type")
            if m_type is None:
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.type",
                        message="Champ 'type' manquant pour une métrique.",
                    )
                )
                # Si pas de type, on ne poursuit pas la validation de la valeur
                continue

            if not isinstance(m_type, str):
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.type",
                        message=(
                            "Champ 'type' doit être une chaîne, "
                            f"trouvé {type(m_type)}."
                        ),
                    )
                )
                continue

            m_type_norm = m_type.strip().lower()
            if m_type_norm not in _ALLOWED_TYPES:
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.type",
                        message=(
                            f"Type de métrique non supporté: {m_type!r}. "
                            f"Types autorisés: {sorted(_ALLOWED_TYPES)}."
                        ),
                    )
                )
                continue

            # Valeur
            if "value" not in metric:
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.value",
                        message="Champ 'value' manquant pour une métrique.",
                    )
                )
                continue

            value = metric.get("value")
            if not self.validate_metric_type(value, m_type):
                errors.append(
                    ValidationError(
                        path=f"{path_prefix}.value",
                        message=(
                            f"Valeur '{value!r}' incohérente avec "
                            f"le type déclaré '{m_type}'."
                        ),
                    )
                )

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Validation du payload réussie, aucune erreur détectée.")
        else:
            logger.warning(
                "Validation du payload échouée : %d erreur(s) détectée(s).",
                len(errors),
            )
            for err in errors:
                logger.debug("Validation error: path=%s message=%s", err.path, err.message)

        return is_valid, [e.to_dict() for e in errors]
