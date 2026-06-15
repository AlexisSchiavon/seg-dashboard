---
phase: 3
slug: google-sheets-leads-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SHEET-01 | — | Google Sheet reads are read-only | unit | `python -m pytest tests/test_sheets_integration.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | SHEET-01 | — | Upsert by sheet_row_id prevents duplicates | unit | `python -m pytest tests/test_leads_service.py::test_upsert_by_row_id -x -q` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | SHEET-02 | — | Talent name match is exact-string | unit | `python -m pytest tests/test_leads_service.py::test_talent_attribution -x -q` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | SHEET-02 | — | Unmatched talent → talent_id=None, counted in Sin talento asignado | unit | `python -m pytest tests/test_leads_service.py::test_sin_talento_bucket -x -q` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | SHEET-02 | — | Calificado = "✅ Aprobado - Respuesta enviada" only | unit | `python -m pytest tests/test_leads_service.py::test_calificado_definition -x -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | DASH-04 | — | GET /leads returns 200 with talent/source/status filters | integration | `python -m pytest tests/test_leads_router.py -x -q` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | DASH-04 | — | GET /dashboard/summary includes leads_total and leads_calificados | integration | `python -m pytest tests/test_dashboard_router.py::test_summary_includes_leads -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sheets_integration.py` — stubs for SHEET-01 (gspread connection, row parsing)
- [ ] `tests/test_leads_service.py` — stubs for SHEET-02 (talent attribution, calificado definition, sin-talento bucket, upsert dedup)
- [ ] `tests/test_leads_router.py` — stubs for DASH-04 (GET /leads with filters)
- [ ] `tests/test_dashboard_router.py` — extend existing fixture for leads KPI assertions

*Existing pytest infrastructure covers all other requirements (framework already installed).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Leads tab renders in browser with talent filter | DASH-04 | UI rendering not covered by unit tests | Open /dashboard → Leads tab, verify rows appear, try talent/source/status dropdowns |
| "Leads totales" and "Calificados" KPI tiles show correct counts on Resumen tab | DASH-04 | Requires real sync data in SQLite | Run sync, open /dashboard → Resumen, compare tile values to Sheet row counts |
| Score_Calidad pill colors render correctly (red/amber/green) | DASH-04 | CSS color rendering is visual-only | Inspect lead rows; verify 0–40 = red, 41–70 = amber, 71–100 = green pills |
| Sync button triggers Sheets sync alongside Pipedrive | SHEET-01 | End-to-end async sync UX | Click "Sincronizar ahora", observe loading state, verify leads table refreshes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
