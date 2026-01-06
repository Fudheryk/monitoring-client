from monitoring_client.pipeline.validator import PayloadValidator


def test_validator_ok():
    v = PayloadValidator()
    payload = {
        "metadata": {},
        "machine": {},
        "metrics": [
            {"name": "cpu.load", "value": 1.0, "type": "numeric"},
            {"name": "sys.flag", "value": True, "type": "boolean"},
            {"name": "str.x", "value": "ok", "type": "string"},
        ],
    }
    valid, errors = v.validate_payload(payload)
    assert valid
    assert errors == []


def test_validator_bad_name():
    v = PayloadValidator()
    payload = {"metadata": {}, "machine": {}, "metrics": [{"name": "bad name !", "value": 1, "type": "numeric"}]}
    valid, errors = v.validate_payload(payload)
    assert not valid
    assert len(errors) == 1
