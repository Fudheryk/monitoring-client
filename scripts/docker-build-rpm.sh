#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# docker-build-rpm.sh - Build d'un package RPM via Docker (CentOS)
#
# Objectifs :
# - Builder dans un environnement CentOS reproductible.
# - Éviter les binaires "stale" (ex: dist/monitoring-client resté en 1.0.50).
# - Éviter de "polluer" le repo hôte avec des fichiers appartenant à root
#   (ce qui casse ensuite les builds hors Docker avec des PermissionError).
#
# Stratégie :
# 1) On exécute le conteneur avec l'UID/GID de l'utilisateur hôte :
#    => tous les fichiers créés/modifiés dans le volume monté restent écriture OK
#       sans sudo / sans demande de mot de passe.
# 2) On passe IS_DOCKER=true à rpm_build.sh :
#    => Le build PyInstaller se fait dans /tmp/dist (isolé)
#    => dist/ du repo reste propre (zéro fichier root-owned)
# 3) On nettoie rpmbuild/ AVANT le build :
#    => pas de réutilisation accidentelle d'artefacts RPM précédents.
#
# Notes :
# - On force HOME/XDG_CACHE_HOME vers /tmp pour éviter l'utilisation de /root
#   (cache PyInstaller, etc.) et rester "stateless".
# - Le binaire PyInstaller est buildé DANS le conteneur, pas sur l'hôte
#   => cohérence totale de l'environnement (CentOS 7, Python 3.11, glibc, etc.)
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_IMAGE="monitoring-build"

# UID/GID hôte (évite les fichiers root-owned dans le repo)
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
HOST_USER="${USER:-$(id -un 2>/dev/null || echo unknown)}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Build RPM dans Docker (CentOS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Image  : ${DOCKER_IMAGE}"
echo "User   : ${HOST_USER} (${HOST_UID}:${HOST_GID})"
echo "Project: ${PROJECT_ROOT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker run --rm \
  -u "${HOST_UID}:${HOST_GID}" \
  -e USER="${HOST_USER}" \
  -e HOME="/tmp" \
  -e XDG_CACHE_HOME="/tmp/.cache" \
  -e IS_DOCKER="true" \
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  "${DOCKER_IMAGE}" \
  bash -lc "
    set -euo pipefail
    echo '[docker] Conteneur démarré (user='\"\$USER\"', uid='\"\$(id -u)\"', gid='\"\$(id -g)\"')'
    echo '[docker] Mode Docker : IS_DOCKER='\"\$IS_DOCKER\"
    echo '[docker] Build du RPM...'

    # -----------------------------------------------------------------------
    # 1) Nettoyage (anti stale)
    # -----------------------------------------------------------------------
    # IMPORTANT :
    # - On ne touche PAS à dist/ (peut contenir un build hôte valide)
    # - On nettoie seulement rpmbuild/ (artefacts RPM précédents)
    # - Le build PyInstaller se fera dans /tmp/dist (isolation totale)
    echo '[docker] Nettoyage des artefacts RPM précédents...'
    if [[ -d ./rpmbuild ]] && [[ ! -w ./rpmbuild ]]; then
      echo '[docker] ❌ ERREUR : rpmbuild/ n'\''est pas writable'
      echo '[docker]    Propriétaire : \$(stat -c '\''%U:%G'\'' ./rpmbuild 2>/dev/null || echo inconnu)'
      echo '[docker]'
      echo '[docker] 🔧 Solution (sur l'\''hôte) :'
      echo '[docker]    sudo chown -R \$(whoami):\$(whoami) rpmbuild/'
      echo '[docker]    OU : ./scripts/check-perms.sh --fix'
      exit 1
    fi
    rm -rf ./rpmbuild || true

    # -----------------------------------------------------------------------
    # 2) Build du package RPM (rebuild binaire inclus dans /tmp/dist)
    # -----------------------------------------------------------------------
    echo '[docker] Build du package RPM via rpm_build.sh (source of truth)'
    ./scripts/rpm_build.sh

    echo '[docker] Build RPM terminé avec succès.'
  "

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Build Docker terminé"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Package RPM : ${PROJECT_ROOT}/rpmbuild/RPMS/x86_64/"
echo ""