#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="${PROJECT_ROOT}/scripts"

echo "=== Monitoring Client - Build All Formats ==="

echo "[1/4] Build binaire (PyInstaller)"
"${SCRIPTS}/build.sh"

echo "[2/4] Build TAR.GZ package"
"${SCRIPTS}/package.sh"

echo "[3/4] Build DEB"
"${SCRIPTS}/deb_build.sh"

echo "[4/4] Build RPM"
"${SCRIPTS}/rpm_build.sh"

echo "=== Build terminé avec succès ==="
echo "Fichiers disponibles dans release/"
