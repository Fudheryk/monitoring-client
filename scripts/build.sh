#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# build.sh - Build du binaire standalone "monitoring-client" via PyInstaller
#
# - Utilise un fichier .spec PyInstaller (par défaut: pyinstaller.spec)
# - Produit un binaire unique : dist/monitoring-client
# - Inclut les fichiers de config (config.yaml.example + schema)
# - Désinstalle toute ancienne version installée dans le venv pour éviter
#   que PyInstaller embarque une version obsolète.
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

# ---------------------------------------------------------------------------
# Vérifications préalables
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 1) Nettoyage des anciennes versions
# ---------------------------------------------------------------------------
# Supprime toute ancienne version installée dans le venv pour éviter
# que PyInstaller emballe une version obsolète.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "[build] Désinstallation éventuelle de l'ancienne version dans le venv..."
  pip uninstall -y monitoring-client || true
fi

# Nettoyage du build précédent
echo "[build] Nettoyage des anciens builds..."
if ! rm -rf "${PYI_BUILD_DIR}" 2>/dev/null; then
  echo "[build] [!] Fichiers verrouillés détectés, utilisation de sudo..."
  sudo rm -rf "${PYI_BUILD_DIR}"
fi

rm -rf "${DIST_DIR:?}/${BINARY_NAME}" "${DIST_DIR:?}/${BINARY_NAME}.exe" 2>/dev/null || true

# Nettoyage du cache PyInstaller utilisateur (résout PermissionError)
if [[ -d "${HOME}/.cache/pyinstaller" ]]; then
  echo "[build] Nettoyage du cache PyInstaller..."
  if ! rm -rf "${HOME}/.cache/pyinstaller" 2>/dev/null; then
    echo "[build] [!] Cache verrouillé, utilisation de sudo..."
    sudo rm -rf "${HOME}/.cache/pyinstaller"
  fi
fi

# Création du répertoire de sortie
mkdir -p "${DIST_DIR}"
cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# 2) Build avec PyInstaller
# ---------------------------------------------------------------------------
echo "[build] Lancement de PyInstaller..."
pyinstaller \
  --clean \
  --noconfirm \
  --workpath "${PYI_BUILD_DIR}" \
  "${SPEC_FILE}"

# ---------------------------------------------------------------------------
# 3) Vérification du binaire
# ---------------------------------------------------------------------------
if [[ -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "[build] Binaire généré : ${DIST_DIR}/${BINARY_NAME}"
  echo "[build] Taille        : $(du -h "${DIST_DIR}/${BINARY_NAME}" | cut -f1)"
else
  echo "[build] Erreur : binaire non trouvé après build."
  exit 1
fi

echo "[build] Build terminé avec succès."