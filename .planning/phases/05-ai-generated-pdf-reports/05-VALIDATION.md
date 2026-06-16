---
phase: 5
slug: ai-generated-pdf-reports
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths = ["tests"]) |
| **Quick run command** | `uv run pytest tests/test_reports.py -x` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_reports.py -x`
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 05-01 | 0 | REPORT-01 | — | N/A | infra | `uv run pytest tests/test_reports.py -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 05-01 | 0 | REPORT-01 | — | mock_anthropic fixture prevents real API calls | fixture | conftest.py has mock_anthropic | ❌ W0 | ⬜ pending |
| 5-01-03 | 05-01 | 0 | REPORT-01 | — | mock_weasyprint fixture prevents real PDF rendering | fixture | conftest.py has mock_weasyprint | ❌ W0 | ⬜ pending |
| 5-02-01 | 05-02 | 1 | REPORT-01 | — | available_months() returns YYYY-MM list | unit | `pytest tests/test_reports.py::test_available_months -x` | ❌ W0 | ⬜ pending |
| 5-02-02 | 05-02 | 1 | REPORT-01 | — | generate_report() uses only Python-computed figures | unit | `pytest tests/test_reports.py::test_generate_report_payload -x` | ❌ W0 | ⬜ pending |
| 5-02-03 | 05-02 | 1 | REPORT-01 | T-path-traversal | slug sanitized: only [a-z0-9-] chars | unit | `pytest tests/test_reports.py::test_pdf_written_to_disk -x` | ❌ W0 | ⬜ pending |
| 5-02-04 | 05-02 | 1 | REPORT-01 | T-ssrf | base_url is fixed "." not user-controlled | unit | `pytest tests/test_reports.py::test_generate_endpoint -x` | ❌ W0 | ⬜ pending |
| 5-03-01 | 05-03 | 2 | REPORT-02 | T-unauth-dl | download endpoint requires get_current_user | integration | `pytest tests/test_reports.py::test_list_reports -x` | ❌ W0 | ⬜ pending |
| 5-03-02 | 05-03 | 2 | REPORT-02 | T-unauth-dl | unauthenticated download returns 401 | integration | `pytest tests/test_reports.py::test_download_report -x` | ❌ W0 | ⬜ pending |
| 5-04-01 | 05-04 | 3 | DASH-05 | T-xss | Claude text escaped with escHtml() before innerHTML | smoke | `grep -q 'page-reportes' frontend/index.html` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_reports.py` — stubs for REPORT-01, REPORT-02, DASH-05 (7 test functions)
- [ ] `mock_anthropic` fixture — add to `tests/conftest.py`
- [ ] `mock_weasyprint` fixture — add to `tests/conftest.py`
- [ ] `reports/` directory — create and add to `.gitignore`
- [ ] `templates/reports/report_template.html` — Jinja2 PDF template
- [ ] Alembic migration for `Report` model

### mock_anthropic fixture (for conftest.py)

```python
@pytest.fixture()
def mock_anthropic(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"resumen_ejecutivo":"Resumen de prueba.","deals_destacados":"Deals de prueba.","recomendacion":"Recomendación de prueba."}')]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr("app.services.reports.anthropic.Anthropic", lambda **kwargs: mock_client)
    return mock_client
```

### mock_weasyprint fixture (for conftest.py)

```python
@pytest.fixture()
def mock_weasyprint(monkeypatch, tmp_path):
    def fake_write_pdf(path_or_none=None):
        if path_or_none:
            open(path_or_none, "wb").write(b"%PDF-1.4")
        return b"%PDF-1.4"
    mock_html = MagicMock()
    mock_html.return_value.write_pdf = fake_write_pdf
    monkeypatch.setattr("app.services.reports.HTML", mock_html)
    return mock_html
```

---

## Security Threat Map

| Threat ID | Pattern | STRIDE | Mitigation |
|-----------|---------|--------|------------|
| T-path-traversal | Path traversal via talent slug in file path | Tampering | Use `str(talent.id)` for filename or `re.sub(r'[^a-z0-9\-]', '', slug)`; validate resolved path stays within `reports/` |
| T-xss | Stored XSS via Claude narrative in preview card | Spoofing | Apply `escHtml()` to all Claude text before `innerHTML` in `reports.js` |
| T-ssrf | SSRF via `base_url` in WeasyPrint | Information Disclosure | Never pass user-controlled values as `base_url`; use `"."` |
| T-unauth-dl | Unauthenticated PDF download | Elevation of Privilege | Router-level `dependencies=[Depends(get_current_user)]` on all `/reports/*` endpoints |
| T-prompt-injection | Prompt injection via deal title in Claude payload | Tampering | Deal data sent as structured JSON in user message, not free-form; system prompt instructs data-only treatment |

---

## ASVS Coverage

| ASVS Category | Applies | Control |
|---------------|---------|---------|
| V2 Authentication | yes | `get_current_user` on all `/reports/*` routes |
| V4 Access Control | yes | Router-level `dependencies=[Depends(get_current_user)]` |
| V5 Input Validation | yes | `ReportGenerate` Pydantic schema: `talent_id: int`, `month: str` (pattern `^\d{4}-\d{2}$`) |
