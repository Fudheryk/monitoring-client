from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.logger import get_logger, log_phase
from .parser import VendorMetric


logger = get_logger(__name__)


SUPPORTED_LANGUAGES = [
    "python",
    "bash",
    "python2",
    "java",
    "node",
    "ruby",
    "perl",
    "powershell",
    "batch",
]


@dataclass
class CommandExecutionResult:
    """
    Résultat d'exécution d'une commande vendor.

    NOTE : cette structure n'est pour l'instant pas exposée par l'API
    publique du CommandExecutor, mais elle documente clairement ce
    qu'on manipulerait si on voulait enrichir le retour plus tard.

    - raw_stdout : sortie brute (strip)
    - raw_stderr : erreur brute (strip)
    - return_code : code de retour du process
    - parsed_value : valeur typée (optionnelle, selon type attendu)
    """

    raw_stdout: str
    raw_stderr: str
    return_code: int
    parsed_value: Optional[Any]


class CommandExecutor:
    """
    Exécuteur de commandes multi-langages pour les métriques vendor.

    Objectifs :
      - Vérifier la disponibilité de chaque langage supporté (which/whereis).
      - Fournir une méthode générique d'exécution avec timeout strict.
      - Parser la sortie stdout selon le type attendu (numeric/boolean/string).
      - Ne jamais casser le pipeline : en cas d'erreur, log + None.

    IMPORTANT :
      - Le CommandExecutor ne construit PAS l'objet métrique envoyé au backend.
        Il ne renvoie que la *valeur* (typed value). C'est le pipeline
        (agrégation) qui se charge de fusionner :
          * méta du VendorMetric (name, vendor, group_name, description,
            is_critical, type)
          * valeur exécutée
        pour produire le dict final :

            {
              "name": vm.name,
              "value": <valeur>,
              "type": vm.type,
              "vendor": vm.vendor,
              "group_name": vm.group_name,
              "description": vm.description,
              "is_critical": vm.is_critical,
            }
    """

    def __init__(self) -> None:
        self._language_binaries: Dict[str, Optional[str]] = {}
        self._init_languages_availability()

    # -------------------------------------------------------------------------
    # Initialisation langages
    # -------------------------------------------------------------------------

    def _init_languages_availability(self) -> None:
        """
        Détecte la disponibilité des langages supportés et mémorise le binaire.

        Exemple :
          - python   -> /usr/bin/python3
          - bash     -> /usr/bin/bash
          - node     -> /usr/bin/node
        """
        log_phase(logger, "vendors.executor.init", "Détection des langages disponibles")

        # Linux / Unix centrée, mais on prépare batch/powershell pour Windows
        candidates = {
            "python": ["python3", "python"],
            "bash": ["bash", "sh"],
            "python2": ["python2"],
            "java": ["java"],
            "node": ["node", "nodejs"],
            "ruby": ["ruby"],
            "perl": ["perl"],
            "powershell": ["pwsh", "powershell"],
            "batch": ["cmd"],  # Windows uniquement
        }

        for lang, bins in candidates.items():
            path = None
            for b in bins:
                p = shutil.which(b)
                if p:
                    path = p
                    break
            self._language_binaries[lang] = path

        logger.debug("Langages détectés: %s", self._language_binaries)

    # -------------------------------------------------------------------------
    # API publique
    # -------------------------------------------------------------------------

    def check_language_available(self, lang: str) -> bool:
        """
        Retourne True si le langage est supporté ET un binaire a été trouvé.

        Exemple :
          executor.check_language_available("bash") -> True/False
        """
        normalized = lang.lower().strip()
        return (
            normalized in self._language_binaries
            and self._language_binaries[normalized] is not None
        )

    def execute(
        self,
        command: str,
        language: str,
        timeout: float,
        expected_type: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Exécute une commande dans le langage donné avec un timeout strict.

        Paramètres :
          - command : code ou commande à exécuter
          - language : langage déclaré ("bash", "python", "node", ...)
          - timeout : timeout en secondes
          - expected_type : "numeric" | "boolean" | "string" (optionnel)

        Retour :
          - Valeur typée (float/int/bool/str) si succès et parsing OK
          - None en cas d'erreur ou de parsing impossible

        Remarque :
          - Cette méthode est volontairement "simple" : le wrapping en objet
            riche (dict de métrique envoyé au backend) est fait ailleurs.
        """
        lang = language.lower().strip()

        if not self.check_language_available(lang):
            logger.warning(
                "Langage '%s' non disponible sur ce système, commande ignorée.",
                language,
            )
            return None

        try:
            proc_args = self._build_process_args(lang, command)
        except ValueError as exc:
            logger.warning("Commande vendor rejetée (langage %s): %s", lang, exc)
            return None

        log_phase(
            logger,
            "vendors.executor.exec",
            f"Exécution commande vendor (lang={lang})",
        )
        logger.debug("Arguments du processus: %r", proc_args)

        try:
            result = subprocess.run(
                proc_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "Commande vendor expirée (timeout=%.2fs, lang=%s): %s",
                timeout,
                lang,
                command,
            )
            return None
        except Exception as exc:
            logger.warning(
                "Erreur lors de l'exécution de la commande vendor (lang=%s): %s",
                lang,
                exc,
            )
            return None

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            logger.warning(
                "Commande vendor terminée en erreur (code=%d, lang=%s, stderr=%s)",
                result.returncode,
                lang,
                stderr,
            )
            return None

        logger.debug(
            "Commande vendor OK (lang=%s, stdout=%r, stderr=%r)",
            lang,
            stdout,
            stderr,
        )

        # Si aucun type attendu n'est fourni, on renvoie la sortie brute
        if expected_type is None:
            return stdout

        parsed = self._parse_output(stdout, expected_type)
        if parsed is None:
            logger.warning(
                "Parsing de la sortie vendor impossible (type=%s, stdout=%r)",
                expected_type,
                stdout,
            )
        return parsed

    def execute_metric(self, metric: VendorMetric, timeout: float) -> Optional[Any]:
        """
        Helper pratique pour exécuter directement une VendorMetric.

        Utilise :
          - metric.command
          - metric.language
          - metric.type (numeric/boolean/string) pour le parsing

        Retour :
          - valeur typée (ou None en cas d'erreur). Les métadonnées
            (vendor, group_name, description, is_critical, ...) restent
            dans l'objet VendorMetric et seront utilisées plus loin
            dans le pipeline.
        """
        return self.execute(
            command=metric.command,
            language=metric.language,
            timeout=timeout,
            expected_type=metric.type,
        )

    # -------------------------------------------------------------------------
    # Helpers internes
    # -------------------------------------------------------------------------

    def _build_process_args(self, language: str, command: str) -> list[str]:
        """
        Construit la ligne de commande (liste d'arguments) pour subprocess.

        On évite d'utiliser shell=True. On passe l'interpréteur explicitement.

        Convention :
          - python   : python -c "<code python>"
          - python2  : python2 -c "<code python2>"
          - bash     : bash -c "<script shell>"
          - node     : node -e "<code JS>"
          - ruby     : ruby -e "<code Ruby>"
          - perl     : perl -e "<code Perl>"
          - powershell : pwsh/powershell -Command "<code>"
          - batch    : cmd /c "<cmd>" (Windows)
          - java     : java -jar <...> (si commande ressemble à 'xxx.jar'), sinon
                       on exécute la commande telle quelle via 'bash -c' si dispo,
                       ou on lève une erreur.
        """
        lang = language.lower().strip()
        interpreter = self._language_binaries.get(lang)
        if not interpreter:
            raise ValueError(f"Aucun interpréteur trouvé pour le langage '{lang}'")

        # Langages script traditionnels
        if lang == "python":
            return [interpreter, "-c", command]
        if lang == "python2":
            return [interpreter, "-c", command]
        if lang == "bash":
            return [interpreter, "-c", command]
        if lang in ("node",):
            return [interpreter, "-e", command]
        if lang == "ruby":
            return [interpreter, "-e", command]
        if lang == "perl":
            return [interpreter, "-e", command]
        if lang == "powershell":
            # Linux: pwsh, Windows: powershell
            return [interpreter, "-Command", command]
        if lang == "batch":
            # Windows uniquement, mais on laisse la possibilité
            return [interpreter, "/c", command]

        if lang == "java":
            # Cas 1 : l'intégrateur fournit directement 'java ...'
            #         Dans ce cas, il devrait utiliser language="bash".
            # Cas 2 : on tente un mode simple pour les jars :
            cmd_str = command.strip()
            if cmd_str.endswith(".jar"):
                return [interpreter, "-jar", cmd_str]

            # Sinon, on considère que c'est trop ambigu => on refuse
            raise ValueError(
                "Commande Java ambiguë. "
                "Soit utilisez 'language: bash' avec 'java ...', "
                "soit fournissez directement un .jar en commande."
            )

        # Par sécurité : si on arrive ici, on ne sait pas quoi faire
        raise ValueError(f"Langage '{lang}' non géré dans _build_process_args.")

    @staticmethod
    def _parse_output(stdout: str, expected_type: str) -> Optional[Any]:
        """
        Parse la sortie stdout vers le type demandé.

        expected_type ∈ {"numeric", "boolean", "string"}
        """
        etype = expected_type.lower().strip()

        if etype == "string":
            return stdout

        if etype == "numeric":
            # On essaie int puis float
            try:
                if "." not in stdout and "e" not in stdout.lower():
                    return int(stdout)
                return float(stdout)
            except Exception:
                try:
                    return float(stdout)
                except Exception:
                    return None

        if etype == "boolean":
            val = stdout.strip().lower()
            if val in ("true", "1", "yes", "y", "on"):
                return True
            if val in ("false", "0", "no", "n", "off"):
                return False
            return None

        # Type inconnu
        return None
