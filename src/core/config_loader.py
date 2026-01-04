import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import jsonschema
import yaml

from .logger import get_logger, log_phase


logger = get_logger(__name__)


@dataclass
class ApiConfig:
    base_url: str
    metrics_endpoint: str
    timeout_seconds: float
    max_retries: int
    api_key_header: str
    api_key_file: str
    api_key_env_var: Optional[str]


@dataclass
class PathsConfig:
    builtin_collectors_dir: str
    vendors_dir: str
    data_dir: str
    logs_dir: Optional[str]


@dataclass
class MachineConfig:
    hostname_source: str
    hostname_override: Optional[str]
    os_override: Optional[str]


@dataclass
class FingerprintConfig:
    method: str
    salt: Optional[str]
    force_recompute: bool
    cache_file: Optional[str]


@dataclass
class LoggingConfig:
    level: str
    format: str
    console_enabled: bool
    file_enabled: bool
    file_name: Optional[str]


@dataclass
class ClientConfig:
    name: str
    version: str
    schema_version: str


@dataclass
class Config:
    client: ClientConfig
    api: ApiConfig
    paths: PathsConfig
    machine: MachineConfig
    fingerprint: FingerprintConfig
    logging: LoggingConfig
    # API key résolue (après lecture fichier / env)
    resolved_api_key: str
    # Chemin de base pour résolution des chemins relatifs
    base_dir: Path


class ConfigError(Exception):
    """Erreur de configuration invalide ou introuvable."""


class ConfigLoader:
    """
    Charge, valide et normalise la configuration du client.

    Responsabilités :
      - Lire un fichier YAML de configuration.
      - Valider le contenu via un schéma JSON (config.schema.json).
      - Appliquer des overrides via variables d'environnement.
      - Résoudre les chemins relatifs (par rapport à la racine du projet).
      - Résoudre la clé API à partir d'un fichier ou d'une variable d'environnement.
    """

    DEFAULT_CONFIG_PATH = Path("config/config.yaml")
    DEFAULT_SCHEMA_PATH = Path("config/config.schema.json")

    def __init__(
        self,
        config_path: Optional[Path] = None,
        schema_path: Optional[Path] = None,
        base_dir: Optional[Path] = None,
    ) -> None:
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.schema_path = schema_path or self.DEFAULT_SCHEMA_PATH
        # base_dir = racine du projet (pour PyInstaller, on pourra l'adapter)
        self.base_dir = base_dir or Path.cwd()

    def load(self) -> Config:
        """Point d'entrée principal : retourne un objet Config prêt à l'emploi."""
        log_phase(logger, "config.load", f"Chargement configuration depuis {self.config_path}")

        raw_config = self._read_config_file(self.config_path)
        schema = self._read_schema_file(self.schema_path)

        self._validate_against_schema(raw_config, schema)

        raw_config = self._apply_env_overrides(raw_config)

        client_cfg = self._build_client_config(raw_config["client"])
        api_cfg = self._build_api_config(raw_config["api"])
        paths_cfg = self._build_paths_config(raw_config["paths"])
        machine_cfg = self._build_machine_config(raw_config["machine"])
        fingerprint_cfg = self._build_fingerprint_config(raw_config["fingerprint"])
        logging_cfg = self._build_logging_config(raw_config["logging"])

        resolved_api_key = self._resolve_api_key(api_cfg, self.base_dir)

        return Config(
            client=client_cfg,
            api=api_cfg,
            paths=paths_cfg,
            machine=machine_cfg,
            fingerprint=fingerprint_cfg,
            logging=logging_cfg,
            resolved_api_key=resolved_api_key,
            base_dir=self.base_dir,
        )

    # ---- Lectures brutes ----

    def _read_config_file(self, path: Path) -> Dict[str, Any]:
        if not path.is_file():
            raise ConfigError(f"Fichier de configuration introuvable : {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            raise ConfigError(f"Impossible de lire le fichier de configuration : {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError("Le fichier de configuration doit contenir un objet YAML racine.")

        return data

    def _read_schema_file(self, path: Path) -> Dict[str, Any]:
        if not path.is_file():
            raise ConfigError(f"Schéma de configuration introuvable : {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
        except Exception as exc:
            raise ConfigError(f"Impossible de lire le schéma de configuration : {exc}") from exc

        if not isinstance(schema, dict):
            raise ConfigError("Le schéma de configuration doit contenir un objet JSON racine.")

        return schema

    # ---- Validation schéma ----

    def _validate_against_schema(self, config: Dict[str, Any], schema: Dict[str, Any]) -> None:
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ConfigError(f"Configuration invalide : {exc.message}") from exc

    # ---- Overrides env ----

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applique quelques overrides via variables d'environnement.

        Conventions :
          - MONITORING_API_BASE_URL
          - MONITORING_API_TIMEOUT
          - MONITORING_API_MAX_RETRIES
          - MONITORING_VENDORS_DIR
          - MONITORING_BUILTIN_DIR
          - MONITORING_DATA_DIR
        """
        log_phase(logger, "config.override", "Application des overrides via variables d'environnement")

        api = config.get("api", {})
        paths = config.get("paths", {})

        env_overrides: Tuple[Tuple[str, str, Dict[str, Any]], ...] = (
            ("MONITORING_API_BASE_URL", "base_url", api),
            ("MONITORING_API_TIMEOUT", "timeout_seconds", api),
            ("MONITORING_API_MAX_RETRIES", "max_retries", api),
            ("MONITORING_VENDORS_DIR", "vendors_dir", paths),
            ("MONITORING_BUILTIN_DIR", "builtin_collectors_dir", paths),
            ("MONITORING_DATA_DIR", "data_dir", paths),
        )

        for env_var, key, target in env_overrides:
            val = os.getenv(env_var)
            if val is None:
                continue

            if key in ("timeout_seconds",):
                try:
                    target[key] = float(val)
                except ValueError:
                    logger.warning(
                        "Variable d'environnement %s invalide (float attendu), ignorée.", env_var
                    )
            elif key in ("max_retries",):
                try:
                    target[key] = int(val)
                except ValueError:
                    logger.warning(
                        "Variable d'environnement %s invalide (int attendu), ignorée.", env_var
                    )
            else:
                target[key] = val

        config["api"] = api
        config["paths"] = paths
        return config

    # ---- Builders ----

    def _build_client_config(self, raw: Dict[str, Any]) -> ClientConfig:
        return ClientConfig(
            name=raw["name"],
            version=raw["version"],
            schema_version=raw["schema_version"],
        )

    def _build_api_config(self, raw: Dict[str, Any]) -> ApiConfig:
        return ApiConfig(
            base_url=raw["base_url"].rstrip("/"),
            metrics_endpoint=raw["metrics_endpoint"],
            timeout_seconds=float(raw["timeout_seconds"]),
            max_retries=int(raw["max_retries"]),
            api_key_header=raw["api_key_header"],
            api_key_file=raw["api_key_file"],
            api_key_env_var=raw.get("api_key_env_var"),
        )

    def _build_paths_config(self, raw: Dict[str, Any]) -> PathsConfig:
        return PathsConfig(
            builtin_collectors_dir=raw["builtin_collectors_dir"],
            vendors_dir=raw["vendors_dir"],
            data_dir=raw["data_dir"],
            logs_dir=raw.get("logs_dir"),
        )

    def _build_machine_config(self, raw: Dict[str, Any]) -> MachineConfig:
        return MachineConfig(
            hostname_source=raw["hostname_source"],
            hostname_override=raw.get("hostname_override"),
            os_override=raw.get("os_override"),
        )

    def _build_fingerprint_config(self, raw: Dict[str, Any]) -> FingerprintConfig:
        return FingerprintConfig(
            method=raw["method"],
            salt=raw.get("salt"),
            force_recompute=bool(raw.get("force_recompute", False)),
            cache_file=raw.get("cache_file"),
        )

    def _build_logging_config(self, raw: Dict[str, Any]) -> LoggingConfig:
        return LoggingConfig(
            level=raw["level"],
            format=raw["format"],
            console_enabled=bool(raw["console_enabled"]),
            file_enabled=bool(raw["file_enabled"]),
            file_name=raw.get("file_name"),
        )

    # ---- Résolution clé API ----

    def _resolve_api_key(self, api_cfg: ApiConfig, base_dir: Path) -> str:
        """
        Résout la clé API à utiliser.

        Priorité :
          1. Variable d'environnement nommée api_cfg.api_key_env_var (si définie et non vide).
          2. Contenu du fichier api_cfg.api_key_file.
        """
        log_phase(logger, "config.api_key", "Résolution de la clé API")

        if api_cfg.api_key_env_var:
            env_val = os.getenv(api_cfg.api_key_env_var)
            if env_val:
                return env_val.strip()

        api_key_path = self._resolve_path(api_cfg.api_key_file, base_dir)
        if not api_key_path.is_file():
            raise ConfigError(
                f"Fichier de clé API introuvable : {api_key_path} "
                "(ou variable d'environnement non définie)"
            )

        try:
            content = api_key_path.read_text(encoding="utf-8")
        except Exception as exc:
            raise ConfigError(f"Impossible de lire la clé API : {exc}") from exc

        key = content.strip()
        if not key:
            raise ConfigError(f"Clé API vide dans le fichier : {api_key_path}")

        return key

    @staticmethod
    def _resolve_path(path_str: str, base_dir: Path) -> Path:
        """Résout un chemin relatif par rapport à base_dir."""
        path = Path(path_str)
        if not path.is_absolute():
            path = base_dir / path
        return path
