#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# install.sh - Installation du binaire monitoring-client sur un serveur Linux
#
# - Copie le binaire dans /usr/local/bin/monitoring-client
# - Prépare /etc/monitoring-client/config.yaml
# - Crée /var/log/monitoring-client
# - Installe un service + timer systemd (optionnel, si systemd est présent)
#
# Usage :
#   ./scripts/install.sh
#   (doit être exécuté en root ou via sudo)
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_BINARY="${PROJECT_ROOT}/dist/monitoring-client"

INSTALL_BIN="/usr/local/bin/monitoring-client"
CONFIG_DIR="/etc/monitoring-client"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
CONFIG_EXAMPLE="${PROJECT_ROOT}/config/config.yaml.example"
LOG_DIR="/var/log/monitoring-client"

SERVICE_FILE="/etc/systemd/system/monitoring-client.service"
TIMER_FILE="/etc/systemd/system/monitoring-client.timer"

echo "[install] Project root : ${PROJECT_ROOT}"

# Vérification root
if [[ "$(id -u)" -ne 0 ]]; then
  echo "[install] Erreur : ce script doit être exécuté en root (ou via sudo)."
  exit 1
fi

# Vérifier le binaire
if [[ ! -x "${DIST_BINARY}" ]]; then
  echo "[install] Erreur : binaire introuvable à ${DIST_BINARY}"
  echo "          Lance d'abord ./scripts/build.sh"
  exit 1
fi

echo "[install] Copie du binaire vers ${INSTALL_BIN}..."
cp "${DIST_BINARY}" "${INSTALL_BIN}"
chmod 755 "${INSTALL_BIN}"

# Préparation de la configuration
echo "[install] Préparation de la configuration dans ${CONFIG_DIR}..."
mkdir -p "${CONFIG_DIR}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "[install] Création de ${CONFIG_FILE} à partir de l'exemple."
  cp "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"
else
  echo "[install] ${CONFIG_FILE} existe déjà, non écrasé."
fi

# Répertoire de logs
echo "[install] Création du répertoire de logs ${LOG_DIR}..."
mkdir -p "${LOG_DIR}"
chmod 755 "${LOG_DIR}"

# Optionnel : création service systemd si systemd est présent
if command -v systemctl >/dev/null 2>&1; then
  echo "[install] Systemd détecté, création des unités service/timer..."

  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Monitoring Client - Collecte et envoi de métriques
After=network.target

[Service]
Type=oneshot
ExecStart=${INSTALL_BIN} --config ${CONFIG_FILE}
WorkingDirectory=/tmp
User=root
Group=root

# Si certaines métriques nécessitent des privilèges élevés (iptables, dmidecode, etc.)
# le service doit tourner en root ou via sudo avec les droits appropriés.

[Install]
WantedBy=multi-user.target
EOF

  cat > "${TIMER_FILE}" <<EOF
[Unit]
Description=Planification périodique du Monitoring Client

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=monitoring-client.service

[Install]
WantedBy=timers.target
EOF

  echo "[install] Rechargement de systemd..."
  systemctl daemon-reload

  echo "[install] Activation du timer (monitoring-client.timer)..."
  systemctl enable monitoring-client.timer || true
  systemctl start monitoring-client.timer || true

  echo "[install] Service systemd installé :"
  echo "  - ${SERVICE_FILE}"
  echo "  - ${TIMER_FILE}"
  echo "Le client sera exécuté toutes les 5 minutes."
else
  echo "[install] systemd non détecté, aucune unité service/timer créée."
fi

echo "[install] Installation terminée."
echo "[install] Test rapide :"
echo "  monitoring-client --config ${CONFIG_FILE} --dry-run"
