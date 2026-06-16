"""Tests for Phase 5 AI-Generated PDF Reports.

Wave 1 (05-02): Service layer and generate endpoint.
Wave 2 (05-03): History list and download endpoints.

Test IDs match the Per-Task Verification Map in 05-VALIDATION.md:
  5-02-01 → test_available_months
  5-02-02 → test_generate_report_payload
  5-02-03 → test_pdf_written_to_disk
  5-02-04 → test_generate_endpoint
  5-03-01 → test_list_reports       (Wave 2 — 05-03)
  5-03-02 → test_download_report    (Wave 2 — 05-03)
  5-04-01 → test_reportes_tab_exists (Wave 3 stubs — 05-04)
"""
import json
from datetime import datetime

import pytest

from app.models import Deal, Report, Talent


class TestAvailableMonths:
    """5-02-01 — REPORT-01: available_months() returns sorted YYYY-MM list."""

    def test_available_months_returns_list(self, db_session, seed_deals):
        """Returns distinct YYYY-MM strings from Deal.add_time for a talent, descending."""
        from app.services import reports as reports_service

        talent_a = seed_deals["deal_open"].talent_id
        months = reports_service.available_months(db_session, talent_a)
        assert isinstance(months, list)
        # seed_deals has deal_open (add_time "2026-05-20T09:00:00Z" → "2026-05")
        # and deal_lost (add_time "2026-05-15T09:00:00Z" → "2026-05") for talent_a
        assert "2026-05" in months

    def test_available_months_empty_for_unknown_talent(self, db_session):
        """Returns empty list for talent ID with no deals."""
        from app.services import reports as reports_service

        result = reports_service.available_months(db_session, 999999)
        assert result == []

    def test_available_months_descending_order(self, db_session, seed_deals):
        """Returned list is sorted descending."""
        from app.services import reports as reports_service

        # Add a second deal for talent_a with a different month
        talent_a = seed_deals["deal_open"].talent_id
        deal_older = Deal(
            pipedrive_id=9001,
            title="Old deal",
            value=1000.0,
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent_a,
            commission_amount=700.0,
            is_sin_cotizar=False,
            update_time="2026-01-01T10:00:00Z",
            add_time="2026-01-10T09:00:00Z",
        )
        db_session.add(deal_older)
        db_session.commit()

        months = reports_service.available_months(db_session, talent_a)
        assert months == sorted(set(months), reverse=True)

    def test_available_months_excludes_invalid_add_time(self, db_session, seed_deals):
        """Excludes entries whose add_time[:7] does not match YYYY-MM."""
        from app.services import reports as reports_service

        talent_a = seed_deals["deal_open"].talent_id
        # Add a deal with an invalid add_time
        bad_deal = Deal(
            pipedrive_id=9002,
            title="Bad time deal",
            value=1000.0,
            currency="MXN",
            stage_id=1,
            stage_name="Llamada",
            status="open",
            talent_id=talent_a,
            commission_amount=700.0,
            is_sin_cotizar=False,
            update_time="2026-01-01T10:00:00Z",
            add_time=None,  # None should be excluded
        )
        db_session.add(bad_deal)
        db_session.commit()

        months = reports_service.available_months(db_session, talent_a)
        # None add_time should not appear
        assert None not in months
        assert "" not in months


class TestGenerateReportPayload:
    """5-02-02 — REPORT-01: generate_report() uses only Python-computed figures.

    Hard rule (05-CONTEXT.md, STATE.md): Claude narrates only; all numeric
    figures must come from Python services (kpis, funnel, leads).
    """

    def test_payload_contains_python_figures(self, db_session, seed_deals,
                                              mock_anthropic, mock_weasyprint):
        """The payload passed to Claude contains only JSON-serializable Python scalars."""
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        talent = db_session.get(Talent, talent_id)

        payload = reports_service._build_payload(db_session, talent, "2026-05")
        # Must be JSON-serializable (no ORM objects)
        json_str = json.dumps(payload)
        assert isinstance(json_str, str)
        # Must contain expected top-level keys
        assert "talent_name" in payload
        assert "month" in payload
        assert "kpis" in payload
        assert "funnel" in payload

    def test_payload_does_not_ask_claude_to_compute_numbers(self, db_session, seed_deals,
                                                              mock_anthropic, mock_weasyprint):
        """The payload includes pre-computed numbers; Claude should only narrate."""
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        talent = db_session.get(Talent, talent_id)

        payload = reports_service._build_payload(db_session, talent, "2026-05")
        kpis = payload["kpis"]
        # pipeline, cerrados_count, cerrados_valor, comision should all be Python numbers
        assert isinstance(kpis.get("pipeline"), (int, float))
        assert isinstance(kpis.get("cerrados_count"), (int, float))
        assert isinstance(kpis.get("cerrados_valor"), (int, float))
        assert isinstance(kpis.get("comision"), (int, float))


class TestPdfWrittenToDisk:
    """5-02-03 — REPORT-01: PDF file is written to disk; path sanitized (T-path-traversal).

    File path must use str(talent.id) slug, not talent.name (avoids Unicode path issues).
    Resolved path must stay within the reports/ directory.
    """

    def test_pdf_written_to_disk(self, db_session, seed_deals,
                                  mock_anthropic, mock_weasyprint):
        """generate_report writes a PDF and returns dict with file_size_bytes > 0."""
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        result = reports_service.generate_report(db_session, talent_id, "2026-05")

        assert isinstance(result, dict)
        assert result["file_size_bytes"] > 0
        assert "narrative" in result
        assert "resumen_ejecutivo" in result["narrative"]
        assert "deals_destacados" in result["narrative"]
        assert "recomendacion" in result["narrative"]

    def test_pdf_path_uses_talent_id_not_name(self, db_session, seed_deals,
                                               mock_anthropic, mock_weasyprint):
        """File path uses str(talent.id) as slug — numeric only, no path separators."""
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        result = reports_service.generate_report(db_session, talent_id, "2026-05")

        # Path should be reports/{talent_id}/{month}.pdf
        file_path = result["file_path"]
        assert f"reports/{talent_id}/" in file_path
        assert file_path.endswith(".pdf")
        # Talent name (Talento Uno) should NOT appear in path
        talent = db_session.get(Talent, talent_id)
        assert talent.name not in file_path


class TestGenerateEndpoint:
    """5-02-04 — REPORT-01: POST /reports/generate returns 200 with full ReportOut payload."""

    def test_generate_requires_auth(self, client):
        """Unauthenticated POST returns 401."""
        response = client.post("/reports/generate", json={"talent_id": 1, "month": "2026-05"})
        assert response.status_code == 401

    def test_generate_returns_200_with_auth(self, auth_client, seed_deals,
                                             mock_anthropic, mock_weasyprint):
        """Authenticated POST with valid talent_id + month returns 200."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "narrative" in data
        assert "resumen_ejecutivo" in data["narrative"]

    def test_generate_response_has_required_fields(self, auth_client, seed_deals,
                                                    mock_anthropic, mock_weasyprint):
        """Response includes all ReportOut fields."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert response.status_code == 200
        data = response.json()
        required = {"id", "talent_id", "talent_name", "month",
                    "generated_at", "file_size_bytes", "narrative"}
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_generate_invalid_month_returns_422(self, auth_client, seed_deals):
        """Invalid month format (not YYYY-MM) returns 422 validation error."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "not-a-month"},
        )
        assert response.status_code == 422

    def test_generate_unknown_talent_returns_404(self, auth_client, mock_anthropic, mock_weasyprint):
        """Unknown talent_id returns 404."""
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": 999999, "month": "2026-05"},
        )
        assert response.status_code == 404


class TestListReports:
    """5-03-01 — REPORT-02: GET /reports/ returns history list; requires auth."""

    def test_list_reports_requires_auth(self, client):
        """Unauthenticated GET /reports/ returns 401 (T-unauth-dl)."""
        response = client.get("/reports/")
        assert response.status_code == 401

    def test_list_reports_returns_empty_list(self, auth_client):
        """Authenticated GET /reports/ returns empty list when no reports exist."""
        response = auth_client.get("/reports/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_reports_returns_generated_reports(self, auth_client, seed_deals,
                                                     mock_anthropic, mock_weasyprint):
        """After generating a report, GET /reports/ returns it with all required fields."""
        talent_id = seed_deals["deal_open"].talent_id

        # Generate a report so a row exists
        gen_response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert gen_response.status_code == 200

        # List reports — should contain the generated one
        response = auth_client.get("/reports/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify all required ReportHistoryItem fields are present
        item = data[0]
        required_fields = {"id", "talent_id", "talent_name", "month", "generated_at", "file_size_bytes"}
        for field in required_fields:
            assert field in item, f"Missing field: {field}"

        assert item["talent_id"] == talent_id
        assert item["month"] == "2026-05"
        assert item["talent_name"] != ""
        assert item["file_size_bytes"] > 0


class TestDownloadReport:
    """5-03-02 — REPORT-02: GET /reports/{id}/download returns PDF; unauthenticated returns 401."""

    def test_download_requires_auth(self, client):
        """Unauthenticated GET /reports/1/download returns 401 (T-unauth-dl)."""
        response = client.get("/reports/1/download")
        assert response.status_code == 401

    def test_download_returns_pdf(self, auth_client, seed_deals,
                                   mock_anthropic, mock_weasyprint):
        """Generated report can be downloaded as application/pdf with Content-Disposition: attachment."""
        talent_id = seed_deals["deal_open"].talent_id

        # Generate a report first so the file exists on disk (via mock_weasyprint)
        gen_response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert gen_response.status_code == 200
        report_id = gen_response.json()["id"]

        # Download the PDF
        response = auth_client.get(f"/reports/{report_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert ".pdf" in content_disp

    def test_download_404_for_missing_report(self, auth_client):
        """GET /reports/999999/download returns 404 when no Report row exists."""
        response = auth_client.get("/reports/999999/download")
        assert response.status_code == 404

    def test_download_missing_file(self, auth_client, db_session, seed_deals):
        """Report row pointing at a nonexistent file path returns 404 (T-stale-path defense)."""
        talent_id = seed_deals["deal_open"].talent_id

        # Insert a Report row with a file_path that does not exist on disk
        stale_report = Report(
            talent_id=talent_id,
            month="2020-01",
            file_path="/nonexistent/path/that/does/not/exist.pdf",
            file_size_bytes=1234,
            generated_at=datetime.utcnow(),
        )
        db_session.add(stale_report)
        db_session.commit()
        db_session.refresh(stale_report)

        response = auth_client.get(f"/reports/{stale_report.id}/download")
        assert response.status_code == 404


class TestReportesTabExists:
    """5-04-01 — DASH-05: Reportes tab is present in frontend/index.html."""

    def test_reportes_tab_exists(self):
        """Smoke check: page-reportes div must exist in index.html (Wave 3 implements content)."""
        pytest.fail("not implemented — Wave 3 (05-04)")
