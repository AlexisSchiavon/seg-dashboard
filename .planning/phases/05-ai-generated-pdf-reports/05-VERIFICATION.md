---
phase: 05-ai-generated-pdf-reports
verified: 2026-06-16T05:55:59Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Abrir el tab Reportes en el navegador y verificar la vista completa"
    expected: "El tab 'Reportes' se activa con highlight accent, el dropdown de talentos se llena con 21 talentos, y la página se muestra sin errores visuales"
    why_human: "La apariencia visual del tab activo, el layout responsive y el estado inicial del formulario solo son verificables desde el navegador"
  - test: "Seleccionar un talento con deals y verificar el dropdown de meses"
    expected: "El dropdown de meses se activa y muestra meses en formato 'Mayo 2025', el botón 'Generar reporte con IA' se habilita"
    why_human: "El comportamiento onChange y el formato visual de los meses requieren interacción real en el navegador"
  - test: "Seleccionar un talento sin deals y verificar el empty state"
    expected: "El dropdown de meses permanece deshabilitado, se muestra el alerta 'Sin datos disponibles. Este talento no tiene deals con fecha registrada.', el botón Generar permanece deshabilitado"
    why_human: "El empty state y la visibilidad de los elementos DOM solo pueden confirmarse visualmente"
  - test: "Hacer click en 'Generar reporte con IA' con ANTHROPIC_API_KEY configurado"
    expected: "Aparece el spinner con texto 'Generando...', luego el skeleton en la preview card, y finalmente los 3 bloques narrativos (Resumen ejecutivo, Deals destacados, Recomendación) con texto coherente en español. Aparece el toast 'Reporte generado correctamente'. Se agrega el reporte al historial abajo."
    why_human: "La llamada real a Claude, el timing del spinner y la renderización de las 3 secciones narrativas solo son verificables end-to-end con API key real"
  - test: "Verificar que los números en el PDF descargado coincidan con los datos del dashboard Por talento"
    expected: "Los valores de Pipeline, Cerrados, Comisión, Leads en el apéndice del PDF deben coincidir exactamente con los valores mostrados en el tab Por talento para el mismo talento y mes — Claude no inventó ningún número"
    why_human: "La reconciliación numérica entre el PDF generado y el dashboard requiere comparación visual humana"
  - test: "Click en 'Descargar PDF' después de generar"
    expected: "Se descarga un archivo reporte-{nombre}-{YYYY-MM}.pdf con tema claro (fondo blanco, acento #e8520a), secciones en orden: portada, resumen ejecutivo, deals destacados, recomendación, apéndice de datos KPI"
    why_human: "El contenido visual del PDF (diseño, tipografía, colores, layout de secciones) solo puede inspeccionarse abriendo el archivo descargado"
  - test: "Verificar el historial de reportes y click en descarga desde el historial"
    expected: "La sección 'Reportes anteriores' lista el reporte recién generado con '{nombre} · Mayo 2025' y 'Generado el {fecha}', el badge PDF en azul, y al hacer click se descarga el PDF correctamente"
    why_human: "El rendering del historial, el formato de fecha y la interacción de descarga desde historial requieren browser testing"
---

# Phase 5: AI-Generated PDF Reports — Verification Report

**Phase Goal:** Users can generate AI-narrated monthly PDF reports per individual talent using Claude, with all financial figures computed in Python and only narrated by the AI, and browse/download report history.
**Verified:** 2026-06-16T05:55:59Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can trigger generation of a monthly PDF report for a single talent | VERIFIED | `POST /reports/generate` endpoint exists in `app/routers/reports.py:63`, auth-protected, tested in `TestGenerateEndpoint` (5 tests, all passing) |
| 2 | Generated PDF contains figures computed entirely in Python with Claude providing only narrative text — no AI-invented numbers | VERIFIED | `_build_payload()` in `app/services/reports.py:83-192` computes all KPIs, funnel, top deals via direct SQLAlchemy queries filtered by `(talent_id, month)`. `_call_claude()` receives only the pre-computed JSON and returns only 3 prose strings. Test `test_payload_does_not_ask_claude_to_compute_numbers` verifies this separation. |
| 3 | The Reportes tab lists previously generated reports and allows downloading any of them | VERIFIED | `GET /reports/` (`app/routers/reports.py:115`) + `GET /reports/{id}/download` (`app/routers/reports.py:125`) exist. Frontend `loadReportHistory()` renders the list. `downloadReport()` triggers download via `window.location.href`. All 7 download/list tests passing. |

**Score:** 9/9 must-haves verified (includes PLAN-level and roadmap success criteria)

### Deferred Items

None.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/reports.py` | available_months, generate_report, list_reports | VERIFIED | 365 lines, 7 functions. All substantive, all wired. |
| `app/routers/reports.py` | GET /talents, /months, POST /generate, GET /, /{id}/download | VERIFIED | 171 lines, 5 endpoints, router-level `dependencies=[Depends(get_current_user)]` confirmed at line 35. |
| `app/models.py::Report` | id, talent_id(FK), month, generated_at, file_path, file_size_bytes + UniqueConstraint | VERIFIED | `class Report(Base)` at line 121. `UniqueConstraint("talent_id", "month", name="uq_report_talent_month")` at line 124. All 6 fields present. |
| `app/schemas/reports.py` | ReportGenerate, NarrativeSections, ReportOut, ReportHistoryItem | VERIFIED | All 4 classes present. `month` field uses `Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")` — stricter than plan spec (rejects invalid months like 2026-00, 2026-13). |
| `templates/reports/template.html` | Light theme, 5 sections, Jinja2 variables | VERIFIED | All 3 narrative variables present. `#e8520a` accent, `Helvetica Neue` font stack (no Google Fonts URL), 5 sections in order confirmed by grep (count=8 matches). |
| `app/main.py` | reports.router before StaticFiles | VERIFIED | `app.include_router(reports.router)` at line 26, `StaticFiles` mount at line 30. |
| `alembic/versions/afc2f8425aa0_add_reports_table.py` | Migration for reports table | VERIFIED | File exists. |
| `frontend/index.html` | 5th tab Reportes + id="page-reports" + script tag | VERIFIED | `setPage('reports', event)` at line 23. `id="page-reports"` at line 240. `<script src="/js/reports.js">` at line 304. |
| `frontend/js/reports.js` | 5 functions: loadReportTalents, loadReportMonths, generateReport, loadReportHistory, downloadReport | VERIFIED | 362 lines. All 5 functions present and substantive. escHtml() wraps all narrative and history strings before innerHTML. No raw `fetch()` calls — all use `apiFetch()`. |
| `frontend/css/styles.css` | .pdf-preview, .pdf-section, .pdf-block, .ai-badge | VERIFIED | `.pdf-preview` at line 1253, `.pdf-section` at 1248, `.pdf-block` at 1289, `.ai-badge` at 1318, `.pdf-skeleton` at 1332. All present. |
| `tests/test_reports.py` | 21 tests covering all phase 5 behaviors | VERIFIED | 21 tests collected, 21 passed (verified via live `pytest` run). |
| `tests/conftest.py` | mock_anthropic + mock_weasyprint fixtures | VERIFIED | `def mock_anthropic` at line 663, `def mock_weasyprint` at line 688. `Report` imported at line 29. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/reports.py` | kpis/funnel/leads services | `kpi_service`, `funnel_service`, `leads_service` imports + calls | VERIFIED | Imports at lines 35-37. All KPI/funnel/leads data from Python queries in `_build_payload()`. CR-01 month filter applied via `add_time.like(month_prefix)` at lines 103, 115, 131, 154. |
| `app/services/reports.py` | Claude API | `anthropic.Anthropic().messages.create(model="claude-sonnet-4-6")` | VERIFIED | Lines 202-213. Returns only 3 prose sections. JSON fence stripping at lines 221-225. |
| `app/routers/reports.py` | `app.services.reports` | `reports_service.generate_report / available_months / list_reports` | VERIFIED | All 5 endpoints delegate to the service layer. |
| `app/routers/reports.py` `/reports/{id}/download` | disk file | `FileResponse(path=report.file_path)` + `os.path.exists` guard | VERIFIED | Line 142 checks existence, line 161 returns FileResponse. `Content-Disposition` at line 165 with RFC 5987 compliant `filename*=UTF-8''...` encoding (CR-02 enhancement). |
| `frontend/js/dashboard.js` `setPage` | `loadReportTalents / loadReportHistory` | `name === "reports"` branch | VERIFIED | Lines 61-64 in dashboard.js. Branch confirmed by grep. |
| `frontend/js/reports.js` | `/reports/*` endpoints | `apiFetch("/reports...)` | VERIFIED | No raw `fetch()` calls found. All API calls through `apiFetch`. |
| `frontend/js/reports.js` | `escHtml` | Wraps narrative.resumen_ejecutivo, narrative.deals_destacados, narrative.recomendacion before innerHTML | VERIFIED | Lines 242, 246, 250 wrap all 3 Claude narrative fields. Lines 315-316, 323 escape history row strings. `function escHtml` is NOT redefined in reports.js (confirmed by grep). |
| `setPage('reports', event)` | `id="page-reports"` | `document.getElementById("page-" + name)` in dashboard.js line 43 | VERIFIED | Name "reports" → DOM id "page-reports". Consistent across index.html and dashboard.js. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/services/reports.py::_build_payload` | `pipeline_val`, `cerrados_count`, `cerrados_valor`, `comision` | Direct SQLAlchemy queries on `Deal` table with `(talent_id, status, add_time LIKE month_prefix)` filters | Yes — DB queries, not hardcoded | FLOWING |
| `app/services/reports.py::_call_claude` | `narrative` dict | `anthropic.Anthropic().messages.create(model="claude-sonnet-4-6", ...)` with pre-computed JSON payload | Yes — real Claude API call (mocked in tests) | FLOWING |
| `app/routers/reports.py::list_reports` | list of `ReportHistoryItem` | `reports_service.list_reports(db)` → queries `Report` table ordered by `generated_at desc` | Yes — real DB query | FLOWING |
| `frontend/js/reports.js::generateReport` | `data.narrative` | `apiFetch("/reports/generate", POST)` → backend returns `ReportOut` with narrative | Yes — proxied from Claude via backend | FLOWING |
| `frontend/js/reports.js::loadReportHistory` | `reports` array | `apiFetch("/reports/")` → backend `list_reports` queries DB | Yes — real DB data | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 21 phase 5 tests pass | `uv run pytest tests/test_reports.py -v` | 21 passed, 0 failed, 8 warnings | PASS |
| Full test suite (145 tests) — no regressions | `uv run pytest --tb=no -q` | 145 passed, 8 warnings in 7.61s | PASS |
| Routes registered: /reports/talents, /months, /generate, /, /{id}/download | Confirmed via `app/main.py` router registration order + router prefix | All 5 routes present | PASS |
| generate_report endpoint is `def` not `async def` | `grep "def generate_report" app/routers/reports.py` | `def generate_report(` at line 64 (no `async`) | PASS |
| escHtml used on all Claude text before innerHTML | `grep "escHtml(" frontend/js/reports.js` | Lines 242, 246, 250, 315, 316, 323 — all 3 narrative fields + history strings wrapped | PASS |
| No raw `fetch()` in reports.js | `grep "fetch(" frontend/js/reports.js | grep -v apiFetch` | No output — all calls through apiFetch | PASS |
| `base_url="."` is literal, never user-controlled | `grep "base_url" app/services/reports.py` | Line 264: `HTML(string=html_str, base_url=".")` — fixed literal | PASS |
| Month filtering (CR-01) applied to all queries | `grep "add_time.like\|month_prefix" app/services/reports.py` | 4 occurrences of `add_time.like(month_prefix)` — KPIs, funnel, top deals all filtered by month | PASS |

---

### Probe Execution

No probe scripts declared for this phase. Step 7c: SKIPPED (behavioral spot-checks and pytest suite cover verification).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REPORT-01 | 05-01, 05-02 | System generates a monthly PDF report per talent using Claude AI — all figures in Python, Claude only narrates | SATISFIED | `generate_report()` service: `_build_payload()` computes all numbers, `_call_claude()` returns only 3 prose strings. `POST /reports/generate` endpoint tested (5 tests passing). PDF written to `reports/{talent_id}/{YYYY-MM}.pdf` via atomic write. |
| REPORT-02 | 05-03 | User can download historical generated reports | SATISFIED | `GET /reports/` returns history list. `GET /reports/{id}/download` returns `FileResponse` with `media_type="application/pdf"` and `Content-Disposition: attachment`. 4 download tests passing including auth (401) and missing-file (404) guards. |
| DASH-05 | 05-04 | Reportes tab UI — generate AI PDF reports and browse/download history | SATISFIED | 5th tab in tabbar. `id="page-reports"` page with talent/month selects, preview card, generate button, history list. `reports.js` 362 lines with all 5 module-contract functions. DASH-05 smoke test passing. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/services/reports.py` | 311 | `datetime.utcnow()` deprecated (Python 3.12) | INFO | Non-blocking warning. Python recommends `datetime.now(datetime.UTC)`. No functional impact on current Python 3.12. |
| `tests/test_reports.py` | 323 | `datetime.utcnow()` deprecated in test fixture | INFO | Same as above, test-only, no production impact. |

No TBD, FIXME, or XXX markers found in any Phase 5 files. No stub implementations, no hardcoded empty returns, no orphaned components.

---

### Security Verification

| Threat | Disposition | Verified |
|--------|-------------|---------|
| T-path-traversal: path `reports/{slug}/{month}.pdf` | `_slug()` returns `str(talent.id)` — numeric only | VERIFIED — line 241 |
| T-ssrf: WeasyPrint base_url | Literal `"."` string, never user input | VERIFIED — line 264 |
| T-claude-numbers: Claude inventing figures | All numbers from Python DB queries; Claude returns only prose strings | VERIFIED — `_build_payload()` + `_call_claude()` separation |
| T-xss: Claude narrative in DOM | `escHtml()` wraps all 3 narrative fields + history strings before innerHTML | VERIFIED — reports.js lines 242, 246, 250, 315, 316, 323 |
| T-unauth-dl: unauthenticated download | Router-level `dependencies=[Depends(get_current_user)]` | VERIFIED — router line 35; `test_download_requires_auth` PASS |
| T-05-VAL: malformed month input | `Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")` in ReportGenerate | VERIFIED — schemas.py line 16; `test_generate_invalid_month_returns_422` PASS |
| T-stale-path: DB row with missing file | `os.path.exists()` check returns 404, not 500 | VERIFIED — router line 142; `test_download_missing_file` PASS |

---

### Notable Deviations from Plan (Auto-Fixed, Not Gaps)

1. **`page-reportes` → `page-reports`** (05-04): The PLAN specified `id="page-reportes"` but the implementation uses `id="page-reports"` for consistency with `setPage('reports')` → `"page-" + name` pattern. Documented in git log (commits `4438895`, `8696d93`). The smoke test was updated accordingly and passes. This is a correct implementation choice, not a gap.

2. **Lazy WeasyPrint import** (05-02): Module-level `from weasyprint import HTML` raises OSError on macOS without Pango/Cairo. Changed to lazy import inside `_render_pdf()` with `HTML = None` sentinel for monkeypatching. Phase 7 Dockerfile handles Linux system libs. Correct pattern per RESEARCH.md.

3. **`.gitignore` root-anchor fix** (05-02): Changed `reports/` to `/reports/` to prevent ignoring `templates/reports/`. Required to commit the Jinja2 template.

4. **Month pattern tightened** (schemas): Plan specified `^\d{4}-\d{2}$` but implementation uses `^\d{4}-(0[1-9]|1[0-2])$` — rejects semantically invalid months (2026-00, 2026-13). Strictly more correct than plan requirement.

5. **`Content-Disposition` RFC 5987** (05-03): Plan specified simple `filename=...`. Implementation adds `filename*=UTF-8''...` (RFC 6266 / CR-02) for non-ASCII talent names. Enhancement, not a gap.

---

### Human Verification Required

Task 3 of plan 05-04 is a `checkpoint:human-verify` (gate: blocking) that requires a real end-to-end browser test with `ANTHROPIC_API_KEY` set and Pango/WeasyPrint available locally. No automated test can substitute for this.

**7 items require human testing:**

#### 1. Tab visual and talent dropdown

**Test:** Abrir http://localhost:8000/, hacer login, click en tab "Reportes"
**Expected:** Tab se activa con highlight accent (`var(--accent)`). Dropdown `#report-talent` se llena con los 21 talentos ordenados alfabéticamente. Dropdown `#report-month` permanece deshabilitado.
**Why human:** Apariencia visual, estado inicial de controles, responsive layout.

#### 2. Month dropdown with deals data

**Test:** Seleccionar un talento que tenga deals en Pipedrive (ej. cualquiera de los 21)
**Expected:** Dropdown `#report-month` se activa con meses en formato "Mayo 2025" (no "2025-05"), botón "Generar reporte con IA" se habilita.
**Why human:** Interacción onChange, formato de label de meses, habilitación de controles DOM.

#### 3. Empty state for talent without deals

**Test:** Seleccionar un talento sin deals en la BD local
**Expected:** Alert `.alert.info` visible con texto "Sin datos disponibles. Este talento no tiene deals con fecha registrada. Sincroniza Pipedrive primero." Botón Generar permanece deshabilitado.
**Why human:** Visibilidad del empty state, copia exacta del alert.

#### 4. Full generation flow with real Claude API

**Test:** Con `ANTHROPIC_API_KEY` en `.env`, seleccionar talento + mes, click "Generar reporte con IA"
**Expected:** (a) Botón muestra spinner SVG + "Generando..." y se deshabilita. (b) Preview card aparece con skeleton pulse. (c) Tras respuesta de Claude: preview muestra 3 secciones narrativas en español con texto coherente (Resumen ejecutivo, Deals destacados, Recomendación). (d) Badge "✦ Claude AI" visible. (e) Toast "Reporte generado correctamente". (f) Botón "Descargar PDF" se habilita. (g) Reporte aparece al tope del historial.
**Why human:** Timing del spinner, llamada real a Claude, calidad del texto narrativo.

#### 5. Number reconciliation — Python vs Claude

**Test:** Comparar cifras del PDF con el tab "Por talento" para el mismo talento y mes
**Expected:** Pipeline, Cerrados (count + valor), Comisión, Leads en el apéndice del PDF deben coincidir exactamente con los KPIs del tab Por talento para ese talento. Claude no debe haber inventado ni calculado ningún número.
**Why human:** Reconciliación numérica requiere comparación visual entre PDF descargado y dashboard.

#### 6. PDF download — visual design

**Test:** Click "Descargar PDF" → abrir el archivo descargado
**Expected:** PDF con tema claro (fondo `#ffffff`, acento `#e8520a`), portada con nombre del talento y "✦ Generado con Claude AI", 5 secciones en orden: portada → Resumen ejecutivo → Deals destacados → Recomendación → Apéndice de datos. Tabla KPI en apéndice con Pipeline, Cerrados, Comisión, Leads. Nombre de archivo: `reporte-{nombre-talento}-{YYYY-MM}.pdf`.
**Why human:** Diseño visual del PDF, tipografía, colores, orden de secciones, nombre de archivo.

#### 7. History list and download

**Test:** Verificar la sección "Reportes anteriores" y hacer click en una fila del historial
**Expected:** Fila muestra "{nombre talento} · {Mes YYYY}", sub-texto "Generado el {D MMM}", badge "PDF" en azul. Click en la fila descarga el PDF correctamente.
**Why human:** Rendering del historial, formato de fecha abreviada, interacción de descarga desde la lista.

---

### Gaps Summary

Ninguno. Todos los must-haves están verificados en el código. El estado `human_needed` refleja únicamente el checkpoint de verificación humana (gate: blocking) declarado en el plan 05-04 Task 3 — que no puede ser sustituido por checks automatizados.

El código está completamente implementado, los 21 tests del suite de Phase 5 pasan, y los 145 tests totales pasan sin regresiones.

---

_Verified: 2026-06-16T05:55:59Z_
_Verifier: Claude (gsd-verifier)_
