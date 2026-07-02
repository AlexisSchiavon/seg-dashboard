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


class TestGenerateReportService:
    """Fase 9.5: generate_report_pdf renders PDF bytes in memory and upserts a
    metadata-only Report row (no PDF on disk, no narrative)."""

    def test_returns_pdf_bytes_and_persists_metadata(self, db_session, seed_deals, mock_weasyprint):
        """Single-talent generation returns bytes + upserts a row with talent_ids/hash."""
        from app.models import Report
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        result = reports_service.generate_report_pdf(db_session, [talent_id], "2026-05")

        assert result["pdf_bytes"].startswith(b"%PDF")
        assert result["file_size_bytes"] == len(result["pdf_bytes"])
        assert result["talent_ids"] == str(talent_id)
        assert result["is_consolidated"] is False
        assert "narrative" not in result  # Claude removed (D8)

        row = db_session.get(Report, result["report_id"])
        assert row.talent_id == talent_id
        assert row.talent_ids == str(talent_id)
        assert row.content_hash and len(row.content_hash) == 64  # sha256 hex
        assert row.file_path is None  # no disk persistence

    def test_filename_uses_talent_slug(self, db_session, seed_deals, mock_weasyprint):
        """Individual filename is reporte-<slug>-<period>.pdf (accent-free)."""
        from app.services import reports as reports_service

        talent = db_session.get(Talent, seed_deals["deal_open"].talent_id)
        result = reports_service.generate_report_pdf(db_session, [talent.id], "2026-05")
        expected = f"reporte-{reports_service.filename_slug(talent.name)}-2026-05.pdf"
        assert result["filename"] == expected

    def test_consolidated_all_persists_null_talent_id(self, db_session, seed_deals, mock_weasyprint):
        """'all' → talent_id NULL, talent_ids='all', consolidated filename."""
        from app.models import Report
        from app.services import reports as reports_service

        result = reports_service.generate_report_pdf(db_session, "all", "2026-05")

        assert result["is_consolidated"] is True
        assert result["talent_ids"] == "all"
        assert result["filename"] == "reporte-consolidado-2026-05.pdf"
        row = db_session.get(Report, result["report_id"])
        assert row.talent_id is None
        assert row.talent_ids == "all"

    def test_unknown_talent_raises(self, db_session, mock_weasyprint):
        """A bad talent id raises ValueError (mapped to 404 at the endpoint)."""
        from app.services import reports as reports_service

        with pytest.raises(ValueError):
            reports_service.generate_report_pdf(db_session, [999999], "2026-05")

    def test_regenerate_reproduces_pdf(self, db_session, seed_deals, mock_weasyprint):
        """Download path: regenerate_report_pdf rebuilds the PDF from the row."""
        from app.models import Report
        from app.services import reports as reports_service

        talent_id = seed_deals["deal_open"].talent_id
        result = reports_service.generate_report_pdf(db_session, [talent_id], "2026-05")
        row = db_session.get(Report, result["report_id"])

        pdf_bytes, filename = reports_service.regenerate_report_pdf(db_session, row)
        assert pdf_bytes.startswith(b"%PDF")
        assert filename == result["filename"]


class TestGenerateEndpoint:
    """5-02-04 — REPORT-01: POST /reports/generate returns 200 with full ReportOut payload."""

    def test_generate_requires_auth(self, client):
        """Unauthenticated POST returns 401."""
        response = client.post("/reports/generate", json={"talent_id": 1, "month": "2026-05"})
        assert response.status_code == 401

    def test_generate_returns_pdf_stream(self, auth_client, seed_deals, mock_weasyprint):
        """Fase 9.5: POST streams the PDF (application/pdf attachment), not JSON."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert response.content.startswith(b"%PDF")

    def test_generate_talent_ids_list(self, auth_client, seed_deals, mock_weasyprint):
        """Fase 9.5: talent_ids as a list works (single-element list here)."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_ids": [talent_id], "month": "2026-05"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    def test_generate_all_consolidated(self, auth_client, seed_deals, mock_weasyprint):
        """Fase 9.5: talent_ids='all' streams the consolidated PDF."""
        response = auth_client.post(
            "/reports/generate",
            json={"talent_ids": "all", "period_type": "month", "period_value": "2026-05"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "consolidado" in response.headers.get("content-disposition", "")

    def test_generate_no_target_returns_422(self, auth_client, seed_deals, mock_weasyprint):
        """Neither talent_ids nor talent_id provided → 422."""
        response = auth_client.post("/reports/generate", json={"month": "2026-05"})
        assert response.status_code == 422

    def test_generate_invalid_month_returns_422(self, auth_client, seed_deals):
        """Invalid month format (not YYYY-MM) returns 422 validation error."""
        talent_id = seed_deals["deal_open"].talent_id
        response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "not-a-month"},
        )
        assert response.status_code == 422

    def test_generate_unknown_talent_returns_404(self, auth_client, mock_weasyprint):
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
                                                     mock_weasyprint):
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

    def test_download_regenerates_pdf(self, auth_client, seed_deals, mock_weasyprint):
        """Fase 9.5: download regenerates the PDF from the stored row (no disk file).

        The generate endpoint now streams the PDF (no JSON body), so the report id
        is fetched from the history list.
        """
        talent_id = seed_deals["deal_open"].talent_id

        gen_response = auth_client.post(
            "/reports/generate",
            json={"talent_id": talent_id, "month": "2026-05"},
        )
        assert gen_response.status_code == 200

        report_id = auth_client.get("/reports/").json()[0]["id"]

        response = auth_client.get(f"/reports/{report_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert ".pdf" in content_disp
        assert response.content.startswith(b"%PDF")

    def test_download_404_for_missing_report(self, auth_client):
        """GET /reports/999999/download returns 404 when no Report row exists."""
        response = auth_client.get("/reports/999999/download")
        assert response.status_code == 404

    def test_download_legacy_row_regenerates_via_fk(self, auth_client, db_session,
                                                     seed_deals, mock_weasyprint):
        """A legacy row (talent_ids NULL, only talent_id set) regenerates via the FK fallback."""
        talent_id = seed_deals["deal_open"].talent_id

        legacy_report = Report(
            talent_id=talent_id,
            talent_ids=None,  # pre-9.5 row
            month="2026-05",
            file_path=None,
            file_size_bytes=1234,
            generated_at=datetime.utcnow(),
        )
        db_session.add(legacy_report)
        db_session.commit()
        db_session.refresh(legacy_report)

        response = auth_client.get(f"/reports/{legacy_report.id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"


class TestReportesTabExists:
    """5-04-01 — DASH-05: Reportes tab is present in frontend/index.html."""

    def test_reportes_tab_exists(self):
        """Smoke check: page-reportes div and reports.js exist (DASH-05 gate)."""
        import os

        # Locate project root relative to this test file
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(tests_dir)

        # Check that index.html contains page-reportes markup
        index_path = os.path.join(project_root, "frontend", "index.html")
        assert os.path.exists(index_path), "frontend/index.html not found"
        with open(index_path, encoding="utf-8") as f:
            html = f.read()
        assert "page-reports" in html, "page-reports div missing from index.html"
        assert "setPage('reports'" in html, "Reportes tab onclick missing from index.html"

        # Check that reports.js exists
        reports_js_path = os.path.join(project_root, "frontend", "js", "reports.js")
        assert os.path.exists(reports_js_path), "frontend/js/reports.js not found"


# ---------------------------------------------------------------------------
# Fase 7 (7.1) — period filtering on the Reporte PDF (D4 selective + quarter + D8)
# ---------------------------------------------------------------------------

from datetime import date as _date, datetime as _dt  # noqa: E402

from app.models import Talent as _Talent, Deal as _Deal  # noqa: E402


def _mk_talent(db):
    t = _Talent(name=f"Rep T {id(object())}", active=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _mk_won(db, talent_id, pid, value, won_dt, commission=0.0):
    d = _Deal(
        pipedrive_id=pid, title=f"Won {pid}", value=value, currency="MXN",
        stage_id=4, stage_name="Contrato", status="won", talent_id=talent_id,
        commission_amount=commission, update_time="2026-01-01T00:00:00", won_time=won_dt,
    )
    db.add(d)
    db.commit()
    return d


def _detail_kpi(data, label):
    """Pluck a detail KPI tile by label from a build_talent_report dict."""
    return next(k for k in data["detail_kpis"] if k["label"] == label)


def test_report_data_filters_won_by_won_time(db_session):
    """7.1/P2/D4 (Fase 9): report 'Cerrados' figures use won_time within the period."""
    from app.services import reports as reports_service

    t = _mk_talent(db_session)
    _mk_won(db_session, t.id, 50001, 10000.0, _dt(2026, 6, 10), commission=7000.0)
    _mk_won(db_session, t.id, 50002, 90000.0, _dt(2026, 3, 10), commission=63000.0)  # outside June

    data = reports_service.build_talent_report(db_session, t, _date(2026, 6, 1), _date(2026, 6, 30))
    cerrados = _detail_kpi(data, "Cerrados")
    assert cerrados["count"] == 1
    assert cerrados["value"] == 10000.0
    assert _detail_kpi(data, "Comisión")["value"] == 7000.0


def test_report_data_pipeline_is_snapshot(db_session):
    """7.1/P2/D4 (Fase 9): open pipeline is NOT filtered by period in the report."""
    from app.services import reports as reports_service

    t = _mk_talent(db_session)
    db_session.add(_Deal(
        pipedrive_id=50101, title="Abierto", value=55000.0, currency="MXN",
        stage_id=2, stage_name="Negociación", status="open", talent_id=t.id,
        update_time="2026-03-01T00:00:00", add_time="2026-03-01T00:00:00",
    ))
    db_session.commit()

    # June period — the March-created open deal must still appear in pipeline (snapshot)
    data = reports_service.build_talent_report(db_session, t, _date(2026, 6, 1), _date(2026, 6, 30))
    assert _detail_kpi(data, "Pipeline")["value"] == 55000.0


def test_generate_accepts_quarter_period(auth_client, db_session, mock_weasyprint):
    """7.1/D5: POST with period_type=quarter streams a report labelled by quarter.

    Fase 9.5: the response is a PDF stream; the period appears in the filename.
    """
    t = _mk_talent(db_session)
    response = auth_client.post(
        "/reports/generate",
        json={"talent_id": t.id, "period_type": "quarter", "period_value": "2026-Q2"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "2026-Q2" in response.headers.get("content-disposition", "")


def test_generate_month_backcompat_still_works(auth_client, db_session, mock_weasyprint):
    """7.1/D8: legacy `month`-only body is treated as period_type=month (streamed)."""
    t = _mk_talent(db_session)
    response = auth_client.post(
        "/reports/generate",
        json={"talent_id": t.id, "month": "2026-05"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "2026-05" in response.headers.get("content-disposition", "")


def test_generate_invalid_period_value_returns_400(auth_client, db_session, mock_weasyprint):
    """7.1/D6: malformed period_value → 400 (not 422/500)."""
    t = _mk_talent(db_session)
    response = auth_client.post(
        "/reports/generate",
        json={"talent_id": t.id, "period_type": "month", "period_value": "2026-13"},
    )
    assert response.status_code == 400


def test_quarters_endpoint_lists_won_quarters(auth_client, db_session):
    """7.1: GET /reports/quarters returns quarters that have a won deal."""
    t = _mk_talent(db_session)
    _mk_won(db_session, t.id, 50201, 1000.0, _dt(2026, 6, 1))
    response = auth_client.get("/reports/quarters")
    assert response.status_code == 200
    assert "2026-Q2" in response.json()
