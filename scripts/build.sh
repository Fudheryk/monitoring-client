#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# build.sh - Build du binaire standalone "monitoring-client" via PyInstaller
#
# - Utilise un fichier .spec PyInstaller (par défaut: pyinstaller.spec)
# - Produit un binaire unique : dist/monitoring-client
# - Inclut les fichiers de config (config.yaml.example + schema)
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
SRC_DIR="${PROJECT_ROOT}/src"

# Répertoire de travail PyInstaller (isolé pour éviter conflits Docker)
PYI_BUILD_DIR="${PROJECT_ROOT}/.build-pyinstaller"

BINARY_NAME="monitoring-client"

# ⚠️ IMPORTANT :
# Ne pas l'appeler "monitoring-client.spec" si tu as aussi un RPM spec du même nom.
# Utilise un nom dédié PyInstaller :
SPEC_FILE="${PROJECT_ROOT}/pyinstaller.spec"

echo "[build] Project root : ${PROJECT_ROOT}"
echo "[build] Dist dir     : ${DIST_DIR}"
echo "[build] Src dir      : ${SRC_DIR}"
echo "[build] Spec file    : ${SPEC_FILE}"

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "[build] Erreur : pyinstaller n'est pas installé."
  echo "         Installe-le par exemple avec : pip install pyinstaller"
  exit 1
fi

if [[ ! -f "${SPEC_FILE}" ]]; then
  echo "[build] Erreur : fichier spec introuvable : ${SPEC_FILE}"
  echo "         (Crée ${SPEC_FILE} avec le contenu fourni.)"
  exit 1
fi

mkdir -p "${DIST_DIR}"
cd "${PROJECT_ROOT}"

# Nettoyage précédent build PyInstaller (isolé)
rm -rf "${PYI_BUILD_DIR}" "${DIST_DIR:?}/${BINARY_NAME}" "${DIST_DIR:?}/${BINARY_NAME}.exe" 2>/dev/null || true

echo "[build] Lancement de PyInstaller..."
pyinstaller \
  --clean \
  --noconfirm \
  --workpath "${PYI_BUILD_DIR}" \
  "${SPEC_FILE}"

# Vérification binaire
if [[ -f "${PROJECT_ROOT}/dist/${BINARY_NAME}" ]]; then
  echo "[build] Binaire généré : dist/${BINARY_NAME}"
else
  echo "[build] Erreur : binaire non trouvé après build."
  exit 1
fi

echo "[build] Build terminé avec succès."
