# src/collectors/builtin/databases.py

import os
import subprocess
import logging

from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class DatabasesCollector(BaseCollector):
    """
    Collecte des métriques de services de bases de données courants :
    - MySQL / MariaDB
    - PostgreSQL
    - Redis
    """

    name = "databases"

    def _collect_metrics(self):
        metrics = []

        # MySQL / MariaDB
        mysql_bin = "/usr/bin/mysql"
        mariadb_bin = "/usr/bin/mariadb"

        has_mysql = os.path.exists(mysql_bin)
        has_mariadb = os.path.exists(mariadb_bin)

        # MySQL
        if has_mysql:
            mysql_active = self._systemd_is_active("mysql")
            metrics.append(
                {
                    "name": "database.mysql.service_active",
                    "value": bool(mysql_active),
                    "type": "boolean",
                    "description": (
                        "Indique si le service MySQL est actif. "
                        "Critique car MySQL est essentiel pour la gestion des bases de données."),
                    "is_critical": True,
                })

        # MariaDB (si présent)
        if has_mariadb:
            mariadb_active = self._systemd_is_active("mariadb")
            metrics.append(
                {
                    "name": "database.mariadb.service_active",
                    "value": bool(mariadb_active),
                    "type": "boolean",
                    "description": (
                        "Indique si le service MariaDB est actif. "
                        "Critique car MariaDB est une alternative essentielle à MySQL."),
                    "is_critical": True,
                })

        # PostgreSQL
        if os.path.exists("/usr/bin/psql"):
            postgres_active = self._systemd_is_active("postgresql")
            metrics.append(
                {
                    "name": "database.postgresql.service_active",
                    "value": bool(postgres_active),
                    "type": "boolean",
                    "description": (
                        "Indique si le service PostgreSQL est actif. "
                        "Critique car PostgreSQL est une base de données relationnelle "
                        "couramment utilisée."),
                    "is_critical": True,
                })

        # Redis
        if os.path.exists("/usr/bin/redis-server"):
            redis_active = self._systemd_is_active("redis")
            metrics.append(
                {
                    "name": "database.redis.service_active",
                    "value": bool(redis_active),
                    "type": "boolean",
                    "description": (
                        "Indique si le service Redis est actif. "
                        "Non critique mais important pour la mise en cache / données en mémoire."),
                    "is_critical": False,
                })

        return metrics

    @staticmethod
    def _systemd_is_active(service_name: str) -> bool:
        """
        Retourne True si systemd considère le service comme 'active'.
        """
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=False,
            )
            return result.stdout.strip() == "active"
        except Exception as exc:  # pragma: no cover - log only
            logger.warning(
                "Erreur lors de la vérification de l'état systemd pour %s : %s",
                service_name,
                exc,
            )
            return False
