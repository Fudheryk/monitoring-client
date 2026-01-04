# tests/integration/test_vendor_bash_end_to_end.py

from __future__ import annotations

from pathlib import Path

from src.vendors.parser import VendorParser
from src.vendors.executor import CommandExecutor
from src.pipeline.validator import PayloadValidator


def test_vendor_bash_end_to_end(tmp_path):
    """
    Test d'intégration "réel" pour un vendor en bash :

    - crée un fichier vendors/demo_bash.yaml
    - parse le fichier
    - exécute les commandes via CommandExecutor
    - construit un payload minimal
    - valide le payload avec PayloadValidator
    - vérifie que description / is_critical sont présents pour les vendors
    """

    vendors_dir = tmp_path / "vendors"
    vendors_dir.mkdir()

    vendor_file = vendors_dir / "demo_bash.yaml"
    vendor_file.write_text(
        """
metadata:
  vendor: demo.bash
  language: bash

metrics:
  - name: demo.bash.hello
    command: 'echo "hello from vendor"'
    type: string
    group_name: demo
    description: "Message de démonstration renvoyé par un script bash"
    is_critical: false

  - name: demo.bash.unix_time
    command: 'date +%s'
    type: numeric
    group_name: demo
    description: "Timestamp Unix courant"
    is_critical: false

  - name: demo.bash.has_systemctl
    command: 'command -v systemctl >/dev/null 2>&1 && echo true || echo false'
    type: boolean
    group_name: demo
    description: "Indique si la commande systemctl est disponible"
    is_critical: false
""",
        encoding="utf-8",
    )

    # 1) Parser les vendors
    parser = VendorParser(vendors_dir)
    vendor_metrics = parser.parse_all()
    assert len(vendor_metrics) == 3

    # 2) Exécuter les métriques
    executor = CommandExecutor()
    metrics_payload = []

    for vm in vendor_metrics:
        value = executor.execute_metric(vm, timeout=2.0)
        # Pour le test, on veut que les commandes réussissent
        assert value is not None, f"Valeur None pour la métrique {vm.name}"

        metric_dict = {
            "name": vm.name,
            "value": value,
            "type": vm.type,
            "vendor": vm.vendor,
            "group_name": vm.group_name,
            # On veut vérifier que ces champs apparaissent bien
            "description": vm.description,
            "is_critical": vm.is_critical,
        }
        metrics_payload.append(metric_dict)

    # 3) Construire un payload complet minimal
    payload = {
        "metadata": {
            "generator": "test",
            "version": "0.0.0",
            "schema_version": "1.0",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        "machine": {
            "hostname": "test-host",
            "os": "linux",
            "fingerprint": "test-fingerprint",
        },
        "metrics": metrics_payload,
    }

    # 4) Validation du payload
    validator = PayloadValidator()
    ok, errors = validator.validate_payload(payload)
    assert ok, f"Payload invalide: {errors}"

    # 5) Vérifications ciblées sur les champs vendor
    hello = next(m for m in payload["metrics"] if m["name"] == "demo.bash.hello")
    assert hello["vendor"] == "demo.bash"
    assert hello["group_name"] == "demo"
    assert hello["description"]
    assert "is_critical" in hello
