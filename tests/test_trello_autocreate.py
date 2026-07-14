import httpx
import pytest

from app.integrations import trello


def test_allowed_create_list_ids_defaults_to_contrato(monkeypatch):
    monkeypatch.setattr(trello.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    ids = trello.allowed_create_list_ids()
    assert trello.CONTRATO_LIST_ID in ids


def test_allowed_create_list_ids_includes_sandbox_override(monkeypatch):
    monkeypatch.setattr(trello.settings, "TRELLO_AUTOCREATE_LIST_ID", "sandbox999")
    ids = trello.allowed_create_list_ids()
    assert "sandbox999" in ids
    assert trello.CONTRATO_LIST_ID in ids


def test_create_card_rejects_non_whitelisted_list(monkeypatch):
    monkeypatch.setattr(trello.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    client = httpx.Client(base_url=trello.BASE_URL)
    with pytest.raises(ValueError, match="not in the auto-create whitelist"):
        trello.create_card(client, "NOT_ALLOWED_LIST", "Some Deal")
    client.close()


def test_list_marker_pipedrive_ids_parses_markers(monkeypatch):
    fake_cards = [
        {"id": "a", "name": "Deal A", "desc": "[seg:deal_id=526]\n\nmonto..."},
        {"id": "b", "name": "Deal B", "desc": "no marker here"},
        {"id": "c", "name": "Deal C", "desc": "[seg:deal_id=488]"},
    ]
    monkeypatch.setattr(trello, "get_list_cards", lambda client, list_id: fake_cards)
    got = trello.list_marker_pipedrive_ids(client=None, list_id="whatever")
    assert got == {526, 488}
