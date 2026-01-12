#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# build.sh - Build du binaire standalone "monitoring-client" via PyInstaller
#
# Objectifs :
# - Construire un binaire unique : dist/monitoring-client
# - Nettoyer les anciens artefacts pour éviter les versions stale
# - Éviter que PyInstaller embarque une ancienne lib installée dans le venv
#
# Garanties (anti “mot de passe sudo”) :
# - AUCUN sudo dans ce script.
# - Le workdir PyInstaller est placé dans /tmp (toujours writable) :
#     ${TMPDIR:-/tmp}/monitoring-client-pyinstaller-${USER}
#   => évite définitivement les PermissionError liés à un ancien build lancé en root
#      (fichiers root dans le repo).
#
# Remarques :
# - Ce script NE DOIT PAS “skip” en fonction de dist/ existant.
# - Il est safe pour Docker/CI (nettoyage + --clean PyInstaller).
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
SRC_DIR="${PROJECT_ROOT}/src"

# Répertoire de travail PyInstaller (isolé et TOUJOURS writable)
# IMPORTANT :
# - Si un build a déjà été lancé en root, un dossier dans le repo peut rester root
#   et casser les builds suivants (PermissionError).
# - En utilisant /tmp, on évite définitivement ce problème.
# - Le chemin est user-scopé pour éviter collisions multi-users.
PYI_BUILD_DIR="${TMPDIR:-/tmp}/monitoring-client-pyinstaller-${USER}"

BINARY_NAME="monitoring-client"

# ⚠️ IMPORTANT :
# Ne pas confondre avec un RPM spec.
# Utiliser un spec PyInstaller dédié :
SPEC_FILE="${PROJECT_ROOT}/pyinstaller.spec"

echo "[build] Project root : ${PROJECT_ROOT}"
echo "[build] Dist dir     : ${DIST_DIR}"
echo "[build] Src dir      : ${SRC_DIR}"
echo "[build] Spec file    : ${SPEC_FILE}"
echo "[build] Work dir     : ${PYI_BUILD_DIR}"

# -----------------------------------------------------------------------------
# Vérifications préalables
# -----------------------------------------------------------------------------
if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "[build] ❌ Erreur : pyinstaller n'est pas installé."
  echo "[build]    Installe-le par exemple avec : pip install pyinstaller"
  exit 1
fi

if [[ ! -f "${SPEC_FILE}" ]]; then
  echo "[build] ❌ Erreur : fichier spec introuvable : ${SPEC_FILE}"
  exit 1
fi

# -----------------------------------------------------------------------------
# 1) Nettoyage des anciennes versions / artefacts
# -----------------------------------------------------------------------------

# 1a) Désinstaller l'ancienne version du package dans le venv (si présent)
# -> évite que PyInstaller embarque un wheel déjà installé et obsolète
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "[build] Désinstallation éventuelle de l'ancienne version dans le venv..."
  pip uninstall -y monitoring-client >/dev/null 2>&1 || true
fi

# 1b) Nettoyage répertoire de travail PyInstaller
# -> Comme il est dans /tmp et user-scopé, aucune demande de sudo.
echo "[build] Nettoyage du workdir PyInstaller..."
rm -rf "${PYI_BUILD_DIR}" 2>/dev/null || true

# 1c) Nettoyage binaire(s) dist précédents (anti-stale)
echo "[build] Suppression des binaires dist précédents..."
rm -f "${DIST_DIR}/${BINARY_NAME}" "${DIST_DIR}/${BINARY_NAME}.exe" 2>/dev/null || true

# 1d) Nettoyage cache PyInstaller utilisateur
# -> C'est dans $HOME, donc aucun sudo. Si ça échoue, on logge et on continue.
if [[ -d "${HOME}/.cache/pyinstaller" ]]; then
  echo "[build] Nettoyage du cache PyInstaller utilisateur..."
  rm -rf "${HOME}/.cache/pyinstaller" 2>/dev/null || {
    echo "[build] ⚠️ Impossible de supprimer ${HOME}/.cache/pyinstaller (on continue)."
  }
fi

# 1e) Créer le répertoire de sortie si nécessaire
mkdir -p "${DIST_DIR}"
cd "${PROJECT_ROOT}"

# -----------------------------------------------------------------------------
# 2) Build PyInstaller
# -----------------------------------------------------------------------------
echo "[build] Lancement de PyInstaller..."
pyinstaller \
  --clean \
  --noconfirm \
  --workpath "${PYI_BUILD_DIR}" \
  "${SPEC_FILE}"

# -----------------------------------------------------------------------------
# 3) Vérification du binaire
# -----------------------------------------------------------------------------
if [[ -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "[build] ✅ Binaire généré : ${DIST_DIR}/${BINARY_NAME}"
  echo "[build] Taille          : $(du -h "${DIST_DIR}/${BINARY_NAME}" | cut -f1)"

  # Afficher la version si supportée (utile pour debug packaging)
  if "${DIST_DIR}/${BINARY_NAME}" --version >/dev/null 2>&1; then
    echo -n "[build] Version         : "
    "${DIST_DIR}/${BINARY_NAME}" --version || true
  else
    echo "[build] Version         : (option --version non disponible)"
  fi
else
  echo "[build] ❌ Erreur : binaire non trouvé après build."
  exit 1
fi

echo "[build] Build terminé avec succès."
