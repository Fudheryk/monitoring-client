"""
Monitoring Client Package.

Client de monitoring système pour collecte et agrégation de métriques.
"""

from __future__ import annotations

try:
    # Option 1 : Importlib metadata (standard moderne)
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("monitoring-client")
    except PackageNotFoundError:
        # Fallback sur le fichier __version__.py
        from monitoring_client.__version__ import __version__
except ImportError:
    # Python < 3.8 : pas d'importlib.metadata
    from monitoring_client.__version__ import __version__

__all__ = ["__version__"]