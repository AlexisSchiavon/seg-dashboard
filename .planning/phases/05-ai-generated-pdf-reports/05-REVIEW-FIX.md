---
phase: 05-ai-generated-pdf-reports
fixed_at: 2026-06-15T23:58:00-06:00
review_path: .planning/phases/05-ai-generated-pdf-reports/05-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-06-15T23:58:00-06:00
**Source review:** `.planning/phases/05-ai-generated-pdf-reports/05-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04)
- Fixed: 6
- Skipped: 0

All 21 tests in `tests/test_reports.py` passed after each individual fix and after the complete set.

---

## Fixed Issues

### WR-04: Month regex tightened to reject impossible values

**Files modified:** `app/schemas/reports.py`
**Commit:** 68df125
**Applied fix:** Changed `pattern=r"^\d{4}-\d{2}$"` to `pattern=r"^\d{4}-(0[1-9]|1[0-2])$"` in `ReportGenerate.month`. Values like `2026-00`, `2026-13`, and `2026-99` now return HTTP 422 instead of reaching the service and producing empty reports.

---

### WR-01: Response guard before accessing `response.content[0].text`

**Files modified:** `app/services/reports.py`, `tests/conftest.py`
**Commit:** 2f9c15d (guard), 91b7e1f (mock fixture update)
**Applied fix:** Added explicit guard in `_call_claude()` before accessing `response.content[0].text`:
```python
if not response.content or response.content[0].type != "text":
    raise ValueError("Claude returned non-JSON")
```
Prevents `IndexError`/`AttributeError` from propagating as HTTP 500 when Claude returns an empty content list or a non-text block. The `mock_anthropic` fixture in `conftest.py` was also updated to set `type="text"` on the mock content block, accurately reflecting the Anthropic API `ContentBlock` structure.

---

### WR-03: `.tmp` file cleanup when WeasyPrint raises an exception

**Files modified:** `app/services/reports.py`
**Commit:** 4ab6bc2
**Applied fix:** Wrapped `write_pdf` + `os.replace` in `try/except` with cleanup in `_render_pdf()`:
```python
try:
    HTML(string=html_str, base_url=".").write_pdf(tmp_path)
    os.replace(tmp_path, output_path)
except Exception:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    raise
```
Prevents orphaned `.tmp` files when WeasyPrint fails mid-write.

---

### CR-01: `_build_payload` now filters all deal data by the requested month

**Files modified:** `app/services/reports.py`
**Commit:** eef0a06
**Applied fix:** Replaced calls to `kpi_service.talent_detail()` and `funnel_service.talent_funnel()` (which have no date filter parameter) with direct queries filtered by `Deal.add_time.like(f"{month}%")`. All three categories of deal data now filter by month: pipeline KPIs (open deals), won/cerrados/commission KPIs, funnel stages, and top 3 deals. Added `sqlalchemy.func` import. Funnel stage ordering uses `funnel_service.STAGES` constant directly (no service call). Leads remain all-time (the `Lead` model has no `add_time` equivalent from deals).

**Note:** This is a logic fix — requires human verification that the month filter is semantically correct in production data (e.g. that `Deal.add_time` consistently stores the deal creation date in `YYYY-MM-DD...` format that matches the LIKE prefix pattern).

---

### CR-02: RFC 5987 `filename*=UTF-8''` encoding in `Content-Disposition` header

**Files modified:** `app/routers/reports.py`
**Commit:** e9ccfcf
**Applied fix:** Added `from urllib.parse import quote` and replaced the bare `filename=` header with dual-parameter RFC 5987 encoding:
```
Content-Disposition: attachment; filename="reporte-2026-05.pdf"; filename*=UTF-8''reporte-Mar%C3%ADa-L%C3%B3pez-2026-05.pdf
```
ASCII-only `filename=` serves as fallback for old clients; `filename*=UTF-8''` carries the full non-ASCII name for modern browsers (Safari, Firefox, Chrome).

---

### WR-02: `ValidationError` from partial Claude JSON caught as 502

**Files modified:** `app/routers/reports.py`
**Commit:** 05a9d2a
**Applied fix:** Added `from pydantic import ValidationError` and wrapped the `ReportOut(...)` construction in a separate `try/except ValidationError` block that raises `HTTPException(status_code=502)`. Previously, if Claude returned valid JSON with a missing key (e.g. no `"recomendacion"`), Pydantic's `ValidationError` bypassed the `except ValueError` handler and surfaced as HTTP 500.

---

## Skipped Issues

None — all 6 in-scope findings were fixed successfully.

---

_Fixed: 2026-06-15T23:58:00-06:00_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
