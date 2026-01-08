#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# docker-build-rpm.sh - Build d'un package RPM via Docker CentOS
#
# - Monte le projet dans un conteneur Docker "monitoring-build"
# - Appelle le script rpm_build.sh à l'intérieur
# - Garantit que le binaire PyInstaller est reconstruit proprement
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Nom de l'image Docker utilisée pour builder les RPM
DOCKER_IMAGE="monitoring-build"

# ---------------------------------------------------------------------------
# Lancement du conteneur Docker
# ---------------------------------------------------------------------------
# - Monte le projet dans /build
# - Positionne le répertoire de travail dans /build
# - Exécute rpm_build.sh à l'intérieur
# ---------------------------------------------------------------------------
docker run --rm \
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  "${DOCKER_IMAGE}" \
  bash -c "
    set -euo pipefail
    echo '[docker] Conteneur démarré, build du RPM...'

    # -----------------------------------------------------------------------
    # 1) Nettoyage et rebuild du binaire via build.sh
    # -----------------------------------------------------------------------
    echo '[docker] Build du binaire via build.sh'
    ./scripts/build.sh

    # -----------------------------------------------------------------------
    # 2) Build du package RPM
    # -----------------------------------------------------------------------
    echo '[docker] Build du package RPM via rpm_build.sh'
    ./scripts/rpm_build.sh

    echo '[docker] Build RPM terminé avec succès.'
  "

echo "[docker] Package RPM généré, vérifier dans rpmbuild/RPMS/x86_64/"
