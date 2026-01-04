from unittest.mock import patch

from src.main import main


def test_cli_dry_run():
    with patch("sys.argv", ["monitoring-client", "--dry-run"]):
        code = main()
        assert code == 0
