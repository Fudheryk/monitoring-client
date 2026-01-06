import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from monitoring_client.core.logger import get_logger, log_phase

logger = get_logger(__name__)


@dataclass
class APIClientConfig:
    """
    Configuration simplifiée du client HTTP pour l'API.

    Cette structure peut être construite à partir de Config (Tâche 1).
    """

    base_url: str
    metrics_endpoint: str
    api_key_header: str
    api_key: str
    timeout_seconds: float = 5.0
    max_retries: int = 3
    verify_ssl: bool = True


class APIClientError(Exception):
    """Erreur lors de la communication avec l'API de monitoring."""


class APIClient:
    """
    Client HTTP responsable de l'envoi du payload de métriques au serveur.

    Fonctionnalités :
      - Construction de l'URL complète.
      - Envoi POST JSON.
      - Gestion de timeout.
      - Stratégie de retry exponentiel (jusqu'à max_retries).
      - Validation SSL.
      - Logging détaillé des requêtes / réponses.
    """

    def __init__(self, config: APIClientConfig, session: Optional[requests.Session] = None) -> None:
        self._config = config
        self._session = session or requests.Session()

        # Préparation des en-têtes de base
        self._base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            config.api_key_header: config.api_key,
        }

    @property
    def base_url(self) -> str:
        return self._config.base_url.rstrip("/")

    @property
    def metrics_url(self) -> str:
        endpoint = self._config.metrics_endpoint
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return self.base_url + endpoint

    def send_payload(self, payload: Dict[str, Any]) -> requests.Response:
        """
        Envoie un payload JSON vers l'endpoint /metrics avec retry logique.

        Retourne l'objet requests.Response (le dernier obtenu).
        Lève APIClientError en cas d'échec final (après retries).
        """
        log_phase(logger, "api.request", "Envoi du payload de métriques au serveur")

        body = json.dumps(payload, ensure_ascii=False)
        logger.debug("Payload JSON prêt à l'envoi: %s", body)

        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt < self._config.max_retries:
            attempt += 1
            try:
                logger.info(
                    "Tentative %d/%d d'envoi des métriques vers %s",
                    attempt,
                    self._config.max_retries,
                    self.metrics_url,
                )

                response = self._session.post(
                    self.metrics_url,
                    headers=self._base_headers,
                    data=body.encode("utf-8"),
                    timeout=self._config.timeout_seconds,
                    verify=self._config.verify_ssl,
                )

                # Logging de base
                logger.debug(
                    "Réponse HTTP reçue (status=%s, length=%s)",
                    response.status_code,
                    len(response.content or b""),
                )

                # Statuts 2xx : succès
                if 200 <= response.status_code < 300:
                    logger.info("Payload envoyé avec succès (HTTP %s).", response.status_code)
                    return response

                # Statuts 4xx : erreur côté client, pas de retry
                if 400 <= response.status_code < 500:
                    logger.error(
                        "Erreur client HTTP %s lors de l'envoi des métriques, pas de retry.",
                        response.status_code,
                    )
                    raise APIClientError(f"Erreur client HTTP {response.status_code}: {response.text}")

                # Statuts 5xx : retry possible
                logger.warning(
                    "Erreur serveur HTTP %s, tentative de retry...",
                    response.status_code,
                )
                last_exc = APIClientError(f"Erreur serveur HTTP {response.status_code}: {response.text}")

            except (requests.Timeout, requests.ConnectionError, requests.RequestException) as exc:
                logger.warning(
                    "Erreur réseau lors de l'envoi des métriques (tentative %d/%d): %s",
                    attempt,
                    self._config.max_retries,
                    exc,
                )
                last_exc = exc

            # Si on arrive ici, on va éventuellement retenter
            if attempt < self._config.max_retries:
                sleep_seconds = self._compute_backoff(attempt)
                logger.info("Attente de %.1f s avant la prochaine tentative.", sleep_seconds)
                time.sleep(sleep_seconds)

        # Toutes les tentatives ont échoué
        msg = f"Échec de l'envoi du payload après {self._config.max_retries} tentatives."
        logger.error(msg)
        raise APIClientError(msg) from last_exc

    @staticmethod
    def _compute_backoff(attempt: int) -> float:
        """
        Calcule le délai de retry exponentiel.

        attempt commence à 1 pour la première tentative.
        Exemple: tentative 1 -> 1s, 2 -> 2s, 3 -> 4s, etc.
        """
        base = 1.0
        # (attempt - 1) pour que la première fois ce soit 1 seconde
        return base * (2 ** (attempt - 1))


# Helpers d'intégration (optionnels) si on veut créer un client depuis Config (Tâche 1)
try:
    # Import protégé pour éviter les cycles dans certains contextes de tests
    from monitoring_client.core.config_loader import Config
except Exception:  # pragma: no cover - uniquement pour éviter un crash si non disponible
    Config = None  # type: ignore


def build_api_client_from_config(app_config: "Config") -> APIClient:  # type: ignore[valid-type]
    """
    Construit un APIClient à partir de la structure Config (Tâche 1).

    Utilise :
      - app_config.api
      - app_config.resolved_api_key
    """
    api_cfg = app_config.api
    client_cfg = APIClientConfig(
        base_url=api_cfg.base_url,
        metrics_endpoint=api_cfg.metrics_endpoint,
        api_key_header=api_cfg.api_key_header,
        api_key=app_config.resolved_api_key,
        timeout_seconds=api_cfg.timeout_seconds,
        max_retries=api_cfg.max_retries,
        verify_ssl=True,  # par défaut on valide SSL, peut être rendu paramétrable si besoin
    )
    return APIClient(client_cfg)
