#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# deb_build.sh - Build d'un package Debian (.deb) professionnel
#
# Produit :
#   release/monitoring-client_<version>_amd64.deb
#
# Utilise les fichiers communs de packaging/ pour éviter la duplication
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"
LOG_FILE="${PROJECT_ROOT}/build-deb.log"
BINARY_NAME="monitoring-client"

# Source des fonctions communes
source "${PROJECT_ROOT}/packaging/common/functions.sh"

# Initialisation du logging
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Démarrage du build DEB"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -----------------------------------------------------------------------------
# Vérification des prérequis
# -----------------------------------------------------------------------------
check_common_prerequisites

# Vérifier dpkg-deb
if ! command -v dpkg-deb &> /dev/null; then
  log_error "dpkg-deb n'est pas installé. Veuillez installer 'dpkg'."
  exit 1
fi

log_success "dpkg-deb détecté"

# -----------------------------------------------------------------------------
# Configuration du package
# -----------------------------------------------------------------------------
VERSION=$(get_version "${PROJECT_ROOT}")
PKG_NAME="monitoring-client_${VERSION}_amd64"
PKG_DIR="${RELEASE_DIR}/${PKG_NAME}"

log_info "Version : ${VERSION}"
log_info "Target  : ${PKG_NAME}"
log_info "Log     : ${LOG_FILE}"

# -----------------------------------------------------------------------------
# Nettoyage et création de la structure
# -----------------------------------------------------------------------------
log_info "Nettoyage de l'ancienne structure..."
rm -rf "${PKG_DIR}"

mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/local/bin"
mkdir -p "${PKG_DIR}/opt/monitoring-client"/{config,data,vendors}
mkdir -p "${PKG_DIR}/var/log/monitoring-client"
mkdir -p "${PKG_DIR}/var/cache/monitoring-client"
mkdir -p "${PKG_DIR}/lib/systemd/system"
mkdir -p "${PKG_DIR}/usr/share/monitoring-client"

log_success "Structure créée"

# -----------------------------------------------------------------------------
# Build du binaire PyInstaller
# -----------------------------------------------------------------------------
log_info "Build du binaire PyInstaller..."
if [[ ! -x "${PROJECT_ROOT}/scripts/build.sh" ]]; then
  log_error "Le script build.sh n'existe pas ou n'est pas exécutable."
  exit 1
fi

"${PROJECT_ROOT}/scripts/build.sh" || {
  log_error "Échec du build PyInstaller"
  exit 1
}

# Vérification du binaire généré
if [[ ! -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  log_error "Le binaire ${BINARY_NAME} n'a pas été généré dans ${DIST_DIR}/"
  exit 1
fi

# Copie binaire
cp "${DIST_DIR}/${BINARY_NAME}" "${PKG_DIR}/usr/local/bin/"
chmod 755 "${PKG_DIR}/usr/local/bin/${BINARY_NAME}"
log_success "Binaire copié et permissions définies"

# -----------------------------------------------------------------------------
# Copie de la configuration
# -----------------------------------------------------------------------------
log_info "Préparation des fichiers de configuration..."

# -----------------------------------------------------------------------------
# Defaults (toujours installés, remplacés à chaque upgrade)
# -----------------------------------------------------------------------------
if [[ -f "${PROJECT_ROOT}/packaging/common/config.defaults.yaml" ]]; then
  cp "${PROJECT_ROOT}/packaging/common/config.defaults.yaml" \
     "${PKG_DIR}/opt/monitoring-client/config/config.defaults.yaml"
else
  log_info "config.defaults.yaml introuvable, création d'un fichier par défaut..."
  create_default_config \
    "${PKG_DIR}/opt/monitoring-client/config/config.defaults.yaml"
fi

# Config example (optionnel, pour référence)
if [[ -f "${PROJECT_ROOT}/config/config.yaml.example" ]]; then
  cp "${PROJECT_ROOT}/config/config.yaml.example" \
     "${PKG_DIR}/opt/monitoring-client/config/config.yaml.example"
fi

# -----------------------------------------------------------------------------
# Fichier override utilisateur (conffile)
# Ne PAS le remplir avec les defaults (il doit rester un override)
# -----------------------------------------------------------------------------
if [[ ! -f "${PKG_DIR}/opt/monitoring-client/config/config.yaml" ]]; then
  cat > "${PKG_DIR}/opt/monitoring-client/config/config.yaml" <<'YAML'
api: {}
YAML
fi

# Schema JSON
if [[ -f "${PROJECT_ROOT}/config/config.schema.json" ]]; then
  cp "${PROJECT_ROOT}/config/config.schema.json" \
     "${PKG_DIR}/opt/monitoring-client/config/config.schema.json"
else
  log_info "config.schema.json introuvable, création d'un fichier par défaut..."
  create_default_schema "${PKG_DIR}/opt/monitoring-client/config/config.schema.json"
fi

chmod 644 "${PKG_DIR}/opt/monitoring-client/config/"*.{yaml,json} 2>/dev/null || true
log_success "Configuration copiée"

# -----------------------------------------------------------------------------
# Installation des fichiers systemd (legacy + modern)
# -----------------------------------------------------------------------------
log_info "Installation des fichiers systemd..."

# Copier les 2 variantes de service dans /usr/share (pour sélection au runtime)
cp "${PROJECT_ROOT}/packaging/systemd/monitoring-client.service.legacy" \
   "${PKG_DIR}/usr/share/monitoring-client/monitoring-client.service.legacy"

cp "${PROJECT_ROOT}/packaging/systemd/monitoring-client.service.modern" \
   "${PKG_DIR}/usr/share/monitoring-client/monitoring-client.service.modern"

# Copier le timer (commun)
cp "${PROJECT_ROOT}/packaging/systemd/monitoring-client.timer" \
   "${PKG_DIR}/lib/systemd/system/monitoring-client.timer"

log_success "Fichiers systemd installés (legacy + modern + timer)"

# -----------------------------------------------------------------------------
# Fichier DEBIAN/control
# -----------------------------------------------------------------------------
log_info "Création du fichier control..."

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
  - Timer systemd (exécution toutes les 60 secondes)
  - Validation complète du payload avant envoi
  - Binaire standalone (aucune dépendance Python runtime)
  - Sécurisation renforcée (ProtectSystem, NoNewPrivileges)
 .
 Prérequis système :
  - systemd >= 219
  - Architecture : amd64
Depends: systemd (>= 219)
Homepage: https://github.com/your-org/monitoring-client
EOF

log_success "Fichier control créé"

# -----------------------------------------------------------------------------
# Fichier DEBIAN/conffiles
# -----------------------------------------------------------------------------
log_info "Création du fichier conffiles..."
cp "${PROJECT_ROOT}/packaging/templates/deb/conffiles" "${PKG_DIR}/DEBIAN/conffiles"
log_success "Fichier conffiles créé"

# -----------------------------------------------------------------------------
# Scripts postinst/prerm/postrm
# -----------------------------------------------------------------------------
log_info "Installation des scripts de maintenance..."

cp "${PROJECT_ROOT}/packaging/templates/deb/postinst.sh" "${PKG_DIR}/DEBIAN/postinst"
cp "${PROJECT_ROOT}/packaging/templates/deb/prerm.sh" "${PKG_DIR}/DEBIAN/prerm"
cp "${PROJECT_ROOT}/packaging/templates/deb/postrm.sh" "${PKG_DIR}/DEBIAN/postrm"

chmod 755 "${PKG_DIR}/DEBIAN/"{postinst,prerm,postrm}
log_success "Scripts de maintenance installés"

# -----------------------------------------------------------------------------
# Permissions finales
# -----------------------------------------------------------------------------
log_info "Application des permissions finales..."
chmod -R 755 "${PKG_DIR}/DEBIAN"
chmod 644 "${PKG_DIR}/lib/systemd/system/monitoring-client.timer"

# -----------------------------------------------------------------------------
# Build final du package DEB
# -----------------------------------------------------------------------------
log_info "Build du package DEB..."
dpkg-deb --build --root-owner-group "${PKG_DIR}" || {
  log_error "Échec de la création du package DEB"
  exit 1
}

# Renommer pour clarté
OUT_DEB="${RELEASE_DIR}/monitoring-client_${VERSION}_amd64.deb"

if [[ "${PKG_DIR}.deb" != "${OUT_DEB}" ]]; then
  mv "${PKG_DIR}.deb" "${OUT_DEB}"
fi

# Vérification finale
if [[ ! -f "${OUT_DEB}" ]]; then
  log_error "Le package DEB n'a pas été créé correctement"
  exit 1
fi

# -----------------------------------------------------------------------------
# Affichage du résumé
# -----------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Package DEB créé avec succès !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo " Fichier   : ${OUT_DEB}"
echo " Taille    : $(du -h "${OUT_DEB}" | cut -f1)"
echo " Version   : ${VERSION}"
echo " Build log : ${LOG_FILE}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Commandes utiles"
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
echo "  Test du binaire :"
echo "    /usr/local/bin/monitoring-client --version"
echo "    /usr/local/bin/monitoring-client --dry-run"
echo ""
echo "  Vérification du timer :"
echo "    sudo systemctl status monitoring-client.timer"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Build terminé avec succès"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"