#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# packaging/common/functions.sh
# Fonctions partagées entre deb_build.sh et rpm_build.sh
# -----------------------------------------------------------------------------

set -euo pipefail

# -----------------------------------------------------------------------------
# Fonction : Récupérer la version depuis __version__.py
# -----------------------------------------------------------------------------
get_version() {
  local project_root="${1}"
  local version_file="${project_root}/src/monitoring_client/__version__.py"
  
  if [[ ! -f "${version_file}" ]]; then
    echo "1.0.0"
    return
  fi
  
  grep -E '^__version__' "${version_file}" \
    | head -1 \
    | cut -d'"' -f2 \
    || echo "1.0.0"
}

# -----------------------------------------------------------------------------
# Fonction : Détecter la version de systemd
# -----------------------------------------------------------------------------
get_systemd_version() {
  if ! command -v systemctl &> /dev/null; then
    echo "0"
    return
  fi
  
  systemctl --version | head -n1 | awk '{print $2}' || echo "0"
}

# -----------------------------------------------------------------------------
# Fonction : Sélectionner le bon fichier service (legacy vs modern)
# Retourne : "legacy" ou "modern"
# -----------------------------------------------------------------------------
select_systemd_variant() {
  local systemd_version
  systemd_version=$(get_systemd_version)
  
  # systemd < 231 → legacy (ReadWriteDirectories)
  # systemd >= 231 → modern (ReadWritePaths)
  if [[ "${systemd_version}" -lt 231 ]]; then
    echo "legacy"
  else
    echo "modern"
  fi
}

# -----------------------------------------------------------------------------
# Fonction : Supprimer les commentaires et lignes vides d'un fichier YAML
# -----------------------------------------------------------------------------
strip_yaml_comments() {
  local input_file="${1}"
  local output_file="${2}"
  
  if [[ ! -f "${input_file}" ]]; then
    echo "[!] Fichier ${input_file} introuvable" >&2
    return 1
  fi
  
  grep -Ev '^[[:space:]]*#' "${input_file}" \
    | awk 'NF' \
    > "${output_file}"
}

# -----------------------------------------------------------------------------
# Fonction : Créer config.yaml par défaut si absent
# -----------------------------------------------------------------------------
create_default_config() {
  local output_file="${1}"
  
  cat > "${output_file}" <<'YAML'
client:
  name: "monitoring-client"
  version: "1.0.0"
  schema_version: "1.0.0"

api:
  base_url: "https://monitoring.local"
  metrics_endpoint: "/api/v1/ingest/metrics"
  timeout_seconds: 5
  max_retries: 3
  api_key_header: "X-API-Key"
  api_key_file: "data/api_key"
  api_key_env_var: "MONITORING_API_KEY"

paths:
  builtin_collectors_dir: "src/collectors/builtin"
  vendors_dir: "vendors"
  data_dir: "data"
  logs_dir: "/var/log/monitoring-client"

machine:
  hostname_source: "system"
  hostname_override: null
  os_override: null

fingerprint:
  method: "default"
  salt: null
  force_recompute: false
  cache_file: "fingerprint"

logging:
  level: "INFO"
  format: "plain"
  console_enabled: true
  file_enabled: false
  file_name: "monitoring-client.log"
YAML
}

# -----------------------------------------------------------------------------
# Fonction : Créer config.schema.json par défaut si absent
# -----------------------------------------------------------------------------
create_default_schema() {
  local output_file="${1}"
  
  cat > "${output_file}" <<'JSON'
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Monitoring Client Configuration",
  "type": "object",
  "required": ["client", "api", "paths", "machine", "fingerprint", "logging"],
  "properties": {
    "client": {
      "type": "object",
      "required": ["name", "version", "schema_version"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "version": { "type": "string", "minLength": 1 },
        "schema_version": { "type": "string", "minLength": 1 }
      },
      "additionalProperties": false
    },
    "api": {
      "type": "object",
      "required": [
        "base_url",
        "metrics_endpoint",
        "timeout_seconds",
        "max_retries",
        "api_key_header",
        "api_key_file"
      ],
      "properties": {
        "base_url": {
          "type": "string",
          "pattern": "^https?://[^/:]+(:[0-9]+)?$",
          "minLength": 1
        },
        "metrics_endpoint": {
          "type": "string",
          "minLength": 1
        },
        "timeout_seconds": {
          "type": "number",
          "minimum": 0.1
        },
        "max_retries": {
          "type": "integer",
          "minimum": 0
        },
        "api_key_header": {
          "type": "string",
          "minLength": 1
        },
        "api_key_file": {
          "type": "string",
          "minLength": 1
        },
        "api_key_env_var": {
          "type": ["string", "null"]
        }
      },
      "additionalProperties": false
    },
    "paths": {
      "type": "object",
      "required": ["builtin_collectors_dir", "vendors_dir", "data_dir"],
      "properties": {
        "builtin_collectors_dir": { "type": "string", "minLength": 1 },
        "vendors_dir": { "type": "string", "minLength": 1 },
        "data_dir": { "type": "string", "minLength": 1 },
        "logs_dir": { "type": "string", "minLength": 1 }
      },
      "additionalProperties": false
    },
    "machine": {
      "type": "object",
      "required": ["hostname_source"],
      "properties": {
        "hostname_source": {
          "type": "string",
          "enum": ["system", "fqdn", "static"]
        },
        "hostname_override": {
          "type": ["string", "null"]
        },
        "os_override": {
          "type": ["string", "null"]
        }
      },
      "additionalProperties": false
    },
    "fingerprint": {
      "type": "object",
      "required": ["method"],
      "properties": {
        "method": {
          "type": "string",
          "minLength": 1
        },
        "salt": {
          "type": ["string", "null"]
        },
        "force_recompute": {
          "type": "boolean"
        },
        "cache_file": {
          "type": ["string", "null"]
        }
      },
      "additionalProperties": false
    },
    "logging": {
      "type": "object",
      "required": ["level", "format", "console_enabled", "file_enabled"],
      "properties": {
        "level": {
          "type": "string",
          "enum": ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
        },
        "format": {
          "type": "string",
          "enum": ["plain", "json"]
        },
        "console_enabled": {
          "type": "boolean"
        },
        "file_enabled": {
          "type": "boolean"
        },
        "file_name": {
          "type": ["string", "null"]
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
JSON
}

# -----------------------------------------------------------------------------
# Fonction : Logging standardisé
# -----------------------------------------------------------------------------
log_info() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
}

log_success() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [✓] $*"
}

# -----------------------------------------------------------------------------
# Fonction : Vérifier les prérequis communs
# -----------------------------------------------------------------------------
check_common_prerequisites() {
  log_info "Vérification des prérequis communs..."
  
  # systemd
  if ! command -v systemctl &> /dev/null; then
    log_error "systemd n'est pas installé"
    return 1
  fi
  
  local systemd_ver
  systemd_ver=$(get_systemd_version)
  log_success "systemd version ${systemd_ver} détecté"
  
  # Python 3 (peut être dans /opt/python311 sur CentOS 7)
  PYTHON_CMD="python3"
  if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
  elif command -v /opt/python311/bin/python3.11 &> /dev/null; then
    PYTHON_CMD="/opt/python311/bin/python3.11"
  else
    log_error "Python 3 n'est pas installé"
    return 1
  fi
  
  log_success "Python 3 détecté : $(${PYTHON_CMD} --version)"
  
  # PyInstaller
  if ! ${PYTHON_CMD} -m pip show pyinstaller &> /dev/null; then
    log_info "PyInstaller n'est pas installé, tentative d'installation..."
    ${PYTHON_CMD} -m pip install pyinstaller || {
      log_error "Impossible d'installer PyInstaller"
      return 1
    }
  fi
  
  log_success "PyInstaller détecté"
  log_success "Tous les prérequis communs sont satisfaits"
}