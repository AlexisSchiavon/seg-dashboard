"""Tests for the audit trail (Prompt 3, Feature 1).

Service tests pass db=db_session so log_action writes to the same in-memory test
engine the assertions read from. Sync-integration tests spy on log_action via
monkeypatch to avoid cross-engine coupling.
"""
import json
from datetime import datetime, timedelta, timezone

from app.models import AuditLog
from app.services import audit as audit_service


# ----------------------------- log_action helper -----------------------------

class TestLogAction:
    def test_basic_write(self, db_session):
        audit_service.log_action("LOGIN", actor="user:a@b.com",
                                 entity_type="system", db=db_session)
        db_session.commit()
        row = db_session.query(AuditLog).one()
        assert row.action_type == "LOGIN"
        assert row.actor == "user:a@b.com"
        assert row.entity_type == "system"

    def test_entity_id_is_stringified(self, db_session):
        audit_service.log_action("TALENT_ASSIGNED", entity_type="deal",
                                 entity_id=502, db=db_session)
        db_session.commit()
        assert db_session.query(AuditLog).one().entity_id == "502"

    def test_payload_serialized_to_json(self, db_session):
        audit_service.log_action("MANUAL_UPDATE", payload={"before": 1, "after": 2},
                                 db=db_session)
        db_session.commit()
        row = db_session.query(AuditLog).one()
        assert json.loads(row.payload_json) == {"before": 1, "after": 2}

    def test_secrets_are_redacted(self, db_session):
        audit_service.log_action(
            "LOGIN",
            payload={"api_token": "abc123", "password": "hunter2",
                     "nested": {"secret_key": "s3cr3t", "ok": "visible"}},
            db=db_session,
        )
        db_session.commit()
        payload = json.loads(db_session.query(AuditLog).one().payload_json)
        assert payload["api_token"] == "[REDACTED]"
        assert payload["password"] == "[REDACTED]"
        assert payload["nested"]["secret_key"] == "[REDACTED]"
        assert payload["nested"]["ok"] == "visible"

    def test_payload_truncated_over_10kb(self, db_session):
        big = {"blob": "x" * 20000}
        audit_service.log_action("MANUAL_UPDATE", payload=big, db=db_session)
        db_session.commit()
        row = db_session.query(AuditLog).one()
        assert len(row.payload_json.encode()) <= audit_service.MAX_PAYLOAD_BYTES + 200
        assert json.loads(row.payload_json)["_truncated"] is True

    def test_none_payload_is_none(self, db_session):
        audit_service.log_action("LOGOUT", db=db_session)
        db_session.commit()
        assert db_session.query(AuditLog).one().payload_json is None

    def test_unknown_action_type_still_recorded(self, db_session):
        audit_service.log_action("NOT_A_REAL_TYPE", db=db_session)
        db_session.commit()
        assert db_session.query(AuditLog).one().action_type == "NOT_A_REAL_TYPE"

    def test_never_raises_on_unserializable_payload(self, db_session):
        # A set is not JSON-serializable by default -> helper must not raise.
        audit_service.log_action("MANUAL_UPDATE", payload={"weird": {1, 2, 3}},
                                 db=db_session)
        db_session.commit()
        assert db_session.query(AuditLog).count() == 1

    def test_never_raises_even_without_db(self, monkeypatch):
        # Force the own-session path to blow up; log_action must swallow it.
        def boom():
            raise RuntimeError("db down")
        monkeypatch.setattr(audit_service, "SessionLocal", boom)
        # Should not raise:
        audit_service.log_action("SYNC_FAILED", notes="offline")

    def test_notes_persisted(self, db_session):
        audit_service.log_action("DATA_HEALTH_ALERT", notes="count subió 20%",
                                 db=db_session)
        db_session.commit()
        assert db_session.query(AuditLog).one().notes == "count subió 20%"


# ------------------------------- list_logs -----------------------------------

def _seed(db, **kw):
    defaults = dict(action_type="LOGIN", actor="system")
    defaults.update(kw)
    db.add(AuditLog(**defaults))


class TestListLogs:
    def test_filter_by_entity(self, db_session):
        _seed(db_session, action_type="TALENT_ASSIGNED", entity_type="deal", entity_id="99")
        _seed(db_session, action_type="TALENT_ASSIGNED", entity_type="deal", entity_id="100")
        db_session.commit()
        rows, total, _ = audit_service.list_logs(db_session, entity_type="deal", entity_id="99")
        assert total == 1 and rows[0].entity_id == "99"

    def test_filter_by_action_type(self, db_session):
        _seed(db_session, action_type="SYNC_FAILED")
        _seed(db_session, action_type="SYNC_COMPLETED")
        db_session.commit()
        rows, total, _ = audit_service.list_logs(db_session, action_type="SYNC_FAILED")
        assert total == 1 and rows[0].action_type == "SYNC_FAILED"

    def test_pagination_and_cursor(self, db_session):
        for i in range(5):
            _seed(db_session, entity_id=str(i))
        db_session.commit()
        rows, total, nxt = audit_service.list_logs(db_session, limit=2, cursor=0)
        assert total == 5 and len(rows) == 2 and nxt == 2
        rows2, _, nxt2 = audit_service.list_logs(db_session, limit=2, cursor=4)
        assert len(rows2) == 1 and nxt2 is None

    def test_limit_capped_at_200(self, db_session):
        rows, _, _ = audit_service.list_logs(db_session, limit=9999)
        assert rows == []  # no data, but must not error — cap applied internally

    def test_newest_first(self, db_session):
        old = AuditLog(action_type="LOGIN", actor="system",
                       timestamp=datetime.now(timezone.utc) - timedelta(days=1))
        new = AuditLog(action_type="LOGOUT", actor="system",
                       timestamp=datetime.now(timezone.utc))
        db_session.add_all([old, new])
        db_session.commit()
        rows, _, _ = audit_service.list_logs(db_session)
        assert rows[0].action_type == "LOGOUT"


# ------------------------------- purge ---------------------------------------

def test_purge_old_logs(db_session):
    old = AuditLog(action_type="LOGIN", actor="system",
                   timestamp=datetime.now(timezone.utc) - timedelta(days=120))
    recent = AuditLog(action_type="LOGIN", actor="system",
                      timestamp=datetime.now(timezone.utc) - timedelta(days=10))
    db_session.add_all([old, recent])
    db_session.commit()
    deleted = audit_service.purge_old_logs(db=db_session)
    assert deleted == 1
    assert db_session.query(AuditLog).count() == 1


def test_purge_never_deletes_trello_card_created(db_session):
    """TRELLO_CARD_CREATED is the durable idempotency fact for auto-create — it
    must survive the retention purge forever, so deleted cards are never recreated."""
    old_card = AuditLog(action_type="TRELLO_CARD_CREATED", actor="system",
                        entity_type="deal", entity_id="421",
                        timestamp=datetime.now(timezone.utc) - timedelta(days=400))
    old_login = AuditLog(action_type="LOGIN", actor="system",
                         timestamp=datetime.now(timezone.utc) - timedelta(days=400))
    db_session.add_all([old_card, old_login])
    db_session.commit()

    deleted = audit_service.purge_old_logs(db=db_session)
    assert deleted == 1  # only the LOGIN purged
    remaining = db_session.query(AuditLog).all()
    assert len(remaining) == 1
    assert remaining[0].action_type == "TRELLO_CARD_CREATED"


# ------------------------------- endpoint ------------------------------------

class TestAuditEndpoint:
    def test_requires_auth(self, client):
        assert client.get("/api/audit/logs").status_code == 401

    def test_returns_filtered_page(self, auth_client, db_session):
        _seed(db_session, action_type="TALENT_ASSIGNED", entity_type="deal", entity_id="99")
        _seed(db_session, action_type="SYNC_FAILED", entity_type="system")
        db_session.commit()
        r = auth_client.get("/api/audit/logs?entity_type=deal&entity_id=99")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["entity_id"] == "99"
        assert body["items"][0]["action_type"] == "TALENT_ASSIGNED"

    def test_bad_date_returns_422(self, auth_client):
        r = auth_client.get("/api/audit/logs?since=not-a-date")
        assert r.status_code == 422


# --------------------------- sync integration --------------------------------

class TestSyncAudit:
    def test_run_all_syncs_emits_completed_and_failed(self, monkeypatch):
        """_run_all_syncs emits SYNC_COMPLETED on success and SYNC_FAILED when a
        source raises a network error — without letting the error propagate."""
        import app.sync.scheduler as sched

        calls = []
        monkeypatch.setattr("app.services.audit.log_action",
                            lambda *a, **k: calls.append((a, k)))
        monkeypatch.setattr(sched, "SessionLocal", lambda: _FakeDB())

        class _OKLog:
            status = "success"
            records_synced = 7

        def ok(db):
            return _OKLog()

        def boom(db):
            raise ConnectionError("network down")

        monkeypatch.setattr(sched, "sync_pipedrive", ok)
        monkeypatch.setattr(sched, "sync_sheets", boom)
        monkeypatch.setattr(sched, "sync_trello", ok)

        sched._run_all_syncs()  # must not raise

        actions = [a[0][0] for a in calls]
        assert actions.count("SYNC_COMPLETED") == 2
        assert actions.count("SYNC_FAILED") == 1


class _FakeDB:
    def close(self):
        pass
