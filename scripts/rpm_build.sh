#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# rpm_build.sh - Build d'un package RPM (.rpm) professionnel
#
# Produit :
#   rpmbuild/RPMS/x86_64/monitoring-client-<version>-1.x86_64.rpm
#
# Points critiques (bug rencontré) :
# - Le RPM "1.0.52" a embarqué un binaire "1.0.50" car dist/ contenait un artefact
#   stale (volume Docker, cache CI, etc.).
#
# Correctifs appliqués ici :
# 1) Nettoyage agressif des artefacts (dist/, build/, .build-pyinstaller/) AVANT build
# 2) Build PyInstaller dans /tmp/dist (isolé, évite pollution du repo)
# 3) Sanity check BLOQUANT : le binaire généré doit annoncer la même version que VERSION
#    -> si mismatch, on FAIL le build (plus de RPM incohérent).
#
# IMPORTANT (Docker) :
# - Si lancé dans Docker, DISTPATH=/tmp/dist garantit que dist/ du repo reste propre
# - Le binaire temporaire est copié vers SOURCES/ (source of truth pour rpmbuild)
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"
LOG_FILE="${PROJECT_ROOT}/build-rpm.log"
BINARY_NAME="monitoring-client"

# Pour Docker : build PyInstaller dans /tmp (évite pollution du repo)
IS_DOCKER="${IS_DOCKER:-false}"
if [[ "${IS_DOCKER}" == "true" ]]; then
  TEMP_DIST_DIR="/tmp/dist"
else
  TEMP_DIST_DIR="${DIST_DIR}"
fi

# Source des fonctions communes
# - get_version
# - check_common_prerequisites
# - log_info/log_success/log_error
source "${PROJECT_ROOT}/packaging/common/functions.sh"

# -----------------------------------------------------------------------------
# Logging : tout vers un fichier + stdout (utile en CI/Docker)
# -----------------------------------------------------------------------------
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Démarrage du build RPM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -----------------------------------------------------------------------------
# Vérification des prérequis communs
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
VERSION="$(get_version "${PROJECT_ROOT}")"
RPMROOT="${PROJECT_ROOT}/rpmbuild"

log_info "Project root : ${PROJECT_ROOT}"
log_info "Version      : ${VERSION}"
log_info "RPMROOT      : ${RPMROOT}"
log_info "Docker mode  : ${IS_DOCKER}"
log_info "Temp dist    : ${TEMP_DIST_DIR}"
log_info "Log          : ${LOG_FILE}"

# -----------------------------------------------------------------------------
# Préparation de l'arborescence rpmbuild
# -----------------------------------------------------------------------------
log_info "Nettoyage de l'ancienne structure rpmbuild..."
rm -rf "${RPMROOT}"
mkdir -p "${RPMROOT}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "${RELEASE_DIR}"
log_success "Structure rpmbuild créée"

# -----------------------------------------------------------------------------
# Build du binaire PyInstaller (source of truth du RPM)
# -----------------------------------------------------------------------------
log_info "Préparation build PyInstaller (anti stale)..."

# IMPORTANT :
# En Docker (volume monté), dist/ peut contenir un vieux binaire.
# On nettoie TEMP_DIST_DIR pour repartir propre.
log_info "Nettoyage du répertoire de build temporaire..."
rm -rf "${TEMP_DIST_DIR}" \
       "${PROJECT_ROOT}/build" \
       "${PROJECT_ROOT}/.build-pyinstaller" \
       2>/dev/null || true
mkdir -p "${TEMP_DIST_DIR}"
log_success "Nettoyage terminé"

log_info "Build du binaire PyInstaller..."
if [[ ! -x "${PROJECT_ROOT}/scripts/build.sh" ]]; then
  log_error "Le script build.sh n'existe pas ou n'est pas exécutable."
  exit 1
fi

# Build avec DISTPATH custom (évite pollution du repo en Docker)
DISTPATH="${TEMP_DIST_DIR}" "${PROJECT_ROOT}/scripts/build.sh" || {
  log_error "Échec du build PyInstaller"
  exit 1
}

# Vérification du binaire généré
if [[ ! -f "${TEMP_DIST_DIR}/${BINARY_NAME}" ]]; then
  log_error "Le binaire ${BINARY_NAME} n'a pas été généré dans ${TEMP_DIST_DIR}/"
  exit 1
fi
log_success "Binaire ${BINARY_NAME} généré dans ${TEMP_DIST_DIR}/"

# -----------------------------------------------------------------------------
# Sanity check BLOQUANT : version binaire == version package
# -----------------------------------------------------------------------------
log_info "Sanity check : vérification de la version du binaire..."
BIN_VER="$("${TEMP_DIST_DIR}/${BINARY_NAME}" --version 2>/dev/null | awk '{print $2}' || true)"

if [[ -z "${BIN_VER}" ]]; then
  log_error "Impossible de lire la version via : ${TEMP_DIST_DIR}/${BINARY_NAME} --version"
  log_error "Assurez-vous que --version est supporté et retourne: 'monitoring-client X.Y.Z'"
  exit 1
fi

if [[ "${BIN_VER}" != "${VERSION}" ]]; then
  log_error "Mismatch version binaire : attendu=${VERSION} obtenu=${BIN_VER}"
  log_error "Refus de créer un RPM incohérent (binaire stale ou build incorrect)."
  exit 1
fi

log_success "Version binaire OK : ${BIN_VER}"

# -----------------------------------------------------------------------------
# Création d'une archive Source0 minimale pour rpmbuild
# -----------------------------------------------------------------------------
log_info "Création de l'archive Source0..."
tar czf "${RPMROOT}/SOURCES/monitoring-client-${VERSION}.tar.gz" \
  -C "${TEMP_DIST_DIR}" "${BINARY_NAME}" || {
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

# Date en anglais pour le changelog RPM
CHANGELOG_DATE="$(LC_TIME=C date '+%a %b %d %Y')"

# Remplacer les placeholders dans le template SPEC
sed -e "s|__VERSION__|${VERSION}|g" \
    -e "s|__DIST_DIR__|${TEMP_DIST_DIR}|g" \
    -e "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" \
    -e "s|__CHANGELOG_DATE__|${CHANGELOG_DATE}|g" \
    "${PROJECT_ROOT}/packaging/templates/rpm/spec.template" \
    > "${RPMROOT}/SPECS/monitoring-client.spec"

log_success "Fichier SPEC généré : ${RPMROOT}/SPECS/monitoring-client.spec"

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
# Nettoyage du binaire temporaire (Docker uniquement)
# -----------------------------------------------------------------------------
if [[ "${IS_DOCKER}" == "true" ]]; then
  log_info "Nettoyage du binaire temporaire Docker..."
  rm -rf "${TEMP_DIST_DIR}" 2>/dev/null || true
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