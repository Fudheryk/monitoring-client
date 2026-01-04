import os
from pathlib import Path
from src.core.config_loader import ConfigLoader, ConfigError

def test_config_loader_ok(tmp_path):
    config_path = tmp_path / "config.yaml"
    schema_path = Path("config/config.schema.json")

    config_path.write_text("""
client:
  name: test-client
  version: "0.1"
  schema_version: "1.0"
api:
  base_url: "http://localhost:8000"
  metrics_endpoint: "/api"
  timeout_seconds: 1
  max_retries: 1
  api_key_header: "X-API"
  api_key_file: "foo"
paths:
  builtin_collectors_dir: "x"
  vendors_dir: "y"
  data_dir: "z"
machine:
  hostname_source: "system"
fingerprint:
  method: "default"
  force_recompute: false
  cache_file: "fp"
logging:
  level: "INFO"
  format: "plain"
  console_enabled: true
  file_enabled: false
""")
    api_key_file = tmp_path / "foo"
    api_key_file.write_text("dummy-key")

    loader = ConfigLoader(config_path=config_path, schema_path=schema_path, base_dir=tmp_path)
    cfg = loader.load()
    assert cfg.client.name == "test-client"
    assert cfg.resolved_api_key == "dummy-key"


def test_config_loader_missing_file():
    loader = ConfigLoader(config_path=Path("missing.yaml"))
    try:
        loader.load()
    except ConfigError:
        assert True
