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
# Garanties (anti "mot de passe sudo") :
# - AUCUN sudo dans ce script.
# - Le workdir PyInstaller est placé dans /tmp (toujours writable) :
#     ${TMPDIR:-/tmp}/monitoring-client-pyinstaller-${RUN_USER}
#   => évite définitivement les PermissionError liés à un ancien build lancé en root
#      (fichiers root dans le repo).
#
# Nouveauté : support de DISTPATH custom (Docker/isolation)
# - Par défaut : ./dist (comportement classique)
# - Avec DISTPATH=/tmp/dist : le binaire final est écrit hors du repo
#   => évite les conflits de permission entre Docker et hôte
# -----------------------------------------------------------------------------

# USER n'est pas toujours défini (ex: docker + set -u). On calcule un identifiant sûr.
RUN_USER="${USER:-$(id -un 2>/dev/null || echo unknown)}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_DIST_DIR="${PROJECT_ROOT}/dist"
SRC_DIR="${PROJECT_ROOT}/src"

# Support DISTPATH custom (pour Docker / builds isolés)
DIST_DIR="${DISTPATH:-${DEFAULT_DIST_DIR}}"

# Répertoire de travail PyInstaller (isolé et TOUJOURS writable)
# IMPORTANT :
# - Si un build a déjà été lancé en root, un dossier dans le repo peut rester root
#   et casser les builds suivants (PermissionError).
# - En utilisant /tmp, on évite définitivement ce problème.
# - Le chemin est user-scopé pour éviter collisions multi-users.
PYI_BUILD_DIR="${TMPDIR:-/tmp}/monitoring-client-pyinstaller-${RUN_USER}"

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
# CRITIQUE : vérifier les permissions du DIST_DIR et du binaire
echo "[build] Suppression des binaires dist précédents..."

# Vérifier si le répertoire dist existe et s'il est writable
if [[ -d "${DIST_DIR}" ]] && [[ ! -w "${DIST_DIR}" ]]; then
  echo "[build] ⚠️  ERREUR CRITIQUE : Le répertoire ${DIST_DIR}/ n'est PAS writable"
  echo "[build]    Propriétaire : $(stat -c '%U:%G' "${DIST_DIR}" 2>/dev/null || echo 'inconnu')"
  echo "[build]    Permissions  : $(stat -c '%A' "${DIST_DIR}" 2>/dev/null || echo 'inconnu')"
  echo "[build]"
  echo "[build] Cause probable : build Docker précédent a créé ce répertoire en root."
  echo "[build]"
  echo "[build] 🔧 Solution :"
  echo "[build]    sudo chown -R \$(whoami):\$(whoami) ${DIST_DIR}/"
  echo "[build]"
  echo "[build] ⚠️  Pour éviter ce problème à l'avenir :"
  echo "[build]    - Utilisez ./scripts/docker-build-rpm.sh au lieu de docker run direct"
  echo "[build]    - Ce script garantit l'UID/GID correct (-u \$(id -u):\$(id -g))"
  exit 1
fi

# Vérifier si le binaire existe et s'il est writable
if [[ -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  if [[ ! -w "${DIST_DIR}/${BINARY_NAME}" ]]; then
    echo "[build] ⚠️  ERREUR CRITIQUE : ${DIST_DIR}/${BINARY_NAME} existe et n'est PAS writable"
    echo "[build]    Propriétaire : $(stat -c '%U:%G' "${DIST_DIR}/${BINARY_NAME}" 2>/dev/null || echo 'inconnu')"
    echo "[build]    Permissions  : $(stat -c '%A' "${DIST_DIR}/${BINARY_NAME}" 2>/dev/null || echo 'inconnu')"
    echo "[build]"
    echo "[build] 🔧 Solution :"
    echo "[build]    sudo chown -R \$(whoami):\$(whoami) ${DIST_DIR}/"
    echo "[build]"
    exit 1
  fi
  rm -f "${DIST_DIR}/${BINARY_NAME}" || {
    echo "[build] ❌ Impossible de supprimer ${DIST_DIR}/${BINARY_NAME}"
    exit 1
  }
fi

rm -f "${DIST_DIR}/${BINARY_NAME}.exe" 2>/dev/null || true

# 1d) Nettoyage cache PyInstaller utilisateur
# -> C'est dans $HOME, donc aucun sudo. Si ça échoue, on logge et on continue.
echo "[build] Nettoyage du cache PyInstaller..."
if [[ -d "${HOME}/.cache/pyinstaller" ]]; then
  rm -rf "${HOME}/.cache/pyinstaller" 2>/dev/null || {
    echo "[build] ⚠️ Impossible de supprimer ${HOME}/.cache/pyinstaller (on continue)."
  }
fi

# 1e) Nettoyage des fichiers Python compilés (*.pyc, __pycache__)
# -> Évite les problèmes de cache de modules Python
echo "[build] Nettoyage des fichiers Python compilés..."
find "${SRC_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${SRC_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${PROJECT_ROOT}" -maxdepth 1 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 1e) Créer le répertoire de sortie si nécessaire
mkdir -p "${DIST_DIR}"
cd "${PROJECT_ROOT}"

# 1f) Afficher la version détectée dans le code source (debug)
echo "[build] Version dans __version__.py : $(grep '__version__ = ' "${SRC_DIR}/monitoring_client/__version__.py" 2>/dev/null | cut -d'"' -f2 || echo 'introuvable')"

# -----------------------------------------------------------------------------
# 2) Build PyInstaller
# -----------------------------------------------------------------------------
echo "[build] Lancement de PyInstaller..."
pyinstaller \
  --clean \
  --noconfirm \
  --workpath "${PYI_BUILD_DIR}" \
  --distpath "${DIST_DIR}" \
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