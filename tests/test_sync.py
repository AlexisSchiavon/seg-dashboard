"""Tests for app/sync/jobs.py (sync_pipedrive job).

Wave 0 (this plan, Task 1): stub file with xfail-marked placeholders.
Task 2 of this plan implements app/sync/jobs.py and turns these into
real RED -> GREEN assertions (TDD).
"""
import pytest

from app.models import Deal, DealStageEvent, SyncLog


def test_sync_paginates_and_upserts_deals(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """PIPE-01: sync_pipedrive paginates /deals and upserts Deal rows."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    deals = db_session.query(Deal).all()
    assert {d.pipedrive_id for d in deals} == {1001, 1002, 1003}


def test_zero_value_deal_sin_cotizar(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """PIPE-03: deals with value $0 are classified is_sin_cotizar=True,
    and commission_amount = value * 0.70 (PIPE-02)."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    deal_zero = db_session.query(Deal).filter(Deal.pipedrive_id == 1002).one()
    assert deal_zero.is_sin_cotizar is True
    assert deal_zero.commission_amount == 0.0

    deal_priced = db_session.query(Deal).filter(Deal.pipedrive_id == 1001).one()
    assert deal_priced.commission_amount == deal_priced.value * 0.70


def test_talent_matched_via_pipedrive_product_id(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """Deal's Pipedrive product resolves to a talent via
    talent_products.pipedrive_product_id (PIPE-02)."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    deal_a = db_session.query(Deal).filter(Deal.pipedrive_id == 1001).one()
    deal_b = db_session.query(Deal).filter(Deal.pipedrive_id == 1002).one()
    deal_sin_talento = db_session.query(Deal).filter(Deal.pipedrive_id == 1003).one()

    assert deal_a.talent_id == seed_talent_products["talent_a"].id
    assert deal_b.talent_id == seed_talent_products["talent_b"].id
    # D-17: unmatched product -> talent_id stays NULL, deal still persists
    assert deal_sin_talento.talent_id is None


def test_first_sync_creates_no_stage_events(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """Pitfall 3: first sync of a deal (INSERT) must NOT create a
    DealStageEvent row. Only subsequent UPDATEs that change stage_id
    create stage events."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    events_after_first_sync = db_session.query(DealStageEvent).filter(
        DealStageEvent.deal_pipedrive_id.in_([1001, 1002, 1003])
    ).all()
    assert events_after_first_sync == []


def test_second_sync_with_stage_change_creates_one_event(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """A subsequent sync that changes a deal's stage_id creates exactly
    one DealStageEvent row (no duplicates, no spurious events for
    unchanged deals)."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    # Simulate a stage change on the next sync by mutating the mock payload's
    # stage_id for deal 1001 and re-running sync.
    from tests.conftest import PIPEDRIVE_DEALS_PAGE_1

    PIPEDRIVE_DEALS_PAGE_1["data"][0]["stage_id"] = 4
    PIPEDRIVE_DEALS_PAGE_1["data"][0]["update_time"] = "2026-06-05 10:00:00"

    jobs.sync_pipedrive(db_session)

    events = db_session.query(DealStageEvent).filter(
        DealStageEvent.deal_pipedrive_id == 1001
    ).all()
    assert len(events) == 1
    assert events[0].to_stage == "Contrato"


def test_concurrent_sync_is_noop(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """Pitfall 5: if a SyncLog with status="running" already exists,
    a second sync_pipedrive call is a no-op (returns without a second
    API fetch)."""
    from datetime import datetime, timezone

    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    running = SyncLog(source="pipedrive", started_at=datetime.now(timezone.utc), status="running")
    db_session.add(running)
    db_session.commit()

    result = jobs.sync_pipedrive(db_session)

    assert result.id == running.id
    assert result.status == "running"
    assert db_session.query(Deal).count() == 0


def test_stage_id_maps_to_one_of_six_funnel_stages(db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch):
    """PIPE-05: stage_id resolves to one of the 6 funnel stage names,
    in order (Llamada, Cotización, Negociación, Contrato, En ejecución,
    Cobranza)."""
    from app.sync import jobs
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    jobs.sync_pipedrive(db_session)

    valid_stages = {"Llamada", "Cotización", "Negociación", "Contrato", "En ejecución", "Cobranza"}
    deals = db_session.query(Deal).all()
    assert all(d.stage_name in valid_stages for d in deals)
