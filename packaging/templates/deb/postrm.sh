#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# postrm - Script post-suppression (DEB)
# -----------------------------------------------------------------------------

log() {
  echo "[postrm] $1" | tee -a /var/log/monitoring-client-install.log
}

# dpkg passe un argument:
# $1 = "remove"   → suppression (GARDER config/données/logs/vendors)
# $1 = "purge"    → purge complète (SUPPRIMER TOUT)
# $1 = "upgrade"  → mise à jour (NE RIEN SUPPRIMER)
# $1 = "disappear", "failed-upgrade", "abort-*" → erreurs (NE RIEN SUPPRIMER)

case "$1" in
  purge)
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Purge complète (action: $1)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Supprimer TOUT lors d'un purge
    rm -rf /opt/monitoring-client
    rm -rf /var/log/monitoring-client
    rm -rf /var/cache/monitoring-client
    
    systemctl daemon-reload 2>/dev/null || true
    
    log "✓ Tous les fichiers supprimés (purge)"
    log ""
    ;;
    
  remove)
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Suppression (action: $1)"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # En mode "remove", préserver config/données/logs/vendors
    # Supprimer uniquement le cache (non critique)
    rm -rf /var/cache/monitoring-client
    
    systemctl daemon-reload 2>/dev/null || true
    
    log "✓ Cache supprimé"
    log "[ℹ]  Configuration, données, logs et vendors préservés"
    log "   Pour tout supprimer : sudo dpkg --purge monitoring-client"
    log ""
    ;;
    
  upgrade|disappear|failed-upgrade|abort-install|abort-upgrade)
    # Ne rien supprimer pendant une mise à jour
    log "Action détectée : $1 - aucune suppression (préservation des données)"
    ;;
    
  *)
    log "Action inconnue dans postrm : $1"
    ;;
esac

exit 0