from pathlib import Path

from monitoring_client.vendors.parser import VendorMetric, VendorParser


def test_parse_valid_vendor(tmp_path):
    """
    Cas nominal : un fichier vendor valide doit produire exactement 1 VendorMetric
    avec tous les champs correctement mappés (y compris description / is_critical).
    """
    vendor_file = tmp_path / "nginx.yaml"
    vendor_file.write_text(
        """
metadata:
  vendor: acme.nginx
  language: bash

metrics:
  - name: nginx.requests
    command: "echo 1"
    type: numeric
    group_name: nginx
    description: "Nombre de requêtes nginx par seconde"
    is_critical: true
"""
    )

    parser = VendorParser(tmp_path)
    res = parser.parse_all()

    # On doit avoir exactement 1 métrique parsée
    assert len(res) == 1

    m: VendorMetric = res[0]
    assert m.vendor == "acme.nginx"
    assert m.group_name == "nginx"
    assert m.name == "nginx.requests"
    assert m.command == "echo 1"
    assert m.language == "bash"
    assert m.type == "numeric"
    # Champs spécifiques aux vendors
    assert m.description == "Nombre de requêtes nginx par seconde"
    assert m.is_critical is True
    # Le fichier source doit être bien renseigné
    assert isinstance(m.source_file, Path)
    assert m.source_file.name == "nginx.yaml"


def test_invalid_vendor_schema_is_ignored(tmp_path, caplog):
    """
    Un fichier vendor invalide (ex: sans champ 'name') doit être ignoré
    et ne produire aucune métrique.
    """
    invalid_file = tmp_path / "broken.yaml"
    invalid_file.write_text(
        """
metadata:
  vendor: acme.invalid

metrics:
  - command: "echo 1"
    type: numeric
    group_name: test
    description: "métrique invalide"
    is_critical: false
"""
    )

    parser = VendorParser(tmp_path)
    res = parser.parse_all()

    # Pas de métriques retournées
    assert res == [] or len(res) == 0

    # Optionnel : vérifier qu'un warning a été loggé
    assert any("Fichier vendor ignoré" in msg for msg in caplog.text.splitlines())
