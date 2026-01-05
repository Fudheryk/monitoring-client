#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# rpm_build.sh - Build d'un package RPM (.rpm) professionnel
#
# Produit :
#   rpmbuild/RPMS/x86_64/monitoring-client-<version>-1.x86_64.rpm
#
# Améliorations par rapport à la version précédente :
#   - Structure /opt/monitoring-client/ complète (config/, data/, vendors/)
#   - Préservation des données lors des mises à jour
#   - Installation de config.schema.json
#   - Gestion %config(noreplace) pour préserver les fichiers utilisateur
#   - Scripts %post/%preun/%postun améliorés
# -----------------------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
RELEASE_DIR="${PROJECT_ROOT}/release"
LOG_FILE="${PROJECT_ROOT}/build-rpm.log"
BINARY_NAME="monitoring-client"

# Initialisation du logging
exec > >(tee -a "${LOG_FILE}") 2>&1
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Démarrage du build RPM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# -----------------------------------------------------------------------------
# Fonction : Vérification des prérequis
# -----------------------------------------------------------------------------
function check_prerequisites() {
  echo "[check] Vérification des prérequis..."

  # Vérifier systemctl
  if ! command -v systemctl &> /dev/null; then
    echo "❌ systemd n'est pas installé. L'installation ne peut pas continuer."
    exit 1
  fi

  # Vérifier rpmbuild
  if ! command -v rpmbuild &> /dev/null; then
    echo "❌ rpmbuild n'est pas installé."
    echo "   Installez-le avec : sudo yum install rpm-build"
    exit 1
  fi

  echo "[check] ✓ rpmbuild détecté"

  # Vérifier la version de systemd (minimum 200)
  SYSTEMD_VERSION=$(systemctl --version | head -n 1 | awk '{print $2}')
  if [[ "${SYSTEMD_VERSION}" -lt 200 ]]; then
    echo "❌ Votre version de systemd (${SYSTEMD_VERSION}) est obsolète."
    echo "   Version minimale requise : 200"
    exit 1
  fi

  echo "[check] ✓ systemd version ${SYSTEMD_VERSION} détecté"

  # Vérifier Python 3 (ou le Python compilé)
  if ! command -v python3 &> /dev/null && ! command -v /opt/python311/bin/python3.11 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé."
    exit 1
  fi

  echo "[check] ✓ Python 3 détecté"

  # Vérifier PyInstaller
  PYTHON_CMD="${PYTHON_CMD:-python3}"
  if [[ -x /opt/python311/bin/python3.11 ]]; then
    PYTHON_CMD="/opt/python311/bin/python3.11"
  fi

  if ! ${PYTHON_CMD} -m pip show pyinstaller &> /dev/null; then
    echo "⚠️  PyInstaller n'est pas installé. Tentative d'installation..."
    ${PYTHON_CMD} -m pip install pyinstaller || {
      echo "❌ Impossible d'installer PyInstaller."
      exit 1
    }
  fi

  echo "[check] ✓ PyInstaller détecté"

  # Vérifier tar
  if ! command -v tar &> /dev/null; then
    echo "❌ tar n'est pas installé."
    exit 1
  fi

  echo "[check] ✓ tar détecté"
  echo "[check] ✓ Tous les prérequis sont satisfaits"
}

# -----------------------------------------------------------------------------
# Exécution des vérifications
# -----------------------------------------------------------------------------
check_prerequisites

# -----------------------------------------------------------------------------
# Configuration du package
# -----------------------------------------------------------------------------

# Récupère la version depuis src/__version__.py
VERSION="$(
  grep -E '^__version__' "${PROJECT_ROOT}/src/__version__.py" \
    | head -1 \
    | cut -d'"' -f2
)"

VERSION="${VERSION:-1.0.0}"
RPMROOT="${PROJECT_ROOT}/rpmbuild"

echo "[rpm] Project root : ${PROJECT_ROOT}"
echo "[rpm] Version      : ${VERSION}"
echo "[rpm] RPMROOT      : ${RPMROOT}"
echo "[rpm] Log          : ${LOG_FILE}"

# -----------------------------------------------------------------------------
# Préparation de l'arborescence rpmbuild
# -----------------------------------------------------------------------------
echo "[rpm] Nettoyage de l'ancienne structure..."
rm -rf "${RPMROOT}"
mkdir -p "${RPMROOT}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
mkdir -p "${RELEASE_DIR}"

echo "[rpm] ✓ Structure rpmbuild créée"

# -----------------------------------------------------------------------------
# Build du binaire PyInstaller
# -----------------------------------------------------------------------------
echo "[rpm] Build du binaire PyInstaller..."
if [[ ! -x "${PROJECT_ROOT}/scripts/build.sh" ]]; then
  echo "❌ Le script build.sh n'existe pas ou n'est pas exécutable."
  exit 1
fi

"${PROJECT_ROOT}/scripts/build.sh" || {
  echo "❌ Échec du build PyInstaller"
  exit 1
}

# Vérification du binaire généré
if [[ ! -f "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "❌ Le binaire ${BINARY_NAME} n'a pas été généré dans ${DIST_DIR}/"
  exit 1
fi

echo "[rpm] ✓ Binaire ${BINARY_NAME} généré"

# -----------------------------------------------------------------------------
# Création d'une archive Source0 minimale pour rpmbuild
# -----------------------------------------------------------------------------
echo "[rpm] Création de l'archive Source0..."
tar czf "${RPMROOT}/SOURCES/monitoring-client-${VERSION}.tar.gz" \
  -C "${DIST_DIR}" "${BINARY_NAME}" || {
  echo "❌ Échec de la création de l'archive Source0"
  exit 1
}

echo "[rpm] ✓ Archive Source0 créée"

# -----------------------------------------------------------------------------
# Génération des fichiers systemd dans release/systemd
# -----------------------------------------------------------------------------
echo "[rpm] Création des fichiers systemd..."
SYSTEMD_DIR="${RELEASE_DIR}/systemd"
mkdir -p "${SYSTEMD_DIR}"

# Service systemd (avec sécurité renforcée)
cat > "${SYSTEMD_DIR}/monitoring-client.service" <<'EOF'
[Unit]
Description=Monitoring Client Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
ExecStart=/usr/local/bin/monitoring-client --config /opt/monitoring-client/config/config.yaml
WorkingDirectory=/opt/monitoring-client
StandardOutput=journal
StandardError=journal
SyslogIdentifier=monitoring-client

# Sécurité renforcée
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/monitoring-client /opt/monitoring-client/data

[Install]
WantedBy=multi-user.target
EOF

# Timer systemd
cat > "${SYSTEMD_DIR}/monitoring-client.timer" <<'EOF'
[Unit]
Description=Run Monitoring Client Agent every 30 seconds
Requires=monitoring-client.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=30s
Unit=monitoring-client.service
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[rpm] ✓ Fichiers systemd créés"

# -----------------------------------------------------------------------------
# Préparation de la configuration
# -----------------------------------------------------------------------------
echo "[rpm] Préparation des fichiers de configuration..."

# Vérifier config.yaml.example
if [[ ! -f "${PROJECT_ROOT}/config/config.yaml.example" ]]; then
  echo "⚠️  Fichier config.yaml.example introuvable. Création d'un fichier par défaut..."
  mkdir -p "${PROJECT_ROOT}/config"
  cat > "${PROJECT_ROOT}/config/config.yaml.example" <<'YAML'
# Configuration Monitoring Client
api:
  base_url: "https://monitoring.example.com"
  metrics_endpoint: "/api/v1/metrics"
  timeout: 30

collectors:
  enabled:
    - cpu
    - memory
    - disk
    - network
YAML
fi

# Vérifier config.schema.json
if [[ ! -f "${PROJECT_ROOT}/config/config.schema.json" ]]; then
  echo "⚠️  Fichier config.schema.json introuvable. Création d'un fichier par défaut..."
  cat > "${PROJECT_ROOT}/config/config.schema.json" <<'JSON'
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["api"],
  "properties": {
    "api": {
      "type": "object",
      "required": ["base_url", "metrics_endpoint"],
      "properties": {
        "base_url": {"type": "string"},
        "metrics_endpoint": {"type": "string"},
        "timeout": {"type": "integer"}
      }
    },
    "collectors": {
      "type": "object",
      "properties": {
        "enabled": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
JSON
fi

echo "[rpm] ✓ Configuration préparée"

# -----------------------------------------------------------------------------
# Génération du fichier SPEC
# -----------------------------------------------------------------------------
echo "[rpm] Génération du fichier SPEC..."

# Générer la date en anglais pour le changelog
CHANGELOG_DATE=$(LC_TIME=C date '+%a %b %d %Y')

cat > "${RPMROOT}/SPECS/monitoring-client.spec" <<EOF
Name:           monitoring-client
Version:        ${VERSION}
Release:        1
Summary:        Agent de monitoring système léger et sécurisé
License:        Proprietary
Group:          Applications/System
Source0:        monitoring-client-${VERSION}.tar.gz
BuildArch:      x86_64
Requires:       systemd >= 200

%description
Collecte et envoie des métriques système, réseau, sécurité
et services vers un serveur central de monitoring.

Fonctionnalités principales :
 - 11 collecteurs builtin (CPU, RAM, disque, réseau, services, etc.)
 - Support des métriques custom via vendors (bash, python, etc.)
 - Timer systemd (exécution toutes les 30 secondes)
 - Validation complète du payload avant envoi
 - Binaire standalone (aucune dépendance Python runtime)
 - Sécurisation renforcée (ProtectSystem, NoNewPrivileges)

Prérequis système :
 - systemd >= 200
 - Architecture : x86_64

%prep
# Rien à préparer : le binaire est déjà construit par PyInstaller

%build
# Aucune étape de build : binaire pre-build

%install
# ============================================================================
# Installation du binaire dans /usr/local/bin
# ============================================================================
mkdir -p %{buildroot}/usr/local/bin
cp -a %{_sourcedir}/../../dist/monitoring-client %{buildroot}/usr/local/bin/monitoring-client
chmod 755 %{buildroot}/usr/local/bin/monitoring-client

# ============================================================================
# Structure /opt/monitoring-client/ (comme Debian)
# Créer TOUS les répertoires d'abord
# ============================================================================
mkdir -p %{buildroot}/opt/monitoring-client/config
mkdir -p %{buildroot}/opt/monitoring-client/data
mkdir -p %{buildroot}/opt/monitoring-client/vendors

# ============================================================================
# Installer les fichiers de configuration dans /opt/monitoring-client/config/
# ============================================================================
install -m 644 ${PROJECT_ROOT}/config/config.yaml.example %{buildroot}/opt/monitoring-client/config/config.yaml
install -m 644 ${PROJECT_ROOT}/config/config.yaml.example %{buildroot}/opt/monitoring-client/config/config.yaml.example
install -m 644 ${PROJECT_ROOT}/config/config.schema.json %{buildroot}/opt/monitoring-client/config/config.schema.json

# ============================================================================
# Répertoires de logs et cache
# ============================================================================
mkdir -p %{buildroot}/var/log/monitoring-client
mkdir -p %{buildroot}/var/cache/monitoring-client

# ============================================================================
# Unités systemd (service + timer)
# ============================================================================
mkdir -p %{buildroot}/usr/lib/systemd/system
install -m 644 ${PROJECT_ROOT}/release/systemd/monitoring-client.service %{buildroot}/usr/lib/systemd/system/monitoring-client.service
install -m 644 ${PROJECT_ROOT}/release/systemd/monitoring-client.timer %{buildroot}/usr/lib/systemd/system/monitoring-client.timer

%files
# ============================================================================
# Binaire principal
# ============================================================================
/usr/local/bin/monitoring-client

# ============================================================================
# Configuration (préservée lors des mises à jour avec noreplace)
# ============================================================================
%config(noreplace) /opt/monitoring-client/config/config.yaml

# ============================================================================
# Unités systemd
# ============================================================================
/usr/lib/systemd/system/monitoring-client.service
/usr/lib/systemd/system/monitoring-client.timer

# ============================================================================
# Structure /opt/monitoring-client/
# Les répertoires data/ et vendors/ sont marqués pour préservation
# ============================================================================
%dir /opt/monitoring-client
%dir /opt/monitoring-client/config
%dir /opt/monitoring-client/data
%dir /opt/monitoring-client/vendors

# Fichiers de configuration dans /opt/monitoring-client/config/
# (noreplace pour préserver les modifications)
%config(noreplace) /opt/monitoring-client/config/config.yaml.example
%config(noreplace) /opt/monitoring-client/config/config.schema.json

# ============================================================================
# Répertoires de logs et cache
# ============================================================================
%dir /var/log/monitoring-client
%dir /var/cache/monitoring-client

%post
# ============================================================================
# Script post-installation
# Exécuté après l'installation des fichiers
# ============================================================================

# Fonction de logging
log() {
  echo "[\$0] \$1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "=== Configuration de Monitoring Client ==="
log ""

# ============================================================================
# Créer les répertoires nécessaires (si pas déjà présents)
# ============================================================================
mkdir -p /opt/monitoring-client/config
mkdir -p /opt/monitoring-client/data
mkdir -p /opt/monitoring-client/vendors
mkdir -p /var/log/monitoring-client
mkdir -p /var/cache/monitoring-client

# ============================================================================
# Permissions strictes
# ============================================================================
chmod 755 /usr/local/bin/monitoring-client

# Vérifier existence avant chmod (éviter les erreurs)
if [[ -f /etc/monitoring-client/config/config.yaml ]]; then
  chmod 644 /etc/monitoring-client/config/config.yaml
fi

chmod 755 /opt/monitoring-client/config
chmod 755 /opt/monitoring-client/data
chmod 755 /opt/monitoring-client/vendors
chmod 755 /var/log/monitoring-client
chmod 755 /var/cache/monitoring-client

log "✓ Répertoires et permissions configurés"

# ============================================================================
# Validation de la configuration
# ============================================================================
if [[ -f /opt/monitoring-client/config/config.yaml ]]; then
  if ! grep -q 'base_url' /opt/monitoring-client/config/config.yaml; then
    log "⚠️  Le fichier de configuration ne contient pas 'base_url'."
    log "   Veuillez le configurer manuellement."
  fi
else
  log "⚠️  Fichier config.yaml manquant dans /opt/monitoring-client/config/"
fi

# ============================================================================
# Recharger systemd
# ============================================================================
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || true
  log "✓ systemd rechargé"
fi

# ============================================================================
# Gestion du timer selon le contexte (nouvelle installation vs mise à jour)
# ============================================================================

# Vérifier si l'API key existe déjà
if [[ -f /opt/monitoring-client/data/api_key && -s /opt/monitoring-client/data/api_key ]]; then
  # Sécuriser la clé API
  chmod 600 /opt/monitoring-client/data/api_key
  log "✓ Clé API détectée et sécurisée (chmod 600)"

  # Vérifier si c'est une mise à jour (le package était déjà installé)
  # \$1 = 1 signifie nouvelle installation
  # \$1 = 2 signifie mise à jour
  if [[ "\$1" -ge 2 ]]; then
    log "✓ Mise à jour détectée"

    # Redémarrer le timer si déjà actif
    if systemctl is-active --quiet monitoring-client.timer 2>/dev/null; then
      systemctl restart monitoring-client.timer || true
      log "✓ Timer redémarré avec la nouvelle version"
    else
      systemctl enable --now monitoring-client.timer >/dev/null 2>&1 || true
      log "✓ Timer activé et démarré"
    fi
  else
    # Nouvelle installation (\$1 = 1)
    log "✓ Nouvelle installation détectée"
    systemctl enable --now monitoring-client.timer >/dev/null 2>&1 || true
    log "✓ Timer activé et démarré (nouvelle installation)"
  fi
else
  log "⚠️  Aucune clé API trouvée dans /opt/monitoring-client/data/api_key"
  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "📋 Étapes suivantes (OBLIGATOIRES)"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
  log "  1️⃣  Ajouter votre clé API :"
  log "      echo 'VOTRE_CLE_API' | sudo tee /opt/monitoring-client/data/api_key"
  log "      sudo chmod 600 /opt/monitoring-client/data/api_key"
  log ""
  log "  2️⃣  Configurer le serveur backend :"
  log "      sudo vi /etc/monitoring-client/config/config.yaml"
  log "      (Modifier 'base_url' et 'metrics_endpoint')"
  log ""
  log "  3️⃣  Activer et démarrer le timer :"
  log "      sudo systemctl enable --now monitoring-client.timer"
  log ""
  log "  4️⃣  Vérifier que le timer est actif :"
  log "      sudo systemctl list-timers | grep monitoring"
  log ""
  log "  5️⃣  Voir les logs en temps réel :"
  log "      sudo journalctl -u monitoring-client -f"
  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "📖 Test rapide : monitoring-client --dry-run"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
fi

log "✓ Installation terminée avec succès"
log "📁 Log complet : /var/log/monitoring-client-install.log"

exit 0

%preun
# ============================================================================
# Script pré-désinstallation
# Exécuté AVANT la suppression des fichiers
# ============================================================================

# Fonction de logging
log() {
  echo "[\$0] \$1" | tee -a /var/log/monitoring-client-install.log
}

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Arrêt du service monitoring-client..."
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ============================================================================
# Gestion selon le contexte
# \$1 = 0 signifie suppression complète (erase)
# \$1 = 1 signifie mise à jour (upgrade) - une nouvelle version va être installée
# ============================================================================

if [[ "\$1" -eq 0 ]]; then
  log "Action détectée : suppression complète"

  # Arrêter le timer
  if systemctl is-active --quiet monitoring-client.timer 2>/dev/null; then
    systemctl stop monitoring-client.timer || true
    log "✓ Timer arrêté"
  fi

  # Désactiver le timer
  if systemctl is-enabled --quiet monitoring-client.timer 2>/dev/null; then
    systemctl disable monitoring-client.timer || true
    log "✓ Timer désactivé"
  fi

  # Arrêter le service s'il tourne
  if systemctl is-active --quiet monitoring-client.service 2>/dev/null; then
    systemctl stop monitoring-client.service || true
    log "✓ Service arrêté"
  fi
else
  log "Action détectée : mise à jour (préservation du timer)"

  # En mise à jour, on arrête juste le timer temporairement
  # Il sera redémarré par le %post de la nouvelle version
  if systemctl is-active --quiet monitoring-client.timer 2>/dev/null; then
    systemctl stop monitoring-client.timer || true
    log "✓ Timer arrêté temporairement pour mise à jour"
  fi
fi

log "✓ Pré-suppression terminée"

exit 0

%postun
# ============================================================================
# Script post-désinstallation
# Exécuté APRÈS la suppression des fichiers
# ============================================================================

# Fonction de logging
log() {
  echo "[\$0] \$1" | tee -a /var/log/monitoring-client-install.log
}

# ============================================================================
# Gestion selon le contexte
# \$1 = 0 signifie suppression complète (erase)
# \$1 = 1 signifie mise à jour (upgrade)
# ============================================================================

if [[ "\$1" -eq 0 ]]; then
  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "Nettoyage post-suppression (action: erase)"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # ============================================================================
  # Suppression complète SEULEMENT DES CACHES et LOGS
  # PRÉSERVATION de /opt/monitoring-client/data/ et /opt/monitoring-client/vendors/
  # ============================================================================

  # Supprimer UNIQUEMENT le cache (non critique)
  rm -rf /var/cache/monitoring-client
  log "✓ Cache supprimé"

  # Supprimer les logs (optionnel - peut être préservé)
  # rm -rf /var/log/monitoring-client
  # log "✓ Logs supprimés"

  # ============================================================================
  # PRÉSERVATION DES DONNÉES UTILISATEUR
  # ============================================================================
  # On NE supprime PAS :
  # - /opt/monitoring-client/data/api_key
  # - /opt/monitoring-client/data/fingerprint
  # - /opt/monitoring-client/vendors/* (scripts custom)
  # - /etc/monitoring-client/config/config.yaml (déjà géré par %config(noreplace))

  log "✓ Données préservées dans /opt/monitoring-client/data/"
  log "✓ Vendors préservés dans /opt/monitoring-client/vendors/"
  log "✓ Configuration préservée dans /etc/monitoring-client/"

  # Recharger systemd après suppression des fichiers service
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload 2>/dev/null || true
    log "✓ systemd rechargé"
  fi

  log ""
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log "✓ Monitoring Client désinstallé"
  log "ℹ️  Données préservées pour réinstallation ultérieure"
  log ""
  log "Pour supprimer TOUTES les données manuellement :"
  log "  sudo rm -rf /opt/monitoring-client"
  log "  sudo rm -rf /etc/monitoring-client"
  log "  sudo rm -rf /var/log/monitoring-client"
  log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log ""
else
  # \$1 = 1 signifie mise à jour - NE RIEN SUPPRIMER
  log "Action détectée : mise à jour - préservation de toutes les données"
fi

exit 0

%changelog
* ${CHANGELOG_DATE} Frederic GIL GARCIA <frederic.gilgarcia@gmail.com> - ${VERSION}-1
- Version ${VERSION}
- Structure /opt/monitoring-client/ complète (config/, data/, vendors/)
- Préservation des données lors des mises à jour
- Build automatique avec Python 3.11 sur CentOS 7

EOF

echo "[rpm] ✓ Fichier SPEC généré"

# -----------------------------------------------------------------------------
# Lancement de rpmbuild
# -----------------------------------------------------------------------------
echo "[rpm] Build du package RPM..."
rpmbuild --define "_topdir ${RPMROOT}" -ba "${RPMROOT}/SPECS/monitoring-client.spec" || {
  echo "❌ Échec de la création du package RPM"
  echo "   Consultez le log : ${LOG_FILE}"
  exit 1
}

# -----------------------------------------------------------------------------
# Vérification et localisation du RPM
# -----------------------------------------------------------------------------
RPM_OUTPUT="${RPMROOT}/RPMS/x86_64/monitoring-client-${VERSION}-1.x86_64.rpm"

if [[ ! -f "${RPM_OUTPUT}" ]]; then
  echo "❌ Le package RPM n'a pas été créé correctement"
  echo "   Attendu : ${RPM_OUTPUT}"
  exit 1
fi

# -----------------------------------------------------------------------------
# Affichage du résumé
# -----------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Package RPM créé avec succès !"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Fichier   : ${RPM_OUTPUT}"
echo "📏 Taille    : $(du -h "${RPM_OUTPUT}" | cut -f1)"
echo "🏗️  Version   : ${VERSION}"
echo "📝 Build log : ${LOG_FILE}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Commandes utiles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Installation :"
echo "    sudo rpm -ivh ${RPM_OUTPUT}"
echo ""
echo "  Mise à jour :"
echo "    sudo rpm -Uvh ${RPM_OUTPUT}"
echo ""
echo "  Vérification du contenu :"
echo "    rpm -qlp ${RPM_OUTPUT}"
echo ""
echo "  Vérification de la structure installée :"
echo "    tree /opt/monitoring-client/"
echo "    tree /etc/monitoring-client/"
echo ""
echo "  Test du binaire :"
echo "    /usr/local/bin/monitoring-client --version"
echo "    /usr/local/bin/monitoring-client --dry-run"
echo ""
echo "  Vérification du timer :"
echo "    sudo systemctl status monitoring-client.timer"
echo "    sudo systemctl list-timers | grep monitoring"
echo ""
echo "  Logs en temps réel :"
echo "    sudo journalctl -u monitoring-client -f"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Build terminé avec succès"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
