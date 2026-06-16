# Phase 5: AI-Generated PDF Reports - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/models.py` (add `Report`) | model | CRUD | `app/models.py` — `TrelloCard`, `Lead` models | exact |
| `app/schemas/reports.py` | schema | request-response | `app/schemas/leads.py` | exact |
| `app/services/reports.py` | service | request-response + file-I/O | `app/services/kpis.py` + `app/services/trello_service.py` | role-match |
| `app/routers/reports.py` | router | request-response | `app/routers/leads.py` | exact |
| `app/main.py` (add router) | config | — | `app/main.py` (existing) | exact |
| `templates/reports/template.html` | template | file-I/O | none (no Jinja2 templates exist yet) | no-analog |
| `frontend/index.html` (add 5th tab) | component | request-response | `frontend/index.html` — existing 4-tab structure | exact |
| `frontend/js/reports.js` | component | request-response | `frontend/js/leads.js` | exact |
| `frontend/css/styles.css` (add classes) | config | — | `frontend/css/styles.css` — existing CSS variables | role-match |
| `tests/test_reports.py` | test | — | `tests/test_leads.py` | exact |
| `tests/conftest.py` (add fixtures) | test | — | `tests/conftest.py` — existing `mock_sheets_rows`, `mock_trello_transport` | exact |

---

## Pattern Assignments

### `app/models.py` — add `Report` model (model, CRUD)

**Analog:** `app/models.py` — `TrelloCard` (lines 121-150) and `Lead` (lines 92-118)

**SQLAlchemy 2.0 declarative pattern** (models.py lines 1-6, 121-130):
```python
from datetime import date, datetime

from sqlalchemy import String, Boolean, Float, Integer, ForeignKey, DateTime, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
```

**FK + relationship pattern** (models.py lines 107-118, 130-140):
```python
# Nullable FK with index — same as Lead.talent_id and TrelloCard.deal_id
talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)

# Relationship — lazy="select" same as Lead.talent
talent: Mapped["Talent"] = relationship("Talent", lazy="select")
```

**server_default=func.now() pattern** (models.py lines 15, 77):
```python
created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
# or with onupdate (TrelloCard pattern):
synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Report model to write** — combine the above:
```python
class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)
    month: Mapped[str] = mapped_column(String, index=True)          # "YYYY-MM"
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    file_path: Mapped[str] = mapped_column(String)                  # reports/{id}/{YYYY-MM}.pdf
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    talent: Mapped["Talent"] = relationship("Talent", lazy="select")
```

Note: Also import `Report` in `tests/conftest.py` line 29 (currently: `from app.models import Deal, DealStageEvent, Lead, Talent, TalentProduct, User`). Add `Report` to that import and to the `_clean_tables` autouse fixture (it truncates `Base.metadata.sorted_tables` automatically — no change needed there).

---

### `app/schemas/reports.py` (schema, request-response)

**Analog:** `app/schemas/leads.py` (all 41 lines)

**Schema file header pattern** (leads.py lines 1-9):
```python
"""Pydantic response schemas for the leads endpoints (Plan 03-01).

Plain BaseModel for computed aggregates — no from_attributes needed since
all responses are built from service-layer dicts, not ORM rows directly.
(Same convention as app/schemas/dashboard.py per 02-PATTERNS.md.)
"""
from datetime import datetime

from pydantic import BaseModel
```

**Simple BaseModel fields pattern** (leads.py lines 12-41):
```python
class LeadRow(BaseModel):
    id: int
    talent_id: int | None
    talent_name: str | None
    # ... all fields are plain Python scalars
    # Optional fields use T | None pattern (not Optional[T])
```

**Schemas to write for reports:**
```python
class ReportGenerate(BaseModel):
    """POST /reports/generate request body."""
    talent_id: int
    month: str  # validated: pattern r'^\d{4}-\d{2}$' via Field(pattern=...)

class NarrativeSections(BaseModel):
    """The 3 Claude-generated prose sections returned to the frontend."""
    resumen_ejecutivo: str
    deals_destacados: str
    recomendacion: str

class ReportOut(BaseModel):
    """POST /reports/generate response — metadata + narrative for in-page preview."""
    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_path: str
    file_size_bytes: int
    narrative: NarrativeSections  # returned to frontend for dark preview card

class ReportHistoryItem(BaseModel):
    """GET /reports/ list item."""
    id: int
    talent_id: int
    talent_name: str
    month: str
    generated_at: datetime
    file_size_bytes: int
```

---

### `app/services/reports.py` (service, request-response + file-I/O)

**Analog:** `app/services/kpis.py` (function signature convention) + `app/services/trello_service.py` (external-call pattern)

**Service file header + import convention** (kpis.py lines 1-18):
```python
"""Global KPI aggregation and talent ranking service.

Functions take db: Session as the first parameter — Depends() wiring belongs
in app/routers/dashboard.py, not here (02-PATTERNS.md convention).
"""
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models import Deal, Talent
from app.services.funnel import talent_funnel
```

**Function signature convention** — `db: Session` first, returns dict or typed value (kpis.py lines 20, 90, 147):
```python
def global_kpis(db: Session) -> dict:
def talent_ranking(db: Session) -> list[dict]:
def talent_detail(db: Session, talent_id: int) -> dict:
```

**Service raises ValueError for missing entity, router catches it** (kpis.py lines 167-168 + dashboard.py lines 147-152):
```python
# In service:
talent = db.get(Talent, talent_id)
if talent is None:
    raise ValueError(f"Talent {talent_id} not found")

# In router (defensive re-raise as 404):
try:
    detail = kpi_service.talent_detail(db, talent_id)
except ValueError:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
```

**Core functions to implement in `services/reports.py`:**
```python
import json
import os
import re
import tempfile
from datetime import datetime

import anthropic
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.config import settings
from app.models import Deal, Report, Talent
from app.services import funnel as funnel_service
from app.services import kpis as kpi_service
from app.services import leads as leads_service

_jinja_env = Environment(loader=FileSystemLoader("templates"))

SYSTEM_PROMPT = """..."""  # strict "narrate only, no invented figures" prompt

def available_months(db: Session, talent_id: int) -> list[str]:
    """Return distinct YYYY-MM strings from Deal.add_time for this talent, desc."""
    # Query Deal.add_time strings, slice [:7], deduplicate, sort descending

def _build_payload(db: Session, talent: Talent, month: str) -> dict:
    """Assemble the Python-computed figures dict to pass to Claude."""
    # Calls kpi_service.talent_detail(), funnel_service.talent_funnel(),
    # leads_service.leads_by_talent() — ALL numeric figures come from here

def _call_claude(payload: dict) -> dict:
    """Call claude-sonnet-4-6 and parse the 3-section JSON response."""
    # Returns {"resumen_ejecutivo": str, "deals_destacados": str, "recomendacion": str}
    # Wraps json.loads in try/except, strips markdown fences if present

def _render_pdf(html_str: str, output_path: str) -> int:
    """Render HTML to PDF via WeasyPrint. Returns file size in bytes.
    Uses atomic write: tmp file → os.replace() → final path (Pitfall 4)."""

def generate_report(db: Session, talent_id: int, month: str) -> dict:
    """Orchestrate: build payload → call Claude → render PDF → upsert Report row."""

def list_reports(db: Session) -> list[dict]:
    """Return all Report rows ordered by generated_at desc, with talent_name resolved."""
```

---

### `app/routers/reports.py` (router, request-response)

**Analog:** `app/routers/leads.py` (all 65 lines) — closest match: same auth pattern, same thin-router contract

**Router header + auth dependency pattern** (leads.py lines 1-21):
```python
"""Reports router — authenticated endpoints for report generation and download.

All endpoints require a valid JWT cookie (router-level dependency).
Business logic lives in app/services/reports.py — this router only wires
HTTP concerns (request parsing, response serialization).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Report, Talent
from app.schemas.reports import ReportGenerate, ReportOut, ReportHistoryItem
from app.services import reports as reports_service

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],   # <-- router-level, same as all others
)
```

**404 guard pattern** (leads.py lines 43-49, dashboard.py lines 136-140):
```python
talent = db.get(Talent, talent_id)
if talent is None:
    raise HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail="Talent not found",
    )
```

**Thin endpoint pattern — delegate everything to service** (leads.py lines 56-64):
```python
@router.get("/summary", response_model=LeadsSummary)
def get_leads_summary(db: Session = Depends(get_db)):
    summary = leads_service.leads_summary(db)
    bars = leads_service.leads_by_talent(db)
    return LeadsSummary(
        leads_totales=summary["leads_totales"],
        calificados=summary["calificados"],
        por_talento=[TalentLeadBar(**bar) for bar in bars],
    )
```

**CRITICAL — sync `def` for generate endpoint** (from RESEARCH.md Pattern 4):
```python
@router.post("/generate", response_model=ReportOut)
def generate_report(   # MUST be `def`, NOT `async def` — WeasyPrint is blocking I/O
    body: ReportGenerate,
    db: Session = Depends(get_db),
):
    return reports_service.generate_report(db, body.talent_id, body.month)
```

**FileResponse pattern for PDF download** (from RESEARCH.md Pattern 3):
```python
from fastapi.responses import FileResponse

@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    talent = db.get(Talent, report.talent_id)
    talent_name = talent.name if talent else "reporte"
    filename = f"reporte-{talent_name.replace(' ', '-')}-{report.month}.pdf"
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

---

### `app/main.py` — add reports router (config)

**Analog:** `app/main.py` lines 1-29 (the existing router registration block)

**Router registration pattern** (main.py lines 6-26):
```python
from app.routers import dashboard, health, leads, sync, talents
# Add:
from app.routers import reports

# Then:
app.include_router(reports.router)
# Position: after dashboard.router, before the StaticFiles mount
# Static mount MUST remain last (main.py line 29 comment explains why)
```

---

### `templates/reports/template.html` (template, file-I/O)

**No analog exists** — no Jinja2 templates exist anywhere in the codebase yet.

Use the RESEARCH.md Pattern 7 (Jinja2 template pattern) as the reference. Key facts from the codebase:

- CSS accent color: `#e8520a` (confirmed from dashboard.js line 8: `"var(--accent)"` = `#e8520a` per styles.css)
- Font: Sora (index.html line 7 Google Fonts import) — embed via `@import` or inline in template `<style>`
- Light theme for PDF: white background, dark text — inverse of the dashboard's dark theme
- Template must live at `templates/reports/template.html`; Jinja2 configured with `FileSystemLoader("templates")`
- Jinja2 variables: `{{ talent_name }}`, `{{ month }}`, `{{ narrative.resumen_ejecutivo }}`, `{{ narrative.deals_destacados }}`, `{{ narrative.recomendacion }}`, `{{ data.kpis.* }}`, `{{ data.funnel }}`, `{{ data.top_deals }}`

See RESEARCH.md lines 603-656 for the complete template scaffold.

---

### `frontend/index.html` — add 5th "Reportes" tab (component)

**Analog:** `frontend/index.html` lines 18-23 (tabbar) and lines 29+ (page divs)

**Tab button pattern** (index.html lines 19-22):
```html
<div class="tabbar">
  <div class="tab active" onclick="setPage('overview', event)">Resumen</div>
  <div class="tab" onclick="setPage('talent', event)">Por talento</div>
  <div class="tab" onclick="setPage('funnel', event)">Funnel</div>
  <div class="tab" onclick="setPage('leads', event)">Leads</div>
  <!-- ADD: -->
  <div class="tab" onclick="setPage('reports', event)">Reportes</div>
</div>
```

**Page div pattern** (index.html line 29):
```html
<div class="page active" id="page-overview">...</div>
<!-- ADD at end of pages, before closing </body>: -->
<div class="page" id="page-reportes">
  <!-- Reportes tab content per mockup id="page-reportes" -->
</div>
```

**setPage extension** — add `reports` branch to `dashboard.js` setPage function (dashboard.js lines 52-61):
```javascript
// Existing pattern:
} else if (name === "leads") {
  loadLeadsSummary();
  loadLeads();
}
// Add:
} else if (name === "reports") {
  loadReportTalents();   // populates #report-talent-select
  loadReportHistory();   // populates history list
}
```

**Script tag pattern** — scripts loaded at bottom of `<body>` in order (index.html); add after leads.js:
```html
<script src="/js/auth.js"></script>
<script src="/js/dashboard.js"></script>
<script src="/js/leads.js"></script>
<script src="/js/reports.js"></script>  <!-- ADD last -->
```

---

### `frontend/js/reports.js` (component, request-response)

**Analog:** `frontend/js/leads.js` (all 264 lines) — direct structural mirror

**File header contract** (leads.js lines 1-9):
```javascript
// Reports tab: talent selector, month selector, report generation, history list.
//
// IMPORTANT: apiFetch, escHtml, showToast are defined in auth.js / dashboard.js
// and MUST NOT be redefined here. This file is loaded after dashboard.js.
//
// XSS mitigation: ALL Claude-generated narrative text MUST pass through escHtml()
// before innerHTML insertion (Pitfall 6 in RESEARCH.md).
```

**Async data loader pattern** (leads.js lines 217-252):
```javascript
async function loadLeadsSummary() {
  const res = await apiFetch("/leads/summary");
  if (!res) return;          // 401 → apiFetch already redirected to /login.html
  if (!res.ok) {
    showToast("Error cargando resumen de leads");
    return;
  }
  const data = await res.json();
  renderLeadsSummary(data);
  populateTalentFilter(data.por_talento || []);
}
```

**Mirror pattern for reports.js:**
```javascript
async function loadReportTalents() {
  const res = await apiFetch("/reports/talents");
  if (!res) return;
  if (!res.ok) { showToast("Error cargando talentos"); return; }
  const talents = await res.json();
  renderTalentDropdown(talents);
}

async function loadReportMonths(talentId) {
  if (!talentId) return;
  const res = await apiFetch(`/reports/months?talent_id=${talentId}`);
  if (!res) return;
  if (!res.ok) { showToast("Error cargando meses"); return; }
  const months = await res.json();
  renderMonthDropdown(months);
}

async function generateReport() {
  const talentId = document.getElementById("report-talent-select").value;
  const month = document.getElementById("report-month-select").value;
  if (!talentId || !month) return;

  const btn = document.getElementById("generate-btn");
  btn.disabled = true;
  // show spinner (add class or innerHTML swap)

  const res = await apiFetch("/reports/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ talent_id: parseInt(talentId), month }),
  });

  btn.disabled = false;
  // hide spinner

  if (!res || !res.ok) { showToast("Error generando reporte"); return; }
  const data = await res.json();
  renderPreviewCard(data);          // populate dark .pdf-preview card
  enableDownloadButton(data.id);    // activate "Descargar PDF" button
  loadReportHistory();              // refresh history list
}

async function loadReportHistory() {
  const res = await apiFetch("/reports/");
  if (!res) return;
  if (!res.ok) { showToast("Error cargando historial"); return; }
  const reports = await res.json();
  renderReportHistory(reports);
}
```

**XSS escape in render functions** (leads.js lines 119-132):
```javascript
// Every Claude-sourced string through escHtml before innerHTML:
container.innerHTML = `
  <div class="pdf-section">
    <div class="section-title">Resumen ejecutivo</div>
    <div class="section-text">${escHtml(data.narrative.resumen_ejecutivo)}</div>
  </div>
  ...
`;
```

**DOMContentLoaded listener pattern** (leads.js lines 258-263):
```javascript
document.addEventListener("DOMContentLoaded", () => {
  const talentSelect = document.getElementById("report-talent-select");
  if (talentSelect) {
    talentSelect.addEventListener("change", () => {
      loadReportMonths(talentSelect.value);
    });
  }
});
```

---

### `frontend/css/styles.css` — add report CSS classes (config)

**Analog:** `frontend/css/styles.css` — existing CSS variable system (dark theme)

The existing file uses CSS custom properties (`var(--accent)`, `var(--bg2)`, etc.) and BEM-like class names. New classes for the Reportes tab must follow this convention. Key classes to add per mockup `id="page-reportes"`:

```css
/* PDF preview card — dark theme in-page widget (NOT the PDF itself) */
.pdf-preview { background: var(--bg2); border-radius: 12px; padding: 24px; }
.pdf-preview .ai-badge { /* purple badge "✦ Claude AI" */ }
.pdf-section { padding: 16px 0; border-bottom: 1px solid var(--bg4); }
.pdf-section .section-title { font-size: 11px; text-transform: uppercase;
                               letter-spacing: 1px; color: var(--accent); }
.pdf-block { /* individual narrative text block */ }

/* Report history list items */
.report-history-item { /* mirrors .deal-row pattern */ }
```

---

### `tests/test_reports.py` (test, request-response)

**Analog:** `tests/test_leads.py` (all 482 lines) — exact structural mirror

**Test class organization pattern** (test_leads.py):
```python
class TestServiceFunctionName:
    """Tests for service_module.function_name()."""

    def test_happy_path(self, db_session, seed_fixture):
        from app.services import reports as reports_service
        result = reports_service.available_months(db_session, talent_id)
        assert ...

    def test_empty_case(self, db_session):
        from app.services import reports as reports_service
        assert reports_service.available_months(db_session, 999) == []
```

**Endpoint auth test pattern** (test_leads.py lines 342-359):
```python
class TestGenerateReportEndpoint:
    def test_generate_requires_auth(self, client):
        response = client.post("/reports/generate", json={"talent_id": 1, "month": "2026-05"})
        assert response.status_code == 401

    def test_generate_returns_200_with_auth(self, auth_client, seed_deals,
                                             mock_anthropic, mock_weasyprint):
        talent_id = ...  # from seed_deals
        response = auth_client.post("/reports/generate",
                                    json={"talent_id": talent_id, "month": "2026-05"})
        assert response.status_code == 200
        data = response.json()
        assert "narrative" in data
        assert "resumen_ejecutivo" in data["narrative"]
```

**Required fields assertion pattern** (test_leads.py lines 470-481):
```python
def test_generate_response_has_required_fields(self, auth_client, seed_deals,
                                                mock_anthropic, mock_weasyprint):
    # ...
    required = {"id", "talent_id", "talent_name", "month",
                "generated_at", "file_size_bytes", "narrative"}
    for field in required:
        assert field in data, f"Missing field: {field}"
```

---

### `tests/conftest.py` — add `mock_anthropic` and `mock_weasyprint` fixtures

**Analog:** `tests/conftest.py` lines 416-506 (`mock_sheets_rows`, `mock_trello_transport`)

**monkeypatch fixture pattern** (conftest.py lines 416-473):
```python
@pytest.fixture()
def mock_sheets_rows(monkeypatch):
    """Replace sheets.get_leads_rows() with a list of SheetLeadRow fixtures."""
    # ...
    monkeypatch.setattr(
        jobs_module,
        "sheets",
        type("_MockSheets", (), {"get_leads_rows": staticmethod(lambda: sample)})(),
    )
    return sample
```

**New fixtures to add** — place after existing Phase 4 fixtures (after line 655):
```python
@pytest.fixture()
def mock_anthropic(monkeypatch):
    """Return a mock Anthropic client that returns a fixed narrative response."""
    from unittest.mock import MagicMock
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=(
        '{"resumen_ejecutivo":"Resumen de prueba.",'
        '"deals_destacados":"Deals de prueba.",'
        '"recomendacion":"Recomendacion de prueba."}'
    ))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr("app.services.reports.anthropic.Anthropic", lambda **kwargs: mock_client)
    return mock_client

@pytest.fixture()
def mock_weasyprint(monkeypatch, tmp_path):
    """Replace weasyprint.HTML with a stub that writes a minimal PDF marker."""
    from unittest.mock import MagicMock

    def fake_write_pdf(path_or_none=None):
        if path_or_none:
            os.makedirs(os.path.dirname(path_or_none), exist_ok=True)
            with open(path_or_none, "wb") as f:
                f.write(b"%PDF-1.4")
        return b"%PDF-1.4"

    mock_html_cls = MagicMock()
    mock_html_cls.return_value.write_pdf = fake_write_pdf
    monkeypatch.setattr("app.services.reports.HTML", mock_html_cls)
    return mock_html_cls
```

Note: `_clean_tables` autouse fixture (conftest.py lines 82-98) handles `reports` table cleanup automatically because it iterates `Base.metadata.sorted_tables`. No change needed there once `Report` is registered with `Base`.

---

## Shared Patterns

### Authentication — router-level `dependencies=[Depends(get_current_user)]`
**Source:** `app/routers/leads.py` lines 17-21, `app/routers/dashboard.py` lines 38-42
**Apply to:** `app/routers/reports.py`
```python
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)
```
This single declaration protects ALL endpoints on the router, including `/{report_id}/download`. No per-endpoint auth decorator needed.

### Error Handling — 404 guard + service ValueError catch
**Source:** `app/routers/dashboard.py` lines 136-152, `app/routers/leads.py` lines 43-49
**Apply to:** `app/routers/reports.py` all endpoints that take `talent_id` or `report_id`
```python
# Entity existence guard:
report = db.get(Report, report_id)
if report is None:
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Report not found")

# Service ValueError → 404 pattern:
try:
    result = reports_service.generate_report(db, body.talent_id, body.month)
except ValueError:
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Talent not found")
```

### DB Session Dependency
**Source:** Every existing router (leads.py line 26, dashboard.py line 52)
**Apply to:** All `app/routers/reports.py` endpoint functions
```python
from app.database import get_db

def some_endpoint(db: Session = Depends(get_db)):
    ...
```

### XSS Escaping — `escHtml()` for all API-sourced strings
**Source:** `frontend/js/leads.js` lines 1-9 (header contract), lines 119-132 (usage)
**Apply to:** `frontend/js/reports.js` — ALL Claude narrative strings, talent names, month strings
```javascript
// escHtml defined in dashboard.js lines 30-38 — do NOT redefine
// Claude text MUST be escaped before innerHTML:
element.innerHTML = `<p>${escHtml(data.narrative.resumen_ejecutivo)}</p>`;
```

### Toast Notification for Errors
**Source:** `frontend/js/leads.js` lines 222-223, 244-245
**Apply to:** `frontend/js/reports.js` — all `!res.ok` branches
```javascript
showToast("Error cargando talentos");  // showToast defined in dashboard.js line 64-70
```

### Service Layer Returning Dicts (not ORM objects)
**Source:** `app/services/kpis.py` lines 60-86, `app/services/funnel.py` lines 66-69
**Apply to:** `app/services/reports.py` — return plain Python dicts from all functions; router builds Pydantic models from them
```python
# Service returns dict:
return {"id": report.id, "talent_id": report.talent_id, "month": report.month, ...}

# Router builds schema:
return ReportOut(**reports_service.generate_report(db, body.talent_id, body.month))
```

### DB Session in Tests — use `db_session` fixture, not `client`
**Source:** `tests/test_leads.py` lines 150-166 (unit tests use `db_session`), lines 342-360 (endpoint tests use `auth_client`)
**Apply to:** `tests/test_reports.py`
```python
def test_available_months_service(self, db_session, seed_deals):
    from app.services import reports as reports_service
    months = reports_service.available_months(db_session, talent_id)
    assert isinstance(months, list)

def test_generate_endpoint(self, auth_client, seed_deals, mock_anthropic, mock_weasyprint):
    response = auth_client.post("/reports/generate", json={...})
    assert response.status_code == 200
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `templates/reports/template.html` | template | file-I/O | No Jinja2 HTML templates exist anywhere in the codebase. Use RESEARCH.md lines 603-656 as the reference scaffold. Key constraint: light theme (white bg, `#e8520a` accent), Jinja2 variable syntax `{{ var }}`, WeasyPrint-compatible CSS (no JavaScript, no external fonts without `@import`). |

---

## Critical Implementation Notes for Planner

1. **`def` not `async def` for generate endpoint** — WeasyPrint (`HTML(...).write_pdf()`) is a blocking system-library call. Declaring the endpoint as `def` causes FastAPI to run it in its threadpool automatically. Never use `async def` for this endpoint (RESEARCH.md Pitfall 3).

2. **Atomic PDF write** — use `os.replace(tmp_path, final_path)` not direct write. This prevents the DB row pointing to a corrupt/partial file if WeasyPrint fails mid-write (RESEARCH.md Pitfall 4).

3. **`reports/` directory must be created** — the service must call `os.makedirs(os.path.dirname(file_path), exist_ok=True)` before writing. Using `str(talent.id)` as the slug (not `talent.name`) avoids Unicode path issues (RESEARCH.md Open Question 1 recommendation).

4. **Claude JSON parsing — defensive strip** — `response.content[0].text` may have markdown fences. Always strip before `json.loads()` (RESEARCH.md Pitfall 2). Wrap in `try/except json.JSONDecodeError` and raise `HTTPException(502)` if parsing fails.

5. **`add_time[:7]` for month extraction** — `Deal.add_time` is `Mapped[str | None]` (models.py line 64). The format from Pipedrive is `"YYYY-MM-DD HH:MM:SS"`. Validate the slice matches `r'\d{4}-\d{2}'` before including.

6. **Router registration order** — `app.include_router(reports.router)` must come before the `StaticFiles` mount on line 29 of `main.py` (the comment on that line already warns about this).

7. **`Report` in conftest imports** — add `Report` to `from app.models import Deal, DealStageEvent, Lead, Talent, TalentProduct, User` (conftest.py line 29) so `_clean_tables` autouse fixture covers the new table.

---

## Metadata

**Analog search scope:** `app/routers/`, `app/services/`, `app/schemas/`, `app/models.py`, `frontend/js/`, `frontend/index.html`, `tests/`
**Files scanned:** 18
**Pattern extraction date:** 2026-06-15
