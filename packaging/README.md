# Structure de packaging

Cette arborescence contient tous les fichiers de packaging partagés entre DEB et RPM.

## Organisation

```
packaging/
├── common/
│   ├── functions.sh              # Fonctions partagées (get_version, logging, etc.)
│   └── config.defaults.yaml      # Configuration par défaut
├── systemd/
│   ├── monitoring-client.service.legacy   # Pour systemd < 231 (CentOS 7)
│   ├── monitoring-client.service.modern   # Pour systemd >= 231 (Debian/Ubuntu)
│   └── monitoring-client.timer            # Timer commun (30s)
└── templates/
    ├── deb/
    │   ├── conffiles             # Fichiers protégés lors upgrade
    │   ├── postinst.sh           # Post-installation
    │   ├── prerm.sh              # Pré-suppression
    │   └── postrm.sh             # Post-suppression
    └── rpm/
        └── spec.template         # Template du fichier .spec
```

## Principes de conception

### 1. Factorisation maximale

- **Fonctions communes** (`functions.sh`) : version, logging, systemd detection
- **Configuration** : un seul fichier `config.defaults.yaml` source de vérité
- **Systemd** : 2 variantes (legacy/modern) + 1 timer, sélection au runtime

### 2. Compatibilité multi-OS

| OS              | systemd | Service utilisé |
|-----------------|---------|-----------------|
| CentOS 7        | 219     | **legacy** (ReadWriteDirectories) |
| Debian 10+      | 241+    | **modern** (ReadWritePaths) |
| Ubuntu 20.04+   | 245+    | **modern** (ReadWritePaths) |
| RHEL 8+         | 239+    | **modern** (ReadWritePaths) |

### 3. Préservation des données utilisateur

**Lors d'un upgrade** :
- ✅ Config préservée (`conffiles` / `%config(noreplace)`)
- ✅ Data préservée (`/opt/monitoring-client/data/`)
- ✅ Vendors préservés (`/opt/monitoring-client/vendors/`)
- ✅ Logs préservés (`/var/log/monitoring-client/`)

**Lors d'une suppression** :
- DEB `remove` : cache supprimé, reste préservé
- DEB `purge` : tout supprimé
- RPM `erase` : cache supprimé, reste préservé

## Builds

### DEB (Debian/Ubuntu)

```bash
./scripts/deb_build.sh
```

**Sortie** : `release/monitoring-client_<version>_amd64.deb`

**Vérification** :
```bash
dpkg-deb --contents release/monitoring-client_*.deb
dpkg-deb --info release/monitoring-client_*.deb
```

### RPM (CentOS/RHEL)

```bash
./scripts/rpm_build.sh
```

**Sortie** : `rpmbuild/RPMS/x86_64/monitoring-client-<version>-1.x86_64.rpm`

**Vérification** :
```bash
rpm -qlp rpmbuild/RPMS/x86_64/monitoring-client-*.rpm
rpm -qip rpmbuild/RPMS/x86_64/monitoring-client-*.rpm
```

## Sélection automatique legacy/modern

Le script `postinst` (DEB) et `%post` (RPM) détectent automatiquement la version de systemd :

```bash
SYSTEMD_VERSION=$(systemctl --version | head -n1 | awk '{print $2}')

if [[ "${SYSTEMD_VERSION}" -lt 231 ]]; then
  # Copier monitoring-client.service.legacy
else
  # Copier monitoring-client.service.modern
fi
```

**Résultat** :
- CentOS 7 → `/usr/lib/systemd/system/monitoring-client.service` = **legacy**
- Debian 11+ → `/lib/systemd/system/monitoring-client.service` = **modern**

## Structure d'installation

### Arborescence cible (identique DEB et RPM)

```
/usr/local/bin/
└── monitoring-client                    # Binaire principal

/opt/monitoring-client/
├── config/
│   ├── config.yaml                      # Config active (préservée)
│   ├── config.yaml.example              # Référence
│   └── config.schema.json               # Schéma de validation
├── data/
│   ├── api_key                          # Clé API (créée par admin)
│   └── fingerprint                      # Empreinte machine
└── vendors/                             # Scripts custom utilisateur

/var/log/monitoring-client/              # Logs
/var/cache/monitoring-client/            # Cache (supprimé lors remove)

# Systemd (legacy/modern sélectionné au runtime)
/lib/systemd/system/                     # DEB
/usr/lib/systemd/system/                 # RPM
├── monitoring-client.service            # Lien vers legacy OU modern
└── monitoring-client.timer

# Fichiers de variantes (pour sélection)
/usr/share/monitoring-client/            # DEB
├── monitoring-client.service.legacy
└── monitoring-client.service.modern
```

## Tests

### Test du build

```bash
# DEB
./scripts/deb_build.sh
dpkg-deb --contents release/monitoring-client_*.deb | grep -E "systemd|config"

# RPM
./scripts/rpm_build.sh
rpm -qlp rpmbuild/RPMS/x86_64/monitoring-client-*.rpm | grep -E "systemd|config"
```

### Test d'installation

**Sur VM Debian/Ubuntu** :
```bash
sudo dpkg -i monitoring-client_*.deb
sudo systemctl status monitoring-client.timer
cat /lib/systemd/system/monitoring-client.service | grep ReadWrite
# Doit contenir "ReadWritePaths" (modern)
```

**Sur VM CentOS 7** :
```bash
sudo rpm -ivh monitoring-client-*.rpm
sudo systemctl status monitoring-client.timer
cat /usr/lib/systemd/system/monitoring-client.service | grep ReadWrite
# Doit contenir "ReadWriteDirectories" (legacy)
```

### Test d'upgrade

```bash
# Modifier config.yaml
sudo nano /opt/monitoring-client/config/config.yaml

# Upgrader
sudo dpkg -i monitoring-client_NEW.deb  # ou rpm -Uvh

# Vérifier que config.yaml n'a pas été écrasé
cat /opt/monitoring-client/config/config.yaml
```

### Test de suppression

**DEB** :
```bash
sudo dpkg -r monitoring-client          # remove
ls /opt/monitoring-client/              # doit exister

sudo dpkg --purge monitoring-client     # purge
ls /opt/monitoring-client/              # ne doit plus exister
```

**RPM** :
```bash
sudo rpm -e monitoring-client           # erase
ls /opt/monitoring-client/              # doit exister (data préservée)
```

## Maintenance

### Ajouter une nouvelle directive systemd

1. Modifier `packaging/systemd/monitoring-client.service.legacy`
2. Modifier `packaging/systemd/monitoring-client.service.modern`
3. Tester sur CentOS 7 (legacy) et Debian 11+ (modern)

### Ajouter une nouvelle fonction commune

1. Ajouter dans `packaging/common/functions.sh`
2. Utiliser dans `scripts/deb_build.sh` et `scripts/rpm_build.sh`

### Modifier la configuration par défaut

1. Éditer `packaging/common/config.defaults.yaml`
2. Rebuild les packages

## Dépannage

### Le service ne démarre pas

```bash
# Vérifier le variant installé
cat /lib/systemd/system/monitoring-client.service | head -20

# Vérifier les logs
sudo journalctl -u monitoring-client -n 50

# Vérifier la config
/usr/local/bin/monitoring-client --config /opt/monitoring-client/config/config.yaml --dry-run
```

### Le timer n'est pas actif après installation

Vérifier si l'API key existe :
```bash
ls -lh /opt/monitoring-client/data/api_key
```

Si absente, le timer n'est pas démarré automatiquement (comportement attendu).

### Différence legacy/modern non appliquée

Vérifier la version systemd détectée :
```bash
systemctl --version | head -n1
```

Vérifier les logs d'installation :
```bash
cat /var/log/monitoring-client-install.log | grep "systemd version"
```

## Références

- [systemd directives](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [Debian packaging](https://www.debian.org/doc/manuals/maint-guide/)
- [RPM packaging](https://rpm-packaging-guide.github.io/)