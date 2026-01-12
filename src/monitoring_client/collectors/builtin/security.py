import logging
import re
import subprocess
from typing import List, Dict, Any
from pathlib import Path

import time
import psutil

from monitoring_client.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


EXCLUDED_PROCESS_PREFIXES = (
    "tracker-miner",
    "tracker-extract",
    "tracker-store",
)

def _get_sshd_version() -> str:
    """
    Retourne la version de sshd de façon compatible Debian/CentOS.

    Notes:
    - Debian: `/usr/sbin/sshd -V` renvoie directement `OpenSSH_...` (souvent sur stdout/stderr)
    - CentOS 7: `/usr/sbin/sshd -V` affiche parfois "unknown option -- V" mais la ligne OpenSSH
      est quand même présente dans la sortie (stdout/stderr). On cherche donc la ligne contenant OpenSSH.
    """
    try:
        result = subprocess.run(
            ["/usr/sbin/sshd", "-V"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        m = re.search(r"(OpenSSH[_ ][^\n]+)", combined)
        return m.group(1).strip() if m else "unknown"

    except FileNotFoundError:
        # sshd absent (container minimal, openssh-server non installé, etc.)
        return "unknown"
    except Exception as exc:  # pragma: no cover - log only
        logger.warning("Erreur lors de la récupération de la version SSH : %s", exc)
        return "unknown"


def _get_ssh_port(default: int = 22) -> int:
    """
    Détermine le port SSH (sshd) de façon portable Debian/CentOS.

    Stratégie (best effort):
    1) Essaye `sshd -T` (imprime la config effective) et lit la directive `port`.
       - Sur la plupart des systèmes, `sshd -T` fonctionne sans root.
       - Peut échouer si sshd n'est pas installé ou si la config est invalide.
    2) Sinon, parse `/etc/ssh/sshd_config` (première directive Port non commentée).
    3) Sinon, retourne 22.

    :param default: port par défaut si rien n'est détectable
    :return: port ssh (int)
    """
    # ------------------------------------------------------------
    # 1) Méthode la plus fiable : sshd -T (config effective)
    # ------------------------------------------------------------
    sshd_candidates = ["/usr/sbin/sshd", "sshd"]
    for sshd_bin in sshd_candidates:
        try:
            result = subprocess.run(
                [sshd_bin, "-T"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            if result.returncode == 0 and result.stdout:
                # Exemple de sortie: "port 22"
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("port "):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            return int(parts[1])

        except FileNotFoundError:
            continue
        except Exception as exc:  # pragma: no cover - log only
            logger.debug("Erreur sshd -T via %s: %s", sshd_bin, exc)

    # ------------------------------------------------------------
    # 2) Fallback : parse sshd_config
    # ------------------------------------------------------------
    config_path = Path("/etc/ssh/sshd_config")
    if config_path.exists():
        try:
            for raw in config_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue

                # Support: "Port 2222" ou "Port\t2222"
                m = re.match(r"(?i)^port\s+(\d+)\s*$", line)
                if m:
                    port = int(m.group(1))
                    if 1 <= port <= 65535:
                        return port
        except Exception as exc:  # pragma: no cover - log only
            logger.debug("Erreur parsing %s: %s", str(config_path), exc)

    # ------------------------------------------------------------
    # 3) Dernier recours
    # ------------------------------------------------------------
    return int(default)


class SecurityCollector(BaseCollector):
    """
    Collecteur de métriques de sécurité (best effort).
    """

    name = "security"
    editor = "builtin"

    def _collect_metrics(self) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []

        # ---------------------------------------------------------------------
        # 1) Utilisateurs connectés (who)
        # ---------------------------------------------------------------------
        users_count = 0
        try:
            result = subprocess.run(
                ["who"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            users_count = len([l for l in (result.stdout or "").splitlines() if l.strip()])
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la récupération des utilisateurs connectés : %s", exc)

        # ---------------------------------------------------------------------
        # 2) Connexions SSH actives sur le port configuré
        # ---------------------------------------------------------------------
        ssh_port = _get_ssh_port()
        ssh_connections = 0
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr and conn.laddr.port == ssh_port and conn.status == psutil.CONN_ESTABLISHED:
                    ssh_connections += 1
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la récupération des connexions SSH : %s", exc)

        # ---------------------------------------------------------------------
        # 3) Processus suspects / high CPU
        # ---------------------------------------------------------------------
        suspicious_processes = 0
        high_cpu_processes = 0
        suspicious_keywords = ["crypto", "miner", "bot", "malware"]

        try:
            # Warmup CPU%: sinon cpu_percent est souvent à 0 au premier passage.
            for p in psutil.process_iter(attrs=["pid"]):
                try:
                    p.cpu_percent(None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            time.sleep(0.2)

            for proc in psutil.process_iter(attrs=["pid", "name", "username"]):
                try:
                    info = proc.info or {}
                    username = (info.get("username") or "").strip()
                    name = (info.get("name") or "").lower().strip()

                    # Exclusions connues (ex: GNOME Tracker)
                    if name.startswith(EXCLUDED_PROCESS_PREFIXES):
                        continue

                    # Mesure CPU réelle après warmup
                    try:
                        cpu = float(proc.cpu_percent(None) or 0.0)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
                        cpu = 0.0

                    # Heuristiques "processus suspects"
                    if username in ("nobody", "nfsnobody") or any(kw in name for kw in suspicious_keywords):
                        suspicious_processes += 1


                    if cpu > 80.0:
                        high_cpu_processes += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
                    continue
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la récupération des processus pour la sécurité : %s", exc)

        # ---------------------------------------------------------------------
        # 4) Ports en écoute (LISTEN)
        # ---------------------------------------------------------------------
        open_ports = set()
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    open_ports.add(conn.laddr.port)
        except Exception as exc:  # pragma: no cover - log only
            logger.warning("Erreur lors de la récupération des ports ouverts : %s", exc)

        # ---------------------------------------------------------------------
        # 5) Version sshd
        # ---------------------------------------------------------------------
        ssh_version = _get_sshd_version()

        # ---------------------------------------------------------------------
        # 6) Build metrics
        # ---------------------------------------------------------------------
        metrics.extend(
            [
                {
                    "name": "logged_users",
                    "value": int(users_count),
                    "type": "numeric",
                    "description": "Nombre d'utilisateurs connectés au système.",
                    "is_critical": False,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
                {
                    "name": "ssh_connections",
                    "value": int(ssh_connections),
                    "type": "numeric",
                    "description": f"Nombre de connexions SSH actives (port {ssh_port}).",
                    "is_critical": True,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
                {
                    "name": "suspicious_processes",
                    "value": int(suspicious_processes),
                    "type": "numeric",
                    "description": "Nombre de processus suspects détectés (heuristiques simples).",
                    "is_critical": True,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
                {
                    "name": "high_cpu_processes",
                    "value": int(high_cpu_processes),
                    "type": "numeric",
                    "description": "Nombre de processus consommant plus de 80% de CPU.",
                    "is_critical": False,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
                {
                    "name": "open_ports_count",
                    "value": int(len(open_ports)),
                    "type": "numeric",
                    "description": "Nombre de ports ouverts (LISTEN) sur le système.",
                    "is_critical": False,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
                {
                    "name": "sshd_version",
                    "value": ssh_version,
                    "type": "string",
                    "description": "Version actuelle de SSH (sshd) sur le système.",
                    "is_critical": False,
                    "collector_name": self.name,
                    "editor_name": self.editor,
                },
            ]
        )

        logger.info("Collecte terminée: %s métriques collectées.", len(metrics))
        return metrics
