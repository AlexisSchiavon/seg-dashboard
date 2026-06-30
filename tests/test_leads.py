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


# ---------------------------------------------------------------------------
# leads_list service tests (Plan 03-02)
# ---------------------------------------------------------------------------

class TestLeadsList:
    """Tests for leads_service.leads_list()."""

    def test_leads_list_all_returns_all_with_talent_name(self, db_session, seed_leads, seed_talent_products):
        """leads_list with no filters returns all leads with talent_name resolved."""
        from app.services import leads as leads_service
        rows = leads_service.leads_list(db_session)
        assert len(rows) == 3
        # Check that dict has talent_name key and it resolves to name or None
        names = [r["talent_name"] for r in rows]
        assert "Talento Uno" in names
        assert "Talento Dos" in names
        assert None in names  # lead_revision has talent_id=None

    def test_leads_list_all_includes_status_display(self, db_session, seed_leads, seed_talent_products):
        """leads_list resolves status_display via STATUS_DISPLAY mapping."""
        from app.services import leads as leads_service
        rows = leads_service.leads_list(db_session)
        status_displays = {r["status_filtrado"]: r["status_display"] for r in rows}
        assert status_displays["✅ Aprobado - Respuesta enviada"] == "Aprobado"
        assert status_displays["🚫 Remitente bloqueado"] == "Bloqueado"
        assert status_displays["En revisión"] == "En revisión"

    def test_leads_list_filter_talent(self, db_session, seed_leads, seed_talent_products):
        """leads_list(talent_id=X) returns only leads for that talent."""
        from app.services import leads as leads_service
        talent_a = seed_talent_products["talent_a"]
        rows = leads_service.leads_list(db_session, talent_id=talent_a.id)
        assert len(rows) == 1
        assert rows[0]["talent_name"] == "Talento Uno"
        assert rows[0]["remitente_email"] == "aprobado@example.com"

    def test_leads_list_filter_status(self, db_session, seed_leads):
        """leads_list(status=QUALIFIED_STATUS) returns only calificado leads."""
        from app.services import leads as leads_service
        rows = leads_service.leads_list(db_session, status="✅ Aprobado - Respuesta enviada")
        assert len(rows) == 1
        assert rows[0]["status_filtrado"] == "✅ Aprobado - Respuesta enviada"
        assert rows[0]["status_display"] == "Aprobado"

    def test_leads_list_filter_fuente(self, db_session, seed_leads):
        """leads_list(fuente='Gmail') returns all leads (all seeds are Gmail)."""
        from app.services import leads as leads_service
        rows = leads_service.leads_list(db_session, fuente="Gmail")
        assert len(rows) == 3

    def test_leads_list_unmapped_status_falls_back_to_raw(self, db_session, seed_talent_products):
        """status_display falls back to raw status_filtrado when not in STATUS_DISPLAY."""
        from app.models import Lead
        from app.services import leads as leads_service
        # Insert a lead with an unmapped status
        lead_weird = Lead(
            sheet_row_id=99,
            remitente_email="weird@example.com",
            remitente_nombre="Weird",
            asunto="Unknown status",
            talent_id=None,
            status_filtrado="Estado desconocido",
            fuente="Gmail",
            score_calidad=None,
            bloqueado=False,
            convertido_a_prospecto=False,
        )
        db_session.add(lead_weird)
        db_session.commit()
        rows = leads_service.leads_list(db_session)
        weird_row = next(r for r in rows if r["remitente_email"] == "weird@example.com")
        assert weird_row["status_display"] == "Estado desconocido"


# ---------------------------------------------------------------------------
# GET /leads endpoint tests (Plan 03-02)
# ---------------------------------------------------------------------------

class TestLeadsListEndpoint:
    """Tests for GET /leads."""

    def test_leads_endpoint_auth(self, auth_client, seed_leads):
        """GET /leads returns 200 with authenticated client."""
        response = auth_client.get("/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    def test_leads_endpoint_unauth(self, client):
        """GET /leads returns 401 without authentication."""
        response = client.get("/leads")
        assert response.status_code == 401

    def test_leads_endpoint_filter_talent_404(self, auth_client):
        """GET /leads?talent_id=<nonexistent> returns 404."""
        response = auth_client.get("/leads?talent_id=99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Talent not found"

    def test_leads_endpoint_filter_talent_valid(self, auth_client, seed_leads, seed_talent_products):
        """GET /leads?talent_id=X returns only leads for that talent."""
        talent_a = seed_talent_products["talent_a"]
        response = auth_client.get(f"/leads?talent_id={talent_a.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["talent_name"] == "Talento Uno"

    def test_leads_endpoint_has_required_fields(self, auth_client, seed_leads):
        """Each lead row has all LeadRow fields."""
        response = auth_client.get("/leads")
        data = response.json()
        required_fields = {
            "id", "sheet_row_id", "remitente_nombre", "remitente_email", "asunto",
            "talent_id", "talent_name", "status_filtrado", "status_display",
            "fuente", "score_calidad", "bloqueado", "convertido_a_prospecto",
        }
        for row in data:
            for field in required_fields:
                assert field in row, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Fase 8 (8.1) — email body sanitization, truncation, sync wiring
# ---------------------------------------------------------------------------

def _sheet_row(**overrides):
    """Build a SheetLeadRow with sane defaults; override any field per test."""
    from app.integrations.sheets import SheetLeadRow
    defaults = dict(
        sheet_row_id=2,
        remitente_email="lead@example.com",
        remitente_nombre="Lead Uno",
        asunto="Colaboración",
        fecha_recepcion="",
        talento_mencionado="",
        status_filtrado="En revisión",
        score_calidad=None,
        bloqueado=False,
        convertido_a_prospecto=False,
        email_completo="",
        razon_validacion="",
        categoria_detectada="",
    )
    defaults.update(overrides)
    return SheetLeadRow(**defaults)


class TestSanitizeEmailBody:
    """_sanitize_email_body: bleach (D9) + 1 MB cap (D8)."""

    def test_innocent_plain_text_passes_through_unchanged(self):
        from app.sync.jobs import _sanitize_email_body
        text = "Hola, muy bien. Soy Pame. Visita https://x.com o a@b.com. Saludos,"
        clean, truncated = _sanitize_email_body(text)
        assert clean == text          # plain text must NOT be mangled
        assert truncated is False

    def test_none_and_empty_return_none(self):
        from app.sync.jobs import _sanitize_email_body
        assert _sanitize_email_body(None) == (None, False)
        assert _sanitize_email_body("") == (None, False)

    def test_html_script_tag_is_stripped(self):
        from app.sync.jobs import _sanitize_email_body
        clean, _ = _sanitize_email_body("Hola <script>alert(1)</script> mundo")
        assert "<script>" not in clean
        assert "</script>" not in clean

    def test_oversize_ascii_is_truncated_under_cap(self):
        from app.sync.jobs import _sanitize_email_body, _EMAIL_MAX_BYTES
        clean, truncated = _sanitize_email_body("a" * (_EMAIL_MAX_BYTES + 5000))
        assert truncated is True
        assert len(clean.encode("utf-8")) <= _EMAIL_MAX_BYTES

    def test_multibyte_truncation_stays_valid_utf8(self):
        from app.sync.jobs import _sanitize_email_body, _EMAIL_MAX_BYTES
        clean, truncated = _sanitize_email_body("ñ" * _EMAIL_MAX_BYTES)  # 2 bytes each
        assert truncated is True
        assert len(clean.encode("utf-8")) <= _EMAIL_MAX_BYTES
        clean.encode("utf-8")  # raises if a partial multibyte char survived


class TestSheetLeadRowEmailFields:
    """SheetLeadRow carries the two new Fase 8 columns."""

    def test_email_fields_present(self):
        row = _sheet_row(
            email_completo="cuerpo",
            razon_validacion="industria prohibida",
            categoria_detectada="Moda/Retail",
        )
        assert row.email_completo == "cuerpo"
        assert row.razon_validacion == "industria prohibida"
        assert row.categoria_detectada == "Moda/Retail"

    def test_email_fields_default_empty(self):
        from app.integrations.sheets import SheetLeadRow
        row = SheetLeadRow(
            sheet_row_id=3, remitente_email="x@y.com", remitente_nombre="X",
            asunto="a", fecha_recepcion="", talento_mencionado="",
            status_filtrado="En revisión", score_calidad=None,
            bloqueado=False, convertido_a_prospecto=False,
        )
        assert row.email_completo == ""
        assert row.razon_validacion == ""
        assert row.categoria_detectada == ""


class TestSyncSheetsEmailBody:
    """sync_sheets persists sanitized, size-capped email bodies (8.1)."""

    def test_sync_stores_sanitized_email_and_razon(self, db_session, monkeypatch):
        from app.sync import jobs
        from app.models import Lead
        monkeypatch.setattr(
            jobs.sheets, "get_leads_rows",
            lambda: [_sheet_row(
                sheet_row_id=2,
                email_completo="Hola <script>alert(1)</script> mundo",
                razon_validacion="<b>industria prohibida (casino)</b>",
                categoria_detectada="<i>Casino</i>",
            )],
        )
        jobs.sync_sheets(db_session)

        lead = db_session.query(Lead).filter(Lead.sheet_row_id == 2).one()
        assert "<script>" not in lead.email_completo
        assert "<b>" not in lead.razon_validacion
        assert "industria prohibida (casino)" in lead.razon_validacion
        assert "<i>" not in lead.categoria_detectada
        assert lead.categoria_detectada == "Casino"
        assert lead.email_truncated is False

    def test_sync_empty_email_stores_none(self, db_session, monkeypatch):
        from app.sync import jobs
        from app.models import Lead
        monkeypatch.setattr(
            jobs.sheets, "get_leads_rows",
            lambda: [_sheet_row(sheet_row_id=5, email_completo="", razon_validacion="")],
        )
        jobs.sync_sheets(db_session)

        lead = db_session.query(Lead).filter(Lead.sheet_row_id == 5).one()
        assert lead.email_completo is None
        assert lead.razon_validacion is None
        assert lead.email_truncated is False

    def test_sync_oversize_email_sets_truncated_flag(self, db_session, monkeypatch):
        from app.sync import jobs
        from app.sync.jobs import _EMAIL_MAX_BYTES
        from app.models import Lead
        monkeypatch.setattr(
            jobs.sheets, "get_leads_rows",
            lambda: [_sheet_row(sheet_row_id=7, email_completo="a" * (_EMAIL_MAX_BYTES + 1000))],
        )
        jobs.sync_sheets(db_session)

        lead = db_session.query(Lead).filter(Lead.sheet_row_id == 7).one()
        assert lead.email_truncated is True
        assert len(lead.email_completo.encode("utf-8")) <= _EMAIL_MAX_BYTES


# ---------------------------------------------------------------------------
# Fase 8 (8.2) — GET /leads/{id} detail endpoint
# ---------------------------------------------------------------------------

class TestLeadDetailEndpoint:
    """Tests for GET /leads/{id} (lead detail for the modal)."""

    def _lead_id(self, email):
        from tests.conftest import TestSessionLocal
        from app.models import Lead
        db = TestSessionLocal()
        try:
            return db.query(Lead).filter(Lead.remitente_email == email).one().id
        finally:
            db.close()

    def test_detail_requires_auth(self, client, seed_leads):
        """GET /leads/{id} without auth → 401."""
        lead_id = self._lead_id("aprobado@example.com")
        assert client.get(f"/leads/{lead_id}").status_code == 401

    def test_detail_returns_200_with_full_shape(self, auth_client, seed_leads, seed_talent_products):
        """GET /leads/{id} returns the full Lead shape + resolved talent_name."""
        lead_id = self._lead_id("aprobado@example.com")
        response = auth_client.get(f"/leads/{lead_id}")
        assert response.status_code == 200
        data = response.json()

        required = {
            "id", "sheet_row_id", "remitente_email", "remitente_nombre", "asunto",
            "fecha_recepcion", "talent_id", "talent_name", "status_filtrado",
            "status_display", "fuente", "score_calidad", "bloqueado",
            "convertido_a_prospecto", "email_completo", "razon_validacion",
            "categoria_detectada", "email_truncated",
        }
        assert required <= set(data.keys()), f"missing: {required - set(data.keys())}"
        assert data["id"] == lead_id
        assert data["talent_name"] == "Talento Uno"
        assert data["status_display"] == "Aprobado"
        assert isinstance(data["email_truncated"], bool)

    def test_detail_404_for_missing_lead(self, auth_client):
        """GET /leads/{id} for a nonexistent id → 404."""
        response = auth_client.get("/leads/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Lead not found"

    def test_detail_null_email_body_returns_null_not_error(self, auth_client, seed_leads):
        """A lead with NULL email_completo returns 200 with null fields (D7)."""
        lead_id = self._lead_id("aprobado@example.com")  # seeded without email body
        response = auth_client.get(f"/leads/{lead_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["email_completo"] is None
        assert data["razon_validacion"] is None
        assert data["categoria_detectada"] is None
        assert data["email_truncated"] is False

    def test_detail_sin_talento_has_null_talent_name(self, auth_client, seed_leads):
        """A lead with talent_id=None → talent_name is null (frontend shows 'Sin talento')."""
        lead_id = self._lead_id("revision@example.com")
        data = auth_client.get(f"/leads/{lead_id}").json()
        assert data["talent_id"] is None
        assert data["talent_name"] is None
