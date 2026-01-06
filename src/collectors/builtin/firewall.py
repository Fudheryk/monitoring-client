from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List

from core.logger import get_logger

from ..base_collector import BaseCollector, Metric

# Configuration du logger
logger = get_logger(__name__)

class FirewallCollector(BaseCollector):
    """
    Collecteur builtin pour les pare-feu courants :

      - UFW
      - iptables
      - firewalld

    Noms de métriques (exemples) :
      - firewall.ufw.enabled (boolean)
      - firewall.ufw.version (string)
      - firewall.iptables.rules_count (numeric)
      - firewall.iptables.version (string)
      - firewall.firewalld.running (boolean)
      - firewall.firewalld.version (string)
    """

    name = "firewall"  # Nom du collecteur
    editor = "builtin"  # Type de collecteur

    def _collect_metrics(self) -> List[Metric]:
        """
        Collecte les métriques des pare-feu (UFW, iptables, firewalld).
        :return: liste des métriques collectées
        """
        metrics: List[Dict[str, Any]] = []

        # Collecte des métriques pour chaque backend de pare-feu
        metrics.extend(self._collect_ufw())        # Collecte pour UFW
        metrics.extend(self._collect_iptables())    # Collecte pour iptables
        metrics.extend(self._collect_firewalld())   # Collecte pour firewalld

        # Retourne toutes les métriques collectées
        logger.info(f"Collecte terminée: {len(metrics)} métriques collectées.")
        return metrics

    # ---- Helpers internes par backend ----

    def _collect_ufw(self) -> List[Metric]:
        """
        Collecte des métriques pour UFW (Uncomplicated Firewall).
        :return: liste des métriques collectées pour UFW
        """
        m: List[Dict[str, Any]] = []

        ufw_cmd = self._which_or_path("ufw", "/usr/sbin/ufw")
        if not ufw_cmd:
            return m  # Si UFW n'est pas installé, on retourne les métriques vides

        # Statut UFW
        try:
            result = subprocess.run(
                [ufw_cmd, "status"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=3.0,
            )
            enabled = "Status: active" in result.stdout
            m.append(
                {
                    "name": "firewall.ufw.enabled",
                    "value": enabled,
                    "type": "boolean",
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Nom de l'éditeur
                }
            )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.ufw.enabled: %s", exc)

        # Version UFW
        try:
            result = subprocess.run(
                [ufw_cmd, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=3.0,
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            m.append(
                {
                    "name": "firewall.ufw.version",
                    "value": version,
                    "type": "string",
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Nom de l'éditeur
                }
            )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.ufw.version: %s", exc)

        return m

    def _collect_iptables(self) -> List[Metric]:
        """
        Collecte des métriques pour iptables.
        :return: liste des métriques collectées pour iptables
        """
        m: List[Dict[str, Any]] = []

        iptables_cmd = self._which_or_path("iptables", "/usr/sbin/iptables")
        if not iptables_cmd:
            return m  # Si iptables n'est pas installé, on retourne les métriques vides

        # Nombre de règles iptables
        try:
            result = subprocess.run(
                [iptables_cmd, "-L", "-n"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                rules_count = len(
                    [
                        line
                        for line in result.stdout.splitlines()
                        if line.strip() and not line.startswith("Chain") and not line.startswith("target")
                    ]
                )
                m.append(
                    {
                        "name": "firewall.iptables.rules_count",
                        "value": rules_count,
                        "type": "numeric",
                        "collector_name": self.name,  # Nom du collecteur
                        "editor_name": self.editor,  # Nom de l'éditeur
                    }
                )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.iptables.rules_count: %s", exc)

        # Version iptables
        try:
            result = subprocess.run(
                [iptables_cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=3.0,
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            m.append(
                {
                    "name": "firewall.iptables.version",
                    "value": version,
                    "type": "string",
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Nom de l'éditeur
                }
            )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.iptables.version: %s", exc)

        return m

    def _collect_firewalld(self) -> List[Metric]:
        """
        Collecte des métriques pour firewalld.
        :return: liste des métriques collectées pour firewalld
        """
        m: List[Dict[str, Any]] = []

        fw_cmd = self._which_or_path("firewall-cmd", "/usr/bin/firewall-cmd")
        if not fw_cmd:
            return m  # Si firewalld n'est pas installé, on retourne les métriques vides

        # État firewalld
        try:
            result = subprocess.run(
                [fw_cmd, "--state"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=3.0,
            )
            running = "running" in result.stdout
            m.append(
                {
                    "name": "firewall.firewalld.running",
                    "value": running,
                    "type": "boolean",
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Nom de l'éditeur
                }
            )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.firewalld.running: %s", exc)

        # Version firewalld
        try:
            result = subprocess.run(
                [fw_cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                timeout=3.0,
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            m.append(
                {
                    "name": "firewall.firewalld.version",
                    "value": version,
                    "type": "string",
                    "collector_name": self.name,  # Nom du collecteur
                    "editor_name": self.editor,  # Nom de l'éditeur
                }
            )
        except Exception as exc:
            logger.debug("Échec de la collecte firewall.firewalld.version: %s", exc)

        return m

    @staticmethod
    def _which_or_path(binary: str, fallback_path: str) -> str | None:
        """
        Retourne le chemin vers un binaire si présent, sinon None.

        Essaie d'abord `shutil.which`, puis un chemin fallback.
        """
        path = shutil.which(binary)
        if path:
            return path
        if os.path.exists(fallback_path) and os.access(fallback_path, os.X_OK):
            return fallback_path
        return None
