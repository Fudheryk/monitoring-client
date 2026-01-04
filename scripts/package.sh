#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# package.sh - Fabrique un package tar.gz prêt à être livré au client final.
#
# Fonctions :
#   1. Compiler le binaire via scripts/build.sh
#   2. Construire un package propre contenant :
#        - bin/monitoring-client
#        - config exemple
#        - vendors/ (vide + README)
#        - scripts/install.sh
#        - fichiers systemd
#        - README.md
#   3. Générer une archive tar.gz dans release/
#
# Le client final n'a besoin ni des sources ni du venv.
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"

BINARY_NAME="monitoring-client"

# Récupère la version depuis config.yaml en supprimant les guillemets
VERSION="$(
  grep -E '^[[:space:]]*version:' "${PROJECT_ROOT}/config/config.yaml" \
    | head -1 \
    | awk '{print $2}' \
    | tr -d '"'
)"

VERSION="${VERSION:-0.1.0}"
TARGET_OS="linux"
TARGET_ARCH="amd64"

PKG_NAME="monitoring-client-${VERSION}-${TARGET_OS}-${TARGET_ARCH}"
PKG_DIR="${RELEASE_DIR}/${PKG_NAME}"

echo "[package] Project root : ${PROJECT_ROOT}"
echo "[package] Version      : ${VERSION}"
echo "[package] Package dir  : ${PKG_DIR}"

mkdir -p "${RELEASE_DIR}"

# -----------------------------------------------------------------------------
# 1) Build du binaire via PyInstaller
# -----------------------------------------------------------------------------
"${PROJECT_ROOT}/scripts/build.sh"

if [[ ! -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "[package] Erreur : binaire introuvable (${DIST_DIR}/${BINARY_NAME})"
  exit 1
fi

# -----------------------------------------------------------------------------
# 2) Préparer arborescence du package
# -----------------------------------------------------------------------------
rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/bin"
mkdir -p "${PKG_DIR}/config"
mkdir -p "${PKG_DIR}/systemd"
mkdir -p "${PKG_DIR}/vendors"         # vendors vide mais présent
mkdir -p "${PKG_DIR}/scripts"
mkdir -p "${PKG_DIR}/examples/vendors"

# -----------------------------------------------------------------------------
# 3) Copier le binaire
# -----------------------------------------------------------------------------
cp "${DIST_DIR}/${BINARY_NAME}" "${PKG_DIR}/bin/"
chmod 755 "${PKG_DIR}/bin/${BINARY_NAME}"

# -----------------------------------------------------------------------------
# 4) Copier configuration (exemple + schema)
# -----------------------------------------------------------------------------
cp "${PROJECT_ROOT}/config/config.yaml.example" "${PKG_DIR}/config/"
cp "${PROJECT_ROOT}/config/config.schema.json" "${PKG_DIR}/config/"

# -----------------------------------------------------------------------------
# 5) Ajouter README pour vendors
# -----------------------------------------------------------------------------
# cat > "${PKG_DIR}/vendors/README.md" << 'EOF'
# Vendors directory
#
#Placez ici vos fichiers vendor personnalisés au format YAML.
#
#Exemple minimal :
#
#```yaml
#metadata:
#  vendor: myapp
#  language: bash
#
#metrics:
#  - name: myapp.status
#    group_name: myapp
#    command: "echo ok"
#    type: string
#    description: "Status applicatif"
#   is_critical: false
