#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# make.sh - Build local de tous les formats (hors publication)
#
# - PyInstaller
# - TAR.GZ
# - DEB
# - RPM (via Docker)
#
# ⚠️ Ne publie rien (pas de git tag, pas de GitHub release)
# ------------------------------------------------------------------------------

# Résolution du chemin racine du projet
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"

echo "=== Monitoring Client - Build All Formats ==="
echo "Project root : ${PROJECT_ROOT}"
echo

# ------------------------------------------------------------------------------
# 1/4 - Build du binaire (PyInstaller)
# ------------------------------------------------------------------------------
echo "[1/4] Build binaire (PyInstaller)"
"${SCRIPTS_DIR}/build.sh"
echo

# ------------------------------------------------------------------------------
# 2/4 - Packaging TAR.GZ
# ------------------------------------------------------------------------------
echo "[2/4] Build package TAR.GZ"
"${SCRIPTS_DIR}/package.sh"
echo

# ------------------------------------------------------------------------------
# 3/4 - Build DEB (exécuté sur l'hôte Debian)
# ------------------------------------------------------------------------------
echo "[3/4] Build DEB"
"${SCRIPTS_DIR}/deb_build.sh"
echo

# ------------------------------------------------------------------------------
# 4/4 - Build RPM (via Docker CentOS)
# ------------------------------------------------------------------------------
echo "[4/4] Build RPM (Docker)"
"${SCRIPTS_DIR}/docker-build-rpm.sh"
echo

# ------------------------------------------------------------------------------
# Fin
# ------------------------------------------------------------------------------
echo "=== Build terminé avec succès ==="
echo "Fichiers disponibles dans ${PROJECT_ROOT}/release/"
