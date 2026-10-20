def test_valid_input():
    assert Parser.decode("value") == "value"


def test_invalid_input():
    assert Parser.decode("invalid") == -1


def test_validation_ownership():
    assert Storage.validate("invalid") is False


def test_legacy_empty():
    assert Parser.decode("") == ""


def test_extra_feature():
    assert Parser.statistics_enabled() is True
