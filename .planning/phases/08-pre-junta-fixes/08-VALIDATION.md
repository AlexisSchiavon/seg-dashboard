---
phase: 8
slug: pre-junta-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-24
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (check for `[tool.pytest]` section) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | FIX-01 | T-08-IC | Sync reads `deal["lost_reason"]` standard field, not custom field resolver | unit | `uv run pytest tests/test_sync.py -x -k lost_reason` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | FIX-01 | T-08-IC | `talent_detail()` returns real reasons in `lost_summary` when DB has `loss_reason` set | unit | `uv run pytest tests/test_sync.py tests/test_kpis.py -x -k "lost_reason or lost"` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | FIX-01 | — | After re-sync, donut shows real percentages not "Sin razón — 100%" | manual | Browser inspection of Por Talento donut | N/A | ⬜ pending |
| 08-02-01 | 02 | 2 | FIX-02 | T-08-IC | `flujo_dinero_kpis()` returns 3 tiles with correct values; endpoint includes `flujo_dinero` field | unit+integration | `uv run pytest tests/test_kpis.py tests/test_dashboard.py -x -k "flujo or talent_detail"` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | FIX-02 | T-08-XSS | DOM toggle renders with `kpi-toggle-btn` class; no raw unsanitized strings inserted | file check | `grep -q "kpi-toggle" frontend/index.html && grep -q "setKpiView" frontend/js/dashboard.js` | ✅ (after edit) | ⬜ pending |
| 08-02-03 | 02 | 2 | FIX-02 | — | Toggle visible in Por Talento; both views render correct data | manual | Browser inspection of Por Talento toggle | N/A | ⬜ pending |
| 08-03-01 | 03 | 3 | FIX-03 | — | "(vía Trello)" badge renders on "En ejecución" and "Cobranza" funnel stages | file check | `grep -q "vía Trello" frontend/js/dashboard.js` | ✅ (after edit) | ⬜ pending |
| 08-03-02 | 03 | 3 | FIX-03 | — | Title renamed to "Histórico de ingresos por mes"; segments relabeled to honest names | file check | `grep -q "Histórico de ingresos por mes" frontend/index.html && grep -q "En campaña" frontend/js/dashboard.js` | ✅ (after edit) | ⬜ pending |
| 08-03-03 | 03 | 3 | FIX-03 | — | Funnel badges visible; chart title renamed; no "(Proyección)" label remains | manual | Browser inspection of funnel + revenue chart | N/A | ⬜ pending |
| 08-04-01 | 04 | 4 | FIX-04 | — | "Sin talento asignado" row visually distinct with actionable copy | file check | `grep -q "sin-talento" frontend/css/styles.css` | ✅ (after edit) | ⬜ pending |
| 08-04-02 | 04 | 4 | FIX-04 | — | APScheduler logs show 30-min interval and last sync timestamp in SyncLog | manual | Browser dev tools / EasyPanel logs inspection | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sync.py` — add `test_lost_reason_standard_field()`: mock deal dict with top-level `lost_reason="Ya no contestó"`, assert `sync_pipedrive` writes `deal.loss_reason = "Ya no contestó"`
- [ ] `tests/test_kpis.py` — add `test_flujo_dinero_kpis()`: fixture with TrelloCard rows covering the three list_state values, assert 3 tiles with correct amounts returned
- [ ] `tests/test_dashboard.py` — add assertion that `GET /dashboard/talents/{id}` response JSON includes `flujo_dinero` key as a non-null list

---

## Security Notes

This phase has no new external attack surface. All threat items are rated low/informational:

- **T-08-IC (Input Canonicalization):** Sync reads `deal.get("lost_reason")` from Pipedrive JSON response. No user-supplied input; trust boundary is the Pipedrive API (existing trust relationship).
- **T-08-XSS (DOM XSS):** Frontend toggle renders KPI tile labels from the API response. Must route through existing `escHtml()` helper (confirmed present in `dashboard.js`). No raw `innerHTML` with unescaped API strings.
- **T-08-SC (Supply Chain):** No new packages installed in this phase. N/A.

No high-severity threats blocking execution.
