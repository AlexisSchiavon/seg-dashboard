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


def test_trigger_sync_requires_auth(client):
    """POST /sync/pipedrive is auth-protected (401 without a session)."""
    response = client.post("/sync/pipedrive")

    assert response.status_code == 401


def test_trigger_sync_returns_202(auth_client):
    """POST /sync/pipedrive schedules a background sync and returns 202 (D-22/D-23)."""
    response = auth_client.post("/sync/pipedrive")

    assert response.status_code == 202
    assert response.json()["status"] in {"accepted", "already_running"}


def test_sync_status_endpoint(auth_client):
    """GET /sync/status returns the latest SyncLog shape for the
    "Última sync" indicator (D-21) and D-24 failure banner."""
    response = auth_client.get("/sync/status")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "records_synced" in body
    assert "error_message" in body


# ---------------------------------------------------------------------------
# 5.3 — won_time (Pipedrive v2 close-of-contract timestamp)
# ---------------------------------------------------------------------------


def test_parse_pipedrive_datetime_handles_formats():
    """5.3: _parse_pipedrive_datetime normalizes Pipedrive timestamp shapes to
    timezone-aware UTC, and returns None for empty/unparseable input."""
    from datetime import timezone

    from app.sync.jobs import _parse_pipedrive_datetime

    assert _parse_pipedrive_datetime(None) is None
    assert _parse_pipedrive_datetime("") is None
    assert _parse_pipedrive_datetime("not-a-date") is None

    # "Z" suffix -> UTC
    z = _parse_pipedrive_datetime("2026-06-15T10:30:00Z")
    assert z is not None and z.tzinfo is not None
    assert z.utcoffset() == timezone.utc.utcoffset(None)
    assert (z.year, z.month, z.day, z.hour, z.minute) == (2026, 6, 15, 10, 30)

    # Space separator (v1-shaped) -> assumed UTC
    s = _parse_pipedrive_datetime("2026-06-15 10:30:00")
    assert s is not None and s.tzinfo is not None
    assert s.utcoffset() == timezone.utc.utcoffset(None)

    # Explicit offset preserved as an instant
    o = _parse_pipedrive_datetime("2026-06-15T10:30:00+00:00")
    assert o == z


def test_sync_persists_won_time_for_won_deals(
    db_session, seed_talent_products, mock_pipedrive_transport, monkeypatch
):
    """5.3: a won deal carrying won_time is persisted as a tz-aware datetime;
    a deal without won_time keeps won_time NULL."""
    from datetime import timezone

    import httpx

    from app.integrations import pipedrive
    from app.sync import jobs

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    won_deal = {
        "id": 2001,
        "title": "Contrato firmado",
        "value": 100000,
        "currency": "MXN",
        "stage_id": 4,  # Contrato
        "status": "won",
        "update_time": "2026-06-15 11:00:00",
        "add_time": "2026-06-01 09:00:00",
        "won_time": "2026-06-15T10:30:00Z",
        "custom_fields": {},
    }
    open_deal = {
        "id": 2002,
        "title": "En negociación",
        "value": 50000,
        "currency": "MXN",
        "stage_id": 3,
        "status": "open",
        "update_time": "2026-06-16 11:00:00",
        "add_time": "2026-06-02 09:00:00",
        "won_time": None,
        "custom_fields": {},
    }
    monkeypatch.setattr(
        pipedrive, "get_deals", lambda client, updated_since=None: iter([won_deal, open_deal])
    )

    jobs.sync_pipedrive(db_session)

    from datetime import datetime

    won = db_session.query(Deal).filter(Deal.pipedrive_id == 2001).one()
    assert won.won_time is not None
    # SQLite has no native tz storage: DateTime(timezone=True) round-trips naive.
    # The parser normalized to UTC before persisting, so the stored instant is
    # 10:30 UTC (this is exactly the mechanism behind the 5.5.2 sync-pill bug).
    assert won.won_time.replace(tzinfo=None) == datetime(2026, 6, 15, 10, 30)

    still_open = db_session.query(Deal).filter(Deal.pipedrive_id == 2002).one()
    assert still_open.won_time is None


# ---------------------------------------------------------------------------
# 5.5.2 — "Última sync: hace 0 min" (timezone serialization)
# ---------------------------------------------------------------------------


def test_sync_status_serializes_timestamps_as_utc_with_offset():
    """5.5.2: a naive (SQLite-stored) UTC timestamp must serialize WITH an
    explicit offset, so the frontend stops parsing it as local time."""
    from datetime import datetime, timezone

    from app.schemas.sync import SyncStatus

    naive_utc = datetime(2026, 6, 25, 14, 0, 0)  # how SQLite returns it
    payload = SyncStatus(
        status="success", started_at=naive_utc, finished_at=naive_utc, records_synced=5
    ).model_dump(mode="json")

    # Must carry an explicit UTC offset (not a bare naive string)
    assert payload["finished_at"].endswith("+00:00")
    assert payload["started_at"].endswith("+00:00")

    # And parse back to the exact UTC instant
    parsed = datetime.fromisoformat(payload["finished_at"])
    assert parsed == naive_utc.replace(tzinfo=timezone.utc)


def test_sync_status_serializes_none_timestamps():
    """5.5.2: missing timestamps stay null (no spurious offset)."""
    from app.schemas.sync import SyncStatus

    payload = SyncStatus().model_dump(mode="json")
    assert payload["started_at"] is None
    assert payload["finished_at"] is None
