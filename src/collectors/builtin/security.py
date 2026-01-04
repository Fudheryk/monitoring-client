# src/collectors/builtin/security.py

import subprocess
import psutil
import logging

from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


def _get_ssh_port() -> int:
    """
    Récupère le port SSH configuré dans /etc/ssh/sshd_config.
    Retourne 22 par défaut si aucune configuration n'est trouvée.
    """
    ssh_config_path = "/etc/ssh/sshd_config"
    default_port = 22

    try:
        with open(ssh_config_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.lower().startswith("port"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        try:
                            return int(parts[1])
                        except ValueError:
                            continue
    except FileNotFoundError:
        # Pas de sshd_config, on garde 22
        pass
    except Exception as exc:  # pragma: no cover - log only
        logger.warning(
            "Erreur lors de la lecture de %s : %s",
            ssh_config_path,
            exc)

    return default_port


class SecurityCollector(BaseCollector):
    """
    Collecte de métriques de sécurité :
    - nb d'utilisateurs connectés
    - nb de connexions SSH actives
    - nb de processus suspects
    - nb de processus très consommateurs CPU
    - nb de ports TCP/UDP en écoute
    - version de sshd
    """

    name = "security"

    def _collect_metrics(self):
        metrics = []

        # Utilisateurs connectés (commande 'who')
        users_count = 0
        try:
            result = subprocess.run(
                ["who"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                check=False,
            )
            users_count = len(
                [l for l in result.stdout.strip().splitlines() if l.strip()]
            )
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la récupération des utilisateurs connectés : %s", exc)

        # Connexions SSH actives sur le port configuré
        ssh_port = _get_ssh_port()
        ssh_connections = 0
        try:
            for conn in psutil.net_connections():
                if (
                    conn.laddr
                    and conn.laddr.port == ssh_port
                    and conn.status == psutil.CONN_ESTABLISHED
                ):
                    ssh_connections += 1
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la récupération des connexions SSH : %s", exc
            )

        # Processus suspects / high CPU
        suspicious_processes = 0
        high_cpu_processes = 0
        suspicious_keywords = ["crypto", "miner", "bot", "malware"]

        try:
            for proc in psutil.process_iter(
                attrs=["pid", "name", "username", "cpu_percent"]
            ):
                try:
                    info = proc.info
                    username = info.get("username") or ""
                    name = (info.get("name") or "").lower()
                    cpu = info.get("cpu_percent") or 0.0

                    if username == "nobody" or any(
                        kw in name for kw in suspicious_keywords
                    ):
                        suspicious_processes += 1

                    if cpu > 80.0:
                        high_cpu_processes += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
                    continue
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la récupération des processus pour la sécurité : %s", exc, )

        # Ports en écoute
        open_ports = set()
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr:
                    open_ports.add(conn.laddr.port)
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la récupération des ports ouverts : %s", exc
            )

        # Version sshd
        ssh_version = "unknown"
        try:
            # sshd -v écrit la version dans stderr
            result = subprocess.run(
                ["sshd", "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
            stderr = result.stderr.strip()
            if stderr:
                ssh_version = stderr.splitlines()[0]
        except FileNotFoundError:
            # sshd absent
            pass
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la récupération de la version SSH : %s", exc
            )

        metrics.extend([{"name": "security.logged_users",
                         "value": int(users_count),
                         "type": "numeric",
                         "description": "Nombre d'utilisateurs connectés au système.",
                         "is_critical": False,
                         },
                        {"name": "security.ssh_connections",
                         "value": int(ssh_connections),
                         "type": "numeric",
                         "description": "Nombre de connexions SSH actives.",
                         "is_critical": True,
                         },
                        {"name": "security.suspicious_processes",
                         "value": int(suspicious_processes),
                         "type": "numeric",
                         "description": "Nombre de processus suspects détectés.",
                         "is_critical": True,
                         },
                        {"name": "security.high_cpu_processes",
                         "value": int(high_cpu_processes),
                         "type": "numeric",
                         "description": "Nombre de processus consommant plus de 80% de CPU.",
                         "is_critical": False,
                         },
                        {"name": "security.open_ports_count",
                         "value": int(len(open_ports)),
                         "type": "numeric",
                         "description": "Nombre de ports ouverts (LISTEN) sur le système.",
                         "is_critical": False,
                         },
                        {"name": "security.sshd_version",
                         "value": ssh_version,
                         "type": "string",
                         "description": "Version actuelle de SSH (sshd) sur le système.",
                         "is_critical": False,
                         },
                        ])

        return metrics
