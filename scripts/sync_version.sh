#!/bin/bash
set -e

# Fichier source de vérité pour la version
VERSION_FILE="VERSION"
NEW_VERSION="${1:-}"

# Vérifier si la version a été passée en paramètre
if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Exemple: $0 1.0.1"
    exit 1
fi

echo "🔄 Synchronisation de la version vers ${NEW_VERSION}..."

# 1. Mettre à jour le fichier VERSION
# Ce fichier contient la version principale du projet.
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "✓ VERSION"

# 2. Mettre à jour le fichier src/monitoring_client/__version__.py
# C'est la source unique de vérité pour la version dans le code.

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

# 3. Mettre à jour le fichier config/config.yaml.example
# Le fichier de configuration peut contenir la version pour le déploiement ou la documentation.
sed -i "s/version: \".*\"/version: \"${NEW_VERSION}\"/" config/config.yaml.example
echo "✓ config/config.yaml.example"

# 4. Mettre à jour README.md si nécessaire
# Si le fichier README.md mentionne la version, nous devons le mettre à jour.
if [ -f README.md ]; then
    # Remplacer les occurrences de la version dans le format vX.Y.Z par la nouvelle version
    sed -i "s/v[0-9]\+\.[0-9]\+\.[0-9]\+/v${NEW_VERSION}/g" README.md
    echo "✓ README.md"
fi


echo ""
echo "✅ Version synchronisée vers ${NEW_VERSION}"
echo ""
echo "Prochaines étapes :"
echo "  1. git add ."
echo "  2. git commit -m 'chore: bump version to ${NEW_VERSION}'"
echo "  3. git tag v${NEW_VERSION}"
echo "  4. ./scripts/deb_build.sh"
