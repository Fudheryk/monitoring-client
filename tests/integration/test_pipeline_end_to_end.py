from pathlib import Path

from monitoring_client.collectors.loader import run_builtin_collectors
from monitoring_client.pipeline.aggregator import MetricsAggregator
from monitoring_client.pipeline.transformer import PayloadTransformer, PayloadTransformerConfig
from monitoring_client.pipeline.validator import PayloadValidator
from monitoring_client.vendors.executor import CommandExecutor
from monitoring_client.vendors.parser import VendorParser


def test_pipeline_end_to_end(tmp_path):
    # 1. builtin
    builtin = run_builtin_collectors()
    assert isinstance(builtin, list)

    # 2. vendor
    yaml_file = tmp_path / "vendor.yaml"
    yaml_file.write_text(
        """
metadata:
  vendor: test.vendor
  language: bash
metrics:
  - name: test.value
    command: "echo 5"
    type: numeric
    group_name: grp
"""
    )

    parser = VendorParser(tmp_path)
    vendor_docs = parser.parse_all()

    exec = CommandExecutor()
    vendor_metrics = []
    for vm in vendor_docs:
        v = exec.execute_metric(vm, timeout=2)
        vendor_metrics.append(
            {"name": vm.name, "value": v, "type": vm.type, "vendor": vm.vendor, "group_name": vm.group_name}
        )

    # 3. aggregation
    agg = MetricsAggregator()
    metrics = agg.aggregate(builtin, vendor_metrics)

    # 4. transform
    tr = PayloadTransformer(PayloadTransformerConfig())
    payload = tr.build_payload(
        metrics, hostname="test-host", os_name="linux", fingerprint="abc123", timestamp_iso="2025-06-01T00:00:00Z"
    )

    # 5. validate
    ok, errors = PayloadValidator().validate_payload(payload)

    assert ok
    assert errors == []
