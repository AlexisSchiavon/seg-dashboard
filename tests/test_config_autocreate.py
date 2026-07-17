from app.config import Settings


def test_autocreate_defaults_are_safe():
    s = Settings(_env_file=None)
    # Kill switch defaults OFF so nothing writes to Trello until explicitly enabled.
    assert s.TRELLO_AUTO_CREATE_ENABLED is False
    # Empty target list means "use the code default (prod Contrato list)".
    assert s.TRELLO_AUTOCREATE_LIST_ID == ""
    # No date floor by default → automatic reconciliation is a no-op (fail-safe).
    assert s.TRELLO_AUTOCREATE_MIN_WON_DATE == ""


def test_autocreate_can_be_enabled_via_env(monkeypatch):
    monkeypatch.setenv("TRELLO_AUTO_CREATE_ENABLED", "true")
    monkeypatch.setenv("TRELLO_AUTOCREATE_LIST_ID", "sandbox123")
    s = Settings(_env_file=None)
    assert s.TRELLO_AUTO_CREATE_ENABLED is True
    assert s.TRELLO_AUTOCREATE_LIST_ID == "sandbox123"
