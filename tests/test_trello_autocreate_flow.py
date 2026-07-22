"""Flow test for auto-create reconciliation. Uses the db_session test-engine
fixture (dual-engine harness gotcha) — sync_trello receives the test db session."""
from datetime import datetime, timezone

import pytest

from app.integrations import trello
from app.models import AuditLog, Deal, Talent, TrelloCard
from app.sync import jobs


@pytest.fixture
def _enable_autocreate(monkeypatch):
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTO_CREATE_ENABLED", True)
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    monkeypatch.setattr(jobs.settings, "PIPEDRIVE_DOMAIN", "talentagency")
    # Permissive date floor so the reconciliation actually runs in these tests.
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_MIN_WON_DATE", "2000-01-01")


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


def test_min_won_date_unset_is_failsafe_creates_nothing(db_session, monkeypatch):
    """Fail-safe: flag ON but MIN_WON_DATE empty → reconciliation creates nothing."""
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTO_CREATE_ENABLED", True)
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_LIST_ID", "")
    monkeypatch.setattr(jobs.settings, "PIPEDRIVE_DOMAIN", "talentagency")
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_MIN_WON_DATE", "")  # unset
    d = Deal(pipedrive_id=700, title="Y", value=1.0, currency="MXN", stage_id=9,
             stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-07-06T00:00:00Z",
             won_time=datetime(2026, 7, 6, tzinfo=timezone.utc))
    db_session.add(d)
    db_session.commit()
    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    assert len(created) == 0


def test_deal_won_before_min_date_is_skipped(db_session, monkeypatch, _enable_autocreate):
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_MIN_WON_DATE", "2026-07-01")
    d = Deal(pipedrive_id=701, title="Old win", value=1.0, currency="MXN", stage_id=9,
             stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-06-16T00:00:00Z",
             won_time=datetime(2026, 6, 16, tzinfo=timezone.utc))  # before cutoff
    db_session.add(d)
    db_session.commit()
    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    assert len(created) == 0


def test_deal_won_on_or_after_min_date_is_created(db_session, monkeypatch, _enable_autocreate):
    monkeypatch.setattr(jobs.settings, "TRELLO_AUTOCREATE_MIN_WON_DATE", "2026-07-01")
    d = Deal(pipedrive_id=702, title="New win", value=1.0, currency="MXN", stage_id=9,
             stage_name="Contrato", status="won", talent_id=None,
             update_time="2026-07-06T00:00:00Z",
             won_time=datetime(2026, 7, 6, tzinfo=timezone.utc))  # after cutoff
    db_session.add(d)
    db_session.commit()
    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    assert len(created) == 1


def _won_deal(pid, title, value=100000.0):
    return Deal(pipedrive_id=pid, title=title, value=value, currency="MXN", stage_id=9,
                stage_name="Contrato", status="won", talent_id=None,
                update_time="2026-07-21T00:00:00Z",
                won_time=datetime(2026, 7, 21, tzinfo=timezone.utc))


# --- Fact-based idempotency: the three real prod scenarios ----------------

def test_maka_fuzzy_trellocard_link_does_not_block(db_session, monkeypatch, _enable_autocreate):
    """Maka 177: a preexisting card of a DIFFERENT campaign fuzzy-linked to this
    deal (trello_cards.deal_id set, no [seg] marker) must NOT block creation.
    Fuzzy similarity is no longer a skip criterion."""
    d = _won_deal(177, "Maka Octubre - Ds Dw", value=200000.0)
    db_session.add(d)
    db_session.flush()
    db_session.add(TrelloCard(
        trello_card_id="old_maka_card", name="Maka - DS y DW",
        list_id="listX", list_name="Enviar encuesta", list_state="cerrado",
        deal_id=d.id, pipedrive_deal_id_desc=None, collection_date=None,
    ))
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created)  # no live marker
    jobs.sync_trello(db_session)
    assert len(created) == 1
    assert created[0]["name"] == "Maka Octubre - Ds Dw"


def test_loreal_creates_even_when_unmarked_manual_card_exists(db_session, monkeypatch, _enable_autocreate):
    """Loreal 401: an unmarked manual card of the same campaign exists in another
    list. Accepted trade-off — the system still creates (a one-time duplicate TA
    can delete). Idempotency is fact-based, not similarity-based."""
    d = _won_deal(401, "Loreal x Talento")
    db_session.add(d)
    db_session.add(TrelloCard(
        trello_card_id="manual_loreal", name="Loreal — campaña previa",
        list_id="finalizados", list_name="Finalizados", list_state="cerrado",
        deal_id=None, pipedrive_deal_id_desc=None, collection_date=None,
    ))
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created)
    jobs.sync_trello(db_session)
    assert len(created) == 1  # accepted duplicate


def test_deleted_autocard_not_recreated_via_audit(db_session, monkeypatch, _enable_autocreate):
    """Leilani deleted the auto-card (421 Festival). The audit_log
    TRELLO_CARD_CREATED event is the durable fact — even with the card gone from
    Trello (no live marker), the system must NEVER recreate it."""
    d = _won_deal(421, "Festival x Talento", value=50000.0)
    db_session.add(d)
    db_session.add(AuditLog(
        action_type="TRELLO_CARD_CREATED", actor="system",
        entity_type="deal", entity_id="421",
    ))
    db_session.commit()

    created = []
    _stub_trello(monkeypatch, created)  # card deleted → no live marker
    jobs.sync_trello(db_session)
    assert len(created) == 0  # audit fact blocks recreation


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
