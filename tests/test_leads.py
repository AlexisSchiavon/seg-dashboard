"""Tests for the Google Sheets leads integration (Plan 03-01).

Test Map:
  - [sheets] SheetLeadRow field_validators (score, bool, convertido)
  - [padding] get_leads_rows pads short rows
  - [score] parse_score: "", "85", "85.0", garbage → None/int/int/None
  - [talent] resolve_talent_id: exact match, empty, whitespace, unknown
  - [calificado] leads_summary counts total and calificados
  - [by_talent] leads_by_talent per-talent totals + Sin-talento bucket
  - [summary] GET /leads/summary returns 200 with auth, 401 without
  - [sync] sync_sheets upserts (idempotent, source-isolated concurrency guard)
"""

import pytest


# ---------------------------------------------------------------------------
# SheetLeadRow field_validator tests (import-time only; no DB needed)
# ---------------------------------------------------------------------------

class TestSheetLeadRowValidators:
    """Unit tests for SheetLeadRow Pydantic validators."""

    def _make(self, **kwargs):
        from app.integrations.sheets import SheetLeadRow
        defaults = dict(
            sheet_row_id=2,
            remitente_email="test@example.com",
            remitente_nombre="Test",
            asunto="Asunto",
            fecha_recepcion="2026-04-01T10:00:00Z",
            talento_mencionado="Emicanico",
            status_filtrado="✅ Aprobado - Respuesta enviada",
            score_calidad=None,
            bloqueado=False,
            convertido_a_prospecto=False,
        )
        defaults.update(kwargs)
        return SheetLeadRow(**defaults)

    def test_score_empty_string_returns_none(self):
        row = self._make(score_calidad="")
        assert row.score_calidad is None

    def test_score_none_returns_none(self):
        row = self._make(score_calidad=None)
        assert row.score_calidad is None

    def test_score_integer_string(self):
        row = self._make(score_calidad="85")
        assert row.score_calidad == 85

    def test_score_float_string_truncated(self):
        row = self._make(score_calidad="85.0")
        assert row.score_calidad == 85

    def test_score_garbage_returns_none(self):
        row = self._make(score_calidad="not-a-number")
        assert row.score_calidad is None

    def test_bloqueado_true_string(self):
        row = self._make(bloqueado="TRUE")
        assert row.bloqueado is True

    def test_bloqueado_false_string(self):
        row = self._make(bloqueado="FALSE")
        assert row.bloqueado is False

    def test_bloqueado_empty_string(self):
        row = self._make(bloqueado="")
        assert row.bloqueado is False

    def test_convertido_true_string(self):
        row = self._make(convertido_a_prospecto="TRUE")
        assert row.convertido_a_prospecto is True

    def test_convertido_false_string(self):
        row = self._make(convertido_a_prospecto="FALSE")
        assert row.convertido_a_prospecto is False


# ---------------------------------------------------------------------------
# get_leads_rows padding test (monkeypatch gspread)
# ---------------------------------------------------------------------------

class TestGetLeadsRowsPadding:
    """Tests that get_leads_rows() pads short rows to header length."""

    def test_short_row_padded_no_index_error(self, monkeypatch):
        """A row with fewer cells than headers must not raise IndexError."""
        import app.integrations.sheets as sheets_module

        # Simulate 5-column header, a full row, and a short row (3 cells)
        mock_values = [
            ["Remitente_Email", "Remitente_Nombre", "Asunto", "Status_Filtrado", "Score_Calidad"],
            ["a@ex.com", "A", "Asunto1", "En revisión", "50"],
            ["b@ex.com", "B"],  # short row — gspread omits trailing empty cells
        ]

        class _MockWorksheet:
            def get_all_values(self):
                return mock_values

        class _MockSpreadsheet:
            def worksheet(self, name):
                return _MockWorksheet()

        class _MockClient:
            def open_by_key(self, key):
                return _MockSpreadsheet()

        monkeypatch.setattr(sheets_module, "_client", lambda: _MockClient())

        from app.integrations.sheets import get_leads_rows
        rows = get_leads_rows()
        assert len(rows) == 2
        # Short row should have empty string for missing columns
        assert rows[1].asunto == ""
        assert rows[1].status_filtrado == ""
        assert rows[1].score_calidad is None

    def test_empty_sheet_returns_empty_list(self, monkeypatch):
        import app.integrations.sheets as sheets_module

        class _MockWorksheet:
            def get_all_values(self):
                return []

        class _MockSpreadsheet:
            def worksheet(self, name):
                return _MockWorksheet()

        class _MockClient:
            def open_by_key(self, key):
                return _MockSpreadsheet()

        monkeypatch.setattr(sheets_module, "_client", lambda: _MockClient())

        from app.integrations.sheets import get_leads_rows
        assert get_leads_rows() == []


# ---------------------------------------------------------------------------
# resolve_talent_id tests
# ---------------------------------------------------------------------------

class TestResolveTalentId:
    """Unit tests for leads_service.resolve_talent_id()."""

    def test_exact_match_returns_talent_id(self, db_session, seed_talent_products):
        from app.services import leads as leads_service
        talent_a = seed_talent_products["talent_a"]
        result = leads_service.resolve_talent_id(db_session, "Talento Uno")
        assert result == talent_a.id

    def test_empty_string_returns_none(self, db_session, seed_talent_products):
        from app.services import leads as leads_service
        assert leads_service.resolve_talent_id(db_session, "") is None

    def test_whitespace_only_returns_none(self, db_session, seed_talent_products):
        from app.services import leads as leads_service
        assert leads_service.resolve_talent_id(db_session, "   ") is None

    def test_unknown_talent_returns_none(self, db_session, seed_talent_products):
        from app.services import leads as leads_service
        assert leads_service.resolve_talent_id(db_session, "TalentoDesconocido") is None

    def test_case_sensitive_mismatch_returns_none(self, db_session, seed_talent_products):
        """Exact match is case-sensitive per D-33."""
        from app.services import leads as leads_service
        assert leads_service.resolve_talent_id(db_session, "talento uno") is None


# ---------------------------------------------------------------------------
# leads_summary tests
# ---------------------------------------------------------------------------

class TestLeadsSummary:
    """Tests for leads_service.leads_summary()."""

    def test_counts_total_and_calificados(self, db_session, seed_leads):
        from app.services import leads as leads_service
        result = leads_service.leads_summary(db_session)
        assert result["leads_totales"] == 3
        # Only "✅ Aprobado - Respuesta enviada" is calificado
        assert result["calificados"] == 1

    def test_empty_db_returns_zeros(self, db_session):
        from app.services import leads as leads_service
        result = leads_service.leads_summary(db_session)
        assert result["leads_totales"] == 0
        assert result["calificados"] == 0


# ---------------------------------------------------------------------------
# leads_by_talent tests
# ---------------------------------------------------------------------------

class TestLeadsByTalent:
    """Tests for leads_service.leads_by_talent()."""

    def test_returns_rows_for_all_talents(self, db_session, seed_leads, seed_talent_products):
        from app.services import leads as leads_service
        bars = leads_service.leads_by_talent(db_session)
        names = [b["name"] for b in bars]
        assert "Talento Uno" in names
        assert "Talento Dos" in names

    def test_talent_with_zero_leads_renders_zero(self, db_session, seed_talent_products):
        """A talent with no leads should appear with total=0, not be absent."""
        # No leads seeded — seed_talent_products only creates talents
        from app.services import leads as leads_service
        bars = leads_service.leads_by_talent(db_session)
        for bar in bars:
            if bar["name"] in ("Talento Uno", "Talento Dos"):
                assert bar["total"] == 0
                assert bar["calificados"] == 0

    def test_sin_talento_bucket_appended(self, db_session, seed_leads):
        """Lead with talent_id=None must appear in the Sin-talento bucket."""
        from app.services import leads as leads_service
        bars = leads_service.leads_by_talent(db_session)
        sin_bucket = next((b for b in bars if b.get("is_sin_talento")), None)
        assert sin_bucket is not None
        assert sin_bucket["name"] == "Sin talento asignado"
        assert sin_bucket["total"] == 1

    def test_calificados_counted_per_talent(self, db_session, seed_leads, seed_talent_products):
        """Talento Uno has 1 calificado lead; Talento Dos has 0."""
        from app.services import leads as leads_service
        bars = leads_service.leads_by_talent(db_session)
        talent_a_bar = next(b for b in bars if b["name"] == "Talento Uno")
        talent_b_bar = next(b for b in bars if b["name"] == "Talento Dos")
        assert talent_a_bar["calificados"] == 1
        assert talent_b_bar["calificados"] == 0


# ---------------------------------------------------------------------------
# sync_sheets tests
# ---------------------------------------------------------------------------

class TestSyncSheets:
    """Integration tests for sync_sheets() job (uses mock_sheets_rows fixture)."""

    def test_sync_sheets_inserts_rows(self, db_session, seed_talent_products, mock_sheets_rows):
        """sync_sheets inserts 3 sample rows on first run."""
        from app.sync.jobs import sync_sheets
        from app.models import Lead

        sync_log = sync_sheets(db_session)

        assert sync_log.status == "success"
        assert sync_log.source == "sheets"
        # 3 sample rows
        assert db_session.query(Lead).count() == 3

    def test_sync_sheets_idempotent(self, db_session, seed_talent_products, mock_sheets_rows):
        """Second run with same rows inserts zero new Lead rows."""
        from app.sync.jobs import sync_sheets
        from app.models import Lead

        sync_sheets(db_session)
        count_after_first = db_session.query(Lead).count()

        sync_sheets(db_session)
        count_after_second = db_session.query(Lead).count()

        assert count_after_first == count_after_second == 3

    def test_sync_sheets_source_filter_isolated(self, db_session, seed_talent_products, mock_sheets_rows):
        """A running pipedrive SyncLog does NOT block sync_sheets (Pitfall 6)."""
        from datetime import datetime, timezone
        from app.models import Lead, SyncLog
        from app.sync.jobs import sync_sheets

        # Plant a running pipedrive sync log
        running_pipedrive = SyncLog(
            source="pipedrive",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        db_session.add(running_pipedrive)
        db_session.commit()

        # sync_sheets should still run and succeed
        sync_log = sync_sheets(db_session)
        assert sync_log.source == "sheets"
        assert sync_log.status == "success"
        assert db_session.query(Lead).count() == 3

    def test_sync_sheets_running_blocks_duplicate(self, db_session, seed_talent_products, mock_sheets_rows):
        """A running sheets SyncLog blocks a second sync_sheets call."""
        from datetime import datetime, timezone
        from app.models import Lead, SyncLog
        from app.sync.jobs import sync_sheets

        # Plant a running sheets log
        running_sheets = SyncLog(
            source="sheets",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        db_session.add(running_sheets)
        db_session.commit()

        result = sync_sheets(db_session)
        # Should return the existing running log unchanged
        assert result.id == running_sheets.id
        assert result.status == "running"
        assert db_session.query(Lead).count() == 0

    def test_sync_sheets_sin_talento_path(self, db_session, seed_talent_products, mock_sheets_rows):
        """Row with talento_mencionado='' should have talent_id=None."""
        from app.sync.jobs import sync_sheets
        from app.models import Lead

        sync_sheets(db_session)
        # sheet_row_id=4 has talento_mencionado=""
        lead = db_session.query(Lead).filter(Lead.sheet_row_id == 4).first()
        assert lead is not None
        assert lead.talent_id is None

    def test_sync_sheets_writes_synclog_with_source_sheets(self, db_session, seed_talent_products, mock_sheets_rows):
        """SyncLog row must have source='sheets'."""
        from app.models import SyncLog
        from app.sync.jobs import sync_sheets

        sync_sheets(db_session)
        log = db_session.query(SyncLog).filter(SyncLog.source == "sheets").first()
        assert log is not None
        assert log.status == "success"
        assert log.records_synced == 3


# ---------------------------------------------------------------------------
# GET /leads/summary endpoint tests
# ---------------------------------------------------------------------------

class TestLeadsSummaryEndpoint:
    """Tests for GET /leads/summary."""

    def test_summary_requires_auth(self, client):
        response = client.get("/leads/summary")
        assert response.status_code == 401

    def test_summary_returns_200_with_auth(self, auth_client, seed_leads):
        response = auth_client.get("/leads/summary")
        assert response.status_code == 200
        data = response.json()
        assert "leads_totales" in data
        assert "calificados" in data
        assert isinstance(data["por_talento"], list)

    def test_summary_counts_match_seed_data(self, auth_client, seed_leads):
        response = auth_client.get("/leads/summary")
        data = response.json()
        assert data["leads_totales"] == 3
        assert data["calificados"] == 1
