#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTO_FIX="${1:-}"

echo "🔍 Vérification des permissions..."

ISSUES_FOUND=0
CRITICAL_DIRS=("dist" "build" "rpmbuild" ".build-pyinstaller")

for DIR in "${CRITICAL_DIRS[@]}"; do
  FULL_PATH="${PROJECT_ROOT}/${DIR}"
  [[ ! -d "${FULL_PATH}" ]] && continue
  
  NON_WRITABLE=$(find "${FULL_PATH}" ! -writable 2>/dev/null || true)
  
  if [[ -n "${NON_WRITABLE}" ]]; then
    echo "❌ Fichiers non-writable dans ${DIR}/"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
  fi
done

if [[ ${ISSUES_FOUND} -gt 0 ]]; then
  if [[ "${AUTO_FIX}" == "--fix" ]]; then
    echo "🔧 Réparation..."
    for DIR in "${CRITICAL_DIRS[@]}"; do
      FULL_PATH="${PROJECT_ROOT}/${DIR}"
      [[ -d "${FULL_PATH}" ]] && sudo chown -R "$(whoami):$(whoami)" "${FULL_PATH}"
    done
    echo "✅ Réparé"
    exit 0
  fi
  
  echo ""
  echo "🔧 Solution : ./scripts/check-perms.sh --fix"
  exit 1
fi

echo "✅ OK"
