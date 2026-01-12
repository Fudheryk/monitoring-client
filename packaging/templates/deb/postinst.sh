#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# postinst - Script post-installation (DEB)
# -----------------------------------------------------------------------------

log() {
  echo "[postinst] $1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "=== Configuration de Monitoring Client ==="
log ""

# -----------------------------------------------------------------------------
# Créer les répertoires nécessaires
# -----------------------------------------------------------------------------
mkdir -p /opt/monitoring-client/{config,data,vendors}
mkdir -p /var/log/monitoring-client
mkdir -p /var/cache/monitoring-client

# -----------------------------------------------------------------------------
# Permissions strictes
# -----------------------------------------------------------------------------
chmod 755 /usr/local/bin/monitoring-client

if [[ -f /opt/monitoring-client/config/config.yaml ]]; then
  chmod 644 /opt/monitoring-client/config/config.yaml
else
  # Si le conffile a été supprimé manuellement, on recrée un override minimal
  cat > /opt/monitoring-client/config/config.yaml <<'YAML'
api: {}
YAML
  chmod 644 /opt/monitoring-client/config/config.yaml
  log "✓ config.yaml recréé (overrides utilisateur)"
fi

if [[ -f /opt/monitoring-client/config/config.schema.json ]]; then
  chmod 644 /opt/monitoring-client/config/config.schema.json
fi

chmod 755 /opt/monitoring-client/{config,data,vendors}
chmod 755 /var/log/monitoring-client
chmod 755 /var/cache/monitoring-client

log "✓ Répertoires et permissions configurés"

# -----------------------------------------------------------------------------
# Détection de la version systemd et installation du bon service
# -----------------------------------------------------------------------------
SYSTEMD_VERSION=$(systemctl --version | head -n1 | awk '{print $2}')
log "Détection systemd version ${SYSTEMD_VERSION}"

if [[ "${SYSTEMD_VERSION}" -lt 231 ]]; then
  SERVICE_VARIANT="legacy"
  log "→ Utilisation du service legacy (ReadWriteDirectories)"
else
  SERVICE_VARIANT="modern"
  log "→ Utilisation du service modern (ReadWritePaths)"
fi

# Copier le bon fichier service
SYSTEMD_UNIT_DIR="/lib/systemd/system"
if [[ -d "/usr/lib/systemd/system" ]]; then
  SYSTEMD_UNIT_DIR="/usr/lib/systemd/system"
fi

if [[ -f "/usr/share/monitoring-client/monitoring-client.service.${SERVICE_VARIANT}" ]]; then
  cp "/usr/share/monitoring-client/monitoring-client.service.${SERVICE_VARIANT}" \
     "${SYSTEMD_UNIT_DIR}/monitoring-client.service"
  log "✓ Service ${SERVICE_VARIANT} installé (${SYSTEMD_UNIT_DIR})"
else
  log "[!] Fichier service ${SERVICE_VARIANT} introuvable"
fi

# -----------------------------------------------------------------------------
# Validation de la configuration
# -----------------------------------------------------------------------------
DEFAULTS_FILE="/opt/monitoring-client/config/config.defaults.yaml"
OVERRIDES_FILE="/opt/monitoring-client/config/config.yaml"

if [[ -f "${DEFAULTS_FILE}" ]] && grep -q 'base_url' "${DEFAULTS_FILE}"; then
  log "✓ base_url présent dans config.defaults.yaml"
elif [[ -f "${OVERRIDES_FILE}" ]] && grep -q 'base_url' "${OVERRIDES_FILE}"; then
  log "✓ base_url présent dans config.yaml (override)"
else
  log "[!] base_url introuvable (defaults + overrides)"
  log "    Veuillez le configurer (recommandé: dans config.yaml)."
fi

# -----------------------------------------------------------------------------
# Recharger systemd
# -----------------------------------------------------------------------------
systemctl daemon-reload
log "✓ systemd rechargé"

# -----------------------------------------------------------------------------
# Gestion du timer selon le contexte
# -----------------------------------------------------------------------------
if [[ -f /opt/monitoring-client/data/api_key && -s /opt/monitoring-client/data/api_key ]]; then
  chmod 600 /opt/monitoring-client/data/api_key
  log "✓ Clé API détectée et sécurisée (chmod 600)"

  # Détection fiable : si $2 est défini, c'est une mise à jour (ancienne version)
  if [[ -n "${2:-}" ]]; then
    log "✓ Mise à jour détectée (ancienne version : ${2})"

    if systemctl is-active --quiet monitoring-client.timer; then
      systemctl restart monitoring-client.timer
      log "✓ Timer redémarré avec la nouvelle version"
    else
      systemctl enable --now monitoring-client.timer >/dev/null 2>&1 || true
      log "✓ Timer activé et démarré"
    fi
  else
    systemctl enable --now monitoring-client.timer >/dev/null 2>&1 || true
    log "✓ Timer activé et démarré (nouvelle installation)"
  fi
else
  log "⚠️  Aucune clé API trouvée."
  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "📋 Étapes suivantes (OBLIGATOIRES)"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
  log "  1️⃣  Ajouter votre clé API :"
  log "      echo 'VOTRE_CLE_API' | sudo tee /opt/monitoring-client/data/api_key"
  log "      sudo chmod 600 /opt/monitoring-client/data/api_key"
  log ""
  log "  2️⃣  (Optionnel) Configurer le serveur backend :"
  log "      sudo nano /opt/monitoring-client/config/config.yaml"
  log "      (Seulement si l’URL change : api.base_url / api.metrics_endpoint)"
  log ""
  log "  3️⃣  Activer et démarrer le timer :"
  log "      sudo systemctl enable --now monitoring-client.timer"
  log ""
  log "  4️⃣  Vérifier que le timer est actif :"
  log "      sudo systemctl list-timers | grep monitoring"
  log ""
  log "  5️⃣  Voir les logs en temps réel :"
  log "      sudo journalctl -u monitoring-client -f"
  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log " Test rapide : monitoring-client --dry-run"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
fi

log "✓ Installation terminée avec succès"
log "   Log complet : /var/log/monitoring-client-install.log"

exit 0