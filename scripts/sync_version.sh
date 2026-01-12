#!/bin/bash
set -e

# -----------------------------------------------------------------------------
# sync_version.sh - Synchronisation de la version dans tous les fichiers
#
# Source de vérité : VERSION
# Propage la version vers :
#   - src/monitoring_client/__version__.py
#   - config/config.yaml.example
#   - packaging/common/config.defaults.yaml
#   - README.md (mentions vX.Y.Z)
#
# Usage :
#   ./scripts/sync_version.sh 1.0.53
# -----------------------------------------------------------------------------

VERSION_FILE="VERSION"
NEW_VERSION="${1:-}"

# Vérifier si la version a été passée en paramètre
if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Exemple: $0 1.0.1"
    exit 1
fi

echo "🔄 Synchronisation de la version vers ${NEW_VERSION}..."

# -----------------------------------------------------------------------------
# 1. Mettre à jour le fichier VERSION (source de vérité)
# -----------------------------------------------------------------------------
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "✓ VERSION"

# -----------------------------------------------------------------------------
# 2. Mettre à jour src/monitoring_client/__version__.py
# -----------------------------------------------------------------------------
if [ ! -f "src/monitoring_client/__version__.py" ]; then
    echo "❌ Erreur : src/monitoring_client/__version__.py introuvable"
    echo "   Vérifiez la structure du projet"
    exit 1
fi

cat > src/monitoring_client/__version__.py <<EOF
"""Version information for monitoring-client."""

__version__ = "${NEW_VERSION}"
__version_info__ = ($(echo $NEW_VERSION | tr '.' ','))  # Version sous forme de tuple (major, minor, patch)
__author__ = "Frederic GIL GARCIA"
__license__ = "MIT"
__email__ = "frederic.gilgarcia@gmail.com"
EOF
echo "✓ src/monitoring_client/__version__.py"

# -----------------------------------------------------------------------------
# 3. Mettre à jour config/config.yaml.example
# -----------------------------------------------------------------------------
if [ -f "config/config.yaml.example" ]; then
    sed -i "s/version: \".*\"/version: \"${NEW_VERSION}\"/" config/config.yaml.example
    echo "✓ config/config.yaml.example"
else
    echo "⚠️  config/config.yaml.example introuvable (ignoré)"
fi

# -----------------------------------------------------------------------------
# 4. Mettre à jour packaging/common/config.defaults.yaml
# -----------------------------------------------------------------------------
if [ -f "packaging/common/config.defaults.yaml" ]; then
    sed -i "s/version: \".*\"/version: \"${NEW_VERSION}\"/" packaging/common/config.defaults.yaml
    echo "✓ packaging/common/config.defaults.yaml"
else
    echo "⚠️  packaging/common/config.defaults.yaml introuvable (ignoré)"
fi

# -----------------------------------------------------------------------------
# 5. Mettre à jour README.md (mentions vX.Y.Z)
# -----------------------------------------------------------------------------
if [ -f README.md ]; then
    # Remplacer les occurrences de la version dans le format vX.Y.Z par la nouvelle version
    sed -i "s/v[0-9]\+\.[0-9]\+\.[0-9]\+/v${NEW_VERSION}/g" README.md
    echo "✓ README.md"
else
    echo "⚠️  README.md introuvable (ignoré)"
fi

# -----------------------------------------------------------------------------
# Vérification de cohérence
# -----------------------------------------------------------------------------
echo ""
echo "🔍 Vérification de la cohérence..."

ERRORS=0

# Vérifier VERSION
VERSION_CONTENT=$(cat VERSION)
if [ "$VERSION_CONTENT" != "$NEW_VERSION" ]; then
    echo "❌ VERSION : attendu=$NEW_VERSION obtenu=$VERSION_CONTENT"
    ERRORS=$((ERRORS + 1))
else
    echo "✓ VERSION : $VERSION_CONTENT"
fi

# Vérifier __version__.py
if [ -f "src/monitoring_client/__version__.py" ]; then
    PY_VERSION=$(grep '__version__ = ' src/monitoring_client/__version__.py | cut -d'"' -f2)
    if [ "$PY_VERSION" != "$NEW_VERSION" ]; then
        echo "❌ __version__.py : attendu=$NEW_VERSION obtenu=$PY_VERSION"
        ERRORS=$((ERRORS + 1))
    else
        echo "✓ __version__.py : $PY_VERSION"
    fi
fi

# Vérifier config.yaml.example
if [ -f "config/config.yaml.example" ]; then
    YAML_VERSION=$(grep 'version:' config/config.yaml.example | head -1 | cut -d'"' -f2)
    if [ "$YAML_VERSION" != "$NEW_VERSION" ]; then
        echo "❌ config.yaml.example : attendu=$NEW_VERSION obtenu=$YAML_VERSION"
        ERRORS=$((ERRORS + 1))
    else
        echo "✓ config.yaml.example : $YAML_VERSION"
    fi
fi

# Vérifier config.defaults.yaml
if [ -f "packaging/common/config.defaults.yaml" ]; then
    DEFAULTS_VERSION=$(grep 'version:' packaging/common/config.defaults.yaml | head -1 | cut -d'"' -f2)
    if [ "$DEFAULTS_VERSION" != "$NEW_VERSION" ]; then
        echo "❌ config.defaults.yaml : attendu=$NEW_VERSION obtenu=$DEFAULTS_VERSION"
        ERRORS=$((ERRORS + 1))
    else
        echo "✓ config.defaults.yaml : $DEFAULTS_VERSION"
    fi
fi

echo ""

if [ $ERRORS -eq 0 ]; then
    echo "✅ Version synchronisée avec succès vers ${NEW_VERSION}"
    echo ""
    echo "Prochaines étapes :"
    echo "  1. git add ."
    echo "  2. git commit -m 'chore: bump version to ${NEW_VERSION}'"
    echo "  3. git tag v${NEW_VERSION}"
    echo "  4. ./scripts/release.sh ${NEW_VERSION} \"Release notes\""
    exit 0
else
    echo "❌ Échec : $ERRORS erreur(s) de synchronisation détectée(s)"
    echo ""
    echo "Vérifiez manuellement les fichiers ci-dessus."
    exit 1
fi