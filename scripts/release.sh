#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# release.sh - Build + publication d'une release GitHub
#
# Usage :
#   ./scripts/release.sh 1.0.48 "Fix: Collector disk missing"
#
# Prérequis :
#   - gh auth login
#   - dépôt git propre
# ------------------------------------------------------------------------------

VERSION="${1:-}"
RELEASE_NOTES="${2:-}"

if [[ -z "${VERSION}" || -z "${RELEASE_NOTES}" ]]; then
  echo "Usage: $0 <version> \"release notes\""
  exit 1
fi

TAG="v${VERSION}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RELEASE_DIR="${PROJECT_ROOT}/release"
DEB_PATH="${RELEASE_DIR}/monitoring-client_${VERSION}_amd64.deb"
RPM_PATH="${PROJECT_ROOT}/rpmbuild/RPMS/x86_64/monitoring-client-${VERSION}-1.x86_64.rpm"
SHA_FILE="${RELEASE_DIR}/monitoring-client_${VERSION}_SHA256SUMS.txt"

echo "🚀 Release ${TAG}"
echo

cd "${PROJECT_ROOT}"

# ------------------------------------------------------------------------------
# Vérifications préalables
# ------------------------------------------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  echo "❌ gh CLI non installé"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "❌ Le dépôt git n'est pas propre"
  git status --short
  exit 1
fi

if gh release view "${TAG}" >/dev/null 2>&1; then
  echo "❌ La release ${TAG} existe déjà sur GitHub"
  exit 1
fi

# ------------------------------------------------------------------------------
# 1) Synchronisation version + git
# ------------------------------------------------------------------------------
echo "🔄 Synchronisation version"
./scripts/sync_version.sh "${VERSION}"

git add .
git commit -m "chore: bump version to ${VERSION}"
git tag "${TAG}"

echo "📤 Push commit + tag"
git push origin main
git push origin "${TAG}"

# ------------------------------------------------------------------------------
# 2) Build des artefacts
# ------------------------------------------------------------------------------
echo
echo "📦 Build DEB (hôte)"
./scripts/deb_build.sh

echo
echo "📦 Build RPM (Docker CentOS)"
./scripts/docker-build-rpm.sh

# ------------------------------------------------------------------------------
# 3) Vérification des artefacts
# ------------------------------------------------------------------------------
for f in "${DEB_PATH}" "${RPM_PATH}"; do
  if [[ ! -f "${f}" ]]; then
    echo "❌ Artefact manquant : ${f}"
    exit 1
  fi
done

# ------------------------------------------------------------------------------
# 4) Génération SHA256SUMS
# ------------------------------------------------------------------------------
sha256sum "$(basename "${DEB_PATH}")" "$(basename "${RPM_PATH}")" > "${SHA_FILE}"
echo "✓ SHA256 généré : ${SHA_FILE}"

# ------------------------------------------------------------------------------
# 5) Publication GitHub Release
# ------------------------------------------------------------------------------
gh release create "${TAG}" \
  "${DEB_PATH}" \
  "${RPM_PATH}" \
  "${SHA_FILE}" \
  --title "Version ${VERSION}" \
  --notes "${RELEASE_NOTES}" \
  --latest

echo
echo "✅ Release ${TAG} publiée avec succès"
