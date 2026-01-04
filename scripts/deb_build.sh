#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# deb_build.sh - Build d'un package Debian (.deb) professionnel
#
# Produit :
#   release/monitoring-client_<version>_amd64.deb
#
# Améliorations :
#   - Vérification version systemd
#   - Logging complet des opérations
#   - Validation de la configuration
#   - Sécurisation renforcée
#   - Gestion des dépendances
#   - Auto-vérification des prérequis
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"
LOG_FILE="${PROJECT_ROOT}/build-deb.log"

BINARY_NAME="monitoring-client"

# Initialisation du logging
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Démarrage du build DEB"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -----------------------------------------------------------------------------
# Fonction : Vérification des prérequis
# -----------------------------------------------------------------------------
function check_prerequisites() {
  echo "[check] Vérification des prérequis..."

  # Vérifier systemctl
  if ! command -v systemctl &> /dev/null; then
    echo "❌ systemd n'est pas installé. L'installation ne peut pas continuer."
    exit 1
  fi

  # Vérifier dpkg-deb
  if ! command -v dpkg-deb &> /dev/null; then
    echo "❌ dpkg-deb n'est pas installé. Veuillez installer 'dpkg'."
    exit 1
  fi

  # Vérifier la version de systemd (minimum 226)
  SYSTEMD_VERSION=$(systemctl --version | head -n 1 | awk '{print $2}')
  if [[ "${SYSTEMD_VERSION}" -lt 226 ]]; then
    echo "❌ Votre version de systemd (${SYSTEMD_VERSION}) est obsolète."
    echo "   Version minimale requise : 226"
    echo "   Veuillez mettre à jour systemd."
    exit 1
  fi

  echo "[check] ✓ systemd version ${SYSTEMD_VERSION} détecté"

  # Vérifier Python 3 (pour le build PyInstaller)
  if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Impossible de builder le binaire."
    exit 1
  fi

  echo "[check] ✓ Python 3 détecté : $(python3 --version)"

  # Vérifier PyInstaller
  if ! python3 -m pip show pyinstaller &> /dev/null; then
    echo "⚠️  PyInstaller n'est pas installé. Tentative d'installation..."
    python3 -m pip install pyinstaller || {
      echo "❌ Impossible d'installer PyInstaller."
      exit 1
    }
  fi

  echo "[check] ✓ PyInstaller détecté"
  echo "[check] ✓ Tous les prérequis sont satisfaits"
}

# -----------------------------------------------------------------------------
# Exécution des vérifications
# -----------------------------------------------------------------------------
check_prerequisites

# -----------------------------------------------------------------------------
# Configuration du package
# -----------------------------------------------------------------------------

# Récupère la version depuis src/__version__.py
VERSION="$(
  grep -E '^__version__' "${PROJECT_ROOT}/src/__version__.py" \
    | head -1 \
    | cut -d'"' -f2
)"

VERSION="${VERSION:-1.0.0}"
PKG_NAME="monitoring-client_${VERSION}_amd64"
PKG_DIR="${RELEASE_DIR}/${PKG_NAME}"

echo "[deb] Version : ${VERSION}"
echo "[deb] Target  : ${PKG_NAME}"
echo "[deb] Log     : ${LOG_FILE}"

# -----------------------------------------------------------------------------
# Nettoyage et création de la structure
# -----------------------------------------------------------------------------
echo "[deb] Nettoyage de l'ancienne structure..."
rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/local/bin"
mkdir -p "${PKG_DIR}/etc/monitoring-client"
mkdir -p "${PKG_DIR}/var/log/monitoring-client"
mkdir -p "${PKG_DIR}/usr/lib/systemd/system"
mkdir -p "${PKG_DIR}/opt/monitoring-client/"{data,vendors}

echo "[deb] ✓ Structure créée"

# -----------------------------------------------------------------------------
# Build du binaire PyInstaller
# -----------------------------------------------------------------------------
echo "[deb] Build du binaire PyInstaller..."
if [[ ! -x "${PROJECT_ROOT}/scripts/build.sh" ]]; then
  echo "❌ Le script build.sh n'existe pas ou n'est pas exécutable."
  exit 1
fi

"${PROJECT_ROOT}/scripts/build.sh" || {
  echo "❌ Échec du build PyInstaller"
  exit 1
}

# Vérification du binaire généré
if [[ ! -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "❌ Le binaire ${BINARY_NAME} n'a pas été généré dans ${DIST_DIR}/"
  exit 1
fi

# Copie binaire
cp "${DIST_DIR}/${BINARY_NAME}" "${PKG_DIR}/usr/local/bin/"
chmod 755 "${PKG_DIR}/usr/local/bin/${BINARY_NAME}"
echo "[deb] ✓ Binaire copié et permissions définies"

# -----------------------------------------------------------------------------
# Copie de la configuration exemple
# -----------------------------------------------------------------------------
if [[ ! -f "${PROJECT_ROOT}/config/config.yaml.example" ]]; then
  echo "⚠️  Fichier config.yaml.example introuvable. Création d'un fichier par défaut..."
  cat > "${PKG_DIR}/etc/monitoring-client/config.yaml" <<'YAML'
# Configuration Monitoring Client
api:
  base_url: "https://monitoring.example.com"
  metrics_endpoint: "/api/v1/metrics"
  timeout: 30

collectors:
  enabled:
    - cpu
    - memory
    - disk
    - network
YAML
else
  cp "${PROJECT_ROOT}/config/config.yaml.example" "${PKG_DIR}/etc/monitoring-client/config.yaml"
fi

chmod 644 "${PKG_DIR}/etc/monitoring-client/config.yaml"
echo "[deb] ✓ Configuration copiée"

# -----------------------------------------------------------------------------
# Création des fichiers systemd
# -----------------------------------------------------------------------------
echo "[deb] Création des fichiers systemd..."

cat > "${PKG_DIR}/usr/lib/systemd/system/monitoring-client.service" <<'EOF'
[Unit]
Description=Monitoring Client Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/bin/monitoring-client --config /etc/monitoring-client/config.yaml
WorkingDirectory=/opt/monitoring-client
StandardOutput=journal
StandardError=journal
SyslogIdentifier=monitoring-client

# Sécurité renforcée
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/monitoring-client /opt/monitoring-client/data

[Install]
WantedBy=multi-user.target
EOF

cat > "${PKG_DIR}/usr/lib/systemd/system/monitoring-client.timer" <<'EOF'
[Unit]
Description=Run Monitoring Client Agent every 30 seconds
Requires=monitoring-client.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=30s
Unit=monitoring-client.service
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[deb] ✓ Fichiers systemd créés"

# -----------------------------------------------------------------------------
# Fichier DEBIAN/control
# -----------------------------------------------------------------------------
echo "[deb] Création du fichier control..."

cat > "${PKG_DIR}/DEBIAN/control" <<EOF
Package: monitoring-client
Version: ${VERSION}
Section: admin
Priority: optional
Architecture: amd64
Maintainer: Frederic GIL GARCIA <frederic.gilgarcia@gmail.com>
Description: Agent de monitoring système léger et sécurisé
 Collecte et envoie des métriques système, réseau, sécurité
 et services vers un serveur central de monitoring.
 .
 Fonctionnalités principales :
  - 11 collecteurs builtin (CPU, RAM, disque, réseau, services, etc.)
  - Support des métriques custom via vendors (bash, python, etc.)
  - Timer systemd (exécution toutes les 30 secondes)
  - Validation complète du payload avant envoi
  - Binaire standalone (aucune dépendance Python runtime)
  - Sécurisation renforcée (ProtectSystem, NoNewPrivileges)
 .
 Prérequis système :
  - systemd >= 226
  - Architecture : amd64
Depends: systemd (>= 226)
Homepage: https://github.com/your-org/monitoring-client
EOF

echo "[deb] ✓ Fichier control créé"

# -----------------------------------------------------------------------------
# Script postinst (post-installation)
# -----------------------------------------------------------------------------
echo "[deb] Création du script postinst..."

cat > "${PKG_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e

# Fonction de logging
log() {
  echo "[postinst] $1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "=== Configuration de Monitoring Client ==="
log ""

# Créer les répertoires nécessaires
mkdir -p /opt/monitoring-client/{data,vendors}
mkdir -p /var/log/monitoring-client
mkdir -p /var/cache/monitoring-client

# Permissions strictes
chmod 755 /usr/local/bin/monitoring-client
chmod 644 /etc/monitoring-client/config.yaml
chmod 755 /opt/monitoring-client/{data,vendors}
chmod 755 /var/log/monitoring-client
chmod 755 /var/cache/monitoring-client

log "✓ Répertoires et permissions configurés"

# Validation de la configuration
if ! grep -q 'base_url' /etc/monitoring-client/config.yaml; then
  log "⚠️  Le fichier de configuration ne contient pas 'base_url'."
  log "   Veuillez le configurer manuellement."
fi

# Recharger systemd
systemctl daemon-reload
log "✓ systemd rechargé"

# Vérifier si l'API key existe déjà
if [[ -f /etc/monitoring-client/api_key && -s /etc/monitoring-client/api_key ]]; then
  # Sécuriser la clé API
  chmod 600 /etc/monitoring-client/api_key
  log "✓ Clé API détectée et sécurisée (chmod 600)"

  # Vérifier si le package est déjà installé (mise à jour)
  if dpkg-query -W -f='${Status}' monitoring-client 2>/dev/null | grep -q "install ok installed"; then
    log "✓ Mise à jour détectée"

    # Redémarrer le timer si déjà actif
    if systemctl is-active --quiet monitoring-client.timer; then
      systemctl restart monitoring-client.timer
      log "✓ Timer redémarré avec la nouvelle version"
    else
      systemctl enable --now monitoring-client.timer >/dev/null 2>&1 || true
      log "✓ Timer activé et démarré"
    fi
  else
    # Nouvelle installation
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
  log "      echo 'VOTRE_CLE_API' | sudo tee /etc/monitoring-client/api_key"
  log "      sudo chmod 600 /etc/monitoring-client/api_key"
  log ""
  log "  2️⃣  Configurer le serveur backend :"
  log "      sudo nano /etc/monitoring-client/config.yaml"
  log "      (Modifier 'base_url' et 'metrics_endpoint')"
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
  log "📖 Test rapide : monitoring-client --dry-run"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
fi

log "✓ Installation terminée avec succès"
log "📁 Log complet : /var/log/monitoring-client-install.log"

exit 0
POSTINST

chmod 755 "${PKG_DIR}/DEBIAN/postinst"
echo "[deb] ✓ Script postinst créé"

# -----------------------------------------------------------------------------
# Script prerm (pré-suppression)
# -----------------------------------------------------------------------------
echo "[deb] Création du script prerm..."

cat > "${PKG_DIR}/DEBIAN/prerm" <<'PRERM'
#!/bin/bash
set -e

# Fonction de logging
log() {
  echo "[prerm] $1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Arrêt du service monitoring-client..."
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# IMPORTANT: en upgrade, on NE DOIT PAS disable le timer
# dpkg appelle prerm avec un argument:
#   - "upgrade" / "failed-upgrade" / "deconfigure" -> ne pas disable
#   - "remove" -> ok pour disable
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
PRERM

chmod 755 "${PKG_DIR}/DEBIAN/prerm"
echo "[deb] ✓ Script prerm créé"

# -----------------------------------------------------------------------------
# Script postrm (post-suppression)
# -----------------------------------------------------------------------------
echo "[deb] Création du script postrm..."

cat > "${PKG_DIR}/DEBIAN/postrm" <<'POSTRM'
#!/bin/bash
set -e

# Fonction de logging
log() {
  echo "[postrm] $1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Nettoyage post-suppression"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Suppression complète des fichiers et répertoires
rm -rf /opt/monitoring-client/data
rm -rf /opt/monitoring-client/vendors
rm -rf /var/log/monitoring-client
rm -rf /var/cache/monitoring-client
rm -rf /etc/monitoring-client

# Si /opt/monitoring-client est vide, le supprimer aussi
if [[ -d /opt/monitoring-client ]] && [[ -z "$(ls -A /opt/monitoring-client)" ]]; then
  rmdir /opt/monitoring-client
  log "✓ Répertoire /opt/monitoring-client supprimé (vide)"
fi

# Recharger systemd après suppression des fichiers
systemctl daemon-reload 2>/dev/null || true
log "✓ systemd rechargé"

log ""
log "✓ Monitoring Client désinstallé complètement"
log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "   Suppression complète effectuée."
log "   Log final : /var/log/monitoring-client-install.log"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""

exit 0
POSTRM

chmod 755 "${PKG_DIR}/DEBIAN/postrm"
echo "[deb] ✓ Script postrm créé"

# -----------------------------------------------------------------------------
# Permissions finales
# -----------------------------------------------------------------------------
echo "[deb] Application des permissions finales..."
chmod -R 755 "${PKG_DIR}/DEBIAN"
chmod 644 "${PKG_DIR}/etc/monitoring-client/config.yaml"
chmod 644 "${PKG_DIR}/usr/lib/systemd/system/monitoring-client.service"
chmod 644 "${PKG_DIR}/usr/lib/systemd/system/monitoring-client.timer"

# -----------------------------------------------------------------------------
# Build final du package DEB
# -----------------------------------------------------------------------------
echo "[deb] Build du package DEB..."
dpkg-deb --build --root-owner-group "${PKG_DIR}" || {
  echo "❌ Échec de la création du package DEB"
  exit 1
}

# Renommer pour clarté
OUT_DEB="${RELEASE_DIR}/monitoring-client_${VERSION}_amd64.deb"

# dpkg-deb sort avec le nom <dirname>.deb, donc on le déplace si nécessaire
if [[ "${PKG_DIR}.deb" != "${OUT_DEB}" ]]; then
  mv "${PKG_DIR}.deb" "${OUT_DEB}"
fi

# Vérification finale
if [[ ! -f "${OUT_DEB}" ]]; then
  echo "❌ Le package DEB n'a pas été créé correctement"
  exit 1
fi

# -----------------------------------------------------------------------------
# Affichage du résumé
# -----------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Package DEB créé avec succès !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Fichier   : ${OUT_DEB}"
echo "📏 Taille    : $(du -h "${OUT_DEB}" | cut -f1)"
echo "🏗️  Version   : ${VERSION}"
echo "📝 Build log : ${LOG_FILE}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Commandes utiles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Installation :"
echo "    sudo dpkg -i ${OUT_DEB}"
echo ""
echo "  Vérification du contenu :"
echo "    dpkg-deb --contents ${OUT_DEB}"
echo ""
echo "  Informations du package :"
echo "    dpkg-deb --info ${OUT_DEB}"
echo ""
echo "  Vérification de l'installation :"
echo "    dpkg -l | grep monitoring-client"
echo ""
echo "  Test du binaire :"
echo "    /usr/local/bin/monitoring-client --version"
echo "    /usr/local/bin/monitoring-client --dry-run"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Build terminé avec succès"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
