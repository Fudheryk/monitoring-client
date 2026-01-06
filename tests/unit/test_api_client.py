from unittest.mock import MagicMock, patch

import requests

from monitoring_client.core.api_client import APIClient, APIClientConfig


def test_api_client_success():
    cfg = APIClientConfig(
        base_url="http://localhost:8000", metrics_endpoint="/api", api_key_header="X-API", api_key="key"
    )

    client = APIClient(cfg)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch.object(client._session, "post", return_value=mock_resp):
        resp = client.send_payload({"a": 1})
        assert resp.status_code == 200
