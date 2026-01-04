import json
import logging
import os
import sys
from typing import Optional

_LOGGER_CONFIGURED = False


def _get_log_level_from_string(level_str: str) -> int:
    """Convertit une chaîne de niveau en constante logging."""
    normalized = level_str.strip().upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }.get(normalized, logging.INFO)


class JsonLogFormatter(logging.Formatter):
    """Formatter JSON simple pour logs structurés."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Champs personnalisés si on veut logguer les phases d'exécution
        for key in ("phase", "component", "step"):
            if hasattr(record, key):
                log_record[key] = getattr(record, key)

        return json.dumps(log_record, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    fmt: str = "plain",
    console_enabled: bool = True,
    file_enabled: bool = False,
    file_path: Optional[str] = None,
) -> None:
    """
    Configure le logging global de l'application.

    Cette fonction est idempotente : les appels suivants sont ignorés.
    Les variables d'environnement peuvent surcharger le niveau :
      - MONITORING_LOG_LEVEL (ex: DEBUG)
      - MONITORING_LOG_FORMAT (plain|json)
    """
    global _LOGGER_CONFIGURED

    if _LOGGER_CONFIGURED:
        return

    env_level = os.getenv("MONITORING_LOG_LEVEL")
    env_format = os.getenv("MONITORING_LOG_FORMAT")

    if env_level:
        level = env_level
    if env_format:
        fmt = env_format

    log_level = _get_log_level_from_string(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    if fmt == "json":
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    if console_enabled:
        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if file_enabled and file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _LOGGER_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger nommé.

    À utiliser dans les autres modules :
        from core.logger import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)


def log_phase(logger: logging.Logger, phase: str, message: str) -> None:
    """
    Helper pour logguer une phase d'exécution importante en temps réel.

    Exemple d'usage dans le pipeline :
        log_phase(logger, "config.load", "Lecture du fichier de configuration")
        log_phase(logger, "fingerprint.compute", "Calcul du fingerprint")
    """
    logger.info(message, extra={"phase": phase})
