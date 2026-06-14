"""Tests for app/services/funnel.py — funnel aggregation, bottleneck detection, activity feed."""

import pytest
from datetime import datetime, timedelta
from tests.conftest import TestSessionLocal
from app.services import funnel as funnel_service
from app.models import Deal, DealStageEvent, Talent


CANONICAL_STAGES = [
    "Llamada",
    "Cotización",
    "Negociación",
    "Contrato",
    "En ejecución",
    "Cobranza",
]


# ---------------------------------------------------------------------------
# test_stage_mapping — all 6 stages returned in canonical order
# ---------------------------------------------------------------------------

def test_stage_mapping(seed_deals):
    """funnel_overview returns exactly 6 stages in canonical order (PIPE-05)."""
    db = TestSessionLocal()
    try:
        result = funnel_service.funnel_overview(db)
        stage_names = [s["stage"] for s in result["stages"]]
        assert stage_names == CANONICAL_STAGES, (
            f"Stage order mismatch: {stage_names}"
        )
        assert len(result["stages"]) == 6
    finally:
        db.close()


def test_stages_with_zero_count(db_session):
    """Stages with no deals still appear (count 0, amount 0.0) — never omitted."""
    # Only add a deal in Llamada — other 5 stages should be 0
    deal = Deal(
        pipedrive_id=8001,
        title="Solo Llamada",
        value=5000.0,
        currency="MXN",
        stage_id=6,
        stage_name="Llamada",
        status="open",
        talent_id=None,
        commission_amount=3500.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db_session.add(deal)
    db_session.commit()

    result = funnel_service.funnel_overview(db_session)
    assert len(result["stages"]) == 6
    for stage_bucket in result["stages"]:
        if stage_bucket["stage"] != "Llamada":
            assert stage_bucket["count"] == 0
            assert stage_bucket["amount"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# test_bottleneck_detection
# ---------------------------------------------------------------------------

def test_bottleneck_insufficient_data(seed_deals):
    """With <10 total deals, bottleneck is None and insufficient_data is True."""
    db = TestSessionLocal()
    try:
        result = funnel_service.funnel_overview(db)
        # seed_deals has 4 deals — below 10-deal threshold
        assert result["insufficient_data"] is True
        assert result["bottleneck"] is None
    finally:
        db.close()


def test_bottleneck_detection(db_session):
    """With >=10 deals, funnel_overview flags the lowest conversion pair."""
    # Create 12 deals across stages to trigger bottleneck detection
    stage_counts = {
        "Llamada": 5,
        "Cotización": 3,
        "Negociación": 1,  # big drop from Cotización → Negociación
        "Contrato": 1,
        "En ejecución": 0,
        "Cobranza": 0,
    }
    pipedrive_id_counter = 5000
    for stage_name, count in stage_counts.items():
        for i in range(count):
            deal = Deal(
                pipedrive_id=pipedrive_id_counter,
                title=f"Deal {stage_name} {i}",
                value=10000.0,
                currency="MXN",
                stage_id=1,
                stage_name=stage_name,
                status="open",
                talent_id=None,
                commission_amount=7000.0,
                is_sin_cotizar=False,
                update_time="2026-06-01T10:00:00Z",
            )
            db_session.add(deal)
            pipedrive_id_counter += 1

    db_session.commit()

    result = funnel_service.funnel_overview(db_session)
    # 5+3+1+1 = 10 deals (>= 10), bottleneck should be detected
    assert result["insufficient_data"] is False
    assert result["bottleneck"] is not None
    bn = result["bottleneck"]
    assert "stage_a" in bn
    assert "stage_b" in bn
    assert "conversion_pct" in bn
    assert 0.0 <= bn["conversion_pct"] <= 100.0


# ---------------------------------------------------------------------------
# test_recent_activity_order
# ---------------------------------------------------------------------------

def test_recent_activity_order(db_session):
    """recent_activity returns DealStageEvents ordered by detected_at desc, limit 20."""
    talent = Talent(name="Talento Actividad", active=True, category="Tech")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    base_time = datetime(2026, 6, 1, 12, 0, 0)
    events = []
    for i in range(5):
        deal = Deal(
            pipedrive_id=6000 + i,
            title=f"Deal Actividad {i}",
            value=float(1000 * (i + 1)),
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent.id,
            commission_amount=700.0,
            is_sin_cotizar=False,
            update_time="2026-06-01T10:00:00Z",
        )
        db_session.add(deal)
        db_session.commit()
        db_session.refresh(deal)

        event = DealStageEvent(
            deal_pipedrive_id=deal.pipedrive_id,
            talent_id=talent.id,
            from_stage="Llamada",
            to_stage="Cotización",
            from_status="open",
            to_status="open",
            detected_at=base_time + timedelta(hours=i),
        )
        db_session.add(event)
        events.append(event)

    db_session.commit()

    activity = funnel_service.recent_activity(db_session, limit=20)
    # Should be ordered most recent first
    assert len(activity) == 5
    detected_times = [item["detected_at"] for item in activity]
    assert detected_times == sorted(detected_times, reverse=True)


def test_recent_activity_limit(db_session):
    """recent_activity respects the limit parameter."""
    talent = Talent(name="Talento Limit", active=True, category="Gaming")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    base_time = datetime(2026, 6, 1, 12, 0, 0)
    for i in range(25):
        deal = Deal(
            pipedrive_id=4000 + i,
            title=f"Deal {i}",
            value=1000.0,
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent.id,
            commission_amount=700.0,
            is_sin_cotizar=False,
            update_time="2026-06-01T10:00:00Z",
        )
        db_session.add(deal)
        db_session.commit()
        db_session.refresh(deal)

        event = DealStageEvent(
            deal_pipedrive_id=deal.pipedrive_id,
            talent_id=talent.id,
            from_stage=None,
            to_stage="Llamada",
            from_status=None,
            to_status="open",
            detected_at=base_time + timedelta(minutes=i),
        )
        db_session.add(event)

    db_session.commit()

    activity_20 = funnel_service.recent_activity(db_session, limit=20)
    assert len(activity_20) == 20

    activity_5 = funnel_service.recent_activity(db_session, limit=5)
    assert len(activity_5) == 5


def test_recent_activity_returns_deal_title_and_talent(db_session):
    """Each activity item has title, to_stage, talent_name, detected_at fields."""
    talent = Talent(name="Talento Check", active=True, category="Lifestyle")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    deal = Deal(
        pipedrive_id=3001,
        title="Mi Deal",
        value=5000.0,
        currency="MXN",
        stage_id=2,
        stage_name="Cotización",
        status="open",
        talent_id=talent.id,
        commission_amount=3500.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)

    event = DealStageEvent(
        deal_pipedrive_id=deal.pipedrive_id,
        talent_id=talent.id,
        from_stage="Llamada",
        to_stage="Cotización",
        from_status="open",
        to_status="open",
        detected_at=datetime(2026, 6, 10, 12, 0, 0),
    )
    db_session.add(event)
    db_session.commit()

    activity = funnel_service.recent_activity(db_session)
    assert len(activity) == 1
    item = activity[0]
    assert item["title"] == "Mi Deal"
    assert item["to_stage"] == "Cotización"
    assert item["talent_name"] == "Talento Check"
    assert item["detected_at"] == datetime(2026, 6, 10, 12, 0, 0)


# ---------------------------------------------------------------------------
# Per-talent funnel tests (Plan 02-03)
# ---------------------------------------------------------------------------

def test_talent_funnel_filters(db_session):
    """Per-talent funnel returns 6 STAGES in order with counts from ONLY that talent's open deals."""
    talent_a = Talent(name="Talento Funnel A", active=True, category="Lifestyle")
    talent_b = Talent(name="Talento Funnel B", active=True, category="Gaming")
    db_session.add_all([talent_a, talent_b])
    db_session.commit()
    db_session.refresh(talent_a)
    db_session.refresh(talent_b)

    # Talent A: 2 open deals in Llamada
    for pid in [30001, 30002]:
        db_session.add(Deal(
            pipedrive_id=pid,
            title=f"Deal A {pid}",
            value=10000.0,
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent_a.id,
            commission_amount=7000.0,
            is_sin_cotizar=False,
            update_time="2026-06-01T10:00:00Z",
        ))

    # Talent B: 1 open deal in Cotización (must not appear in talent_a's funnel)
    db_session.add(Deal(
        pipedrive_id=30003,
        title="Deal B 30003",
        value=15000.0,
        currency="MXN",
        stage_id=2,
        stage_name="Cotización",
        status="open",
        talent_id=talent_b.id,
        commission_amount=10500.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    ))
    db_session.commit()

    result = funnel_service.talent_funnel(db_session, talent_a.id)

    # Must return exactly 6 stages in canonical order
    stage_names = [s["stage"] for s in result]
    assert stage_names == CANONICAL_STAGES, f"Stage order mismatch: {stage_names}"
    assert len(result) == 6

    # Talent A has 2 deals in Llamada — only Llamada should have count=2
    stage_map = {s["stage"]: s for s in result}
    assert stage_map["Llamada"]["count"] == 2
    # Cotización must be 0 — talent_b's deal must NOT be counted
    assert stage_map["Cotización"]["count"] == 0


def test_recent_activity_sin_talento(db_session):
    """Activity items with no talent assigned use 'Sin talento' as talent_name."""
    deal = Deal(
        pipedrive_id=3002,
        title="Deal sin talento",
        value=8000.0,
        currency="MXN",
        stage_id=3,
        stage_name="Negociación",
        status="open",
        talent_id=None,
        commission_amount=5600.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db_session.add(deal)
    db_session.commit()
    db_session.refresh(deal)

    event = DealStageEvent(
        deal_pipedrive_id=deal.pipedrive_id,
        talent_id=None,
        from_stage=None,
        to_stage="Negociación",
        from_status=None,
        to_status="open",
        detected_at=datetime(2026, 6, 11, 9, 0, 0),
    )
    db_session.add(event)
    db_session.commit()

    activity = funnel_service.recent_activity(db_session)
    assert len(activity) == 1
    assert activity[0]["talent_name"] == "Sin talento"
