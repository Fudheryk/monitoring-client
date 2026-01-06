#!/bin/bash

echo "🔍 Vérification de cohérence des versions..."
echo ""

# Extraire les versions depuis les fichiers
VERSION_FILE=$(cat VERSION 2>/dev/null || echo "N/A")
VERSION_PY=$(grep -E '^__version__' src/monitoring_client/__version__.py 2>/dev/null | cut -d'"' -f2 || echo "N/A")
VERSION_CONFIG=$(grep -E 'version:' config/config.yaml.example | head -1 | awk '{print $2}' | tr -d '"' || echo "N/A")

# On ne vérifie pas src/main.py ici, car il importe déjà la version
echo "VERSION file        : ${VERSION_FILE}"
echo "src/monitoring_client/__version__.py  : ${VERSION_PY}"
echo "config.yaml.example : ${VERSION_CONFIG}"
echo ""

# Vérifier cohérence
if [ "$VERSION_FILE" = "$VERSION_PY" ] && \
   [ "$VERSION_PY" = "$VERSION_CONFIG" ]; then
    echo "✅ Toutes les versions sont cohérentes !"
    exit 0
else
    echo "❌ Incohérence détectée !"
    echo ""
    echo "Exécutez : ./scripts/sync_version.sh <version>"
    exit 1
fi
