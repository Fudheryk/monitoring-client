import hashlib
import logging
import os
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .logger import get_logger, log_phase

logger = get_logger(__name__)


class FingerprintError(Exception):
    """Erreur lors de la génération du fingerprint."""


def _read_file_safely(path: Path) -> str:
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        logger.debug("Impossible de lire le fichier %s pour le fingerprint", path)
    return ""


def _run_command(cmd: List[str], timeout: float = 2.0) -> str:
    """
    Exécute une commande système de manière sûre pour la collecte d'infos
    (dmidecode, lscpu, etc.). En cas d'erreur, retourne une chaîne vide.
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as exc:
        logger.debug("Commande %s échouée pour fingerprint: %s", cmd, exc)
    return ""


def _normalize_mac(address: str) -> Optional[str]:
    """
    Normalise une adresse MAC en majuscules avec ":" comme séparateur.

    Retourne None si l'adresse ne semble pas valide.
    """
    addr = address.strip().lower()
    if not addr or addr == "00:00:00:00:00:00":
        return None

    # Certains systèmes peuvent retourner des MAC sans les ":" (ex: 4c1fccaabbcc)
    addr = addr.replace("-", "").replace(":", "")
    if len(addr) != 12:
        return None

    try:
        int(addr, 16)
    except ValueError:
        return None

    return ":".join(addr[i : i + 2] for i in range(0, 12, 2)).upper()


def _collect_mac_addresses() -> List[str]:
    """
    Récupère une liste d'adresses MAC triées.

    Sous Linux : /sys/class/net/*/address
    Fallback : uuid.getnode() si aucun autre n'est disponible.
    """
    macs: List[str] = []

    sys_class_net = Path("/sys/class/net")
    if sys_class_net.is_dir():
        for iface in sys_class_net.iterdir():
            addr_file = iface / "address"
            raw = _read_file_safely(addr_file)
            normalized = _normalize_mac(raw) if raw else None
            if normalized:
                macs.append(normalized)

    # Fallback de sécurité : au moins une MAC issue de uuid.getnode()
    if not macs:
        import uuid

        node = uuid.getnode()
        if (node >> 40) % 2 == 0:  # Vérifie si ce n'est pas un MAC aléatoire
            mac_hex = f"{node:012x}"
            normalized = _normalize_mac(mac_hex)
            if normalized:
                macs.append(normalized)

    macs = sorted(set(macs))
    return macs


def _collect_cpu_id() -> str:
    """
    Tente d'extraire un identifiant CPU stable.

    Sous Linux :
      - lecture de /proc/cpuinfo
      - éventuellement utilisation de lscpu
    Si rien de spécifique n'est trouvable, on hash le contenu brut de /proc/cpuinfo.
    """
    cpuinfo_path = Path("/proc/cpuinfo")
    cpuinfo = _read_file_safely(cpuinfo_path)

    if cpuinfo:
        # Pour certains processeurs (ARM), il existe un champ "Serial"
        for line in cpuinfo.splitlines():
            if ":" in line:
                key, value = [p.strip() for p in line.split(":", 1)]
                if key.lower() in ("serial", "processor serial", "cpu serial"):
                    if value:
                        return value

        # À défaut, on utilise un hash du contenu de /proc/cpuinfo
        return hashlib.sha256(cpuinfo.encode("utf-8", errors="ignore")).hexdigest()

    # Fallback : lscpu
    lscpu = _run_command(["lscpu"])
    if lscpu:
        return hashlib.sha256(lscpu.encode("utf-8", errors="ignore")).hexdigest()

    return ""


def _collect_dmidecode_uuid() -> str:
    """
    Tente de récupérer l'uuid système via dmidecode.

    Requiert généralement les privilèges root. En cas d'échec, retourne une chaîne vide.
    """
    dmidecode_output = _run_command(["dmidecode", "-s", "system-uuid"])
    if dmidecode_output:
        return dmidecode_output.strip()
    return ""


def collect_fingerprint_components() -> Dict[str, str]:
    """
    Collecte les composants bruts du fingerprint.

    Retourne un dict avec :
      - hostname
      - macs (liste jointe par ",")
      - cpu_id
      - dmidecode_uuid
    """
    hostname = socket.gethostname() or ""

    macs = _collect_mac_addresses()
    macs_joined = ",".join(macs)

    cpu_id = _collect_cpu_id()
    dmi_uuid = _collect_dmidecode_uuid()

    components = {
        "hostname": hostname,
        "macs": macs_joined,
        "cpu_id": cpu_id,
        "dmidecode_uuid": dmi_uuid,
    }

    logger.debug("Composants du fingerprint collectés: %s", components)
    return components


def _compute_fingerprint_string(components: Dict[str, str], salt: Optional[str] = None) -> str:
    """
    Construit la chaîne source du fingerprint à partir des composants + salt.

    Format déterministe et stable (ajouter des champs à la fin si besoin).
    """
    parts = [
        f"hostname={components.get('hostname', '')}",
        f"macs={components.get('macs', '')}",
        f"cpu_id={components.get('cpu_id', '')}",
        f"dmidecode_uuid={components.get('dmidecode_uuid', '')}",
    ]
    if salt:
        parts.append(f"salt={salt}")

    return "|".join(parts)


def _load_cached_fingerprint(cache_path: Path) -> Optional[str]:
    try:
        if cache_path.is_file():
            value = cache_path.read_text(encoding="utf-8").strip()
            if value:
                return value
    except Exception as exc:
        logger.debug("Impossible de charger le fingerprint cache (%s): %s", cache_path, exc)
    return None


def _store_cached_fingerprint(cache_path: Path, fingerprint: str) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(fingerprint + "\n", encoding="utf-8")
    except Exception as exc:
        logger.debug("Impossible d'écrire le fingerprint cache (%s): %s", cache_path, exc)


def generate_fingerprint(
    method: str = "default",
    salt: Optional[str] = None,
    cache_path: Optional[Path] = None,
    force_recompute: bool = False,
) -> str:
    """
    Génère un fingerprint déterministe de la machine (SHA256 hex).

    Paramètres :
      - method : pour le futur si d'autres stratégies sont nécessaires.
      - salt : sel optionnel pour différencier environnements.
      - cache_path : si fourni, permet de mettre en cache / relire le fingerprint.
      - force_recompute : ignore le cache et recalcule si True.

    Retour :
      - Chaîne hexadécimale SHA256.

    Exceptions :
      - FingerprintError si un problème critique survient.
    """
    log_phase(logger, "fingerprint.compute", "Calcul du fingerprint serveur")

    if method != "default":
        logger.warning("Méthode de fingerprint inconnue '%s', fallback sur 'default'.", method)

    if cache_path and not force_recompute:
        cached = _load_cached_fingerprint(cache_path)
        if cached:
            logger.info("Fingerprint chargé depuis le cache : %s", cache_path)
            return cached

    try:
        components = collect_fingerprint_components()
        source = _compute_fingerprint_string(components, salt=salt)
        digest = hashlib.sha256(source.encode("utf-8", errors="ignore")).hexdigest()
        logger.info("Fingerprint généré (SHA256).")

        if cache_path:
            _store_cached_fingerprint(cache_path, digest)

        return digest
    except Exception as exc:
        logger.error("Erreur lors de la génération du fingerprint: %s", exc)
        raise FingerprintError(str(exc)) from exc
