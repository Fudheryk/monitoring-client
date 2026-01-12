#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# docker-build-rpm.sh - Build d'un package RPM via Docker (CentOS)
#
# Objectifs :
# - Builder dans un environnement CentOS reproductible.
# - Éviter les binaires "stale" (ex: dist/monitoring-client resté en 1.0.50).
# - Éviter de “polluer” le repo hôte avec des fichiers appartenant à root
#   (ce qui casse ensuite les builds hors Docker avec des PermissionError).
#
# Stratégie :
# 1) On exécute le conteneur avec l'UID/GID de l'utilisateur hôte :
#    => tous les fichiers créés/modifiés dans le volume monté restent écriture OK
#       sans sudo / sans demande de mot de passe.
# 2) On nettoie dist/ build/ rpmbuild/ AVANT le build dans le conteneur :
#    => pas de réutilisation accidentelle d'artefacts.
# 3) scripts/rpm_build.sh est la SINGLE source of truth :
#    => il rebuild le binaire + construit le RPM.
#    => on ne lance PAS build.sh ici (redondant/confus).
#
# Notes :
# - On force HOME/XDG_CACHE_HOME vers /tmp pour éviter l'utilisation de /root
#   (cache PyInstaller, etc.) et rester “stateless”.
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_IMAGE="monitoring-build"

# UID/GID hôte (évite les fichiers root-owned dans le repo)
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_USER="${USER:-$(id -un 2>/dev/null || echo unknown)}"

docker run --rm \
  -u "${HOST_UID}:${HOST_GID}" \
  -e USER="${HOST_USER}" \
  -e HOME="/tmp" \
  -e XDG_CACHE_HOME="/tmp/.cache" \
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  "${DOCKER_IMAGE}" \
  bash -lc "
    set -euo pipefail
    echo '[docker] Conteneur démarré (user='\"\$USER\"', uid='\"\$(id -u)\"', gid='\"\$(id -g)\"')'
    echo '[docker] Build du RPM...'

    # -----------------------------------------------------------------------
    # 1) Nettoyage (anti stale)
    # -----------------------------------------------------------------------
    # IMPORTANT :
    # /build est un volume monté => dist/ peut contenir un vieux binaire.
    # On supprime les répertoires d'artefacts pour repartir propre.
    echo '[docker] Nettoyage des artefacts persistants (dist/build/rpmbuild)...'
    rm -rf ./dist ./build ./.build-pyinstaller ./rpmbuild || true

    # -----------------------------------------------------------------------
    # 2) Build du package RPM (rebuild binaire inclus)
    # -----------------------------------------------------------------------
    echo '[docker] Build du package RPM via rpm_build.sh (source of truth)'
    ./scripts/rpm_build.sh

    echo '[docker] Build RPM terminé avec succès.'
  "

echo "[docker] Package RPM généré, vérifier dans rpmbuild/RPMS/x86_64/"
