---
phase: 02-pipedrive-integration-core-dashboard
fixed_at: 2026-06-14T20:55:00Z
review_path: .planning/phases/02-pipedrive-integration-core-dashboard/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-06-14T20:55:00Z
**Source review:** .planning/phases/02-pipedrive-integration-core-dashboard/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 7
- Skipped: 0

All 65 tests pass after fixes (`uv run pytest -x -q`).

## Fixed Issues

### CR-01: DOM destruction in renderBrandDonut

**Files modified:** `frontend/js/dashboard.js`
**Commit:** 902b1f4
**Applied fix:** Removed the `card.innerHTML = ...` line that replaced the entire `#brand-donut-card` container. Instead, clear only `donutEl.innerHTML` and write the empty-state message into `legendEl.innerHTML`. The `#brand-donut` and `#brand-legend` child elements are now never removed from the DOM, so subsequent talent selections with brand categories render correctly.

---

### CR-02: Stored XSS via unescaped innerHTML

**Files modified:** `frontend/js/dashboard.js`
**Commit:** a1d003f
**Applied fix:** Added `escHtml(str)` helper at the top of the file (escapes `&`, `<`, `>`, `"`, `'`). Applied to all Pipedrive-sourced strings interpolated into template-literal innerHTML:
- Ranking: `row.name`, `row.category`, `avatarContent`
- Activity feed: `item.title`, `item.talent_name`, `item.to_stage`
- Funnel rows (renderFunnel + renderTalentFunnel): `stage.stage`
- renderTalentDeals: `deal.title`, `deal.stage_name`
- Brand legend: `slice.category`
- Lost opportunities: `s.reason`, `opp.loss_reason`, `opp.title`
- Talent selector: `talent.name`, `initials`
- loadTalentDetail inline deals: `stage.stage`

---

### WR-01: window.event in setPage() breaks Firefox tab highlight

**Files modified:** `frontend/js/dashboard.js`, `frontend/index.html`
**Commit:** 8e2626a
**Applied fix:** Changed `setPage(name)` to `setPage(name, e)`. Updated all three `onclick` handlers in `index.html` to pass `event` explicitly. Changed `event.target` to `e.currentTarget` so the tab div element itself (not a potential text-node child) receives the `active` class.

---

### WR-02: Missing res.ok check in load functions

**Files modified:** `frontend/js/dashboard.js`
**Commit:** 548a97f
**Applied fix:** Added `if (!res.ok) { showToast(...); return; }` guard before every `.json()` call in `loadSummary`, `loadFunnel`, and `loadTalentSelector`. Consistent with the existing pattern in `loadTalentDetail`. Prevents `SyntaxError` from a non-JSON error response body.

---

### WR-03: Redundant db.get in talent_detail() causes 500 on race

**Files modified:** `app/routers/dashboard.py`
**Commit:** 8a47585
**Applied fix:** Applied Option B (minimal, no service signature change). Wrapped the `kpi_service.talent_detail(db, talent_id)` call in a `try/except ValueError` that re-raises as `HTTPException(404)`. The service's own `db.get` + `ValueError` path now surfaces correctly as a 404 in the rare race where a talent is deleted between the router guard and the service call.

---

### WR-04: Conic-gradient stops exceed 100% due to rounding

**Files modified:** `frontend/js/dashboard.js`
**Commit:** 7d5f0b3
**Applied fix:** Introduced `start = Math.min(cumPct, 100)` and `end = Math.min(cumPct + slice.pct, 100)` in the gradient stop builder. Changed the gap-fill guard from `cumPct < 100` to `cumPct < 99.99` (absorbs floating-point noise) and clamped `cumPct` with `Math.min` before using it in the fill stop. The gradient now never produces a CSS stop past 100%.

---

### WR-05: Pipeline KPI includes lost-deal values

**Files modified:** `app/services/kpis.py`, `tests/test_kpis.py`
**Commit:** c91e4eb
**Applied fix:** Added `Deal.status == "open"` filter to the per-talent pipeline query in `talent_detail()`. Updated `test_talent_detail_only_own_deals` to assert `50000.0` (open deal only) instead of `65000.0` (open + lost). Lost deals are already surfaced explicitly in `lost_opportunities`; including them in Pipeline was misleading double-counting.

---

_Fixed: 2026-06-14T20:55:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
