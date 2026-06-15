---
phase: 4
slug: trello-integration-collection-automation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed active, 111 tests collected) |
| **Config file** | none — discovery via `pytest.ini` / `pyproject.toml` defaults |
| **Quick run command** | `python3 -m pytest tests/test_trello.py -x -q` |
| **Full suite command** | `python3 -m pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_trello.py -x -q`
- **After every plan wave:** Run `python3 -m pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Req | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-----|----------|-----------|-------------------|-------------|--------|
| 04-trello-model | TRELLO-01 | `TrelloCard` model + Alembic migration | integration | `python3 -m pytest tests/test_trello.py::test_sync_trello_upserts_cards -x` | ❌ Wave 0 | ⬜ pending |
| 04-sync-upsert | TRELLO-01 | `sync_trello()` upserts cards from 6 lists | unit | `python3 -m pytest tests/test_trello.py::test_sync_trello_upserts_cards -x` | ❌ Wave 0 | ⬜ pending |
| 04-list-filter | TRELLO-01 | Cards in "Otros pendientes" NOT synced | unit | `python3 -m pytest tests/test_trello.py::test_sync_trello_ignores_otros_pendientes -x` | ❌ Wave 0 | ⬜ pending |
| 04-list-state | TRELLO-01 | `list_state` correctly assigned from list ID | unit | `python3 -m pytest tests/test_trello.py::test_list_state_mapping -x` | ❌ Wave 0 | ⬜ pending |
| 04-collection-date-due | TRELLO-02 | `collection_date` from Trello due date | unit | `python3 -m pytest tests/test_trello.py::test_collection_date_from_due -x` | ❌ Wave 0 | ⬜ pending |
| 04-collection-date-fallback | TRELLO-02 | Fallback to `add_time + 2 months` | unit | `python3 -m pytest tests/test_trello.py::test_collection_date_fallback -x` | ❌ Wave 0 | ⬜ pending |
| 04-auto-create | TRELLO-03 | Won deals with no card get card created | unit | `python3 -m pytest tests/test_trello.py::test_auto_create_card_for_won_deal -x` | ❌ Wave 0 | ⬜ pending |
| 04-no-dup | TRELLO-03 | Won deals with existing card NOT duplicated | unit | `python3 -m pytest tests/test_trello.py::test_no_duplicate_card_creation -x` | ❌ Wave 0 | ⬜ pending |
| 04-desc-header | TRELLO-03 | `[seg:deal_id=N]` written on card creation | unit | `python3 -m pytest tests/test_trello.py::test_card_desc_contains_deal_id -x` | ❌ Wave 0 | ⬜ pending |
| 04-projection-math | DASH-02 | `income_projection` returns cobrado/proyeccion/pendiente | unit | `python3 -m pytest tests/test_trello.py::test_income_projection_math -x` | ❌ Wave 0 | ⬜ pending |
| 04-endpoint-field | DASH-02 | `/dashboard/talents/{id}` includes `income_projection` | integration | `python3 -m pytest tests/test_dashboard.py::test_talent_detail_includes_income_projection -x` | ❌ Wave 0 | ⬜ pending |
| 04-concurrency | DASH-02 | Concurrency guard uses `source="trello"` filter | unit | `python3 -m pytest tests/test_trello.py::test_sync_trello_concurrency_guard -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_trello.py` — stubs for TRELLO-01, TRELLO-02, TRELLO-03, DASH-02 (all 12 test functions above)
- [ ] `TrelloCard` model and Alembic migration must exist before integration tests can run

*The existing `tests/test_dashboard.py` infrastructure covers the integration test; Wave 0 adds `test_talent_detail_includes_income_projection`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Trello card visible in board UI after auto-creation | TRELLO-03 | Live external write to Trello API | Log into Trello, mark a test deal as "ganado" in Pipedrive, run sync job, verify card appears in "En ejecución" list with `[seg:deal_id=N]` in description |
| Por talento revenue projection bars render correctly | DASH-02 | Frontend visual rendering | Open dashboard → Por talento tab → select a talent with Trello data → verify stacked bar chart shows cobrado/proyeccion/pendiente segments |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
