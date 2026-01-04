from src.pipeline.transformer import PayloadTransformer, PayloadTransformerConfig


def test_transformer_basic():
    t = PayloadTransformer(PayloadTransformerConfig())
    payload = t.build_payload(
        metrics=[], hostname="test", os_name="linux", fingerprint="abc", timestamp_iso="2025-01-01T00:00:00Z"
    )
    assert payload["metadata"]["generator"] == "monitoring-client"
    assert payload["machine"]["hostname"] == "test"
