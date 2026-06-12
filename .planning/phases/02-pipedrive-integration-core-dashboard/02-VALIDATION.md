---
phase: 02
slug: pipedrive-integration-core-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + httpx-based `TestClient` (FastAPI) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_pipedrive_integration.py tests/test_sync.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~2-5 seconds (mocked `httpx` for Pipedrive, SQLite local DB, no live network calls) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<module>.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

> Task ID / Plan / Wave are TBD — to be assigned by the planner. This table maps each phase
> requirement to its required test per RESEARCH.md's "Phase Requirements → Test Map".

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | PIPE-01 | V4 | Sync paginates and upserts deals from Pipedrive v2; "Sincronizar ahora" endpoint is authenticated, returns immediately (async), and is a no-op if a sync is already running | unit + integration | `uv run pytest tests/test_sync.py -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | PIPE-02 | — | Deal's Pipedrive product resolves to a talent via `talent_products.pipedrive_product_id`; 70% commission computed and stored at sync time | unit | `uv run pytest tests/test_kpis.py::test_commission_calculation -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | PIPE-03 | — | Deals with value `$0 MXN` are classified `is_sin_cotizar=True` | unit | `uv run pytest tests/test_sync.py::test_zero_value_deal_sin_cotizar -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | PIPE-04 | V6 | Custom fields (razón de pérdida, categoría de marca, fecha de cobro esperada) resolved via `/dealFields` hash→name and option id→label maps; token never logged | unit | `uv run pytest tests/test_pipedrive_integration.py::test_resolve_custom_fields -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | PIPE-05 | — | Pipedrive deal stages mapped to the 6 known funnel stages (Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza), in order | unit | `uv run pytest tests/test_funnel.py::test_stage_mapping -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | DASH-01 | V4/V5 | `GET /dashboard/summary` (auth required) returns global KPIs, talent ranking, and activity feed (from `DealStageEvent`) with validated response shapes, sourced from real synced data | integration | `uv run pytest tests/test_dashboard.py::test_summary_endpoint -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | DASH-02 | V4/V5 | Per-talent endpoint (auth required) returns KPIs, individual funnel, lost opportunities grouped by razón de pérdida, and brand category donut (% by deal count) | integration | `uv run pytest tests/test_dashboard.py::test_talent_detail_endpoint -x` | ❌ Wave 0 | ⬜ pending |
| TBD | TBD | TBD | DASH-03 | — | Funnel tab aggregates all 6 stages (count + amount) and flags a bottleneck stage via stage-to-stage conversion ratio from current snapshot | unit | `uv run pytest tests/test_funnel.py::test_bottleneck_detection -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipedrive_integration.py` — `PipedriveClient` against API v2 (`x-api-token` header, Pitfall 1), `dealFields` hash→name and option id→label resolution (Pitfall 2, PIPE-04); mock `httpx` with recorded v2-shaped JSON
- [ ] `tests/test_sync.py` — sync paginate/upsert (PIPE-01), commission + Sin cotizar at write time (PIPE-02/PIPE-03), first-sync produces no spurious `DealStageEvent` rows (Pitfall 3), "Sin talento asignado" bucket counted in global totals (Pitfall 4), concurrent-sync guard (Pitfall 5)
- [ ] `tests/test_kpis.py` — 70% commission math, global vs per-talent aggregation (Pitfall 4)
- [ ] `tests/test_funnel.py` — 6-stage mapping (PIPE-05), bottleneck heuristic (DASH-03), activity feed query (DASH-01)
- [ ] `tests/test_dashboard.py` — `/dashboard/summary` and per-talent endpoint contracts (DASH-01/DASH-02), lost-opportunities summary by reason + brand-category donut by deal count (D-25/D-26/D-27)
- [ ] `tests/conftest.py` additions — seeded `Talent`/`TalentProduct`/`Deal`/`DealStageEvent` fixtures; `httpx.MockTransport` fixture for `PipedriveClient`
- [ ] Framework install: `uv add apscheduler rapidfuzz`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "Última sync: hace X min" indicator visible in top nav across all tabs (D-21) | DASH-01 | Cross-tab UI placement not asserted by integration tests | Run dev server, navigate between Resumen/Funnel/Por talento, confirm indicator is present and updates after a sync |
| "Sincronizar ahora" shows "Sincronizando..." state, stays navigable, and shows completion toast (D-22/D-23) | PIPE-01 | Async UX/toast behavior requires browser interaction | Click "Sincronizar ahora" on Resumen, confirm button text changes, navigate to another tab during sync, confirm toast on completion |
| Sync-failure banner shows "No se pudo sincronizar — mostrando datos de hace X horas" while keeping last data visible (D-24) | PIPE-01 | Requires simulating a Pipedrive failure and observing UI fallback | Temporarily break `PIPEDRIVE_API_TOKEN`, trigger sync, confirm banner text and that previously synced data still renders |
| Brand category donut + legend render using `.donut-wrap`/`.donut-legend` styles (D-26/D-27) | DASH-02 | Visual chart rendering not asserted by integration tests | Open Por talento for a talent with categorized deals, compare donut + legend against `.planning/reference/mockup.html` |
| Por talento section order: KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas (D-28) | DASH-02 | Visual layout order not asserted by integration tests | Open Por talento tab, confirm section order and that "Fuente de leads" no longer appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
