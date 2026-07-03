"""Fase 9.7a — Tests for the talent-facing KPI helpers.

compute_talent_facing_kpis and account_status_breakdown apply the talent's 70%
share (Deal.commission_amount, which equals value*0.70) and expose only
talent-appropriate figures — no pipeline/commission/funnel internals.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Deal, Talent, TrelloCard
from app.services import kpis as kpi_service
from app.services import reports as reports_service


def _talent(db: Session, name="Tal Prueba") -> Talent:
    t = Talent(name=name, active=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _deal(db, talent_id, pid, value, *, status="won", won_time=None,
          add_time="2026-05-01T00:00:00", commission=None):
    d = Deal(
        pipedrive_id=pid, title=f"Deal {pid}", value=value, currency="MXN",
        stage_id=4, stage_name="Contrato", status=status, talent_id=talent_id,
        commission_amount=commission if commission is not None else value * 0.70,
        is_sin_cotizar=False, update_time="2026-06-01T00:00:00",
        add_time=add_time, won_time=won_time,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _card(db, cid, list_state, deal_id, collection_date):
    c = TrelloCard(
        trello_card_id=cid, name=cid, list_id="L", list_name="L",
        list_state=list_state, deal_id=deal_id, collection_date=collection_date,
    )
    db.add(c)
    db.commit()
    return c


class TestComputeTalentFacingKpis:
    def test_firmadas_cobrado_porcobrar_in_70pct(self, db_session):
        t = _talent(db_session)
        # Firmado en junio: value 100k -> 70% = 70,000
        _deal(db_session, t.id, 9001, 100000.0, won_time=datetime(2026, 6, 10))
        # Cobrado en junio: cerrado card, deal value 50k -> 70% = 35,000
        d2 = _deal(db_session, t.id, 9002, 50000.0, won_time=datetime(2026, 6, 12))
        _card(db_session, "c-cerr", "cerrado", d2.id, date(2026, 6, 20))

        res = kpi_service.compute_talent_facing_kpis(
            db_session, t.id, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert res["firmadas_count"] == 2
        assert res["firmadas_70"] == 105000.0        # (100k+50k)*0.70
        assert res["cobrado_70"] == 35000.0          # only the cerrado card
        assert res["por_cobrar_70"] == 70000.0       # 105000 - 35000

    def test_por_cobrar_floored_at_zero(self, db_session):
        t = _talent(db_session)
        # Nothing firmed in period, but a cobro happened -> por_cobrar must floor to 0
        d = _deal(db_session, t.id, 9101, 40000.0, won_time=datetime(2026, 5, 1))
        _card(db_session, "c-x", "cerrado", d.id, date(2026, 6, 5))
        res = kpi_service.compute_talent_facing_kpis(
            db_session, t.id, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert res["firmadas_70"] == 0.0
        assert res["cobrado_70"] == 28000.0
        assert res["por_cobrar_70"] == 0.0


class TestAccountStatusBreakdown:
    def test_buckets_split_future_overdue_collected(self, db_session):
        t = _talent(db_session)
        today = date.today()
        # Próximos: ejecucion, collection in the future
        d_fut = _deal(db_session, t.id, 9201, 100000.0)
        _card(db_session, "c-fut", "ejecucion", d_fut.id, date(today.year, 12, 1))
        # Retraso: cobranza, collection in the past (valid, after add_time)
        d_late = _deal(db_session, t.id, 9202, 50000.0, add_time="2026-01-01T00:00:00")
        _card(db_session, "c-late", "cobranza", d_late.id, date(2026, 3, 1))
        # Cobrado año: cerrado, collection this year
        d_col = _deal(db_session, t.id, 9203, 30000.0)
        _card(db_session, "c-col", "cerrado", d_col.id, date(today.year, 2, 1))

        res = kpi_service.account_status_breakdown(db_session, t.id)
        assert res["proximos_meses"]["count"] == 1
        assert res["proximos_meses"]["value70"] == 70000.0
        assert res["retraso"]["count"] == 1
        assert res["retraso"]["value70"] == 35000.0
        assert res["cobrado_ano"]["value70"] == 21000.0

    def test_retraso_excludes_impossible_dates(self, db_session):
        """A card whose collection_date precedes the deal's add_time is data garbage
        (D-9.7: sanitize overdue) and must NOT count toward retraso."""
        t = _talent(db_session)
        # Impossible: collection Dec-2025 but deal added Jun-2026
        d_bad = _deal(db_session, t.id, 9301, 500000.0, add_time="2026-06-26T00:00:00")
        _card(db_session, "c-bad", "cobranza", d_bad.id, date(2025, 12, 22))
        # A valid overdue card so the bucket isn't trivially empty
        d_ok = _deal(db_session, t.id, 9302, 10000.0, add_time="2026-01-01T00:00:00")
        _card(db_session, "c-ok", "cobranza", d_ok.id, date(2026, 3, 1))

        res = kpi_service.account_status_breakdown(db_session, t.id)
        assert res["retraso"]["count"] == 1                 # only the valid one
        assert res["retraso"]["value70"] == 7000.0          # 10000*0.70, garbage excluded

    def test_retraso_excludes_ejecucion_past_due(self, db_session):
        """9.8b: an 'ejecucion' card past its date is stalled execution, NOT overdue
        collection. Only 'cobranza' (Trello "Cobrar") cards count toward retraso."""
        t = _talent(db_session)
        past = date.today() - timedelta(days=30)
        d = _deal(db_session, t.id, 9401, 200000.0, add_time="2024-01-01T00:00:00")
        _card(db_session, "c-ej", "ejecucion", d.id, past)
        res = kpi_service.account_status_breakdown(db_session, t.id)
        assert res["retraso"]["count"] == 0
        assert res["retraso"]["value70"] == 0.0

    def test_retraso_excludes_beyond_180_days(self, db_session):
        """9.8b: cobranza cards overdue by more than 180 days are stale / likely
        already collected and are excluded from retraso."""
        t = _talent(db_session)
        old = date.today() - timedelta(days=200)
        d = _deal(db_session, t.id, 9402, 90000.0, add_time="2024-01-01T00:00:00")
        _card(db_session, "c-old", "cobranza", d.id, old)
        res = kpi_service.account_status_breakdown(db_session, t.id)
        assert res["retraso"]["count"] == 0
        assert res["retraso"]["value70"] == 0.0

    def test_retraso_excludes_zero_value(self, db_session):
        """9.8b: a cobranza card whose deal has value 0 has nothing to collect."""
        t = _talent(db_session)
        past = date.today() - timedelta(days=30)
        d = _deal(db_session, t.id, 9403, 0.0, add_time="2024-01-01T00:00:00")
        _card(db_session, "c-zero", "cobranza", d.id, past)
        res = kpi_service.account_status_breakdown(db_session, t.id)
        assert res["retraso"]["count"] == 0


class TestSignedDealBadge:
    """P3: 'Cobrado' badge only when the card is cerrado AND collected in the month."""

    def test_cobrado_only_when_collected_in_report_month(self, db_session):
        t = _talent(db_session)
        # Firmado en junio + cerrado cobrado EN junio -> "Cobrado"
        d1 = _deal(db_session, t.id, 8001, 100000.0, won_time=datetime(2026, 6, 10))
        _card(db_session, "c1", "cerrado", d1.id, date(2026, 6, 20))
        # Firmado en junio + cerrado cobrado en AGOSTO -> "En ejecución" (no este mes)
        d2 = _deal(db_session, t.id, 8002, 50000.0, won_time=datetime(2026, 6, 11))
        _card(db_session, "c2", "cerrado", d2.id, date(2026, 8, 1))
        # Firmado en junio SIN card -> "Firmado"
        _deal(db_session, t.id, 8003, 20000.0, won_time=datetime(2026, 6, 12))

        data = reports_service.build_talent_report(db_session, t, date(2026, 6, 1), date(2026, 6, 30))
        badges = {s["title"]: s["estado_label"] for s in data["signed_deals"]}
        assert badges["Deal 8001"] == "Cobrado"
        assert badges["Deal 8002"] == "En ejecución"
        assert badges["Deal 8003"] == "Firmado"


class TestTalentProjection:
    """P4: projection is forward-only (>= today), excludes cerrado, and stays
    consistent with account_status 'proximos_meses'."""

    def test_projection_excludes_overdue_and_collected(self, db_session):
        t = _talent(db_session)
        # Future ejecucion, IN-window (August) -> counted
        d_fut = _deal(db_session, t.id, 8101, 100000.0)
        _card(db_session, "pf", "ejecucion", d_fut.id, date(2026, 8, 1))
        # Overdue cobranza (March) -> excluded
        d_late = _deal(db_session, t.id, 8102, 500000.0)
        _card(db_session, "pl", "cobranza", d_late.id, date(2026, 3, 1))
        # Cerrado, future -> excluded (already collected, not a projection)
        d_col = _deal(db_session, t.id, 8103, 300000.0)
        _card(db_session, "pc", "cerrado", d_col.id, date(2026, 8, 1))

        data = reports_service.build_talent_report(db_session, t, date(2026, 6, 1), date(2026, 6, 30))
        total = sum(m["estimado70"] for m in data["projection70"])
        assert total == 70000.0  # only the future ejecucion card (100000*0.70)

        # Consistency (P4): with all future cards in-window, projection total ==
        # the "por cobrar próximos meses" tile.
        prox = kpi_service.account_status_breakdown(db_session, t.id)["proximos_meses"]["value70"]
        assert total == prox
