from __future__ import annotations

from typing import Any, Dict, List

from monitoring_client.core.logger import get_logger, log_phase

logger = get_logger(__name__)

MetricDict = Dict[str, Any]


class MetricsAggregator:
    """
    Agrège les métriques builtin et vendor en une seule liste cohérente.

    Règles :
      - Les métriques builtin sont ajoutées en premier.
      - Les métriques vendor sont ajoutées ensuite.
      - En cas de doublon sur le champ 'name' :
          * la métrique vendor ÉCRASE la builtin
          * un warning est loggué
      - Les métriques sans champ 'name' ou 'type' ou 'value' sont ignorées.

    Format attendu :
      - builtin_metrics : [{"name": str, "value": any, "type": str}, ...]
      - vendor_metrics  : [{"name": str, "value": any, "type": str,
                            "vendor": str, "group_name": str, ...}, ...]
    """

    def aggregate(
        self,
        builtin_metrics: List[MetricDict],
        vendor_metrics: List[MetricDict],
    ) -> List[MetricDict]:
        """
        Concatène les métriques builtin et vendor avec gestion des doublons.

        Retour :
          - Liste finale de métriques (builtin + vendor, avec écrasement).
        """
        log_phase(
            logger,
            "pipeline.aggregate",
            "Agrégation des métriques builtin et vendor",
        )

        merged: Dict[str, MetricDict] = {}

        # 1. Ajout des métriques builtin
        for metric in builtin_metrics:
            m = self._normalize_metric_dict(metric, source="builtin")
            if not m:
                continue
            name = m["name"]
            if name in merged:
                logger.warning(
                    "Doublon inattendu dans les métriques builtin pour name='%s', "
                    "la dernière valeur sera conservée.",
                    name,
                )
            merged[name] = m

        # 2. Ajout des métriques vendor (écrasent les builtin en cas de doublon)
        for metric in vendor_metrics:
            m = self._normalize_metric_dict(metric, source="vendor")
            if not m:
                continue
            name = m["name"]
            if name in merged:
                logger.warning(
                    "La métrique vendor '%s' écrase une métrique builtin existante.",
                    name,
                )
            merged[name] = m

        final_metrics = list(merged.values())
        logger.info(
            "Agrégation terminée : %d métriques builtin, %d métriques vendor, %d métriques finales.",
            len(builtin_metrics),
            len(vendor_metrics),
            len(final_metrics),
        )
        return final_metrics

    # ---------------------------------------------------------------------
    # Helpers internes
    # ---------------------------------------------------------------------

    @staticmethod
    def _normalize_metric_dict(
        metric: Dict[str, Any],
        source: str,
    ) -> MetricDict | None:
        """
        Vérifie qu'une métrique possède au minimum :
          - name (str, non vide)
          - type (str)
          - value (any)

        En cas de problème, log un warning et renvoie None.
        """
        if not isinstance(metric, dict):
            logger.warning("Métrique %s ignorée (type non dict): %r", source, metric)
            return None

        name = metric.get("name")
        m_type = metric.get("type")

        if not isinstance(name, str) or not name:
            logger.warning(
                "Métrique %s ignorée (champ 'name' invalide ou manquant): %r",
                source,
                metric,
            )
            return None

        if not isinstance(m_type, str) or not m_type:
            logger.warning(
                "Métrique %s ignorée (champ 'type' invalide ou manquant): %r",
                source,
                metric,
            )
            return None

        # 'value' peut être None (ex: métrique non disponible), on le laisse passer.
        if "value" not in metric:
            logger.warning(
                "Métrique %s ignorée (champ 'value' manquant) pour name='%s'.",
                source,
                name,
            )
            return None

        return metric
