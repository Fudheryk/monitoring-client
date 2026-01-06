from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

# Ajouter le répertoire parent au sys.path pour l'import relatif
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from __version__ import __version__

from core.logger import get_logger, log_phase

logger = get_logger(__name__)

MetricDict = Dict[str, Any]


@dataclass
class PayloadTransformerConfig:
    """
    Configuration du transformer pour générer le payload API.

    - generator      : nom du client (ex: "monitoring-client")
    - version        : version du client
    - schema_version : version du schéma de payload (ex: "1.1.0")
    - timestamp_field: nom du champ timestamp dans metadata (ex: "timestamp"
                       ou "collection_time")
    """

    generator: str = "monitoring-client"
    version: str = __version__
    schema_version: str = "1.1.0"
    timestamp_field: str = "timestamp"


class PayloadTransformer:
    """
    Transforme des métriques + infos machine en payload JSON pour l'API.

    Format final :

    {
      "metadata": {
        "generator": "monitoring-client",
        "version": "0.1.0",
        "schema_version": "1.0",
        "timestamp": "2025-01-01T12:34:56Z"
      },
      "machine": {
        "hostname": "test-server",
        "os": "linux",
        "fingerprint": "sha256..."
      },
      "metrics": [
        {
          "name": "cpu.usage_percent",
          "value": 0.6,
          "type": "numeric"
        },
        {
          "name": "nginx.requests_per_sec",
          "value": 123.4,
          "vendor": "acme.nginx",
          "group_name": "nginx",
          "type": "numeric"
        }
      ]
    }
    """

    def __init__(self, config: PayloadTransformerConfig) -> None:
        self._config = config

    def build_payload(
        self,
        metrics: List[MetricDict],
        hostname: str,
        os_name: str,
        fingerprint: str,
        timestamp_iso: str,
    ) -> Dict[str, Any]:
        """
        Construit le payload API final.

        Paramètres :
          - metrics       : liste de métriques agrégées (builtin + vendor)
          - hostname      : nom d'hôte de la machine
          - os_name       : OS (ex: "linux", "windows")
          - fingerprint   : empreinte unique de la machine (SHA256)
          - timestamp_iso : timestamp ISO8601 (UTC) de la collecte

        Retour :
          - dict prêt à être sérialisé en JSON et envoyé à l'API.
        """
        log_phase(logger, "pipeline.transform", "Construction du payload API final")

        metadata = self._build_metadata(timestamp_iso)
        machine = self._build_machine(hostname, os_name, fingerprint)

        payload = {
            "metadata": metadata,
            "machine": machine,
            "metrics": metrics,
        }

        logger.info(
            "Payload construit : %d métriques, hostname='%s', os='%s'.",
            len(metrics),
            hostname,
            os_name,
        )

        return payload

    # ---------------------------------------------------------------------
    # Helpers internes
    # ---------------------------------------------------------------------

    def _build_metadata(self, timestamp_iso: str) -> Dict[str, Any]:
        """
        Construit le bloc 'metadata' selon la config actuelle.
        """
        meta = {
            "generator": self._config.generator,
            "version": self._config.version,
            "schema_version": self._config.schema_version,
        }

        # Champ timestamp configurable (timestamp, collection_time, etc.)
        meta[self._config.timestamp_field] = timestamp_iso

        return meta

    @staticmethod
    def _build_machine(
        hostname: str,
        os_name: str,
        fingerprint: str,
    ) -> Dict[str, Any]:
        """
        Construit le bloc 'machine' du payload.
        """
        return {
            "hostname": hostname,
            "os": os_name,
            "fingerprint": fingerprint,
        }
