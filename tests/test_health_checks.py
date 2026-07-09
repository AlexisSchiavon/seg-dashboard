"""Tests for data-health checks (Prompt 3, Feature 2)."""
from datetime import date, datetime, timedelta

from app.models import Deal, HealthCheckSnapshot, TrelloCard
from app.services import health_checks as hc


def _deal(db, pid, **kw):
    d = Deal(
        pipedrive_id=pid, title=kw.get("title", f"Deal {pid}"),
        value=kw.get("value", 1000.0), currency="MXN",
        stage_id=kw.get("stage_id", 1), stage_name=kw.get("stage_name", "Negociación"),
        status=kw.get("status", "won"), talent_id=kw.get("talent_id"),
        commission_amount=0.0, is_sin_cotizar=False, update_time="2026-06-01",
        won_time=kw.get("won_time"), expected_collection_date=kw.get("ecd"),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _card(db, cid, list_state, deal_id=None, collection_date=None):
    c = TrelloCard(trello_card_id=cid, name=f"card {cid}", list_id="L", list_name="L",
                   list_state=list_state, deal_id=deal_id, collection_date=collection_date)
    db.add(c)
    db.commit()
    return c


JUN = datetime(2026, 6, 1)


class TestChecks:
    def test_sin_atribucion(self, db_session):
        _deal(db_session, 1, status="won", talent_id=None, won_time=JUN, value=5000)
        _deal(db_session, 2, status="won", talent_id=10, won_time=JUN)   # assigned → no
        _deal(db_session, 3, status="won", talent_id=None,
              won_time=datetime(2025, 6, 1))                              # pre-cutoff → no
        count, value, items = hc._c_deals_sin_atribucion(db_session)
        assert count == 1 and value == 5000
        assert items[0]["id_ref"] == "pipedrive:1"
        assert items[0]["link_pipedrive"].endswith("/deal/1")

    def test_final_funnel_no_won(self, db_session):
        _deal(db_session, 1, stage_name="Contrato", status="open", value=3000)
        _deal(db_session, 2, stage_name="Contrato", status="won")        # won → no
        _deal(db_session, 3, stage_name="Negociación", status="open")    # not final → no
        count, value, _ = hc._c_final_funnel_no_won(db_session)
        assert count == 1 and value == 3000

    def test_won_sin_card(self, db_session):
        _deal(db_session, 1, status="won", value=7000)   # no card → should be flagged
        d2 = _deal(db_session, 2, status="won")
        _card(db_session, "c2", "ejecucion", deal_id=d2.id)              # d2 linked
        count, value, items = hc._c_won_sin_card(db_session)
        assert count == 1 and value == 7000 and items[0]["id_ref"] == "pipedrive:1"

    def test_cobrar_sin_due(self, db_session):
        _card(db_session, "c1", "cobranza", collection_date=None)
        _card(db_session, "c2", "cobranza", collection_date=date(2026, 6, 1))  # has due
        _card(db_session, "c3", "ejecucion", collection_date=None)             # not cobranza
        count, _, items = hc._c_cobrar_sin_due(db_session)
        assert count == 1 and items[0]["id_ref"] == "trello:c1"
        assert items[0]["link_trello"].endswith("/c/c1")

    def test_vencidas_sin_actualizar(self, db_session):
        old = date.today() - timedelta(days=60)
        recent = date.today() - timedelta(days=5)
        d = _deal(db_session, 1, value=9000)
        _card(db_session, "c1", "cobranza", deal_id=d.id, collection_date=old)
        _card(db_session, "c2", "cobranza", collection_date=recent)      # within 30d → no
        count, value, _ = hc._c_vencidas_sin_actualizar(db_session)
        assert count == 1 and value == 9000

    def test_won_valor_cero(self, db_session):
        _deal(db_session, 1, status="won", value=0)
        _deal(db_session, 2, status="won", value=None)
        _deal(db_session, 3, status="won", value=100)                    # nonzero → no
        count, _, _ = hc._c_won_valor_cero(db_session)
        assert count == 2

    def test_collection_pasado(self, db_session):
        past = (date.today() - timedelta(days=5)).isoformat()
        future = (date.today() + timedelta(days=5)).isoformat()
        _deal(db_session, 1, status="open", ecd=past, value=4000)
        _deal(db_session, 2, status="open", ecd=future)                  # future → no
        _deal(db_session, 3, status="won", ecd=past)                     # won → no
        _deal(db_session, 4, status="open", ecd="basura")               # unparseable → no
        count, value, _ = hc._c_collection_pasado(db_session)
        assert count == 1 and value == 4000


class TestSnapshots:
    def test_save_creates_snapshot_and_delta(self, db_session):
        _deal(db_session, 1, status="won", value=0)                      # DEALS_WON_VALOR_CERO=1
        hc.save_snapshots(db_session)
        first = db_session.query(HealthCheckSnapshot).filter_by(
            check_id="DEALS_WON_VALOR_CERO").one()
        assert first.count == 1 and first.resolved_delta is None
        _deal(db_session, 2, status="won", value=0)                      # now 2
        hc.save_snapshots(db_session)
        latest = (db_session.query(HealthCheckSnapshot)
                  .filter_by(check_id="DEALS_WON_VALOR_CERO")
                  .order_by(HealthCheckSnapshot.snapshot_at.desc(),
                            HealthCheckSnapshot.id.desc()).first())
        assert latest.count == 2 and latest.resolved_delta == 1

    def test_growth_triggers_alert(self, db_session, monkeypatch):
        calls = []
        monkeypatch.setattr("app.services.audit.log_action",
                            lambda *a, **k: calls.append((a, k)))
        _deal(db_session, 1, status="won", value=0)
        hc.save_snapshots(db_session)
        for pid in range(2, 12):  # jump 1 → 11 (>10% growth)
            _deal(db_session, pid, status="won", value=0)
        hc.save_snapshots(db_session)
        alerts = [c for c in calls if c[0][0] == "DATA_HEALTH_ALERT"]
        assert any(k["entity_id"] == "DEALS_WON_VALOR_CERO" for _, k in alerts)

    def test_degraded_check_marks_unavailable(self, db_session, monkeypatch):
        def boom(db):
            raise RuntimeError("boom")
        spec = dict(hc.CHECKS[0], fn=boom)
        result = hc._run_one(db_session, spec)
        assert result["available"] is False and result["count"] == 0


class TestEndpoints:
    def test_health_requires_auth(self, client):
        assert client.get("/api/health").status_code == 401

    def test_health_returns_checks(self, auth_client, db_session):
        _deal(db_session, 1, status="won", value=0)
        r = auth_client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert "generated_at" in body
        ids = {c["check_id"] for c in body["checks"]}
        assert "DEALS_WON_VALOR_CERO" in ids
        for c in body["checks"]:
            assert c["responsibility"] == "TA"
            assert "trend_24h" in c

    def test_items_endpoint(self, auth_client, db_session):
        _deal(db_session, 1, status="won", value=0)
        r = auth_client.get("/api/health/DEALS_WON_VALOR_CERO/items")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1 and body["items"][0]["id_ref"] == "pipedrive:1"

    def test_items_unknown_check_404(self, auth_client):
        assert auth_client.get("/api/health/NOPE/items").status_code == 404
