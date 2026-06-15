---
phase: 02-pipedrive-integration-core-dashboard
reviewed: 2026-06-14T20:45:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - app/main.py
  - app/routers/dashboard.py
  - app/schemas/dashboard.py
  - app/services/funnel.py
  - app/services/kpis.py
  - frontend/css/styles.css
  - frontend/index.html
  - frontend/js/dashboard.js
  - tests/test_dashboard.py
  - tests/test_funnel.py
  - tests/test_kpis.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-14T20:45:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 02 dashboard KPI/funnel services, router endpoints, Pydantic schemas, frontend shell, and test suite. The backend logic is structurally sound — auth guards are in place, response models validate shape at the boundary, and the Pitfall 4 (sin-talento split) is correctly handled. Two blockers were found: a DOM-destruction bug that permanently breaks the brand-category donut for any talent switch after viewing a talent with no brand categories, and an XSS vector in `innerHTML` rendering of unescaped API-sourced strings (deal titles, talent names, loss reasons). Five warnings cover the implicit `window.event` reliance in `setPage()` that fails in Firefox, unchecked `res.ok` before calling `.json()` in `loadSummary`/`loadFunnel`, a redundant `db.get()` in `talent_detail()` that can surface as a 500 instead of a 404 in a race, conic-gradient stops potentially exceeding 100% due to rounding, and the semantic ambiguity of the "Pipeline" KPI including lost-deal values.

---

## Critical Issues

### CR-01: DOM Destruction in `renderBrandDonut` Breaks Subsequent Talent Switches

**File:** `frontend/js/dashboard.js:566-573`

**Issue:** When a talent has no brand categories, `renderBrandDonut` replaces the entire `#brand-donut-card` container's `innerHTML` with an empty-state string:

```js
const card = document.getElementById("brand-donut-card");
if (card) {
  card.innerHTML = `<div ...>Sin categorías...</div>`;
}
```

This destroys the `<div id="brand-donut">` and `<div id="brand-legend">` child elements. On the very next talent selection (a talent that _does_ have brand categories), `renderBrandDonut` runs again: `document.getElementById("brand-donut")` returns `null`, the early-return fires on line 564, and the donut is silently never rendered. Every subsequent talent in the same session also silently skips donut rendering, because the IDs are gone from the DOM for the rest of the page lifetime.

**Fix:** Never destroy the containing structure. Replace only the inner elements, or restore the wrapper markup on the empty path:

```js
if (!brandCategories || brandCategories.length === 0) {
  if (donutEl) donutEl.innerHTML = "";
  if (legendEl) legendEl.innerHTML = `
    <div style="text-align:center;color:var(--text3);font-size:13px;padding:8px 0;">
      Sin categorías de marca registradas todavía
    </div>`;
  return;
}
```

---

### CR-02: Stored XSS — Unescaped API Strings Injected via `innerHTML`

**File:** `frontend/js/dashboard.js:288, 319, 543, 611, 642, 649, 690`

**Issue:** Every render function builds HTML via template literals and assigns it to `innerHTML`, interpolating strings that originate from Pipedrive API data stored in the SQLite DB: deal `title`, talent `name`, `stage_name`, `category`, `loss_reason`, brand `category`, `s.reason`. If any of these fields contains `<script>alert(1)</script>` or an `<img onerror=...>` payload — either from a malicious Pipedrive deal title or from a future import path — it executes in the authenticated user's browser session.

Representative examples:
```js
// line 288 — talent name from API
`<div class="rank-name">${row.name}</div>`

// line 319 — deal title + talent name + stage name
`<div class="act-main"><strong>${title}</strong> — ${item.talent_name} pasó a ${item.to_stage}</div>`

// line 649 — deal title in lost opportunities
`<div class="deal-brand">${opp.title || "Sin título"}</div>`

// line 642 — loss_reason label in pill (could contain HTML if label stored with < > chars)
`<span class="pill">${opp.loss_reason}</span>`
```

While this is a self-contained internal dashboard with a single admin user, the project CLAUDE.md explicitly mandates read-only integration with Pipedrive. A corrupted/adversarial Pipedrive deal title is a realistic threat surface.

**Fix:** Add a shared escape helper and use it for all user-visible API strings:

```js
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
```

Then replace every interpolated server string:
```js
// Before
`<div class="rank-name">${row.name}</div>`
// After
`<div class="rank-name">${escHtml(row.name)}</div>`
```

Apply to: `row.name`, `row.category`, `title` (activity feed and lost opps), `item.talent_name`, `item.to_stage`, `deal.title`, `deal.stage_name`, `opp.title`, `opp.loss_reason`, `slice.category`, `s.reason`, `stage.stage`, `talent.name` in the selector.

---

## Warnings

### WR-01: `setPage()` Relies on `window.event` — Tab Highlight Breaks in Firefox

**File:** `frontend/js/dashboard.js:30-32`

**Issue:** `setPage(name)` references the bare identifier `event` inside the function body:

```js
function setPage(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (event && event.target) {           // ← `event` = window.event (IE legacy)
    event.target.classList.add("active");
  }
}
```

`window.event` is a deprecated, non-standard API that is `undefined` in Firefox. In Firefox, the `if` branch never executes: all `.tab` elements lose the `active` class but none gets it back. The result is that clicking any tab in Firefox leaves the tab bar with no active indicator (visual regression, not a crash).

**Fix:** Pass the event explicitly from the `onclick` handler in `index.html`:

```html
<!-- index.html -->
<div class="tab active" onclick="setPage('overview', event)">Resumen</div>
```

```js
// dashboard.js
function setPage(name, e) {
  document.querySelectorAll(".page").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (e && e.currentTarget) {
    e.currentTarget.classList.add("active");
  }
}
```

Note: use `e.currentTarget` (the element with the listener), not `e.target` (which may be a text node child of the div when the user clicks on the label text).

---

### WR-02: `loadSummary` and `loadFunnel` Call `.json()` Without Checking `res.ok`

**File:** `frontend/js/dashboard.js:391, 426`

**Issue:** Both functions call `await res.json()` immediately after checking only for `null` (401 redirect). If the server returns a 500 with a non-JSON body (HTML error page, plain text traceback), `res.json()` throws a `SyntaxError`. Since neither function has a `try/catch`, this becomes an unhandled promise rejection — the dashboard silently freezes with no error shown to the user.

```js
async function loadSummary() {
  const res = await apiFetch("/dashboard/summary");
  if (!res) return; // only guards 401
  const data = await res.json(); // throws on 500 with HTML body
```

**Fix:** Check `res.ok` before parsing, and surface a toast on error:

```js
async function loadSummary() {
  const res = await apiFetch("/dashboard/summary");
  if (!res) return;
  if (!res.ok) {
    showToast("Error al cargar el resumen");
    return;
  }
  const data = await res.json();
  // ...
}
```

Apply the same pattern to `loadFunnel` (line 422) and `loadTalentSelector` (line 672).

---

### WR-03: `kpi_service.talent_detail()` Performs Redundant `db.get(Talent)` — `ValueError` Surfaces as 500

**File:** `app/services/kpis.py:166-168` and `app/routers/dashboard.py:125-129`

**Issue:** The router at `dashboard.py:125` already calls `db.get(Talent, talent_id)` and raises a `404` if the talent is not found. Then `kpi_service.talent_detail()` at `kpis.py:166` calls `db.get(Talent, talent_id)` **again** and raises a bare `ValueError` if the talent is absent. In a race condition where a talent is deleted between those two calls, the uncaught `ValueError` propagates as an HTTP 500 rather than a 404. While SQLite single-writer semantics make this rare, the error type mismatch is a correctness defect.

**Fix — Option A (preferred):** Remove the redundant lookup from `talent_detail()`. Since the router already guarantees the talent exists before calling the service, pass `talent` directly:

```python
# router
talent = db.get(Talent, talent_id)
if talent is None:
    raise HTTPException(status_code=404, detail="Talent not found")
detail = kpi_service.talent_detail(db, talent)  # pass the ORM object
```

```python
# service — accepts Talent object instead of id
def talent_detail(db: Session, talent: Talent) -> dict:
    # remove the db.get() call; use talent.name, talent.category directly
    talent_id = talent.id
    ...
```

**Fix — Option B (minimal):** Catch `ValueError` in the router:

```python
try:
    detail = kpi_service.talent_detail(db, talent_id)
except ValueError:
    raise HTTPException(status_code=404, detail="Talent not found")
```

---

### WR-04: Conic-Gradient Percentage Stops Can Exceed 100% Due to Rounding

**File:** `frontend/js/dashboard.js:579-587`

**Issue:** The backend rounds each brand category's `pct` to 2 decimal places (`round(pct, 2)`, `kpis.py:231`). With certain deal counts the sum of rounded percentages can exceed 100.0. For example, 3 categories at exactly 33.33% each sum to 99.99%, but other distributions can produce a cumulative total above 100. The JS accumulates these rounded values without clamping:

```js
brandCategories.forEach((slice, idx) => {
  conicStops.push(`${color} ${cumPct}% ${cumPct + slice.pct}%`);
  cumPct += slice.pct;
});
if (cumPct < 100) {                         // does NOT handle cumPct > 100
  conicStops.push(`var(--bg5) ${cumPct}% 100%`);
}
```

A `conic-gradient` with a stop past 100% is technically invalid CSS and browser rendering is undefined — the donut may render incorrectly or with missing segments.

**Fix:** Clamp the last stop's end to 100 and add a guard for over-run:

```js
let cumPct = 0;
brandCategories.forEach((slice, idx) => {
  const start = Math.min(cumPct, 100);
  const end = Math.min(cumPct + slice.pct, 100);
  const color = DONUT_COLORS[idx % DONUT_COLORS.length];
  conicStops.push(`${color} ${start}% ${end}%`);
  cumPct += slice.pct;
});
if (cumPct < 99.99) {
  conicStops.push(`var(--bg5) ${Math.min(cumPct, 100)}% 100%`);
}
```

---

### WR-05: "Pipeline" Per-Talent KPI Includes Lost-Deal Values Without Label Clarification

**File:** `app/services/kpis.py:171-173`

**Issue:** The per-talent "Pipeline" KPI sums `Deal.value` with no `status` filter, so it includes open, won, and lost deals:

```python
pipeline_row = db.query(
    func.coalesce(func.sum(Deal.value), 0.0),
).filter(Deal.talent_id == talent_id).scalar() or 0.0
```

The test at `test_kpis.py:194` asserts `Pipeline == 65000` (50000 open + 15000 lost), confirming this is the current design. However, a "Pipeline" label conventionally refers to deals still in play (open). Including lost-deal value inflates the number displayed to the user under a label that implies active opportunity. The global "Pipeline total" tile has the same behavior, but for the per-talent view it is more misleading because the detail page also shows those same lost deals explicitly in "Oportunidades perdidas."

**Fix:** Either filter to open-only deals and rename nothing, or rename the label to "Histórico total" / "Total facturado + en curso" to reflect what it actually shows. Whichever choice is made should be consistent between global and per-talent tiles.

```python
# Option: open-only pipeline
pipeline_row = db.query(
    func.coalesce(func.sum(Deal.value), 0.0),
).filter(Deal.talent_id == talent_id, Deal.status == "open").scalar() or 0.0
```

---

## Info

### IN-01: `renderTalentFunnel` Duplicates `renderFunnel` — Dead Code Path

**File:** `frontend/js/dashboard.js:491-518`

**Issue:** `renderTalentFunnel()` is a verbatim copy of `renderFunnel()` with the only difference being the target container ID (`"talent-funnel"` vs `"funnel-rows"`). The comment at line 488 acknowledges this. This is code duplication — any future change to funnel row markup must be made in two places.

**Fix:** Parameterize the existing function by container ID:

```js
function renderFunnel(stages, containerId = "funnel-rows") {
  const container = document.getElementById(containerId);
  // ...
}
// Callers:
renderFunnel(data.stages);                    // global funnel tab
renderFunnel(data.funnel, "talent-funnel");   // per-talent funnel
```

---

### IN-02: `renderTalentDeals` Function Is Defined but Never Called

**File:** `frontend/js/dashboard.js:524-554`

**Issue:** `renderTalentDeals(deals)` is defined (line 524) but never invoked anywhere in the file. `loadTalentDetail` builds its own inline deal-row markup from funnel stages (lines 749-766) rather than calling this function. The dead function takes a `deals` array parameter (with an `is_sin_cotizar` field) that does not match anything the `/dashboard/talents/{id}` endpoint returns.

**Fix:** Remove `renderTalentDeals()` entirely to prevent future confusion, or wire it to the actual call site if a raw-deal endpoint is added in a later phase.

---

### IN-03: `_clean_tables` Fixture Uses Post-Yield Cleanup — Lost if Test Session Crashes

**File:** `tests/conftest.py:82-98`

**Issue:** The `autouse=True` `_clean_tables` fixture cleans up after each test in the `yield`-after phase. If pytest crashes mid-session (e.g., a segfault or keyboard interrupt), the cleanup never runs and the shared in-memory `StaticPool` DB retains rows from the previous test. This can cause spurious `IntegrityError` failures on re-runs within the same process. This is a known trade-off with shared in-memory test databases, but it is worth noting.

**Fix:** Move cleanup to _before_ the test (or use both), so each test always starts from a clean state regardless of the previous test's outcome:

```python
@pytest.fixture(autouse=True)
def _clean_tables():
    db = TestSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()
    yield  # cleanup runs before the test, not after
```

---

_Reviewed: 2026-06-14T20:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
