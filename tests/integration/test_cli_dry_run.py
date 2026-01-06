from unittest.mock import patch

from monitoring_client.main import main


def test_cli_dry_run():
    with patch("sys.argv", ["monitoring-client", "--dry-run"]):
        code = main()
        assert code == 0
