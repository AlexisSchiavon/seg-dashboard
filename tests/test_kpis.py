"""Tests for app/services/kpis.py — global KPI and talent ranking aggregates."""

import pytest
from tests.conftest import TestSessionLocal
from app.services import kpis as kpi_service
from app.models import Deal, Talent, SyncLog
from datetime import datetime


# ---------------------------------------------------------------------------
# test_commission_calculation
# ---------------------------------------------------------------------------

def test_commission_calculation(seed_deals):
    """global_kpis returns Pipeline total = SUM(Deal.value) over ALL deals."""
    db = TestSessionLocal()
    try:
        result = kpi_service.global_kpis(db)
        # seed_deals has: 50000 + 0 + 20000 + 15000 = 85000
        pipeline_tile = next(t for t in result["kpis"] if t["label"] == "Pipeline total")
        assert pipeline_tile["value"] == pytest.approx(85000.0)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# test_global_includes_sin_talento
# ---------------------------------------------------------------------------

def test_global_includes_sin_talento(seed_deals):
    """Sin-talento bucket + per-talent revenues == global Pipeline total (Pitfall 4)."""
    db = TestSessionLocal()
    try:
        kpis = kpi_service.global_kpis(db)
        ranking = kpi_service.talent_ranking(db)

        pipeline_total = next(
            t["value"] for t in kpis["kpis"] if t["label"] == "Pipeline total"
        )

        # Sum all ranking rows (includes sin-talento bucket)
        ranking_total = sum(row["revenue"] for row in ranking)
        assert ranking_total == pytest.approx(pipeline_total), (
            f"ranking_total ({ranking_total}) != pipeline_total ({pipeline_total}) — "
            "Sin-talento deals must appear in both global KPI and ranking bucket"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# test_ranking_has_sin_talento_row
# ---------------------------------------------------------------------------

def test_ranking_has_sin_talento_row(seed_deals):
    """talent_ranking includes a 'Sin talento asignado' row when talent_id=None deals exist."""
    db = TestSessionLocal()
    try:
        ranking = kpi_service.talent_ranking(db)
        sin_talento_rows = [r for r in ranking if r["is_sin_talento"]]
        assert len(sin_talento_rows) == 1
        row = sin_talento_rows[0]
        assert row["name"] == "Sin talento asignado"
        assert row["revenue"] == pytest.approx(20000.0)
        assert row["deal_count"] == 1
        assert row["talent_id"] is None
        # Must be LAST row
        assert ranking[-1]["is_sin_talento"] is True
    finally:
        db.close()


def test_ranking_no_sin_talento_row_when_all_mapped(db_session):
    """talent_ranking omits the Sin-talento row when all deals have a talent."""
    talent = Talent(name="Talento Único", active=True, category="Lifestyle")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    deal = Deal(
        pipedrive_id=9001,
        title="Deal con talento",
        value=10000.0,
        currency="MXN",
        stage_id=1,
        stage_name="Llamada",
        status="open",
        talent_id=talent.id,
        commission_amount=7000.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db_session.add(deal)
    db_session.commit()

    ranking = kpi_service.talent_ranking(db_session)
    sin_talento_rows = [r for r in ranking if r["is_sin_talento"]]
    assert sin_talento_rows == [], "No sin-talento row when all deals have a talent"


# ---------------------------------------------------------------------------
# test_en_negociacion_kpi
# ---------------------------------------------------------------------------

def test_en_negociacion_kpi(seed_deals):
    """En negociación KPI counts/sums deals with stage_name=Negociación and status=open."""
    db = TestSessionLocal()
    try:
        result = kpi_service.global_kpis(db)
        tile = next(t for t in result["kpis"] if t["label"] == "En negociación")
        # seed_deals: deal_open is Negociación/open (50000), deal_lost is Negociación/lost (excluded)
        assert tile["value"] == pytest.approx(50000.0)
        assert tile["count"] == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# test_cerrados_kpi
# ---------------------------------------------------------------------------

def test_cerrados_kpi(seed_deals):
    """Cerrados KPI counts/sums deals with status=won."""
    db = TestSessionLocal()
    try:
        result = kpi_service.global_kpis(db)
        tile = next(t for t in result["kpis"] if t["label"] == "Cerrados")
        # seed_deals has 0 won deals
        assert tile["count"] == 0
        assert tile["value"] == pytest.approx(0.0)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# test_en_campana_kpi
# ---------------------------------------------------------------------------

def test_en_campana_kpi(db_session):
    """En campaña KPI counts deals with stage_name='En ejecución' and status=open."""
    deal = Deal(
        pipedrive_id=7001,
        title="Deal en campaña",
        value=30000.0,
        currency="MXN",
        stage_id=5,
        stage_name="En ejecución",
        status="open",
        talent_id=None,
        commission_amount=21000.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    )
    db_session.add(deal)
    db_session.commit()

    result = kpi_service.global_kpis(db_session)
    tile = next(t for t in result["kpis"] if t["label"] == "En campaña")
    assert tile["count"] == 1
    assert tile["value"] == pytest.approx(30000.0)


# ---------------------------------------------------------------------------
# test_empty_global_kpis
# ---------------------------------------------------------------------------

def test_empty_global_kpis(db_session):
    """global_kpis returns zeros when no deals exist."""
    result = kpi_service.global_kpis(db_session)
    assert len(result["kpis"]) == 4
    for tile in result["kpis"]:
        assert tile["value"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Per-talent KPI tests (Plan 02-03)
# ---------------------------------------------------------------------------

def test_talent_detail_only_own_deals(seed_deals):
    """talent_detail(db, talent_id) computes KPIs from ONLY that talent's deals.

    Deals for other talents and talent_id=None deals must be excluded (Pitfall 4).
    """
    db = TestSessionLocal()
    try:
        talent_a = seed_deals["deal_open"].talent_id  # talent_a's id
        result = kpi_service.talent_detail(db, talent_a)

        # seed_deals: deal_open (50000, open, talent_a), deal_lost (15000, lost, talent_a)
        # sin-cotizar deal and sin-talento deal must NOT appear
        kpi_dict = {kpi["label"]: kpi["value"] for kpi in result["kpis"]}

        # Pipeline = open deals only (WR-05 fix: lost deals excluded from pipeline).
        # seed_deals: deal_open (50000, open, talent_a), deal_lost (15000, lost, talent_a)
        # Lost deal must NOT appear in Pipeline; it is surfaced in lost_opportunities.
        assert kpi_dict["Pipeline"] == pytest.approx(50000.0), (
            f"Expected 50000 (open deals only) but got {kpi_dict.get('Pipeline')} — "
            "lost deals must be excluded from Pipeline KPI"
        )
    finally:
        db.close()


def test_lost_opportunities_grouped(seed_deals):
    """talent_detail returns per-reason summary and itemized list; loss_reason is a label not int."""
    db = TestSessionLocal()
    try:
        talent_a_id = seed_deals["deal_open"].talent_id
        result = kpi_service.talent_detail(db, talent_a_id)

        # seed_deals has deal_lost with loss_reason="Presupuesto insuficiente"
        lost_summary = result["lost_summary"]
        lost_opps = result["lost_opportunities"]

        assert len(lost_opps) == 1
        # Reason must be a Spanish label string, never an integer
        opp = lost_opps[0]
        assert isinstance(opp["loss_reason"], str), "loss_reason must be a string label, not an int"
        assert opp["loss_reason"] == "Presupuesto insuficiente"

        # Summary should have one entry for "Presupuesto insuficiente"
        assert len(lost_summary) == 1
        summary = lost_summary[0]
        assert summary["reason"] == "Presupuesto insuficiente"
        assert summary["count"] == 1
    finally:
        db.close()


def test_brand_category_by_count(db_session):
    """brand_categories are % by DEAL COUNT (D-27), not by revenue; sum to ~100."""
    talent = Talent(name="Talento Marcas", active=True, category="Lifestyle")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    # 3 deals: 2 Moda/Retail, 1 Agencias
    deals_data = [
        (10001, 10000.0, "Moda/Retail"),
        (10002, 50000.0, "Moda/Retail"),   # higher revenue but same count weight as the one above
        (10003, 5000.0, "Agencias"),
    ]
    for pid, val, cat in deals_data:
        db_session.add(Deal(
            pipedrive_id=pid,
            title=f"Deal {pid}",
            value=val,
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent.id,
            commission_amount=val * 0.7,
            is_sin_cotizar=False,
            brand_category=cat,
            update_time="2026-06-01T10:00:00Z",
        ))
    db_session.commit()

    result = kpi_service.talent_detail(db_session, talent.id)
    brand_cats = result["brand_categories"]

    # 2 categories should be present
    assert len(brand_cats) == 2

    # Percentages must sum to ~100 (by count, not revenue)
    total_pct = sum(s["pct"] for s in brand_cats)
    assert total_pct == pytest.approx(100.0, abs=1.0)

    # Moda/Retail = 2/3 = 66.7%, Agencias = 1/3 = 33.3%
    cat_map = {s["category"]: s for s in brand_cats}
    assert cat_map["Moda/Retail"]["count"] == 2
    assert cat_map["Agencias"]["count"] == 1
    assert cat_map["Moda/Retail"]["pct"] == pytest.approx(66.67, abs=0.5)


def test_talent_detail_empty(db_session):
    """A talent with no lost deals / no brand categories returns empty lists."""
    talent = Talent(name="Talento Vacio", active=True, category="Tech")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    # One open deal with no loss_reason and no brand_category
    db_session.add(Deal(
        pipedrive_id=20001,
        title="Deal abierto",
        value=12000.0,
        currency="MXN",
        stage_id=2,
        stage_name="Cotización",
        status="open",
        talent_id=talent.id,
        commission_amount=8400.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
    ))
    db_session.commit()

    result = kpi_service.talent_detail(db_session, talent.id)

    # Empty lost opportunities
    assert result["lost_opportunities"] == []
    assert result["lost_summary"] == []

    # Empty brand categories
    assert result["brand_categories"] == []


# ---------------------------------------------------------------------------
# 5.1 (D1) — flujo_dinero_kpis: "Campañas firmadas" = status='won' only
# ---------------------------------------------------------------------------


def _tile(result, label):
    return next(t for t in result["kpis"] if t["label"] == label)


def test_flujo_firmadas_counts_only_won_not_contrato_stage(db_session):
    """5.1/D1: a deal sitting in the 'Contrato' stage but still status='open'
    is in the signing process — NOT firmada. Only status='won' counts."""
    from app.models import TrelloCard

    talent = Talent(name="Talento Flujo", active=True, category="Tech")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    # status='won' — counts as firmada
    won = Deal(
        pipedrive_id=30001, title="Ganado", value=100000.0, currency="MXN",
        stage_id=4, stage_name="Contrato", status="won", talent_id=talent.id,
        commission_amount=70000.0, update_time="2026-06-10T10:00:00Z",
    )
    # In 'Contrato' stage but still open — must NOT count as firmada
    contrato_open = Deal(
        pipedrive_id=30002, title="En firma", value=999999.0, currency="MXN",
        stage_id=4, stage_name="Contrato", status="open", talent_id=talent.id,
        commission_amount=699999.3, update_time="2026-06-11T10:00:00Z",
    )
    db_session.add_all([won, contrato_open])
    db_session.commit()

    result = kpi_service.flujo_dinero_kpis(db_session, talent.id)
    firmadas = _tile(result, "Campañas firmadas")

    assert firmadas["count"] == 1                 # only the won deal
    assert firmadas["value"] == 100000.0          # NOT the 999999 open Contrato deal


def test_flujo_pendiente_equals_won_minus_cobrado(db_session):
    """5.1/D1: 'Pendiente por cobrar' = firmadas(won) - cobrado, never negative."""
    from datetime import date

    from app.models import TrelloCard

    talent = Talent(name="Talento Pendiente", active=True, category="Tech")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    won_cobrado = Deal(
        pipedrive_id=31001, title="Ganado y cobrado", value=100000.0, currency="MXN",
        stage_id=4, stage_name="Contrato", status="won", talent_id=talent.id,
        commission_amount=70000.0, update_time="2026-06-10T10:00:00Z",
    )
    won_pendiente = Deal(
        pipedrive_id=31002, title="Ganado sin cobrar", value=40000.0, currency="MXN",
        stage_id=4, stage_name="Contrato", status="won", talent_id=talent.id,
        commission_amount=28000.0, update_time="2026-06-11T10:00:00Z",
    )
    db_session.add_all([won_cobrado, won_pendiente])
    db_session.commit()
    db_session.refresh(won_cobrado)

    # Only won_cobrado has a 'cerrado' Trello card → counts as cobrado
    db_session.add(TrelloCard(
        trello_card_id="card-cerrado-flujo", name="Cobrado", list_id="L1",
        list_name="Finalizados", list_state="cerrado", deal_id=won_cobrado.id,
        collection_date=date(2026, 7, 1),
    ))
    db_session.commit()

    result = kpi_service.flujo_dinero_kpis(db_session, talent.id)
    firmadas = _tile(result, "Campañas firmadas")
    cobrado = _tile(result, "Cobrado")
    pendiente = _tile(result, "Pendiente por cobrar")

    assert firmadas["value"] == 140000.0          # both won deals
    assert cobrado["value"] == 100000.0           # only the cerrado-card deal
    # Coherence: pendiente == ganados - cobrado
    assert pendiente["value"] == firmadas["value"] - cobrado["value"]
    assert pendiente["value"] == 40000.0


# ---------------------------------------------------------------------------
# 5.4 (D3) — deals_won_in_period: agent date-range filter on won_time
# ---------------------------------------------------------------------------


def _make_won_deal(db, pid, talent_id, value, won_time):
    deal = Deal(
        pipedrive_id=pid, title=f"Deal {pid}", value=value, currency="MXN",
        stage_id=4, stage_name="Contrato", status="won", talent_id=talent_id,
        commission_amount=value * 0.7, update_time="2026-06-30T10:00:00Z",
        won_time=won_time,
    )
    db.add(deal)
    return deal


def test_deals_won_in_period_filters_by_won_time(db_session):
    """5.4/D3: only status='won' deals whose won_time falls in [start, end]
    (inclusive) are returned; open deals and out-of-range deals are excluded."""
    talent = Talent(name="Talento Periodo", active=True, category="Tech")
    db_session.add(talent)
    db_session.commit()
    db_session.refresh(talent)

    # In June 2026 (boundaries inclusive)
    _make_won_deal(db_session, 40001, talent.id, 10000.0, datetime(2026, 6, 1, 0, 0, 0))
    _make_won_deal(db_session, 40002, talent.id, 20000.0, datetime(2026, 6, 30, 23, 59, 0))
    # Out of range (May and July)
    _make_won_deal(db_session, 40003, talent.id, 99999.0, datetime(2026, 5, 31, 23, 0, 0))
    _make_won_deal(db_session, 40004, talent.id, 88888.0, datetime(2026, 7, 1, 0, 1, 0))
    # won but NULL won_time -> excluded (cannot place in period)
    _make_won_deal(db_session, 40005, talent.id, 77777.0, None)
    # open deal in range by add_time but not won -> excluded
    db_session.add(Deal(
        pipedrive_id=40006, title="Abierto", value=66666.0, currency="MXN",
        stage_id=4, stage_name="Contrato", status="open", talent_id=talent.id,
        commission_amount=0.0, update_time="2026-06-15T10:00:00Z",
        won_time=datetime(2026, 6, 15, 10, 0, 0),  # even with a won_time, status!=won
    ))
    db_session.commit()

    result = kpi_service.deals_won_in_period(db_session, "2026-06-01", "2026-06-30")

    assert result["count"] == 2
    assert result["total_value"] == 30000.0
    titles = {d["title"] for d in result["deals"]}
    assert titles == {"Deal 40001", "Deal 40002"}
    # talent name resolved
    assert all(d["talent_name"] == talent.name for d in result["deals"])


def test_deals_won_in_period_optional_talent_filter(db_session):
    """5.4/D3: talent_id narrows the period to a single talent."""
    t1 = Talent(name="Talento A", active=True)
    t2 = Talent(name="Talento B", active=True)
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    _make_won_deal(db_session, 41001, t1.id, 10000.0, datetime(2026, 6, 10, 12, 0, 0))
    _make_won_deal(db_session, 41002, t2.id, 50000.0, datetime(2026, 6, 11, 12, 0, 0))
    db_session.commit()

    all_result = kpi_service.deals_won_in_period(db_session, "2026-06-01", "2026-06-30")
    assert all_result["count"] == 2

    t1_result = kpi_service.deals_won_in_period(db_session, "2026-06-01", "2026-06-30", talent_id=t1.id)
    assert t1_result["count"] == 1
    assert t1_result["total_value"] == 10000.0
    assert t1_result["deals"][0]["talent_name"] == "Talento A"


def test_deals_won_in_period_rejects_bad_dates(db_session):
    """5.4/D3: malformed date strings raise ValueError (caught by the agent loop)."""
    with pytest.raises(ValueError):
        kpi_service.deals_won_in_period(db_session, "junio", "2026-06-30")
