#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# rpm_build.sh - Build d'un package RPM (.rpm) professionnel
#
# Produit :
#   rpmbuild/RPMS/x86_64/monitoring-client-<version>-1.x86_64.rpm
#
# Utilise les fichiers communs de packaging/ pour éviter la duplication
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"
LOG_FILE="${PROJECT_ROOT}/build-rpm.log"
BINARY_NAME="monitoring-client"

# Source des fonctions communes
source "${PROJECT_ROOT}/packaging/common/functions.sh"

# Initialisation du logging
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Démarrage du build RPM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -----------------------------------------------------------------------------
# Vérification des prérequis
# -----------------------------------------------------------------------------
check_common_prerequisites

# Vérifier rpmbuild
if ! command -v rpmbuild &> /dev/null; then
  log_error "rpmbuild n'est pas installé."
  log_error "Installez-le avec : sudo yum install rpm-build"
  exit 1
fi

log_success "rpmbuild détecté"

# Vérifier tar
if ! command -v tar &> /dev/null; then
  log_error "tar n'est pas installé."
  exit 1
fi

log_success "tar détecté"

# -----------------------------------------------------------------------------
# Configuration du package
# -----------------------------------------------------------------------------
VERSION=$(get_version "${PROJECT_ROOT}")
RPMROOT="${PROJECT_ROOT}/rpmbuild"

log_info "Project root : ${PROJECT_ROOT}"
log_info "Version      : ${VERSION}"
log_info "RPMROOT      : ${RPMROOT}"
log_info "Log          : ${LOG_FILE}"

# -----------------------------------------------------------------------------
# Préparation de l'arborescence rpmbuild
# -----------------------------------------------------------------------------
log_info "Nettoyage de l'ancienne structure..."
rm -rf "${RPMROOT}"
mkdir -p "${RPMROOT}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "${RELEASE_DIR}"

log_success "Structure rpmbuild créée"

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

log_success "Binaire ${BINARY_NAME} généré"

# -----------------------------------------------------------------------------
# Création d'une archive Source0 minimale pour rpmbuild
# -----------------------------------------------------------------------------
log_info "Création de l'archive Source0..."
tar czf "${RPMROOT}/SOURCES/monitoring-client-${VERSION}.tar.gz" \
  -C "${DIST_DIR}" "${BINARY_NAME}" || {
  log_error "Échec de la création de l'archive Source0"
  exit 1
}

log_success "Archive Source0 créée"

# -----------------------------------------------------------------------------
# Préparation des fichiers de configuration (si manquants)
# -----------------------------------------------------------------------------
log_info "Vérification des fichiers de configuration..."

# Créer config.yaml.example si manquant
if [[ ! -f "${PROJECT_ROOT}/config/config.yaml.example" ]]; then
  log_info "config.yaml.example introuvable, création..."
  mkdir -p "${PROJECT_ROOT}/config"
  create_default_config "${PROJECT_ROOT}/config/config.yaml.example"
fi

# Créer config.schema.json si manquant
if [[ ! -f "${PROJECT_ROOT}/config/config.schema.json" ]]; then
  log_info "config.schema.json introuvable, création..."
  mkdir -p "${PROJECT_ROOT}/config"
  create_default_schema "${PROJECT_ROOT}/config/config.schema.json"
fi

log_success "Fichiers de configuration vérifiés"

# -----------------------------------------------------------------------------
# Génération du fichier SPEC depuis le template
# -----------------------------------------------------------------------------
log_info "Génération du fichier SPEC..."

# Générer la date en anglais pour le changelog
CHANGELOG_DATE=$(LC_TIME=C date '+%a %b %d %Y')

# Remplacer les placeholders dans le template
sed -e "s|__VERSION__|${VERSION}|g" \
    -e "s|__DIST_DIR__|${DIST_DIR}|g" \
    -e "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
    -e "s|__CHANGELOG_DATE__|${CHANGELOG_DATE}|g" \
    "${PROJECT_ROOT}/packaging/templates/rpm/spec.template" \
    > "${RPMROOT}/SPECS/monitoring-client.spec"

log_success "Fichier SPEC généré"

# -----------------------------------------------------------------------------
# Lancement de rpmbuild
# -----------------------------------------------------------------------------
log_info "Build du package RPM..."
rpmbuild --define "_topdir ${RPMROOT}" -ba "${RPMROOT}/SPECS/monitoring-client.spec" || {
  log_error "Échec de la création du package RPM"
  log_error "Consultez le log : ${LOG_FILE}"
  exit 1
}

# -----------------------------------------------------------------------------
# Vérification et localisation du RPM
# -----------------------------------------------------------------------------
RPM_OUTPUT="${RPMROOT}/RPMS/x86_64/monitoring-client-${VERSION}-1.x86_64.rpm"

if [[ ! -f "${RPM_OUTPUT}" ]]; then
  log_error "Le package RPM n'a pas été créé correctement"
  log_error "Attendu : ${RPM_OUTPUT}"
  exit 1
fi

# -----------------------------------------------------------------------------
# Affichage du résumé
# -----------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✓ Package RPM créé avec succès !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo " Fichier   : ${RPM_OUTPUT}"
echo " Taille    : $(du -h "${RPM_OUTPUT}" | cut -f1)"
echo " Version   : ${VERSION}"
echo " Build log : ${LOG_FILE}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Commandes utiles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Installation :"
echo "    sudo rpm -ivh ${RPM_OUTPUT}"
echo ""
echo "  Mise à jour :"
echo "    sudo rpm -Uvh ${RPM_OUTPUT}"
echo ""
echo "  Vérification du contenu :"
echo "    rpm -qlp ${RPM_OUTPUT}"
echo ""
echo "  Vérification de la structure installée :"
echo "    rpm -qlp ${RPM_OUTPUT} | grep -E 'opt|systemd|config'"
echo ""
echo "  Test du binaire :"
echo "    /usr/local/bin/monitoring-client --version"
echo "    /usr/local/bin/monitoring-client --dry-run"
echo ""
echo "  Vérification du timer :"
echo "    sudo systemctl status monitoring-client.timer"
echo "    sudo systemctl list-timers | grep monitoring"
echo ""
echo "  Logs en temps réel :"
echo "    sudo journalctl -u monitoring-client -f"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Build terminé avec succès"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"