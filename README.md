[![Release](https://img.shields.io/github/v/release/Fudheryk/monitoring-client)](https://github.com/Fudheryk/monitoring-client/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/Fudheryk/monitoring-client/actions/workflows/python-tests.yml/badge.svg)]


# 📘 **Monitoring Client — Documentation Officielle**

Agent léger de monitoring système permettant de :

* Collecter des métriques **builtin** (système, réseau, sécurité, services)
* Exécuter des métriques **custom** via fichiers *vendor*
* Construire un payload validé conforme au backend
* L'envoyer via HTTPS avec gestion automatique des erreurs
* Fonctionner en **binaire standalone** (PyInstaller)
* S'installer via **DEB**, **RPM**, ou **TAR.GZ**

---

## 📋 **Table des matières**

- [Installation](#-installation)
- [Configuration initiale](#-configuration-initiale)
- [Utilisation](#-utilisation)
- [Métriques collectées](#-métriques-collectées)
- [Vendors (métriques custom)](#-vendors-métriques-custom)
- [Build & Développement](#-build--développement)
- [Troubleshooting](#-troubleshooting)

---

## 🔧 **Installation**

Le projet fournit trois formats d'installation :

| Format | Systèmes supportés | Recommandé pour |
|--------|-------------------|-----------------|
| **DEB** | Debian, Ubuntu | ✅ Recommandé pour Debian/Ubuntu |
| **RPM** | CentOS, RHEL, Alma, Oracle Linux | ✅ Recommandé pour RHEL-based |
| **TAR.GZ** | Tous Linux | Installation manuelle |

Chaque release contient :

```
release/
  monitoring-client_0.1.0_amd64.deb
  monitoring-client-0.1.0-1.x86_64.rpm
  monitoring-client-0.1.0-linux-amd64.tar.gz
```

---

### 🏗️ **Installation via DEB (Debian/Ubuntu)**

```bash
# Télécharger le package
wget https://releases.example.com/monitoring-client_0.1.0_amd64.deb

# Installer
sudo dpkg -i monitoring-client_0.1.0_amd64.deb

# Vérifier l'installation
monitoring-client --version
```

---

### 🏗️ **Installation via RPM (RHEL/CentOS)**

```bash
# Télécharger le package
wget https://releases.example.com/monitoring-client-0.1.0-1.x86_64.rpm

# Installer
sudo rpm -ivh monitoring-client-0.1.0-1.x86_64.rpm

# Vérifier l'installation
monitoring-client --version
```

---

### 🏗️ **Installation via TAR.GZ (installation manuelle)**

```bash
# Créer le répertoire d'installation
sudo mkdir -p /opt/monitoring-client

# Extraire l'archive
sudo tar -xzf monitoring-client-0.1.0-linux-amd64.tar.gz -C /opt/monitoring-client

# Créer un lien symbolique
sudo ln -s /opt/monitoring-client/monitoring-client /usr/local/bin/monitoring-client

# Créer les répertoires de configuration
sudo mkdir -p /etc/monitoring-client
sudo cp /opt/monitoring-client/config.yaml.example /etc/monitoring-client/config.yaml

# Configurer systemd manuellement (optionnel)
sudo cp /opt/monitoring-client/monitoring-client.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
```

---

## 🗝️ **Configuration initiale**

### 1️⃣ **Ajouter la clé API** (obligatoire)

L'agent ne peut rien envoyer sans clé d'authentification.

```bash
# Créer le fichier de clé API
echo "VOTRE_CLE_API_SECRETE" | sudo tee /etc/monitoring-client/api_key > /dev/null

# Sécuriser les permissions
sudo chmod 600 /etc/monitoring-client/api_key
sudo chown root:root /etc/monitoring-client/api_key
```

⚠️ **Sécurité** : Ne jamais commiter la clé API dans Git !

---

### 2️⃣ **Configurer le serveur backend**

Éditer le fichier de configuration :

```bash
sudo nano /etc/monitoring-client/config.yaml
```

Configuration minimale requise :

```yaml
api:
  base_url: "https://monitoring.exemple.com"
  metrics_endpoint: "/api/v1/ingest/metrics"
  api_key_file: "/etc/monitoring-client/api_key"
  timeout_seconds: 30
  max_retries: 3

machine:
  hostname_source: "system"  # ou "fqdn" ou "static"
  # hostname_override: "mon-serveur-prod"  # optionnel

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  console_enabled: true
  file_enabled: true
  file_name: "/var/log/monitoring-client/monitoring-client.log"
```

---

### 3️⃣ **Activer l'exécution automatique**

#### **Avec systemd timer (recommandé)**

Exécution périodique toutes les 5 minutes :

```bash
sudo systemctl daemon-reload
sudo systemctl enable monitoring-client.timer
sudo systemctl start monitoring-client.timer

# Vérifier le statut
sudo systemctl status monitoring-client.timer
```

#### **Avec cron (alternative)**

```bash
# Éditer la crontab root
sudo crontab -e

# Ajouter : exécution toutes les 5 minutes
*/5 * * * * /usr/local/bin/monitoring-client >> /var/log/monitoring-client/cron.log 2>&1
```

---

## ⚙️ **Utilisation**

### **Exécution manuelle**

```bash
# Exécution normale (envoi au serveur)
monitoring-client

# Dry-run (test sans envoi)
monitoring-client --dry-run

# Mode verbose (debug)
monitoring-client --verbose

# Fichier de config spécifique
monitoring-client --config /path/to/config.yaml
```

---

### **Options disponibles**

| Option | Description |
|--------|-------------|
| `--dry-run` | Collecte et valide sans envoyer au serveur |
| `--verbose` | Active les logs détaillés (niveau DEBUG) |
| `--config PATH` | Utilise un fichier de configuration spécifique |
| `--version` | Affiche la version de l'agent |
| `--help` | Affiche l'aide |

---

### **Vérifier les logs**

```bash
# Logs systemd
sudo journalctl -u monitoring-client -f

# Logs fichier
sudo tail -f /var/log/monitoring-client/monitoring-client.log
```

---

## 📊 **Métriques collectées**

L'agent collecte automatiquement ces catégories de métriques :

### **🖥️ Système**
- Hostname, OS, distribution, architecture
- Kernel version, uptime
- Nombre de processus
- Python version (agent)

### **💾 Ressources**
- CPU : utilisation globale (%)
- RAM : totale, disponible, utilisation (%)
- SWAP : totale, utilisation (%)
- Disques : usage par partition `disk[/var].usage_percent`

### **🌐 Réseau**
- Interfaces réseau actives
- Bytes sent/received par interface
- Exemple : `network.eth0.bytes_sent`

### **🔥 Firewall**
- Statut UFW/iptables/firewalld
- Nombre de règles actives

### **📦 Packages**
- Mises à jour disponibles (apt/yum/dnf)
- Mises à jour de sécurité

### **🔧 Services**
- État des services systemd
- Exemple : `service.nginx.service.active`

### **🔒 Sécurité**
- Utilisateurs avec UID 0 (root)
- Sessions SSH actives
- Ports en écoute

### **⏰ Tâches planifiées**
- Nombre de crontabs utilisateurs
- Jobs at en attente

### **📝 Logs**
- Anomalies dans syslog (dernier jour)
- Comptage d'erreurs

### **🐳 Docker**
- Conteneurs actifs/stoppés
- Images disponibles

### **💾 Bases de données**
- Détection PostgreSQL, MySQL, MongoDB, Redis
- État running/stopped

---

## 🎨 **Vendors (métriques custom)**

Les vendors permettent d'ajouter vos propres métriques personnalisées.

### **📌 Créer un vendor**

Créer le fichier `/etc/monitoring-client/vendors/mon-app.yaml` :

```yaml
metadata:
  vendor: "acme.nginx"
  language: "bash"

metrics:
  - name: "nginx.requests_total"
    command: "wc -l < /var/log/nginx/access.log"
    type: "numeric"
    group_name: "nginx"
    description: "Nombre total de requêtes HTTP"
    is_critical: true

  - name: "nginx.errors_today"
    command: "grep -c 'error' /var/log/nginx/error.log || echo 0"
    type: "numeric"
    group_name: "nginx"
    description: "Nombre d'erreurs dans les logs du jour"
    is_critical: false
```

---

### **📋 Champs obligatoires**

#### **Metadata**
| Champ | Description | Exemple |
|-------|-------------|---------|
| `vendor` | Identifiant unique du fournisseur | `"acme.nginx"` |
| `language` | Langage d'exécution | `"bash"`, `"python3"` |

#### **Metrics**
| Champ | Type | Description |
|-------|------|-------------|
| `name` | string | Nom unique de la métrique |
| `command` | string | Commande shell à exécuter |
| `type` | string | `"numeric"`, `"boolean"`, `"string"` |
| `group_name` | string | Catégorie pour le dashboard |
| `description` | string | Description affichée |
| `is_critical` | boolean | Alerte si métrique critique |

---

### **🧠 Langages supportés**

- `bash` (par défaut)
- `python3`, `python2`
- `nodejs`, `node`
- `ruby`
- `perl`
- `powershell` (Windows)
- `java` (via `.jar`)

Exemple avec Python :

```yaml
metrics:
  - name: "custom.disk_io"
    command: "python3 -c \"import psutil; print(psutil.disk_io_counters().read_bytes)\""
    language: "python3"
    type: "numeric"
    group_name: "io"
    description: "Bytes lus sur disque"
    is_critical: false
```

---

### **🔒 Sécurité des vendors**

- ✅ Aucun `shell=True` (injection impossible)
- ✅ Timeout strict par métrique (30s par défaut)
- ✅ Exécution isolée par subprocess
- ⚠️ Les vendors sont traités comme extensions de confiance (ne pas exécuter de code non vérifié)

---

## 🛠️ **Build & Développement**

### **Prérequis**

```bash
# Python 3.11+
python3 --version

# Dépendances
pip install -r requirements.txt
```

---

### **Tests**

```bash
# Lancer les tests unitaires
pytest -vv

# Avec couverture
pytest --cov=src --cov-report=html

# Tests d'intégration
pytest tests/integration/ -v
```

---

### **Build du binaire PyInstaller**

```bash
# Build simple
pyinstaller --clean pyinstaller.spec

# Avec script automatisé
./scripts/build.sh

# Le binaire sera dans dist/
./dist/monitoring-client --version
```

---

### **Build des packages (DEB/RPM/TAR.GZ)**

```bash
# Build tous les formats
./scripts/make.sh

# Les packages seront dans release/
ls -lh release/
```

---

## 📁 **Arborescence installée**

### **Fichiers principaux**

```
/usr/local/bin/monitoring-client          # Binaire principal
/etc/monitoring-client/config.yaml        # Configuration
/etc/monitoring-client/api_key            # Clé API (à créer)
/etc/monitoring-client/vendors/           # Métriques custom
/var/log/monitoring-client/               # Logs
/opt/monitoring-client/data/              # Cache (fingerprint)
```

### **Systemd**

```
/usr/lib/systemd/system/monitoring-client.service
/usr/lib/systemd/system/monitoring-client.timer
```

---

## 🔥 **Codes de retour**

| Code | Signification |
|------|--------------|
| **0** | ✅ Exécution réussie |
| **1** | ❌ Erreur de configuration |
| **2** | ❌ Erreur de validation du payload |
| **3** | ❌ Erreur réseau/HTTP (serveur inaccessible) |

---

## 🛠️ **Troubleshooting**

### **❓ Aucune métrique firewall collectée**

**Cause** : UFW/iptables/firewalld non installés

**Solution** :
```bash
# Debian/Ubuntu
sudo apt install ufw

# RHEL/CentOS
sudo yum install firewalld
```

---

### **❓ Erreur "Permission denied" sur /proc**

**Cause** : L'agent doit s'exécuter en root pour accéder à certaines métriques système

**Solution** :
```bash
# Exécution manuelle en root
sudo monitoring-client

# Le service systemd s'exécute automatiquement en root
```

---

### **❓ HTTP 401 Unauthorized**

**Cause** : Clé API invalide ou manquante

**Solution** :
```bash
# Vérifier la clé
sudo cat /etc/monitoring-client/api_key

# Vérifier la config
sudo grep api_key_file /etc/monitoring-client/config.yaml

# Vérifier les permissions
ls -l /etc/monitoring-client/api_key
# Doit afficher : -rw------- 1 root root
```

---

### **❓ Validation du payload échouée**

**Cause** : Format de métrique invalide (noms, types, valeurs)

**Solution** :
```bash
# Tester en dry-run avec debug
monitoring-client --dry-run --verbose

# Vérifier les logs
sudo journalctl -u monitoring-client -n 100 --no-pager
```

---

### **❓ Certains collecteurs ne renvoient rien**

**Causes possibles** :
- Docker non installé → pas de métriques Docker
- PostgreSQL/MySQL non installés → pas de métriques DB
- Pas de crontabs utilisateurs → compteur à 0

**C'est normal** : l'agent collecte uniquement ce qui est disponible sur le système.

---

### **❓ Le timer systemd ne s'exécute pas**

**Vérification** :
```bash
# Statut du timer
sudo systemctl status monitoring-client.timer

# Liste des prochaines exécutions
sudo systemctl list-timers --all | grep monitoring

# Forcer une exécution manuelle
sudo systemctl start monitoring-client.service
```

---

## 📚 **Documentation avancée**

- [Architecture détaillée](docs/ARCHITECTURE.md)
- [Format des métriques](docs/METRICS_FORMAT.md)
- [API Backend](docs/API_SPEC.md)
- [Contribution](CONTRIBUTING.md)

---

## 📄 **Licence**

MIT License - voir [LICENSE](LICENSE)

---

## 🤝 **Support**

- 📧 Email : support@example.com
- 🐛 Issues : https://github.com/your-org/monitoring-client/issues
- 📖 Wiki : https://github.com/your-org/monitoring-client/wiki

---

## 🎉 **Contributeurs**

Merci à tous les contributeurs qui ont participé au projet !

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
