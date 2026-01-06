from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union

from monitoring_client.core.logger import get_logger, log_phase

# Configuration du logger (simplifiée)
logger = get_logger(__name__)

# Définition du type Metric
Metric = Dict[str, Any]

class BaseCollector(ABC):
    """
    Classe de base pour tous les collecteurs. Elle définit les attributs `name` et `editor`
    partagés par tous les collecteurs hérités. Elle inclut également la logique pour collecter
    les métriques et normaliser leur format.

    Contrat :
      - collect() : méthode publique, robuste (ne doit jamais lever d'exception)
      - _collect_metrics() : méthode à implémenter, peut lever des exceptions internes
    """

    # Attributs partagés entre tous les collecteurs
    name: str = "base"  # Identifiant logique du collecteur
    editor: str = "builtin"  # Type de collecteur (ex: "builtin", "custom")

    def collect(self) -> List[Metric]:
        """
        Point d'entrée standard pour exécuter un collecteur. Cette méthode encapsule l'appel
        à _collect_metrics(), gère les exceptions et garantit un retour de type list[dict].
        """
        phase_name = f"collector.{self.name}"
        log_phase(logger, phase_name, f"Exécution du collecteur '{self.name}'")

        try:
            # Appel de la méthode _collect_metrics() qui collecte les métriques spécifiques
            metrics = self._collect_metrics()
            if not isinstance(metrics, list):
                logger.error(
                    "Le collecteur '%s' a renvoyé un type invalide (%s), liste attendue.",
                    self.name,
                    type(metrics),
                )
                return []

            # Normalisation des métriques avant de les retourner
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
        Méthode à implémenter dans chaque collecteur spécifique. Elle doit retourner une liste de
        métriques brutes sous forme de dictionnaires.
        """
        raise NotImplementedError

    # ---- Helpers de normalisation ----

    def _normalize_metric(self, metric: Dict[str, Any]) -> Union[Metric, None]:
        """
        Normalise une métrique brute en appliquant des règles simples :
        - 'name' doit être une chaîne non vide
        - 'type' doit être parmi {"numeric", "boolean", "string"}
        - 'value' doit être cohérent avec 'type'
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

        # Coercion selon le type
        if m_type == "numeric":
            if isinstance(value, bool):
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

        # Dynamique : On utilise self.__class__.__name__ pour obtenir la classe enfant
        return {
            "name": name,
            "value": value,
            "type": m_type,
            "collector_name": self.__class__.__name__,  # Utilisation dynamique du nom de la classe enfant
            "editor_name": self.editor,  # Si chaque enfant a un éditeur propre, il peut être défini ici
        }
