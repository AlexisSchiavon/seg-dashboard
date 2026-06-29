"""Tests for app/services/funnel.py — funnel aggregation, bottleneck detection, activity feed."""

import pytest
from datetime import date, datetime, timedelta
from tests.conftest import TestSessionLocal
from app.services import funnel as funnel_service
from app.models import Deal, DealStageEvent, Talent, TrelloCard


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


# ---------------------------------------------------------------------------
# Fase 6 — Trello-sourced funnel stages (En ejecución / Cobranza)
# ---------------------------------------------------------------------------


def _deal(db, pid, value, talent_id=None, stage="Contrato", status="won"):
    d = Deal(
        pipedrive_id=pid, title=f"Deal {pid}", value=value, currency="MXN",
        stage_id=4, stage_name=stage, status=status, talent_id=talent_id,
        commission_amount=value * 0.7, is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _card(db, cid, list_state, deal_id=None):
    state_to_list = {"ejecucion": "Contrato", "cobranza": "Cobrar", "cerrado": "Finalizados"}
    c = TrelloCard(
        trello_card_id=cid, name=f"Card {cid}", list_id="L",
        list_name=state_to_list[list_state], list_state=list_state,
        deal_id=deal_id, collection_date=date(2026, 7, 1),
    )
    db.add(c)
    db.commit()
    return c


def test_funnel_counts_trello_cards(db_session):
    """6.1/D1/D5: En ejecución & Cobranza counts+amounts come from TrelloCard
    (linked Deal.value); 'cerrado' cards never enter the funnel."""
    de1 = _deal(db_session, 70001, 10000.0)
    de2 = _deal(db_session, 70002, 20000.0)
    dcob = _deal(db_session, 70003, 5000.0)
    dcer = _deal(db_session, 70004, 99999.0)
    _card(db_session, "c-e1", "ejecucion", de1.id)
    _card(db_session, "c-e2", "ejecucion", de2.id)
    _card(db_session, "c-cob", "cobranza", dcob.id)
    _card(db_session, "c-cer", "cerrado", dcer.id)  # must NOT appear in funnel

    stages = {s["stage"]: s for s in funnel_service.funnel_overview(db_session)["stages"]}

    assert stages["En ejecución"]["count"] == 2
    assert stages["En ejecución"]["amount"] == pytest.approx(30000.0)
    assert stages["Cobranza"]["count"] == 1
    assert stages["Cobranza"]["amount"] == pytest.approx(5000.0)
    # 'cerrado' is not a funnel stage and its value never leaks into the two Trello stages
    assert "Cerrado" not in stages
    assert stages["En ejecución"]["amount"] + stages["Cobranza"]["amount"] == pytest.approx(35000.0)


def test_funnel_orphan_cards_count_but_zero_amount(db_session):
    """6.1/D2: a card with no linked deal counts toward card_count but adds 0 amount."""
    d = _deal(db_session, 71001, 10000.0)
    _card(db_session, "c-linked", "ejecucion", d.id)
    _card(db_session, "c-orphan", "ejecucion", None)  # deal_id NULL

    stages = {s["stage"]: s for s in funnel_service.funnel_overview(db_session)["stages"]}
    assert stages["En ejecución"]["count"] == 2          # both cards counted
    assert stages["En ejecución"]["amount"] == pytest.approx(10000.0)  # orphan adds 0


def test_talent_funnel_includes_trello_filtered_by_talent(db_session):
    """6.1/D4: per-talent funnel shows only cards whose deal belongs to that talent;
    orphan cards and other talents' cards are excluded."""
    ta = Talent(name="Talento Trello A", active=True)
    tb = Talent(name="Talento Trello B", active=True)
    db_session.add_all([ta, tb])
    db_session.commit()
    db_session.refresh(ta)
    db_session.refresh(tb)

    da = _deal(db_session, 72001, 10000.0, talent_id=ta.id)
    db_ = _deal(db_session, 72002, 50000.0, talent_id=tb.id)
    _card(db_session, "c-a", "ejecucion", da.id)
    _card(db_session, "c-b", "ejecucion", db_.id)
    _card(db_session, "c-orphan2", "ejecucion", None)

    a_stages = {s["stage"]: s for s in funnel_service.talent_funnel(db_session, ta.id)}
    assert a_stages["En ejecución"]["count"] == 1            # only talent A's card
    assert a_stages["En ejecución"]["amount"] == pytest.approx(10000.0)

    b_stages = {s["stage"]: s for s in funnel_service.talent_funnel(db_session, tb.id)}
    assert b_stages["En ejecución"]["count"] == 1
    assert b_stages["En ejecución"]["amount"] == pytest.approx(50000.0)


def test_bottleneck_handles_zero_count_trello_stage(db_session):
    """6.1/D3: bottleneck recalculates over all 6 stages without crashing when a
    Trello stage has count=0 (new talent / no cobranza cards yet)."""
    # >=10 deals across Pipedrive stages to pass the sample-size gate
    pid = 73000
    for stage, n in {"Llamada": 5, "Cotización": 3, "Negociación": 2}.items():
        for _ in range(n):
            _deal(db_session, pid, 10000.0, stage=stage, status="open")
            pid += 1
    # ejecucion cards exist, but ZERO cobranza cards -> Cobranza count stays 0
    de = _deal(db_session, 73900, 15000.0)
    _card(db_session, "c-exec", "ejecucion", de.id)

    result = funnel_service.funnel_overview(db_session)
    stages = {s["stage"]: s for s in result["stages"]}
    assert stages["En ejecución"]["count"] == 1
    assert stages["Cobranza"]["count"] == 0          # zero-count Trello stage
    assert result["insufficient_data"] is False
    # Must not raise and must produce a valid bottleneck (or None) — no ZeroDivision
    if result["bottleneck"] is not None:
        assert 0.0 <= result["bottleneck"]["conversion_pct"] <= 100.0
