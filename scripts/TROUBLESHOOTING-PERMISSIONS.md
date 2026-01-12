# 🔧 Résolution des problèmes de permissions (PermissionError)

## 📋 Table des matières

- [Symptômes](#symptômes)
- [Cause racine](#cause-racine)
- [Analyse technique](#analyse-technique)
- [Solution immédiate](#solution-immédiate)
- [Corrections appliquées](#corrections-appliquées)
- [Prévention](#prévention)
- [Tests de validation](#tests-de-validation)

---

## 🔴 Symptômes

### Erreur PyInstaller
```
WARNING: Execution of 'copyfile' failed on attempt #1 / 20: PermissionError(13, 'Permission denied')
WARNING: Execution of 'copyfile' failed on attempt #2 / 20: PermissionError(13, 'Permission denied')
...
RuntimeError: Execution of 'copyfile' failed - no more attempts left!
```

**Impact :**
- Build PyInstaller échoue après 20 tentatives (~15 secondes perdues)
- Message d'erreur cryptique (stacktrace Python)
- Impossible de construire le binaire sans intervention manuelle

---

## 🎯 Cause racine

### Problème identifié
Le répertoire `dist/` (et/ou son contenu) appartient à **root:root** au lieu de l'utilisateur courant.

### Origine
1. **Build Docker lancé en root** (sans `-u $(id -u):$(id -g)`)
2. **Volume monté** (`-v $PWD:/build`) → écriture dans le repo hôte
3. **Fichiers créés en root** → persistent après la fin du conteneur
4. **Builds suivants échouent** → l'utilisateur normal ne peut plus écrire

### Vérification du problème
```bash
# Vérifier le propriétaire du répertoire
ls -ld dist/
# ❌ drwxr-xr-x 2 root root 4096 ...

# Vérifier les fichiers à l'intérieur
ls -la dist/
# ❌ -rwxr-xr-x 1 root root ... monitoring-client
```

---

## 🔍 Analyse technique

### Pourquoi PyInstaller échoue ?

PyInstaller doit écrire dans `dist/` pour :
1. Copier le bootloader
2. Créer le binaire final
3. Attacher l'archive PKG

**Sans permissions d'écriture** :
- `shutil.copyfile()` échoue avec `PermissionError`
- PyInstaller retry 20 fois (backoff exponentiel)
- Échec définitif après ~15 secondes

### Pourquoi `--workpath /tmp` ne suffit pas ?

Le `--workpath` contrôle **où PyInstaller travaille** (fichiers temporaires), mais le binaire final est **toujours** écrit dans `--distpath` (par défaut `./dist`).

```bash
pyinstaller \
  --workpath /tmp/...  # ✅ Fichiers temporaires OK
  --distpath ./dist    # ❌ Destination finale = problème
```

---

## ⚡ Solution immédiate

### Commande de réparation
```bash
# Récupérer la propriété du répertoire dist/
sudo chown -R $(whoami):$(whoami) dist/

# Vérifier que c'est réparé
ls -ld dist/
# ✅ drwxr-xr-x 2 axivit axivit 4096 ...

# Relancer le build
./scripts/build.sh
```

### Si le problème persiste sur d'autres répertoires
```bash
# Réparer tous les répertoires critiques
sudo chown -R $(whoami):$(whoami) dist/ build/ rpmbuild/ .build-pyinstaller/

# Ou utiliser le script de réparation automatique
./scripts/check-perms.sh --fix
```

---

## ✅ Corrections appliquées

### 1️⃣ Détection proactive dans `build.sh`

**Avant :**
```bash
# Suppression silencieuse (échec si root-owned)
rm -f "${DIST_DIR}/${BINARY_NAME}" 2>/dev/null || true
```

**Après :**
```bash
# Vérification du répertoire
if [[ -d "${DIST_DIR}" ]] && [[ ! -w "${DIST_DIR}" ]]; then
  echo "[build] ⚠️  ERREUR CRITIQUE : Le répertoire ${DIST_DIR}/ n'est PAS writable"
  echo "[build]    Propriétaire : $(stat -c '%U:%G' "${DIST_DIR}")"
  echo "[build]    Permissions  : $(stat -c '%A' "${DIST_DIR}")"
  echo "[build]"
  echo "[build] 🔧 Solution :"
  echo "[build]    sudo chown -R \$(whoami):\$(whoami) ${DIST_DIR}/"
  exit 1
fi

# Vérification du binaire
if [[ -f "${DIST_DIR}/${BINARY_NAME}" ]] && [[ ! -w "${DIST_DIR}/${BINARY_NAME}" ]]; then
  echo "[build] ⚠️  ERREUR CRITIQUE : ${DIST_DIR}/${BINARY_NAME} n'est PAS writable"
  # ... message d'erreur détaillé ...
  exit 1
fi
```

**Bénéfices :**
- ✅ **Fail-fast** : erreur détectée immédiatement (pas 20 retries)
- ✅ **Message clair** : commande de réparation fournie
- ✅ **Diagnostic** : propriétaire et permissions affichés

### 2️⃣ Isolation Docker dans `rpm_build.sh`

**Principe :**
En mode Docker, le binaire PyInstaller est construit dans `/tmp/dist` (à l'intérieur du conteneur) au lieu de `./dist` (volume monté).

```bash
# Détection du mode Docker
IS_DOCKER="${IS_DOCKER:-false}"
if [[ "${IS_DOCKER}" == "true" ]]; then
  TEMP_DIST_DIR="/tmp/dist"  # ✅ Isolé, ne touche pas le repo
else
  TEMP_DIST_DIR="${DIST_DIR}" # ✅ Comportement normal hôte
fi

# Build avec DISTPATH custom
DISTPATH="${TEMP_DIST_DIR}" "${PROJECT_ROOT}/scripts/build.sh"

# Le binaire est archivé pour rpmbuild
tar czf "${RPMROOT}/SOURCES/monitoring-client-${VERSION}.tar.gz" \
  -C "${TEMP_DIST_DIR}" "${BINARY_NAME}"

# Nettoyage après build (Docker uniquement)
if [[ "${IS_DOCKER}" == "true" ]]; then
  rm -rf "${TEMP_DIST_DIR}"
fi
```

**Bénéfices :**
- ✅ Le repo hôte `dist/` n'est **jamais** touché par Docker
- ✅ Zéro risque de fichiers root-owned dans le repo
- ✅ Le RPM final contient quand même le bon binaire (via l'archive)

### 3️⃣ Activation dans `docker-build-rpm.sh`

```bash
docker run --rm \
  -u "${HOST_UID}:${HOST_GID}" \
  -e USER="${HOST_USER}" \
  -e HOME="/tmp" \
  -e XDG_CACHE_HOME="/tmp/.cache" \
  -e IS_DOCKER="true" \              # ← Active le mode isolé
  -v "${PROJECT_ROOT}:/build" \
  -w /build \
  "${DOCKER_IMAGE}" \
  bash -lc "./scripts/rpm_build.sh"
```

### 4️⃣ Script de diagnostic `check-perms.sh`

```bash
#!/usr/bin/env bash
# Vérification automatique des permissions
./scripts/check-perms.sh          # Diagnostic
./scripts/check-perms.sh --fix    # Réparation automatique
```

**Fonctionnalités :**
- Scanne `dist/`, `build/`, `rpmbuild/`, `.build-pyinstaller/`
- Détecte les fichiers non-writable
- Propose une réparation automatique avec `--fix`

---

## 🛡️ Prévention

### ✅ Bonnes pratiques

#### 1. Toujours utiliser les scripts fournis

```bash
# ✅ BON : Build Docker avec UID/GID correct
./scripts/docker-build-rpm.sh

# ❌ MAUVAIS : docker run direct sans -u
docker run --rm -v "$PWD:/build" monitoring-build ./scripts/build.sh
```

#### 2. Workflow recommandé

```bash
# Sur l'hôte (dev/test)
./scripts/build.sh           # Binaire pour tests locaux
./scripts/deb_build.sh       # Package Debian

# Via Docker (CI/production)
./scripts/docker-build-rpm.sh  # Package RPM (CentOS 7)

# Release complète
./scripts/release.sh 1.0.55 "Fix: PermissionError resolved"
```

#### 3. Vérification pre-build (CI)

```bash
# Dans votre pipeline CI, ajoutez :
./scripts/check-perms.sh || {
  echo "❌ Problèmes de permissions détectés"
  exit 1
}
```

### ⚠️ À éviter

```bash
# ❌ Ne JAMAIS lancer Docker sans -u
docker run --rm -v "$PWD:/build" image ./build.sh

# ❌ Ne JAMAIS utiliser sudo dans les scripts de build
sudo ./scripts/build.sh

# ❌ Ne JAMAIS fixer les permissions avec chmod 777
chmod -R 777 dist/  # Dangereux et inefficace
```

---

## 🧪 Tests de validation

### Test 1 : Build normal (doit fonctionner)
```bash
./scripts/build.sh
# ✅ [build] ✅ Binaire généré : dist/monitoring-client
```

### Test 2 : Détection du problème (doit échouer proprement)
```bash
# Simuler le problème
sudo chown root:root dist/

# Tenter un build
./scripts/build.sh
# ✅ [build] ⚠️ ERREUR CRITIQUE : Le répertoire dist/ n'est PAS writable
# ✅ [build] 🔧 Solution : sudo chown -R $(whoami):$(whoami) dist/
```

### Test 3 : Réparation automatique
```bash
# Créer le problème
sudo chown root:root dist/

# Réparer
./scripts/check-perms.sh --fix
# ✅ 🔧 Réparation...
# ✅ ✅ Réparé

# Vérifier
./scripts/check-perms.sh
# ✅ ✅ OK
```

### Test 4 : Build Docker (doit rester propre)
```bash
# Build RPM via Docker
./scripts/docker-build-rpm.sh

# Vérifier que dist/ n'a pas été touché
ls -la dist/
# ✅ Vide ou contient seulement un ancien binaire axivit:axivit

# Vérifier les permissions
./scripts/check-perms.sh
# ✅ ✅ OK
```

### Test 5 : Release complète
```bash
# Nettoyer
rm -rf dist/* rpmbuild/ release/*.deb

# Release
./scripts/release.sh 1.0.55 "Test: Permission fixes"
# ✅ Build binaire OK
# ✅ Build DEB OK
# ✅ Build RPM OK
# ✅ Publication GitHub OK
```

---

## 📊 Comparaison avant/après

| Aspect | Avant | Après |
|--------|-------|-------|
| **Erreur** | 20 retries + stacktrace Python | Message clair immédiat |
| **Temps perdu** | ~15 secondes | Fail-fast instantané |
| **Solution** | Deviner `sudo chown` | Commande exacte fournie |
| **Diagnostic** | Chercher dans les logs | Visible dès le début |
| **Prévention** | Aucune | Build Docker isolé |
| **Autonomie** | Nécessite expertise | Script de réparation auto |

---

## 🎯 Résumé

### Problème résolu ✅
- **PermissionError** détecté proactivement
- **Message clair** avec solution prête à l'emploi
- **Build Docker isolé** (plus jamais de fichiers root dans le repo)

### Outils disponibles
```bash
./scripts/build.sh              # Détection intégrée
./scripts/check-perms.sh        # Diagnostic
./scripts/check-perms.sh --fix  # Réparation automatique
./scripts/docker-build-rpm.sh   # Build Docker safe
```

### En cas de problème
```bash
# 1. Diagnostic
./scripts/check-perms.sh

# 2. Réparation
./scripts/check-perms.sh --fix

# 3. Build
./scripts/build.sh
```

---

## 📚 Références

- Issue originale : PermissionError lors du build PyInstaller
- Scripts modifiés :
  - `scripts/build.sh` (détection proactive)
  - `scripts/rpm_build.sh` (isolation Docker)
  - `scripts/docker-build-rpm.sh` (activation IS_DOCKER)
  - `scripts/check-perms.sh` (diagnostic + réparation)
- Date de résolution : 12 janvier 2025

---

## 💡 Pour aller plus loin

### Architecture recommandée

```
┌─────────────────────────────────────────────────────┐
│  HÔTE (développement)                                │
│  • build.sh → dist/monitoring-client                 │
│  • deb_build.sh → release/*.deb                      │
│  • Fichiers : user:user ✅                           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  DOCKER (production/CI)                              │
│  • Build PyInstaller dans /tmp/dist (isolé)          │
│  • Archive → rpmbuild/SOURCES/                       │
│  • RPM final → rpmbuild/RPMS/x86_64/                 │
│  • dist/ du repo : jamais touché ✅                  │
└─────────────────────────────────────────────────────┘
```

### Support

En cas de problème persistant :
1. Vérifier les logs : `cat build-rpm.log`
2. Tester manuellement : `./scripts/check-perms.sh`
3. Ouvrir une issue avec les logs complets

---

**Date de création** : 12 janvier 2025  
**Version** : 1.0  
**Auteur** : Équipe monitoring-client