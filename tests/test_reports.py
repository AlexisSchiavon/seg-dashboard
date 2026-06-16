"""Wave 0 — Failing test stubs for Phase 5 AI-Generated PDF Reports.

These stubs define the test contract for REPORT-01, REPORT-02, and DASH-05.
They all fail intentionally until the service layer (05-02) and router (05-03)
are implemented. The pattern mirrors tests/test_leads.py.

Test IDs match the Per-Task Verification Map in 05-VALIDATION.md:
  5-02-01 → test_available_months
  5-02-02 → test_generate_report_payload
  5-02-03 → test_pdf_written_to_disk
  5-02-04 → test_generate_endpoint
  5-03-01 → test_list_reports
  5-03-02 → test_download_report
  5-04-01 → test_reportes_tab_exists (DASH-05 smoke)
"""
import pytest


class TestAvailableMonths:
    """5-02-01 — REPORT-01: available_months() returns sorted YYYY-MM list."""

    def test_available_months_returns_list(self, db_session, seed_deals):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_available_months_empty_for_unknown_talent(self, db_session):
        pytest.fail("not implemented — Wave 1 (05-02)")


class TestGenerateReportPayload:
    """5-02-02 — REPORT-01: generate_report() uses only Python-computed figures.

    Hard rule (05-CONTEXT.md, STATE.md): Claude narrates only; all numeric
    figures must come from Python services (kpis, funnel, leads).
    """

    def test_payload_contains_python_figures(self, db_session, seed_deals,
                                              mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_payload_does_not_ask_claude_to_compute_numbers(self, db_session, seed_deals,
                                                              mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")


class TestPdfWrittenToDisk:
    """5-02-03 — REPORT-01: PDF file is written to disk; path sanitized (T-path-traversal).

    File path must use str(talent.id) slug, not talent.name (avoids Unicode path issues).
    Resolved path must stay within the reports/ directory.
    """

    def test_pdf_written_to_disk(self, db_session, seed_deals,
                                  mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_pdf_path_uses_talent_id_not_name(self, db_session, seed_deals,
                                               mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")


class TestGenerateEndpoint:
    """5-02-04 — REPORT-01: POST /reports/generate returns 200 with full ReportOut payload."""

    def test_generate_requires_auth(self, client):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_generate_returns_200_with_auth(self, auth_client, seed_deals,
                                             mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_generate_response_has_required_fields(self, auth_client, seed_deals,
                                                    mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 1 (05-02)")

    def test_generate_invalid_month_returns_422(self, auth_client, seed_deals):
        pytest.fail("not implemented — Wave 1 (05-02)")


class TestListReports:
    """5-03-01 — REPORT-02: GET /reports/ returns history list; requires auth."""

    def test_list_reports_requires_auth(self, client):
        pytest.fail("not implemented — Wave 2 (05-03)")

    def test_list_reports_returns_empty_list(self, auth_client):
        pytest.fail("not implemented — Wave 2 (05-03)")

    def test_list_reports_returns_generated_reports(self, auth_client, seed_deals,
                                                     mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 2 (05-03)")


class TestDownloadReport:
    """5-03-02 — REPORT-02: GET /reports/{id}/download returns PDF; unauthenticated returns 401."""

    def test_download_requires_auth(self, client):
        pytest.fail("not implemented — Wave 2 (05-03)")

    def test_download_returns_pdf(self, auth_client, seed_deals,
                                   mock_anthropic, mock_weasyprint):
        pytest.fail("not implemented — Wave 2 (05-03)")

    def test_download_404_for_missing_report(self, auth_client):
        pytest.fail("not implemented — Wave 2 (05-03)")


class TestReportesTabExists:
    """5-04-01 — DASH-05: Reportes tab is present in frontend/index.html."""

    def test_reportes_tab_exists(self):
        """Smoke check: page-reportes div must exist in index.html (Wave 3 implements content)."""
        pytest.fail("not implemented — Wave 3 (05-04)")
