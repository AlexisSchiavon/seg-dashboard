"""Flow test for auto-create reconciliation. Uses the db_session test-engine
fixture (dual-engine harness gotcha) — sync_trello receives the test db session."""
from datetime import datetime, timezone

import pytest

from app.integrations import trello
from app.models import Deal, Talent, TrelloCard
from app.sync import jobs


@pytest.fixture
def _enable_autocreate(monkeypatch):
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTO_CREATE_ENABLED", True)
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    monkeypatch.setattr(jobs.settings, "PIPEDRIVE_DOMAIN", "talentagency")


def _stub_trello(monkeypatch, created, existing_marker_ids=None):
    # No live cards synced (empty lists) unless overridden.
    monkeypatch.setattr(trello, "get_list_cards", lambda client, list_id: [])
    monkeypatch.setattr(
        trello, "list_marker_pipedrive_ids",
        lambda client, list_id: set(existing_marker_ids or []),
    )

    def fake_create(client, list_id, name, desc="", due=None):
        card = {"id": f"card_{len(created) + 1}", "name": name, "desc": desc,
                "due": due, "idList": list_id}
        created.append(card)
        return card

    monkeypatch.setattr(trello, "create_card", fake_create)


def test_creates_card_for_won_deal_without_card(db_session, monkeypatch, _enable_autocreate):
    t = Talent(name="Emicanico")
    db_session.add(t)
    db_session.flush()
    d = Deal(pipedrive_id=526, title="Embajador Plata - Emicanico", value=1500000.0,
             currency="MXN", stage_id=9, stage_name="Contrato", status="won",
             talent_id=t.id, update_time="2026-07-13T00:00:00Z",
             won_time=datetime(2026, 7, 13, tzinfo=timezone.utc))
    db_session.add(d)
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created)

    jobs.sync_trello(db_session)

    assert len(created) == 1
    assert created[0]["name"] == "Embajador Plata - Emicanico"
    assert "[seg:deal_id=526]" in created[0]["desc"]
    assert created[0]["due"] is None  # no due date invented
    row = db_session.query(TrelloCard).filter_by(pipedrive_deal_id_desc=526).first()
    assert row is not None and row.deal_id == d.id


def test_idempotent_second_run_creates_nothing(db_session, monkeypatch, _enable_autocreate):
    d = Deal(pipedrive_id=488, title="Nestle x MS", value=255000.0, currency="MXN",
             stage_id=9, stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-06-16T00:00:00Z",
             won_time=datetime(2026, 6, 16, tzinfo=timezone.utc))
    db_session.add(d)
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    jobs.sync_trello(db_session)  # second run
    assert len(created) == 1  # exactly one card total


def test_skips_when_live_marker_already_present(db_session, monkeypatch, _enable_autocreate):
    d = Deal(pipedrive_id=551, title="Underarmour x EM", value=345000.0, currency="MXN",
             stage_id=9, stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-07-06T00:00:00Z",
             won_time=datetime(2026, 7, 6, tzinfo=timezone.utc))
    db_session.add(d)
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created, existing_marker_ids={551})  # exists live, not in DB
    jobs.sync_trello(db_session)
    assert len(created) == 0  # live-marker idempotency prevented duplicate


def test_disabled_flag_creates_nothing(db_session, monkeypatch):
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTO_CREATE_ENABLED", False)
    d = Deal(pipedrive_id=999, title="X", value=1.0, currency="MXN", stage_id=9,
             stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-07-06T00:00:00Z",
             won_time=datetime(2026, 7, 6, tzinfo=timezone.utc))
    db_session.add(d)
    db_session.commit()
    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    assert len(created) == 0
