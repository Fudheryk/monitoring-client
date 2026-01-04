#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from core.logger import configure_logging, get_logger, log_phase
from core.config_loader import ConfigLoader, ConfigError
from core.fingerprint import generate_fingerprint, FingerprintError
from core.api_client import build_api_client_from_config, APIClientError

from collectors.loader import run_builtin_collectors
from vendors.parser import VendorParser
from vendors.executor import CommandExecutor

from pipeline.aggregator import MetricsAggregator
from pipeline.transformer import PayloadTransformer, PayloadTransformerConfig
from pipeline.validator import PayloadValidator

from __version__ import __version__


# Affiche la version du client
print(f"Monitoring Client - Version {__version__}")
print(__version__)  # Debug: Affiche la version pour vérifier


logger = get_logger(__name__)


# Exit codes
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_VALIDATION_ERROR = 2
EXIT_NETWORK_ERROR = 3


# ---------------------------------------------------------------------------
# CLI PARSING
# ---------------------------------------------------------------------------

def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitoring Client - Metrics Collector & Sender"
    )

    parser.add_argument(
        "--config",
        help="Chemin vers le fichier de configuration (defaut: config/config.yaml)",
        type=str,
        default="config/config.yaml",
    )

    parser.add_argument(
        "--dry-run",
        help="Génère le payload mais n'envoie rien au serveur (affiche le JSON)",
        action="store_true"
    )

    parser.add_argument(
        "--verbose",
        help="Active le mode DEBUG pour les logs",
        action="store_true",
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# MAIN ORCHESTRATION
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_cli_args()

    # Configure global logging
    configure_logging(
        level="DEBUG" if args.verbose else "INFO",
        fmt="plain",
        console_enabled=True,
        file_enabled=False,
    )

    logger.info("=== Monitoring Client - Starting Execution ===")

    # ------------------------
    # 1) LOAD CONFIG
    # ------------------------
    try:
        config_loader = ConfigLoader(config_path=Path(args.config))
        config = config_loader.load()
    except ConfigError as exc:
        logger.error("❌ Erreur de configuration : %s", exc)
        return EXIT_CONFIG_ERROR

    log_phase(logger, "config.loaded", "✓ Configuration chargée avec succès")

    # ------------------------
    # 2) API KEY RESOLUTION
    # ------------------------
    log_phase(logger, "apikey", "✓ Clé API récupérée")
    api_key = config.resolved_api_key

    # ------------------------
    # 3) FINGERPRINT
    # ------------------------
    try:
        cache_path = (
            config.base_dir
            / config.paths.data_dir
            / (config.fingerprint.cache_file or "fingerprint")
        )
        fingerprint = generate_fingerprint(
            method=config.fingerprint.method,
            salt=config.fingerprint.salt,
            cache_path=cache_path,
            force_recompute=config.fingerprint.force_recompute,
        )
        log_phase(logger, "fingerprint.done", f"✓ Fingerprint calculé : {fingerprint[:20]}…")
    except FingerprintError as exc:
        logger.error("❌ Erreur fingerprint : %s", exc)
        return EXIT_CONFIG_ERROR

    # ------------------------
    # 4) COLLECT BUILTIN METRICS
    # ------------------------
    builtin_metrics = run_builtin_collectors()
    log_phase(
        logger,
        "builtin.collect",
        f"✓ Collecte builtin terminée ({len(builtin_metrics)} métriques)"
    )

    # ------------------------
    # 5) VENDOR METRICS : PARSE + EXECUTE
    # ------------------------
    vendor_parser = VendorParser(Path(config.paths.vendors_dir))
    vendor_docs = vendor_parser.parse_all()  # VendorMetric objects (raw)

    executor = CommandExecutor()
    vendor_metrics = []

    for vm in vendor_docs:
        value = executor.execute_metric(vm, timeout=5.0)
        if value is not None:
            vendor_metrics.append(
                {
                    "name": vm.name,
                    "value": value,
                    "type": vm.type,
                    "vendor": vm.vendor,
                    "group_name": vm.group_name,
	            "description": vm.description,
                    "is_critical": vm.is_critical
                }
            )
        else:
            logger.warning(
                "Vendor metric '%s' ignorée (erreur d'exécution).", vm.name
            )

    log_phase(
        logger,
        "vendor.collect",
        f"✓ Vendor : {len(vendor_docs)} définitions, {len(vendor_metrics)} métriques exécutées"
    )

    # ------------------------
    # 6) AGGREGATION & TRANSFORMATION
    # ------------------------
    aggregator = MetricsAggregator()
    all_metrics = aggregator.aggregate(builtin_metrics, vendor_metrics)

    transformer = PayloadTransformer(
        PayloadTransformerConfig(
            generator=config.client.name,
            version=config.client.version,
            schema_version=config.client.schema_version,
            timestamp_field="timestamp",
        )
    )

    timestamp_iso = datetime.utcnow().isoformat() + "Z"

    payload = transformer.build_payload(
        metrics=all_metrics,
        hostname=_resolve_hostname(config),
        os_name=_resolve_os(config),
        fingerprint=fingerprint,
        timestamp_iso=timestamp_iso,
    )

    log_phase(logger, "pipeline.transform", "✓ Agrégation & transformation OK")

    # ------------------------
    # 7) VALIDATION DU PAYLOAD
    # ------------------------
    validator = PayloadValidator()
    is_valid, errors = validator.validate_payload(payload)

    if not is_valid:
        logger.error("❌ Le payload contient %d erreurs et ne peut pas être envoyé.", len(errors))
        for err in errors:
            logger.error("  - %s: %s", err["path"], err["message"])
        return EXIT_VALIDATION_ERROR

    log_phase(logger, "payload.validation", "✓ Validation des données OK")

    # ------------------------
    # 8) API SEND or DRY-RUN
    # ------------------------
    if args.dry_run:
        log_phase(logger, "dryrun", "✓ Mode dry-run, aucun envoi effectué")
        import json
        print(json.dumps(payload, indent=2))
        return EXIT_OK

    try:
        api_client = build_api_client_from_config(config)
        response = api_client.send_payload(payload)
        log_phase(
            logger,
            "api.sent",
            f"✓ Payload envoyé au serveur (HTTP {response.status_code})"
        )
        return EXIT_OK

    except APIClientError as exc:
        logger.error("❌ Erreur réseau/API : %s", exc)
        return EXIT_NETWORK_ERROR

    except Exception as exc:
        logger.error("❌ Erreur inattendue lors de l'envoi API : %s", exc)
        return EXIT_NETWORK_ERROR


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _resolve_hostname(config) -> str:
    """
    Détermine le hostname selon les règles de configuration.
    """
    import socket

    src = config.machine.hostname_source
    if src == "system":
        return socket.gethostname()
    if src == "fqdn":
        return socket.getfqdn()
    if src == "static":
        return config.machine.hostname_override or socket.gethostname()

    return socket.gethostname()


def _resolve_os(config) -> str:
    """
    Détermine l’OS selon config ou autodetection.
    """
    if config.machine.os_override:
        return config.machine.os_override

    import platform
    name = platform.system().lower()
    return "linux" if "linux" in name else name


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.error("Interruption manuelle (CTRL+C).")
        sys.exit(1)
