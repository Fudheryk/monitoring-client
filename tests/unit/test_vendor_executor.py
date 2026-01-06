from pathlib import Path

from monitoring_client.vendors.executor import CommandExecutor
from monitoring_client.vendors.parser import VendorMetric


def test_executor_basic():
    """
    Vérifie qu'une commande simple est exécutée correctement par CommandExecutor,
    et que la valeur retournée est bien parsée en fonction de metric.type.
    """
    exec = CommandExecutor()

    metric = VendorMetric(
        vendor="acme",
        group_name="test",
        name="test.metric",
        command="echo 42",
        language="bash",
        type="numeric",
        description="Test de métrique numérique",
        is_critical=False,
        source_file=Path("dummy.yaml"),
        raw_metric={},
    )

    # On demande l'exécution avec parsing numeric
    value = exec.execute_metric(metric, timeout=2.0)

    # La valeur doit être bien parsée en int/float, pas en string
    assert value == 42 or value == 42.0
