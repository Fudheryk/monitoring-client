from src.core.fingerprint import generate_fingerprint


def test_fingerprint_deterministic(tmp_path):
    fp1 = generate_fingerprint(cache_path=tmp_path / "fp")
    fp2 = generate_fingerprint(cache_path=tmp_path / "fp")
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA256 hex
