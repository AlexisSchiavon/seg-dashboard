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
