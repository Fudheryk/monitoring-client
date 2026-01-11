#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# prerm - Script pré-suppression (DEB)
# -----------------------------------------------------------------------------

log() {
  echo "[prerm] $1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Arrêt du service monitoring-client..."
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# dpkg passe un argument:
#   - "upgrade" / "failed-upgrade" / "deconfigure" → ne pas disable
#   - "remove" → ok pour disable
action="${1:-}"

log "Action détectée : ${action}"

# Arrêter le timer
if systemctl is-active --quiet monitoring-client.timer 2>/dev/null; then
  systemctl stop monitoring-client.timer || true
  log "✓ Timer arrêté"
fi

# Désactiver uniquement en cas de suppression (pas de mise à jour)
if [[ "$action" == "remove" ]]; then
  if systemctl is-enabled --quiet monitoring-client.timer 2>/dev/null; then
    systemctl disable monitoring-client.timer || true
    log "✓ Timer désactivé (suppression)"
  fi
fi

# Arrêter le service s'il tourne
if systemctl is-active --quiet monitoring-client.service 2>/dev/null; then
  systemctl stop monitoring-client.service || true
  log "✓ Service arrêté"
fi

log "✓ Pré-suppression terminée"

exit 0