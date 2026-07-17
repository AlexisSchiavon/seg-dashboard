"""Tests for the targeted backfill script (app/scripts/backfill_trello_cards.py)."""
from datetime import datetime, timezone

import pytest

from app.integrations import trello
from app.models import AuditLog, Deal, Talent, TrelloCard
from app.scripts import backfill_trello_cards as bf


@pytest.fixture
def _cfg(monkeypatch):
    monkeypatch.setattr(bf.settings, "TRELLO_AUTO_CREATE_ENABLED", True)
    monkeypatch.setattr(bf.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    monkeypatch.setattr(bf.settings, "PIPEDRIVE_DOMAIN", "talentagency")


def _stub_trello(monkeypatch, created, existing_marker_ids=None):
    monkeypatch.setattr(
        trello, "list_marker_pipedrive_ids",
        lambda client, list_id: set(existing_marker_ids or []),
    )

    def fake_create(client, list_id, name, desc="", due=None):
        card = {"id": f"card_{len(created) + 1}", "name": name, "desc": desc,
                "due": due, "shortUrl": f"https://trello.com/c/x{len(created) + 1}"}
        created.append(card)
        return card

    monkeypatch.setattr(trello, "create_card", fake_create)


def _seed(db, pid, title, talent_id=None, value=1000.0):
    d = Deal(pipedrive_id=pid, title=title, value=value, currency="MXN", stage_id=9,
             stage_name="Contrato", status="won", talent_id=talent_id,
             update_time="2026-07-06T00:00:00Z",
             won_time=datetime(2026, 7, 6, tzinfo=timezone.utc))
    db.add(d)
    db.commit()
    return d


def test_dry_run_creates_nothing(db_session, monkeypatch, _cfg):
    _seed(db_session, 488, "Nestle x MS")
    created = []
    _stub_trello(monkeypatch, created)
    summary = bf.run_backfill(db_session, client=None, pipedrive_ids=[488], confirm=False, out=lambda s: None)
    assert created == []
    assert summary["created"] == []
    assert db_session.query(TrelloCard).count() == 0


def test_confirm_creates_card_audit_and_registry(db_session, monkeypatch, _cfg):
    t = Talent(name="Mariana Sanchez")
    db_session.add(t)
    db_session.flush()
    _seed(db_session, 488, "Nestle x MS", talent_id=t.id, value=255000.0)
    created = []
    _stub_trello(monkeypatch, created)

    summary = bf.run_backfill(db_session, client=None, pipedrive_ids=[488], confirm=True, out=lambda s: None)

    assert summary["created"] == [488]
    assert len(created) == 1
    assert "Mariana Sanchez" in created[0]["desc"]
    assert "[seg:deal_id=488]" in created[0]["desc"]
    row = db_session.query(TrelloCard).filter_by(pipedrive_deal_id_desc=488).one()
    assert row.list_name == "Contrato"
    audit = db_session.query(AuditLog).filter_by(action_type="TRELLO_CARD_CREATED").one()
    assert audit.actor == "backfill-script"


def test_talent_from_db_null_shows_sin_talento(db_session, monkeypatch, _cfg):
    # pid=519 style: talent_id NULL locally → desc must say "Sin talento asignado"
    # (no hardcode). In prod the same code reads the real talent_id.
    _seed(db_session, 519, "Leche San Juan x Elisa M", talent_id=None, value=35000.0)
    created = []
    _stub_trello(monkeypatch, created)
    bf.run_backfill(db_session, client=None, pipedrive_ids=[519], confirm=True, out=lambda s: None)
    assert "Sin talento asignado" in created[0]["desc"]


def test_idempotent_when_marker_present(db_session, monkeypatch, _cfg):
    _seed(db_session, 526, "Embajador Plata - Emicanico")
    created = []
    _stub_trello(monkeypatch, created, existing_marker_ids={526})
    summary = bf.run_backfill(db_session, client=None, pipedrive_ids=[526], confirm=True, out=lambda s: None)
    assert created == []
    assert summary["skipped_existing"] == [526]


def test_missing_deal_is_skipped(db_session, monkeypatch, _cfg):
    created = []
    _stub_trello(monkeypatch, created)
    summary = bf.run_backfill(db_session, client=None, pipedrive_ids=[99999], confirm=True, out=lambda s: None)
    assert summary["skipped_missing"] == [99999]
    assert created == []
