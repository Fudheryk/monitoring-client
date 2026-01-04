from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from core.logger import get_logger, log_phase

logger = get_logger(__name__)


Metric = Dict[str, Any]


class BaseCollector(ABC):
    """
    Classe de base pour tous les collecteurs builtin.

    Contrat :
      - collect() : méthode publique, robuste (ne doit jamais lever d'exception)
      - _collect_metrics() : méthode à implémenter, peut lever des exceptions internes

    Les métriques doivent respecter le format :
      {
        "name": "category.metric_name",
        "value": 123.4,
        "type": "numeric" | "boolean" | "string"
      }
    """

    # Identifiant logique du collecteur (ex: "system", "network", "firewall")
    name: str = "base"

    def collect(self) -> List[Metric]:
        """
        Point d'entrée standard pour exécuter un collecteur.

        Cette méthode :
          - encapsule l'appel à _collect_metrics()
          - gère les exceptions pour éviter de casser le pipeline
          - garantit un retour de type list[dict]
        """
        phase_name = f"collector.{self.name}"
        log_phase(logger, phase_name, f"Exécution du collecteur builtin '{self.name}'")

        try:
            metrics = self._collect_metrics()
            if not isinstance(metrics, list):
                logger.error(
                    "Le collecteur '%s' a renvoyé un type invalide (%s), liste attendue.",
                    self.name,
                    type(metrics),
                )
                return []

            normalized: List[Metric] = []
            for metric in metrics:
                norm = self._normalize_metric(metric)
                if norm is not None:
                    normalized.append(norm)

            return normalized
        except Exception as exc:
            logger.error(
                "Erreur inattendue dans le collecteur '%s': %s",
                self.name,
                exc,
                exc_info=True,
            )
            return []

    @abstractmethod
    def _collect_metrics(self) -> List[Metric]:
        """
        Implémentation réelle de la collecte.

        Doit retourner une liste de métriques brutes (dicts).
        Les erreurs peuvent être levées ici, elles seront gérées par collect().
        """
        raise NotImplementedError

    # ---- Helpers de normalisation ----

    @staticmethod
    def _normalize_metric(metric: Dict[str, Any]) -> Metric | None:
        """
        Normalise une métrique brute et applique quelques règles simples :

          - 'name' doit être une chaîne non vide
          - 'type' ∈ {"numeric", "boolean", "string"}
          - 'value' doit être cohérente avec 'type'
        """
        if not isinstance(metric, dict):
            logger.warning("Métrique ignorée (type non dict): %r", metric)
            return None

        name = metric.get("name")
        value = metric.get("value")
        m_type = metric.get("type")

        if not isinstance(name, str) or not name:
            logger.warning("Métrique ignorée (name invalide): %r", metric)
            return None

        if m_type not in ("numeric", "boolean", "string"):
            logger.warning("Métrique ignorée (type invalide): %r", metric)
            return None

        # Coercion légère selon le type
        if m_type == "numeric":
            if isinstance(value, bool):
                # éviter True/False comme numériques
                logger.warning("Métrique numeric avec bool détecté, ignorée: %r", metric)
                return None
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except Exception:
                    logger.warning("Métrique numeric non convertible, ignorée: %r", metric)
                    return None
        elif m_type == "boolean":
            if not isinstance(value, bool):
                # Essai de conversion simple
                if isinstance(value, str):
                    lower = value.strip().lower()
                    if lower in ("true", "1", "yes", "on"):
                        value = True
                    elif lower in ("false", "0", "no", "off"):
                        value = False
                    else:
                        logger.warning("Métrique boolean non convertible, ignorée: %r", metric)
                        return None
                else:
                    logger.warning("Métrique boolean non convertible, ignorée: %r", metric)
                    return None
        elif m_type == "string":
            if value is None:
                value = ""
            elif not isinstance(value, str):
                value = str(value)

        return {
            "name": name,
            "value": value,
            "type": m_type,
        }
