#!/bin/bash
# Test complet de la chaîne de build

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 TEST COMPLET - Validation version 1.0.52"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

EXPECTED_VERSION="1.0.52"
ERRORS=0

# Fonction de test
test_step() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "▶ ${name}... "
    result=$(eval "$command" 2>&1)
    
    if [[ "$result" == *"$expected"* ]]; then
        echo "✅"
        return 0
    else
        echo "❌"
        echo "   Attendu : $expected"
        echo "   Obtenu  : $result"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo "Phase 1 : Vérification des fichiers sources"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_step "Fichier VERSION" "cat VERSION" "$EXPECTED_VERSION"
test_step "Fichier __version__.py" "grep '__version__ =' src/monitoring_client/__version__.py" "$EXPECTED_VERSION"
test_step "Fichier __init__.py (pas d'importlib)" "grep -c 'importlib' src/monitoring_client/__init__.py" "0"
test_step "Fichier __init__.py (import direct)" "grep 'from monitoring_client.__version__ import' src/monitoring_client/__init__.py" "__version__"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "Phase 2 : Vérification de l'environnement"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_step "Package NON installé dans venv" "pip list | grep -c monitoring-client || echo 0" "0"
test_step "Pas de cache PyInstaller" "ls ~/.cache/pyinstaller 2>/dev/null | wc -l" "0"
test_step "Pas de __pycache__ dans src/" "find src/ -name __pycache__ | wc -l" "0"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "Phase 3 : Test d'import Python"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_step "Import depuis __version__.py" "python -c \"import sys; sys.path.insert(0, 'src'); from monitoring_client.__version__ import __version__; print(__version__)\"" "$EXPECTED_VERSION"
test_step "Import depuis __init__.py" "python -c \"import sys; sys.path.insert(0, 'src'); from monitoring_client import __version__; print(__version__)\"" "$EXPECTED_VERSION"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "Phase 4 : Build du binaire"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "▶ Nettoyage complet..."
rm -rf dist/ build/ ~/.cache/pyinstaller /tmp/monitoring-client-pyinstaller-* 2>/dev/null
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "✅"

echo "▶ Build PyInstaller..."
if ./scripts/build.sh >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ Build échoué"
    ERRORS=$((ERRORS + 1))
fi

test_step "Binaire existe" "ls dist/monitoring-client" "monitoring-client"
test_step "Binaire exécutable" "test -x dist/monitoring-client && echo OK" "OK"
test_step "Version du binaire" "dist/monitoring-client --version" "$EXPECTED_VERSION"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "Phase 5 : Build des packages"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "▶ Build DEB..."
if ./scripts/deb_build.sh >/dev/null 2>&1; then
    echo "✅"
    test_step "Package DEB existe" "ls release/monitoring-client_${EXPECTED_VERSION}_amd64.deb" "${EXPECTED_VERSION}"
    test_step "Version DEB metadata" "dpkg-deb -I release/monitoring-client_${EXPECTED_VERSION}_amd64.deb | grep Version" "${EXPECTED_VERSION}"
else
    echo "❌ Build DEB échoué"
    ERRORS=$((ERRORS + 1))
fi

echo "▶ Build RPM (Docker)..."
if ./scripts/docker-build-rpm.sh >/dev/null 2>&1; then
    echo "✅"
    test_step "Package RPM existe" "ls rpmbuild/RPMS/x86_64/monitoring-client-${EXPECTED_VERSION}-1.x86_64.rpm" "${EXPECTED_VERSION}"
    test_step "Version RPM metadata" "rpm -qip rpmbuild/RPMS/x86_64/monitoring-client-${EXPECTED_VERSION}-1.x86_64.rpm | grep Version" "${EXPECTED_VERSION}"
else
    echo "❌ Build RPM échoué"
    ERRORS=$((ERRORS + 1))
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "Phase 6 : Vérification de cohérence"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Extraire le binaire du DEB et vérifier sa version
echo -n "▶ Version binaire dans DEB... "
dpkg-deb -x "release/monitoring-client_${EXPECTED_VERSION}_amd64.deb" /tmp/test-deb-$$ 2>/dev/null
DEB_BIN_VERSION=$(/tmp/test-deb-$$/usr/local/bin/monitoring-client --version 2>/dev/null | awk '{print $2}')
rm -rf /tmp/test-deb-$$

if [[ "$DEB_BIN_VERSION" == "$EXPECTED_VERSION" ]]; then
    echo "✅"
else
    echo "❌ (attendu: $EXPECTED_VERSION, obtenu: $DEB_BIN_VERSION)"
    ERRORS=$((ERRORS + 1))
fi

# Vérifier que les permissions sont toujours OK
test_step "Permissions après build" "./scripts/check-perms.sh >/dev/null 2>&1 && echo OK" "OK"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ TOUS LES TESTS SONT PASSÉS (100%)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "🎉 Version $EXPECTED_VERSION validée sur TOUS les artefacts !"
    echo ""
    echo "Artefacts générés :"
    echo "  • Binaire : dist/monitoring-client"
    echo "  • DEB     : release/monitoring-client_${EXPECTED_VERSION}_amd64.deb"
    echo "  • RPM     : rpmbuild/RPMS/x86_64/monitoring-client-${EXPECTED_VERSION}-1.x86_64.rpm"
    echo ""
    echo "Prochaine étape :"
    echo "  ./scripts/release.sh $EXPECTED_VERSION \"Fix: Version sync + permission issues\""
    exit 0
else
    echo "❌ ÉCHEC : $ERRORS erreur(s) détectée(s)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi