# Phase 5: AI-Generated PDF Reports - Research

**Researched:** 2026-06-15
**Domain:** Anthropic SDK + WeasyPrint + Jinja2 + FastAPI file serving + SQLAlchemy model extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-53:** Reports are individual per talent only. "Todos los talentos" excluded from this phase.
- **D-54:** Month selector is dynamic — shows only months that have deal data in SQLite (not a fixed 12-month lookback). Python queries distinct months from the `Deal` table ordered descending. If no data, dropdown is empty and the generate button is disabled.
- **D-55:** Claude generates exactly 3 sections: (1) Resumen ejecutivo, (2) Deals destacados, (3) Recomendación.
- **D-56:** Python pre-computes all numeric figures and passes them to Claude as a structured JSON payload. Claude receives: talent name, month, KPI dict (leads, deals by stage, revenue cobrado/proyección/pendiente, top deals list). Claude's task is to produce readable prose from this data — it must NOT invent numbers.
- **D-57:** Claude model: `claude-sonnet-4-6` (confirmed — see Standard Stack below).
- **D-58:** Generation is synchronous with a loading spinner. "Generar reporte con IA" button disables itself and shows a spinner. No async job queue needed.
- **D-59:** After generation, PDF is immediately available for download; new report appears at top of history list.
- **D-60:** PDF uses a light/print-friendly theme (white background, dark text, SEG accent `#e8520a`). In-page dark preview is a separate HTML widget — not the PDF itself.
- **D-61:** PDF template structure (Jinja2): `reports/template.html`. Sections: cover page, 3 narrative sections, data appendix (KPI table, funnel table).
- **D-62:** PDFs stored on disk at `reports/{talent_slug}/{YYYY-MM}.pdf`. The `reports/` directory is in `.gitignore`, mapped as Docker volume in Phase 7.
- **D-63:** `Report` SQLAlchemy model fields: `id`, `talent_id` (FK), `month` (YYYY-MM string), `generated_at` (datetime), `file_path` (relative), `file_size_bytes`.
- **D-64:** If report for same talent + month exists, overwrite it (file + DB row). No versioned history.
- **D-65:** Reportes tab does not yet exist. Phase 5 adds 5th tab "Reportes" following mockup `id="page-reportes"`.
- **D-66:** Frontend JS goes in `frontend/js/reports.js` (consistent with `dashboard.js`, `leads.js` pattern).
- **D-67:** No "Compartir por WhatsApp" button (deferred). Only "Generar reporte con IA" and "Descargar PDF".

### Claude's Discretion

- Exact system prompt wording, temperature, max_tokens — left to planner.
- Data appendix content (which tables beyond 3 Claude sections) — planner decides.
- Whether to use `talent_slug` derived from `talent.name` or `talent.id` for file path — left to planner.

### Deferred Ideas (OUT OF SCOPE)

- "Todos los talentos" batch report.
- Compartir por WhatsApp button.
- Report scheduling (auto-generate at month end).
- Report versioning (multiple generations per talent/month).

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REPORT-01 | Generate monthly PDF report per talent using Claude AI — all financial figures computed in Python, Claude only narrates | Covered by Anthropic SDK pattern (Section: Code Examples), WeasyPrint API, Jinja2 template pattern, Report model, reports.py service architecture |
| REPORT-02 | User can download historical generated reports | Covered by FastAPI FileResponse pattern, Report model + history query, reports.py router GET /reports/ and GET /reports/{id}/download |
| DASH-05 | Reportes UI tab — generate AI PDF reports and browse/download report history | Covered by 5th tab pattern (setPage), reports.js module pattern mirroring leads.js, mockup `page-reportes` HTML analysis |

</phase_requirements>

---

## Summary

Phase 5 adds the AI-narrated PDF report generation capability to the SEG dashboard. The architecture is a three-tier pipeline: (1) Python assembles a structured data payload by calling existing `kpis.py`, `funnel.py`, and `leads.py` services, (2) the Anthropic SDK sends that payload to `claude-sonnet-4-6` with a strict "narrate only, no invented numbers" prompt and receives JSON with 3 narrative sections back, (3) WeasyPrint renders a Jinja2 HTML template (light-themed, SEG branding) into a PDF file stored at `reports/{slug}/{YYYY-MM}.pdf`. Report metadata is persisted in a new `Report` SQLAlchemy model. The frontend adds a 5th tab ("Reportes") following the exact mockup design, with a `reports.js` module mirroring the `leads.js` pattern.

The critical constraint — enforced in `services/reports.py` — is that Claude receives a fully pre-computed JSON payload and is only asked to generate prose. Numbers in the PDF come from Python, not from Claude's response. This prevents hallucinated figures and satisfies the STATE.md blocker.

The key operational fact for the planner: WeasyPrint is a blocking I/O library (calls Pango/Cairo system libs). The FastAPI route that calls it MUST be declared as `def` (not `async def`) so FastAPI automatically offloads it to its thread pool. This is the correct pattern for this codebase (the existing service layer is also sync). There is no need for a background job queue — the decision D-58 (synchronous with spinner) is sound at the scale of this internal tool.

**Primary recommendation:** Implement `services/reports.py` as the orchestration layer that calls existing services, calls Claude, renders Jinja2, and writes the PDF. Keep the router thin. Use `def` (sync) endpoints for the generation route.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| KPI/funnel data collection for report | API / Backend (services/kpis.py, funnel.py, leads.py) | — | Already exists; reports.py calls these, not Claude |
| Claude narrative generation | API / Backend (services/reports.py) | — | Anthropic SDK call is server-side; never expose API key to frontend |
| PDF rendering (Jinja2 + WeasyPrint) | API / Backend (services/reports.py) | — | WeasyPrint requires system libs; belongs on server |
| PDF file storage | API / Backend filesystem (reports/ dir) | — | Gitignored dir, Docker volume in Phase 7 |
| Report metadata persistence | Database / Storage (SQLite via Report model) | — | Standard ORM write, same pattern as all other models |
| Report history query | API / Backend (routers/reports.py) | — | READ from Report table, protected by get_current_user |
| PDF file download | API / Backend (FastAPI FileResponse) | — | Serve file from disk with correct Content-Disposition header |
| Dynamic month selector | API / Backend (GET /reports/months?talent_id=) + Browser / Client | — | Python queries distinct Deal months; JS renders dropdown |
| Reportes tab UI | Browser / Client (frontend/js/reports.js + index.html) | — | Follows established setPage() pattern; no SSR |
| In-page dark preview card | Browser / Client (reports.js DOM rendering) | — | Populated from generate response JSON; mirrors mockup .pdf-preview |

---

## Standard Stack

### Core (already in pyproject.toml — no new install for SDK calls)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.109.2 [VERIFIED: PyPI 2026-06-15] | Claude API client — call `claude-sonnet-4-6` for narrative JSON | Already declared in CLAUDE.md stack; Python >=3.9, compatible with 3.12 |
| Jinja2 | 3.1.6 [VERIFIED: PyPI 2025-03-05] | HTML template rendering for PDF | Already transitively available via FastAPI; render report data into HTML before WeasyPrint |

### New Dependencies (to add to pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| weasyprint | 69.0 [VERIFIED: PyPI 2026-06-02] | HTML/CSS → PDF rendering | CLAUDE.md recommended choice; Python >=3.10 (compatible with 3.12); HTML(string=...).write_pdf(path) API |

### Confirmed Model ID

| Model | API ID | Context Window | Max Output | Pricing |
|-------|--------|----------------|------------|---------|
| Claude Sonnet 4.6 | `claude-sonnet-4-6` [VERIFIED: platform.claude.com/docs/en/about-claude/models/overview, 2026-06-15] | 1M tokens | 64k tokens | $3/$15 per MTok |

This is the current "best combination of speed and intelligence" tier. The dateless ID is a pinned snapshot (not an alias) as of the 4.6 generation — it will not silently change.

### Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| WeasyPrint | fpdf2 | If Docker image size is a hard constraint — fpdf2 is pure-Python, no system lib deps, but no CSS layout, so "AI writes HTML → polished PDF" is much harder |
| WeasyPrint | ReportLab | If pixel-level layout control needed (complex financial tables) — more code, doesn't reuse CSS |
| `def` sync route for generation | `async def` + `run_in_threadpool` | If a future endpoint must call WeasyPrint from an async context — use `from fastapi.concurrency import run_in_threadpool` |
| JSON via prompt engineering | `output_format=JSONOutputFormat` (beta) | If structured outputs beta is available for the model at build time — verify against current SDK docs; prompt engineering is the stable fallback |

### Installation

```bash
# Add to pyproject.toml dependencies section:
# "anthropic>=0.79,<1.0",
# "weasyprint>=66,<70",
# "jinja2>=3.1",
uv add "anthropic>=0.79,<1.0" "weasyprint>=66,<70" "jinja2>=3.1"
```

Note: Jinja2 is already available transitively via FastAPI. Adding it explicitly pins the dependency for clarity and correctness in pyproject.toml.

---

## Package Legitimacy Audit

> slopcheck was not available at research time. All packages are verified via PyPI + official documentation. Packages are tagged [ASSUMED] per protocol — planner must add `checkpoint:human-verify` before install for any new package.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| anthropic | PyPI | Released 2023, updated 2026-06-15 | Multi-million/wk | github.com/anthropics/anthropic-sdk-python | N/A (official SDK) | [ASSUMED] — verify before install |
| weasyprint | PyPI | Since ~2012, v69.0 released 2026-06-02 | High (PDF library) | github.com/Kozea/WeasyPrint | N/A | [ASSUMED] — verify before install |
| jinja2 | PyPI | Since ~2008, v3.1.6 released 2025-03-05 | Hundreds of millions/wk | github.com/pallets/jinja | N/A | [ASSUMED] — already transitively installed; verify explicitly |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time. All packages are well-established (anthropic = Anthropic's own SDK; weasyprint = long-standing Python PDF library; jinja2 = Pallets project with massive adoption). Registry presence and official documentation confirm legitimacy. Planner must add a `checkpoint:human-verify` task before each pip install.*

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (reports.js)
  │
  ├── GET /reports/talents      → list active talents
  ├── GET /reports/months?talent_id={id}  → dynamic month list from Deal table
  │
  ├── POST /reports/generate    ──► services/reports.py
  │                                   │
  │                                   ├── kpis.talent_detail(db, talent_id)    [existing]
  │                                   ├── funnel.talent_funnel(db, talent_id)  [existing]
  │                                   ├── leads.leads_by_talent(db)            [existing]
  │                                   │
  │                                   ├── build payload dict (Python only — no AI yet)
  │                                   │
  │                                   ├── anthropic.Anthropic().messages.create(
  │                                   │     model="claude-sonnet-4-6",
  │                                   │     system="...", messages=[{role:user, content:JSON}]
  │                                   │   )  → response with 3 prose sections
  │                                   │
  │                                   ├── jinja2.Environment().get_template("template.html")
  │                                   │     .render(data=payload, narrative=sections)
  │                                   │
  │                                   ├── weasyprint.HTML(string=html).write_pdf(path)
  │                                   │     → reports/{slug}/{YYYY-MM}.pdf (disk)
  │                                   │
  │                                   └── upsert Report row in SQLite
  │
  ├── GET /reports/             → Report history list (DB query)
  └── GET /reports/{id}/download → FileResponse(path=..., media_type="application/pdf")
```

### Recommended Project Structure (new files only)

```
app/
├── models.py                   # + Report model (add to existing)
├── routers/
│   └── reports.py              # NEW: 4 endpoints
├── schemas/
│   └── reports.py              # NEW: ReportGenerate, ReportOut, ReportHistory schemas
├── services/
│   └── reports.py              # NEW: orchestration service
reports/                        # NEW: gitignored PDF storage root
│   └── {talent_slug}/
│       └── {YYYY-MM}.pdf
frontend/
├── index.html                  # MODIFY: add 5th tab + page-reportes HTML
├── js/
│   └── reports.js              # NEW: tab data loading + report generation
└── css/
    └── styles.css              # MODIFY: add .pdf-section, .pdf-preview, .pdf-block,
                                #          .ai-badge CSS classes from mockup
templates/
└── reports/
    └── template.html           # NEW: Jinja2 PDF template (light theme, SEG branding)
```

Note: `templates/` directory is new. Jinja2 must be configured to load from it:
```python
from jinja2 import Environment, FileSystemLoader
jinja_env = Environment(loader=FileSystemLoader("templates"))
```

### Pattern 1: Claude Narrative Generation (JSON via Prompt Engineering)

The stable approach — instruct Claude via prompt to respond in JSON, parse `response.content[0].text`. Do not rely on the `output_format=JSONOutputFormat` beta feature until verified against the current SDK version at build time.

```python
# Source: github.com/anthropics/anthropic-sdk-python (verified 2026-06-15)
import json
import anthropic

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Eres un analista de talentería para Santillán Entertainment Group.
Recibirás datos comerciales de un talento para un mes específico.
Tu tarea es generar texto narrativo en español para un reporte ejecutivo.

REGLA CRÍTICA: Usa ÚNICAMENTE los números del JSON que recibes. NO inventes cifras,
porcentajes, ni fechas. Si un valor es 0 o no existe, menciónalo honestamente.

Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:
{
  "resumen_ejecutivo": "texto narrativo...",
  "deals_destacados": "texto narrativo...",
  "recomendacion": "texto narrativo..."
}
No incluyas texto fuera del JSON."""

def generate_narrative(payload: dict) -> dict:
    """Call claude-sonnet-4-6 and return the 3 narrative sections as a dict.
    
    payload: pre-computed Python dict with all numeric figures.
    Returns: {"resumen_ejecutivo": str, "deals_destacados": str, "recomendacion": str}
    """
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Genera el reporte para los siguientes datos:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            }
        ]
    )
    text = response.content[0].text
    return json.loads(text)  # parse the JSON response
```

**Important:** Wrap `json.loads(text)` in a try/except — if Claude returns malformed JSON (rare but possible), the endpoint should return a 502 with a descriptive error rather than crashing with a 500.

### Pattern 2: WeasyPrint PDF Generation

```python
# Source: doc.courtbouillon.org/weasyprint/stable/api_reference.html (verified 2026-06-15)
from weasyprint import HTML

def render_pdf(html_string: str, output_path: str) -> int:
    """Render HTML to PDF, write to output_path, return file size in bytes."""
    HTML(string=html_string, base_url=".").write_pdf(output_path)
    return os.path.getsize(output_path)
```

Note: `base_url="."` allows WeasyPrint to resolve relative asset paths if the template embeds fonts or images. For a self-contained template with inline CSS, this is optional but harmless.

### Pattern 3: FastAPI FileResponse for PDF Download

```python
# Source: FastAPI docs + verified via WebSearch (2026-06-15)
from fastapi.responses import FileResponse

@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Serve a generated PDF as a file download."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    filename = f"reporte-{report.month}.pdf"
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

### Pattern 4: Sync `def` Endpoint for Blocking WeasyPrint

```python
# Source: fastapi.tiangolo.com/async/ (verified via WebSearch 2026-06-15)
# WeasyPrint is blocking I/O (calls Pango/Cairo system libs).
# Using `def` (not `async def`) causes FastAPI to run the endpoint in its
# thread pool automatically via Starlette's run_in_threadpool — no manual
# wrapping needed.

@router.post("/generate", response_model=ReportOut)
def generate_report(   # <-- MUST be def, NOT async def
    body: ReportGenerate,
    db: Session = Depends(get_db),
):
    """Generate a PDF report. Runs in FastAPI's thread pool (blocking allowed)."""
    # ... call services/reports.py ...
```

The Anthropic SDK's `client.messages.create()` is also synchronous (blocking HTTP). Both the Claude call and WeasyPrint call are synchronous — using `def` endpoint covers both correctly. For this internal tool's concurrency requirements (occasional report generation, <21 talents, not a high-traffic public API), the default threadpool size of 40 is ample.

### Pattern 5: Report SQLAlchemy Model

```python
# Follows existing pattern: Mapped/mapped_column SQLAlchemy 2.0 declarative style
# (same as User, Talent, Deal, Lead, TrelloCard in models.py)

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)
    month: Mapped[str] = mapped_column(String, index=True)  # "YYYY-MM"
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    file_path: Mapped[str] = mapped_column(String)  # relative: reports/{slug}/{YYYY-MM}.pdf
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    talent: Mapped["Talent"] = relationship("Talent", lazy="select")
```

Unique constraint on `(talent_id, month)` — enforces D-64 (overwrite, not version). Use `upsert` logic in the service layer: query for existing row, update if found, insert if not.

### Pattern 6: Dynamic Month List Query

```python
# Query distinct months (YYYY-MM) from Deal.add_time for a given talent.
# Deal.add_time is stored as a string in format "YYYY-MM-DD HH:MM:SS"
# Extract YYYY-MM prefix via substr() or Python slicing after query.

from sqlalchemy import func, distinct

def available_months(db: Session, talent_id: int) -> list[str]:
    """Return distinct YYYY-MM strings from Deal.add_time for this talent,
    ordered descending (most recent first)."""
    rows = (
        db.query(Deal.add_time)
        .filter(Deal.talent_id == talent_id, Deal.add_time.isnot(None))
        .distinct()
        .all()
    )
    months = sorted(
        set(row[0][:7] for row in rows if row[0] and len(row[0]) >= 7),
        reverse=True,
    )
    return months
```

Note: `Deal.add_time` is stored as a string (confirmed from models.py: `add_time: Mapped[str | None] = mapped_column(String, nullable=True)`). The `[:7]` slice extracts "YYYY-MM".

### Pattern 7: frontend/js/reports.js Module Structure

```javascript
// reports.js — follows leads.js pattern exactly
// All API strings passed through escHtml() before innerHTML
// apiFetch, escHtml, showToast defined in auth.js / dashboard.js — do NOT redefine

async function loadReportTalents() { /* GET /reports/talents */ }
async function loadReportMonths(talentId) { /* GET /reports/months?talent_id= */ }
async function generateReport() { /* POST /reports/generate + disable btn + show spinner */ }
async function loadReportHistory() { /* GET /reports/ → render history list */ }

document.addEventListener("DOMContentLoaded", () => {
  // Wire change listener on talent dropdown to reload months
});
```

The `setPage('reports', event)` branch in `dashboard.js` must call `loadReportHistory()` and populate the talent dropdown on tab activation.

### Pattern 8: PDF Payload Structure for Claude

The JSON payload passed to Claude must contain all the numeric figures Claude will reference in its narrative. Based on existing services:

```python
payload = {
    "talent_name": talent.name,
    "month": month,           # "YYYY-MM"
    "leads_totales": int,     # from leads_by_talent()
    "leads_calificados": int,
    "kpis": {
        "pipeline": float,    # from talent_detail()
        "cerrados_count": int,
        "cerrados_valor": float,
        "comision": float,
    },
    "funnel": [               # from talent_funnel()
        {"stage": str, "count": int, "amount": float},
        ...
    ],
    "top_deals": [            # top 3 by value from deals query
        {"title": str, "value": float, "stage": str, "status": str},
        ...
    ],
    "lost_count": int,
    "lost_summary": [{"reason": str, "count": int}],
}
```

### Anti-Patterns to Avoid

- **Passing raw SQL results or ORM objects to Claude:** Only pass a plain Python dict of serializable scalar values. Never pass SQLAlchemy model instances — they are not JSON-serializable and expose schema details.
- **Calling WeasyPrint from an `async def` endpoint without `run_in_threadpool`:** Will block the event loop. Use `def` endpoints for blocking calls.
- **Using `async def` for the generate endpoint "just in case":** Incorrect — `async def` in FastAPI means "I am doing async I/O myself"; if you then call blocking WeasyPrint, you block the whole event loop. Use `def`.
- **Storing PDFs inside the `frontend/` directory:** The `frontend/` directory is served as static files. PDFs should live in `reports/` (gitignored, separate from static assets) and be served via the `/reports/{id}/download` FastAPI endpoint with auth.
- **Generating slug from `talent.name` without sanitizing:** Names like "María José" contain spaces and accented characters. Use `slugify` or a simple `re.sub(r'[^a-z0-9]', '-', name.lower())` approach. Or use `talent.id` as the directory name instead (simpler, no Unicode issues — left to planner per D-67 discretion area).
- **Trusting Claude's JSON output without try/except:** Claude's JSON response may occasionally contain extra whitespace, BOM characters, or prose before/after the JSON block. Always strip and parse defensively.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML → PDF conversion | Custom PDF writer using reportlab draw primitives | WeasyPrint HTML(string=).write_pdf() | WeasyPrint handles page layout, fonts, page breaks — hand-rolling PDF is months of work |
| LLM JSON output parsing | Custom regex extraction of Claude's text response | `json.loads(response.content[0].text)` with try/except | Simple and direct; regex breaks on any format variation |
| AI text generation | Template strings with slot-filling | `anthropic.Anthropic().messages.create()` | Claude's prose is the product; don't substitute pre-written templates |
| File serving auth | Custom streaming middleware | FastAPI `FileResponse` with `dependencies=[Depends(get_current_user)]` at router level | FileResponse is async-safe, handles chunked transfer, sets correct headers |
| Slug generation | Complex unicode normalization | `re.sub(r'[^a-z0-9]+', '-', name.lower().strip())` or just use `str(talent.id)` | Simple enough to inline; no extra library needed |

**Key insight:** WeasyPrint's value is that the PDF template is just HTML/CSS — the same design language the frontend already uses. Jinja2 renders data into HTML, WeasyPrint converts to PDF. This three-layer pipeline (Python data → Jinja2 HTML → WeasyPrint PDF) is vastly simpler than any other approach.

---

## Common Pitfalls

### Pitfall 1: WeasyPrint System Library Dependencies in Docker

**What goes wrong:** WeasyPrint renders to PDF via Pango/Cairo system libraries. A bare `python:3.12-slim` Docker image does not include these. WeasyPrint will fail silently or raise `OSError` at runtime.

**Why it happens:** The Python package installs correctly via pip, but it delegates rendering to OS-level fonts/graphics libraries.

**How to avoid:** In the Dockerfile (Phase 7), add before `pip install`:
```dockerfile
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Warning signs:** `OSError: cannot load library 'libpango-1.0-0'` or `ImportError` from cffi/pango at startup.

**Phase 5 impact:** This is a Phase 7 concern. In local development (macOS), WeasyPrint typically works if Pango is installed via Homebrew (`brew install pango`). Document this in the Wave 0 environment check.

### Pitfall 2: Claude Returns Non-JSON or Partial JSON

**What goes wrong:** Claude occasionally prefixes its JSON with "Aquí está el JSON:" or wraps it in markdown code fences (` ```json ... ``` `).

**Why it happens:** Even with a strict system prompt, the model may add conversational framing, especially at lower temperatures or with short max_tokens.

**How to avoid:** In the parsing code:
```python
text = response.content[0].text.strip()
# Strip markdown code fences if present
if text.startswith("```"):
    text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]
try:
    return json.loads(text)
except json.JSONDecodeError as e:
    raise ValueError(f"Claude returned non-JSON: {e}") from e
```

**Warning signs:** `json.JSONDecodeError` during `reports.py` execution.

### Pitfall 3: WeasyPrint Called from `async def` Endpoint

**What goes wrong:** If the generate endpoint is mistakenly declared `async def`, WeasyPrint's blocking PDF rendering call freezes the entire event loop for 2-5 seconds, making the server unresponsive to all other requests during that time.

**Why it happens:** FastAPI auto-offloads `def` endpoints to a thread pool, but `async def` endpoints run on the event loop directly.

**How to avoid:** Always declare the generate endpoint as `def` (not `async def`). FastAPI will run it in its threadpool automatically.

**Warning signs:** API server appears completely frozen for all users during report generation.

### Pitfall 4: PDF Path Collision on Overwrite (D-64)

**What goes wrong:** When overwriting a report (D-64), the old PDF file must be deleted or overwritten before the new `Report` row is updated. If the DB update succeeds but the file write fails, the DB row points to a stale/missing file.

**Why it happens:** Non-atomic operation: disk write + DB update are two separate operations.

**How to avoid:** Write the PDF to a temp path first, then atomically rename it to the final path (on the same filesystem, `os.replace()` is atomic on Unix), then update the DB row. If either step fails, the old file is still intact.

```python
import tempfile, os

tmp_path = file_path + ".tmp"
HTML(string=html).write_pdf(tmp_path)
os.replace(tmp_path, file_path)  # atomic rename on same filesystem
# only now update the DB row
```

**Warning signs:** Download returns 404 even though the DB shows a report row.

### Pitfall 5: `Deal.add_time` Format Inconsistency

**What goes wrong:** `Deal.add_time` is stored as a string (see models.py line 64: `add_time: Mapped[str | None]`). The string format from Pipedrive is `"YYYY-MM-DD HH:MM:SS"`. The `[:7]` slice to extract `"YYYY-MM"` is correct for this format but will silently produce wrong values if the format changes (e.g., ISO 8601 with `T`).

**Why it happens:** Dates stored as strings have no type enforcement.

**How to avoid:** In `available_months()`, validate that `add_time[:7]` matches `r'\d{4}-\d{2}'` before including it. Log a warning if not.

### Pitfall 6: XSS in In-Page Preview Card

**What goes wrong:** The in-page `.pdf-preview` card renders Claude's narrative text via `innerHTML`. Claude's text could theoretically contain `<script>` or other HTML if the prompt is manipulated.

**Why it happens:** Claude generates text that is then reflected into DOM.

**How to avoid:** In `reports.js`, render Claude's narrative sections using `escHtml()` (already defined in `dashboard.js`) when interpolating into `innerHTML`. The three narrative strings (resumen_ejecutivo, deals_destacados, recomendacion) must be escaped before DOM insertion.

---

## Code Examples

### Report Generation Endpoint (Thin Router Pattern)

```python
# app/routers/reports.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Report, Talent
from app.schemas.reports import ReportGenerate, ReportOut, ReportHistoryItem
from app.services import reports as reports_service

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)

@router.get("/talents")
def list_report_talents(db: Session = Depends(get_db)):
    """Return list of active talents for the report talent dropdown."""
    talents = db.query(Talent).filter(Talent.active == True).order_by(Talent.name).all()
    return [{"id": t.id, "name": t.name} for t in talents]

@router.get("/months")
def available_months(talent_id: int, db: Session = Depends(get_db)):
    """Return distinct YYYY-MM strings for this talent's deals, desc."""
    return reports_service.available_months(db, talent_id)

@router.post("/generate", response_model=ReportOut)
def generate_report(body: ReportGenerate, db: Session = Depends(get_db)):
    """Generate (or regenerate) a PDF report for a talent+month. Sync endpoint."""
    return reports_service.generate_report(db, body.talent_id, body.month)

@router.get("/", response_model=list[ReportHistoryItem])
def list_reports(db: Session = Depends(get_db)):
    """Return all generated reports ordered by generated_at desc."""
    return reports_service.list_reports(db)

@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    """Serve a generated PDF as a file download."""
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

### Jinja2 Template Pattern for PDF

```html
<!-- templates/reports/template.html (light theme, SEG branding) -->
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: sans-serif; color: #1a1a1a; background: #fff; margin: 0; }
  .cover { text-align: center; padding: 80px 40px; border-bottom: 3px solid #e8520a; }
  .cover-title { font-size: 28px; font-weight: 700; color: #e8520a; }
  .cover-sub { font-size: 16px; color: #555; margin-top: 8px; }
  .ai-badge { display: inline-block; background: #f4e8ff; color: #6b54d6;
              border-radius: 20px; padding: 4px 12px; font-size: 12px; margin-top: 16px; }
  .section { padding: 32px 40px; border-bottom: 1px solid #eee; }
  .section-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                   color: #e8520a; margin-bottom: 12px; font-weight: 600; }
  .section-text { font-size: 14px; line-height: 1.7; color: #333; }
  .appendix table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .appendix td, .appendix th { border: 1px solid #ddd; padding: 8px 12px; }
  .appendix th { background: #f5f5f5; font-weight: 600; }
</style>
</head>
<body>
  <div class="cover">
    <div class="cover-title">{{ talent_name }}</div>
    <div class="cover-sub">Reporte mensual · {{ month }}</div>
    <div class="ai-badge">✦ Generado con Claude AI</div>
  </div>
  <div class="section">
    <div class="section-title">Resumen ejecutivo</div>
    <div class="section-text">{{ narrative.resumen_ejecutivo }}</div>
  </div>
  <div class="section">
    <div class="section-title">Deals destacados</div>
    <div class="section-text">{{ narrative.deals_destacados }}</div>
  </div>
  <div class="section">
    <div class="section-title">Recomendación</div>
    <div class="section-text">{{ narrative.recomendacion }}</div>
  </div>
  <div class="section appendix">
    <div class="section-title">Apéndice de datos</div>
    <table>
      <tr><th>KPI</th><th>Valor</th></tr>
      <tr><td>Pipeline</td><td>${{ "%.0f"|format(data.kpis.pipeline) }} MXN</td></tr>
      <tr><td>Cerrados ({{ data.kpis.cerrados_count }} deals)</td><td>${{ "%.0f"|format(data.kpis.cerrados_valor) }} MXN</td></tr>
      <tr><td>Comisión SEG</td><td>${{ "%.0f"|format(data.kpis.comision) }} MXN</td></tr>
      <tr><td>Leads totales</td><td>{{ data.leads_totales }}</td></tr>
      <tr><td>Leads calificados</td><td>{{ data.leads_calificados }}</td></tr>
    </table>
  </div>
</body>
</html>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` for JWT | `PyJWT` | 2024 (FastAPI docs migration PR #13917) | Already using PyJWT per Phase 1 |
| Dated model IDs (`claude-sonnet-4-5-20250929`) | Dateless IDs (`claude-sonnet-4-6`) pinned | Claude 4.6 generation (2026) | `claude-sonnet-4-6` is the correct pinned ID |
| `weasyprint <= 62` required `libgdk-pixbuf` | `weasyprint >= 63` uses `libpangoft2` only | ~2023 | Fewer Docker system dependencies needed |

**Deprecated/outdated:**
- `python-pdfkit`/`wkhtmltopdf`: Abandoned HTML-to-PDF approach — wkhtmltopdf is unmaintained. Use WeasyPrint.
- `reportlab` for narrative PDFs: Too low-level for AI-narrated content — requires pixel-level layout code.
- Streaming response for PDF generation: Not needed at this scale. FileResponse is correct (reads file asynchronously, doesn't load into memory).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `Deal.add_time` strings are consistently formatted as `"YYYY-MM-DD HH:MM:SS"` (Pipedrive format), making `[:7]` a reliable YYYY-MM extractor | Common Pitfalls #5, Pattern 6 | Dynamic month list would produce malformed or empty month strings |
| A2 | Jinja2 is already transitively available via FastAPI without explicit install | Standard Stack | If not, `jinja2` must be added explicitly to pyproject.toml (low risk — it is a FastAPI dependency) |
| A3 | WeasyPrint works on the developer's local macOS if Pango is installed via Homebrew | Common Pitfalls #1 | PDF generation fails in local dev; must install system libs via Homebrew |
| A4 | The `reports/` directory will be created by the service layer at startup or on first write | Architecture Patterns | FileNotFoundError on first report generation if directory doesn't exist |
| A5 | Claude's JSON response for the 3 sections will be under 1500 tokens for a single-talent monthly report | Pattern 1 | If context + response exceeds max_tokens, Claude will truncate; increase max_tokens or reduce payload |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed. (Table is not empty — A1 through A5 need planner attention.)

---

## Open Questions

1. **Talent slug strategy (D-67 discretion area)**
   - What we know: D-63 specifies `reports/{talent_slug}/{YYYY-MM}.pdf`; D-67 leaves the slug derivation to the planner.
   - What's unclear: Whether to use `str(talent.id)` (simple, no Unicode issues) or `slugify(talent.name)` (human-readable paths).
   - Recommendation: Use `str(talent.id)` for simplicity. Example: `reports/3/2025-05.pdf`. The Report model stores the human-readable display name and file_path separately — the path being numeric is not a user-visible concern.

2. **Month filtering scope (YYYY-MM vs full date)**
   - What we know: D-54 says "months that have deal data in SQLite." `Deal.add_time` is the creation date string.
   - What's unclear: Whether to filter by `add_time` (deal creation month) or by `stage_entered_at` (current month activity). The mockup shows "Mayo 2025" implying deal-creation month.
   - Recommendation: Filter by `add_time[:7]` (deal creation month) — matches user expectation for "this month's deals."

3. **Max_tokens for Claude narrative**
   - What we know: Three narrative sections at approximately 150-250 words each = ~500-750 tokens total output.
   - What's unclear: Whether to set `max_tokens=1000` or `max_tokens=1500`.
   - Recommendation: Use `max_tokens=1500` as a safe upper bound. Claude Sonnet 4.6 supports 64k max output, so there is no constraint on this side.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.x (pyproject.toml specifies >=3.12) | — |
| anthropic SDK | Claude API calls | Not yet installed (not in pyproject.toml) | 0.109.2 (latest PyPI 2026-06-15) | — (required) |
| WeasyPrint Python pkg | PDF rendering | Not yet installed | 69.0 (latest PyPI 2026-06-02) | — (required) |
| Jinja2 | HTML templating | Present (transitively via FastAPI) | 3.1.6 | — |
| Pango system lib | WeasyPrint on Linux | ✗ in Docker (Phase 7) | Installed locally via Homebrew on macOS | Dockerfile apt-get (Phase 7) |
| ANTHROPIC_API_KEY | Claude API auth | Present in .env (config.py line 21: `ANTHROPIC_API_KEY: str = ""`) | — | — (required, value must be set) |

**Missing dependencies with no fallback:**
- `anthropic` Python package — must be installed via `uv add`
- `weasyprint` Python package — must be installed via `uv add`
- `ANTHROPIC_API_KEY` env var value — must be set in `.env` before generation will work

**Missing dependencies with fallback:**
- Pango system libs in Docker — handled in Phase 7 Dockerfile; local dev uses Homebrew

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x (pyproject.toml dev dependency) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_reports.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REPORT-01 | `available_months()` returns correct YYYY-MM list from Deal data | unit | `pytest tests/test_reports.py::test_available_months -x` | ❌ Wave 0 |
| REPORT-01 | `generate_report()` assembles payload with only Python-computed figures | unit (mock Claude) | `pytest tests/test_reports.py::test_generate_report_payload -x` | ❌ Wave 0 |
| REPORT-01 | `generate_report()` writes PDF to disk at correct path | unit (mock Claude + mock WeasyPrint) | `pytest tests/test_reports.py::test_pdf_written_to_disk -x` | ❌ Wave 0 |
| REPORT-01 | `POST /reports/generate` returns 200 with narrative sections | integration (auth_client fixture) | `pytest tests/test_reports.py::test_generate_endpoint -x` | ❌ Wave 0 |
| REPORT-02 | `GET /reports/` returns report history list | integration | `pytest tests/test_reports.py::test_list_reports -x` | ❌ Wave 0 |
| REPORT-02 | `GET /reports/{id}/download` returns PDF bytes with correct Content-Type | integration | `pytest tests/test_reports.py::test_download_report -x` | ❌ Wave 0 |
| DASH-05 | 5th tab "Reportes" exists in index.html + page-reportes div | smoke (file inspection) | `grep -q 'page-reportes' frontend/index.html` | ❌ Wave 0 |

### Mocking Strategy for Tests

The `anthropic.Anthropic()` client and `weasyprint.HTML` must be mocked in tests to avoid real API calls and system lib dependencies:

```python
# In conftest.py — add fixtures:
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture()
def mock_anthropic(monkeypatch):
    """Return a mock Anthropic client that returns a fixed narrative response."""
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"resumen_ejecutivo":"Resumen de prueba.","deals_destacados":"Deals de prueba.","recomendacion":"Recomendación de prueba."}')]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr("app.services.reports.anthropic.Anthropic", lambda **kwargs: mock_client)
    return mock_client

@pytest.fixture()
def mock_weasyprint(monkeypatch, tmp_path):
    """Replace weasyprint.HTML with a stub that writes a 1-byte file."""
    def fake_write_pdf(path_or_none=None):
        if path_or_none:
            open(path_or_none, "wb").write(b"%PDF-1.4")
        return b"%PDF-1.4"
    mock_html = MagicMock()
    mock_html.return_value.write_pdf = fake_write_pdf
    monkeypatch.setattr("app.services.reports.HTML", mock_html)
    return mock_html
```

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_reports.py -x`
- **Per wave merge:** `uv run pytest -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_reports.py` — covers all REQ IDs above (7 test functions)
- [ ] `mock_anthropic` fixture — add to `tests/conftest.py`
- [ ] `mock_weasyprint` fixture — add to `tests/conftest.py`
- [ ] `reports/` directory — create and add to `.gitignore`
- [ ] `templates/reports/template.html` — Jinja2 PDF template (light theme)
- [ ] Alembic migration for `Report` model — `alembic revision --autogenerate -m "add_reports_table"`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `get_current_user` dependency on all `/reports/*` routes — same as existing routers |
| V3 Session Management | yes (inherited) | JWT cookie validation — already implemented in Phase 1 |
| V4 Access Control | yes | All report endpoints protected by `dependencies=[Depends(get_current_user)]` at router level |
| V5 Input Validation | yes | Pydantic `ReportGenerate` schema validates `talent_id: int`, `month: str` (pattern: `^\d{4}-\d{2}$`) |
| V6 Cryptography | no | No new crypto operations — PDF files are not encrypted |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `talent_slug` in file path | Tampering | Sanitize slug: use `re.sub(r'[^a-z0-9\-]', '', slug)` or use `str(talent.id)`; validate resolved path stays within `reports/` dir |
| Stored XSS via Claude narrative in preview card | Spoofing | Apply `escHtml()` to all Claude text before `innerHTML` in `reports.js` |
| SSRF via `base_url` in WeasyPrint | Information disclosure | Do not pass user-controlled values as `base_url`; use a fixed string or `"."` |
| Unauthenticated PDF download | Elevation of privilege | Router-level `dependencies=[Depends(get_current_user)]` covers all endpoints including download |
| Prompt injection via deal title/name in Claude payload | Tampering | The system prompt instructs Claude to treat the user message as data only; deal titles in the payload are in a JSON structure, not free-form instructions — low risk but document |

---

## Sources

### Primary (HIGH confidence)
- [platform.claude.com/docs/en/about-claude/models/overview](https://platform.claude.com/docs/en/about-claude/models/overview) — confirmed `claude-sonnet-4-6` as the current pinned model ID, max output 64k tokens, pricing $3/$15 per MTok (fetched 2026-06-15)
- [platform.claude.com/docs/en/about-claude/models/model-ids-and-versions](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) — confirmed dateless IDs are pinned snapshots for 4.6 generation (fetched 2026-06-15)
- [github.com/anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) — `messages.create(model, max_tokens, system, messages)` signature, `response.content[0].text` access pattern (fetched 2026-06-15)
- [doc.courtbouillon.org/weasyprint/stable/api_reference.html](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html) — `HTML(string=html).write_pdf(path)` API, parameters (fetched 2026-06-15)
- [doc.courtbouillon.org/weasyprint/stable/first_steps.html](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) — Debian system library requirements: `libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` (fetched 2026-06-15)
- [pypi.org/project/anthropic/](https://pypi.org/pypi/anthropic/json) — version 0.109.2, uploaded 2026-06-15, requires_python>=3.9 (fetched 2026-06-15)
- [pypi.org/project/weasyprint/](https://pypi.org/pypi/weasyprint/json) — version 69.0, uploaded 2026-06-02, requires_python>=3.10 (fetched 2026-06-15)
- [pypi.org/project/jinja2/](https://pypi.org/pypi/jinja2/json) — version 3.1.6, uploaded 2025-03-05, requires_python>=3.7 (fetched 2026-06-15)
- Codebase read: `app/models.py`, `app/services/kpis.py`, `app/services/funnel.py`, `app/services/leads.py`, `app/routers/dashboard.py`, `app/main.py`, `app/config.py`, `frontend/js/dashboard.js`, `frontend/js/leads.js`, `frontend/index.html`, `tests/conftest.py` — all read directly from filesystem 2026-06-15

### Secondary (MEDIUM confidence)
- [fastapi.tiangolo.com/async/](https://fastapi.tiangolo.com/async/) — `def` vs `async def` endpoint behavior; sync endpoints auto-offloaded to threadpool (verified via WebSearch cross-referencing official FastAPI docs)
- [slingacademy.com — FastAPI FileResponse](https://www.slingacademy.com/article/how-to-return-pdf-files-in-fastapi/) — `FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=..."})` pattern (WebSearch verified)

### Tertiary (LOW confidence)
- None — all critical claims verified from official sources or codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified live from PyPI; model ID verified from official Anthropic docs
- Architecture: HIGH — based on direct codebase read of all existing patterns + verified API docs
- Pitfalls: HIGH — WeasyPrint blocking confirmed from FastAPI docs; JSON parsing pitfall from Anthropic SDK experience
- Test patterns: HIGH — based on direct read of existing conftest.py and test structure

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (anthropic SDK releases frequently — verify version pin at build time)
