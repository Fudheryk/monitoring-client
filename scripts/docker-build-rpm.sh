#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# docker-build-rpm.sh - Build d'un package RPM via Docker CentOS
#
# Objectifs :
# - Builder dans un environnement CentOS reproductible
# - ÉVITER d'embarquer un binaire stale (ex: dist/monitoring-client en 1.0.50)
#   à cause du volume Docker monté (-v PROJECT_ROOT:/build)
#
# Stratégie :
# - On nettoie dist/ build/ rpmbuild/ AVANT le build dans le conteneur
# - On laisse scripts/rpm_build.sh être la SINGLE source of truth :
#     -> il rebuild le binaire + fait le rpm
# - On ne lance PLUS ./scripts/build.sh ici (redondant et source de confusion)
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Nom de l'image Docker utilisée pour builder les RPM
DOCKER_IMAGE="monitoring-build"

# -----------------------------------------------------------------------------
# Lancement du conteneur Docker
# -----------------------------------------------------------------------------
# - Monte le projet dans /build
# - Positionne le répertoire de travail dans /build
# - Nettoie les artefacts persistants du volume
# - Exécute rpm_build.sh (qui fait rebuild binaire + rpm)
# -----------------------------------------------------------------------------
docker run --rm \
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  -e USER="${USER:-$(id -un 2>/dev/null || echo unknown)}" \
  "${DOCKER_IMAGE}" \
  bash -c "
    set -euo pipefail
    echo '[docker] Conteneur démarré, build du RPM...'

    # -----------------------------------------------------------------------
    # 1) Nettoyage (anti stale)
    # -----------------------------------------------------------------------
    # IMPORTANT :
    # Comme /build est un volume monté, dist/ peut contenir un vieux binaire.
    # Si build.sh “skip” ou réutilise dist, le RPM embarque une mauvaise version.
    echo '[docker] Nettoyage des artefacts (dist/build/rpmbuild)...'
    rm -rf ./dist ./build ./.build-pyinstaller ./rpmbuild || true

    # -----------------------------------------------------------------------
    # 2) Build du package RPM (rebuild binaire inclus)
    # -----------------------------------------------------------------------
    echo '[docker] Build du package RPM via rpm_build.sh'
    ./scripts/rpm_build.sh

    echo '[docker] Build RPM terminé avec succès.'
  "

echo "[docker] Package RPM généré, vérifier dans rpmbuild/RPMS/x86_64/"
