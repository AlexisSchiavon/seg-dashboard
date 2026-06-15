---
phase: 02-pipedrive-integration-core-dashboard
verified: 2026-06-14T21:10:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification: false
human_verification:
  - test: "Open the dashboard at / after logging in. Confirm the Resumen tab shows Pipeline total KPI in orange (accent color), exactly 3 other KPI tiles in amber/purple/green, and the single accent tile is Pipeline total only. Confirm the talent ranking lists talents by revenue, gold/silver/bronze medals on ranks 1-3, and a 'Sin talento asignado' row appears last if any unmapped deals exist. Confirm the sum of all ranking row revenues + Sin talento row equals the Pipeline total KPI."
    expected: "Pipeline total in accent (orange), 3 semantic tiles, ranking sums reconcile with global total, Sin talento row present when unmapped deals exist"
    why_human: "Color accuracy (accent vs amber vs purple vs green), medal rendering, and arithmetic reconciliation across live data require browser verification"
  - test: "Open the Funnel tab. Confirm all 6 stages render in order: Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza. Confirm En ejecución and Cobranza show count=0 (expected until Phase 4 Trello data). Confirm the bottleneck alert shows 'Cuello de botella detectado: solo el X% de los deals en {EtapaA} avanzan a {EtapaB}' OR 'Datos insuficientes para detectar cuellos de botella'. Confirm no 'industria' text appears."
    expected: "All 6 stages in canonical order, last 2 show 0, bottleneck copy matches UI-SPEC exactly, no industria text"
    why_human: "Stage bar rendering, color fills, bottleneck alert variant (warn vs info) require browser inspection"
  - test: "Click the Por talento tab. Confirm a horizontal talent selector renders with talent cards. Click a talent card and confirm the detail sections update. Verify section order is exactly: KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas. Confirm there is NO 'Fuente de leads' section."
    expected: "Talent selector populates, clicking a card loads that talent's detail, D-28 order enforced, Fuente de leads absent"
    why_human: "Tab interaction, selector click behavior, and visual section ordering require browser verification"
  - test: "In the Por talento tab, select a talent with lost deals. Confirm the Oportunidades perdidas section shows a per-reason summary line (e.g. '3 por Presupuesto insuficiente, 2 por No respondieron') and each lost deal row shows a .pill with a SPANISH LABEL (not an integer). Select a talent with no lost deals and confirm 'Sin oportunidades perdidas este periodo' appears."
    expected: "Spanish label pills (never integers), per-reason summary in correct format, empty state copy exact"
    why_human: "Loss reason label vs integer rendering requires browser inspection against live Pipedrive data"
  - test: "In the Por talento tab, confirm the Categorías de marca section renders a donut chart and legend. Each legend row should read '{Categoría} — {pct}% ({count} deals)'. Percentages should be based on DEAL COUNT, not revenue. Select a talent with no categorized deals and confirm 'Sin categorías de marca registradas todavía'."
    expected: "Donut by deal count, legend format matches UI-SPEC, empty state copy exact"
    why_human: "Donut visual rendering and confirming % is by count (not revenue) requires cross-checking numbers against DB"
  - test: "Click 'Sincronizar ahora'. Confirm the button shows 'Sincronizando...', then the 'Última sync: hace X min' indicator updates and a completion toast appears. Confirm clicking a second time while sync is running shows 'Ya hay una sincronización en curso' (or equivalent no-op behavior, 202)."
    expected: "Button label changes, live-pill updates, toast appears on completion, second click is a no-op"
    why_human: "Async UI behavior (button state, toast timing, live-pill update) requires browser interaction"
---

# Phase 02: Pipedrive Integration & Core Dashboard — Verification Report

**Phase Goal:** Pipedrive deal data flows into local SQLite on a schedule (and on-demand), and the dashboard's Resumen, Por talento, and Funnel tabs display real, computed revenue/funnel data per talent.
**Verified:** 2026-06-14T21:10:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Deals sync from Pipedrive into SQLite with stage, value, product→talent, 70% commission, Sin cotizar flag, and custom fields | ✓ VERIFIED | `app/sync/jobs.py` implements `sync_pipedrive(db)` with `COMMISSION_RATE = 0.70`, `is_sin_cotizar = value == 0`, `resolve_custom_field` for loss_reason/brand_category/expected_collection_date. Live verification: 476 deals synced in 4 real stages. |
| 2 | Manual "Sincronizar ahora" (async 202) and hourly scheduler both call sync_pipedrive | ✓ VERIFIED | `app/routers/sync.py` POST /pipedrive returns 202 with background task. `app/sync/scheduler.py` adds hourly job `id="sync_pipedrive"`. `app/main.py` lifespan wires scheduler start/shutdown. |
| 3 | The Resumen tab shows global KPIs, talent ranking (with Sin-talento bucket), and recent activity feed from real Pipedrive data | ✓ VERIFIED | `app/services/kpis.py` `global_kpis()` + `talent_ranking()` with `Deal.talent_id.is_(None)` bucket. `/dashboard/summary` endpoint returns `DashboardSummary`. `frontend/js/dashboard.js` `loadSummary()` calls `apiFetch("/dashboard/summary")`. |
| 4 | The Funnel tab shows all 6 stages (Llamada→Cotización→Negociación→Contrato→En ejecución→Cobranza) with count/amount and bottleneck detection | ✓ VERIFIED | `app/services/funnel.py` `STAGES` constant has all 6 stages; `funnel_overview()` always emits all 6 (zero count for En ejecución/Cobranza until Phase 4). Bottleneck heuristic returns `insufficient_data=True` when < 10 deals. |
| 5 | The Por talento tab shows per-talent KPIs, individual funnel, lost opportunities (with Spanish-label reason pills), and brand category breakdown (% by deal count) | ✓ VERIFIED | `app/services/kpis.py` `talent_detail()` filters `Deal.talent_id == talent_id`; groups by `Deal.loss_reason` (already resolved labels per Pitfall 2); groups by `Deal.brand_category` with `% by count`. `/dashboard/talents/{id}` endpoint returns `TalentDetail`. `frontend/js/dashboard.js` `loadTalentDetail()` renders pills, donut, lost-opps. |
| 6 | Before any successful sync, all tabs show empty state "Aún no hay datos de Pipedrive"; authenticated endpoints return 401 to unauthenticated callers | ✓ VERIFIED | Empty state gated on `Deal count == 0` in both `/dashboard/summary` and `/dashboard/funnel` (`has_data=False`). All three routers use `dependencies=[Depends(get_current_user)]`. 65/65 tests pass including auth tests. |

**Score: 6/6 truths verified**

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | DASH-02 full scope: monthly revenue projection (stacked bars), collection calendar, top 3 campaigns, full campaign table | Phase 4 | ROADMAP Phase 4 SC #4: "Por talento tab now shows monthly revenue projection as stacked bars (cobrado/proyección/pendiente), a collection calendar, top 3 campaigns of the month, and full campaign table" |
| 2 | PIPE-05 "En ejecución" and "Cobranza" stage live data (currently emitting 0 counts) | Phase 4 | ROADMAP Phase 4 SC #1: Trello cards for deals with signed contracts sync in, distinguishing "en ejecución" from "en cobranza" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | Deal, DealStageEvent, SyncLog ORM models | ✓ VERIFIED | `class Deal` with `is_sin_cotizar`, `commission_amount`, `talent_id` nullable, `loss_reason`, `brand_category`, `expected_collection_date`. `class DealStageEvent`. `class SyncLog`. SQLAlchemy 2.0 Mapped/mapped_column style. |
| `app/integrations/pipedrive.py` | Pipedrive v2 client with x-api-token header, cursor pagination, field resolution | ✓ VERIFIED | `headers={"x-api-token": settings.PIPEDRIVE_API_TOKEN}`. `_paginate()` generator with `next_cursor`. `resolve_custom_field()` returns Spanish labels not integer IDs. |
| `app/sync/jobs.py` | sync_pipedrive(db) orchestration with commission/Sin-cotizar/event-diffing/concurrency guard | ✓ VERIFIED | `def sync_pipedrive(db: Session)`. `COMMISSION_RATE = 0.70`. Concurrency guard checks `SyncLog.status == "running"`. Event diffing creates `DealStageEvent` only on stage change for existing deals. |
| `app/routers/sync.py` | POST /sync/pipedrive async trigger + GET sync status | ✓ VERIFIED | 202 ACCEPTED with `background_tasks.add_task`. `already_running` guard returns 202 without scheduling. Auth via `dependencies=[Depends(get_current_user)]`. |
| `app/scripts/match_talent_products.py` | Rapidfuzz talent↔product auto-match + unmapped report | ✓ VERIFIED | `process.extractOne()` with `THRESHOLD=85`. `MANUAL_PRODUCT_MATCHES` dict. `NO_PRODUCT_TALENTS` set. Unmapped product report printed to stdout. |
| `app/services/kpis.py` | global_kpis(db), talent_ranking(db) including Sin-talento bucket, talent_detail(db, talent_id) | ✓ VERIFIED | `def global_kpis`, `def talent_ranking` with `Deal.talent_id.is_(None)` query, `def talent_detail` filtering by `Deal.talent_id == talent_id`. |
| `app/services/funnel.py` | funnel_overview(db) with 6-stage aggregation + bottleneck, recent_activity(db), talent_funnel(db, talent_id) | ✓ VERIFIED | `STAGES` constant with all 6 stages. `def funnel_overview`. `def recent_activity` with limit=20. `def talent_funnel` reusing STAGES (not duplicated). |
| `app/schemas/dashboard.py` | DashboardSummary, FunnelOverview, RankingRow, ActivityItem, BottleneckInfo, TalentDetail, LostOpportunity, LostReasonSummary, BrandCategorySlice | ✓ VERIFIED | All 9 schema classes present. Pydantic v2 BaseModel. |
| `app/routers/dashboard.py` | GET /dashboard/summary + GET /dashboard/funnel + GET /dashboard/talents/{id}, auth-protected | ✓ VERIFIED | All 3 routes present. `response_model=DashboardSummary`, `response_model=FunnelOverview`, `response_model=TalentDetail`. 404 guard on talent endpoint using `db.get(Talent, talent_id)`. |
| `app/sync/scheduler.py` | APScheduler hourly sync job | ✓ VERIFIED | `BackgroundScheduler`. `hours=1, id="sync_pipedrive"`. `start()` / `shutdown()` functions. |
| `frontend/index.html` | Dashboard shell: nav, tabbar (3 tabs), live-pill, Sincronizar ahora, tab containers with stable IDs | ✓ VERIFIED | `.live-pill` with `id="sync-pill"`. `.tabbar` with Resumen/Por talento/Funnel. `id="kpi-grid"`, `id="ranking-list"`, `id="funnel-rows"`, `id="talent-selector"`, `id="talent-kpis"`, `id="brand-donut"`, `id="lost-list"`. D-28 order comment present. |
| `frontend/js/dashboard.js` | setPage, loadSyncStatus, triggerSync, loadSummary, loadFunnel, loadTalentDetail, render functions | ✓ VERIFIED | All functions present. Empty states "Aún no hay datos de Pipedrive", "Sin oportunidades perdidas este periodo", "Sin categorías de marca registradas todavía". |
| `frontend/css/styles.css` | .kpi-val font-weight 500, .card padding 16px, all component classes | ✓ VERIFIED | `.kpi-val { font-weight: 500; }` with comment "UI-SPEC: 600 -> 500". `.card { padding: 16px }`. `.kpi-grid`, `.funnel-row`, `.activity-row`, `.alert`, `.talent-selector`, `.deal-row`, `.pill`, `.donut-wrap`, `.donut-legend` all present. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `frontend/js/dashboard.js` | `/sync/pipedrive` | `apiFetch("/sync/pipedrive", { method: "POST" })` on Sincronizar ahora click | ✓ WIRED | Line 215: `const res = await apiFetch("/sync/pipedrive", { method: "POST" })` |
| `app/sync/jobs.py` | `talent_products.pipedrive_product_id` | Product→talent resolution at sync write | ✓ WIRED | `talent_id_by_product_id = { tp.pipedrive_product_id: tp.talent_id ... }` drives `talent_id` on every deal row |
| `app/main.py` | `app/sync/scheduler.py` | `lifespan` starts BackgroundScheduler | ✓ WIRED | `lifespan` asynccontextmanager calls `sync_scheduler.start()` / `sync_scheduler.shutdown()`. Static mount is the last registration. |
| `frontend/js/dashboard.js` | `/dashboard/summary` | `apiFetch GET` on Resumen tab activation | ✓ WIRED | `loadSummary()` called on DOMContentLoaded and on Resumen tab activation |
| `frontend/js/dashboard.js` | `/dashboard/funnel` | `apiFetch GET` on Funnel tab activation | ✓ WIRED | `loadFunnel()` called on Funnel tab activation |
| `app/services/kpis.py` | `Deal.talent_id IS NULL` | Sin-talento bucket query | ✓ WIRED | `Deal.talent_id.is_(None)` at line 129 — separate query appends "Sin talento asignado" row last |
| `app/routers/dashboard.py` | `app/services/funnel.py` | `funnel_overview` / `recent_activity` delegation | ✓ WIRED | `funnel_data = funnel_service.funnel_overview(db)` at line 98; `activity_data = funnel_service.recent_activity(db)` at line 63 |
| `frontend/js/dashboard.js` | `/dashboard/talents/` | `apiFetch GET` on talent-card selection | ✓ WIRED | `loadTalentDetail(talentId)` calls `apiFetch("/dashboard/talents/" + talentId)` at line 755 |
| `app/services/kpis.py` | `Deal.loss_reason` | Lost-opportunity grouping by resolved label | ✓ WIRED | `deal.loss_reason or "Sin razón"` used to group lost deals; label stored at sync time (Plan 02-01 Pitfall 2 mitigation) |
| `app/services/kpis.py` | `Deal.brand_category` | Brand-category donut grouped by deal count | ✓ WIRED | `db.query(Deal.brand_category, func.count(Deal.id)).filter(Deal.talent_id == talent_id, Deal.brand_category.isnot(None)).group_by(Deal.brand_category)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `frontend/js/dashboard.js` renderKpis | `data.kpis` | GET /dashboard/summary → `kpi_service.global_kpis(db)` → `db.query(func.sum(Deal.value))` | Yes — SQLite query over Deal table populated by sync | ✓ FLOWING |
| `frontend/js/dashboard.js` renderFunnel | `data.stages` | GET /dashboard/funnel → `funnel_service.funnel_overview(db)` → `db.query(Deal.stage_name, func.count(Deal.id))` | Yes — SQLite query over Deal table | ✓ FLOWING |
| `frontend/js/dashboard.js` loadTalentDetail | `data.kpis`, `data.funnel`, `data.lost_opportunities`, `data.brand_categories` | GET /dashboard/talents/{id} → `kpi_service.talent_detail(db, talent_id)` → multiple `db.query(Deal...)` | Yes — all queries filter `Deal.talent_id == talent_id` from SQLite | ✓ FLOWING |
| `frontend/js/dashboard.js` renderLostOpportunities | `data.lost_summary`, `data.lost_opportunities` | `Deal.loss_reason` — stored as Spanish label by `resolve_custom_field()` at sync time | Yes — no re-resolution at read time; labels stored by Plan 02-01 | ✓ FLOWING |
| `frontend/js/dashboard.js` renderBrandDonut | `data.brand_categories` | `db.query(Deal.brand_category, func.count(Deal.id))` — % by count (D-27) | Yes — count-based, not revenue-based | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase 02 tests pass | `uv run pytest tests/test_pipedrive_integration.py tests/test_sync.py tests/test_kpis.py tests/test_funnel.py tests/test_dashboard.py -q` | 48 passed in 1.42s | ✓ PASS |
| Full test suite (no regressions) | `uv run pytest -q` | 65 passed in 2.29s | ✓ PASS |
| App imports cleanly with scheduler lifespan | `uv run python -c "from app.main import app; print('app boots ok')"` | app boots ok | ✓ PASS |
| Models importable | `uv run python -c "from app.models import Deal, DealStageEvent, SyncLog; print('models ok')"` | models ok | ✓ PASS |
| Alembic at head | `uv run alembic current` | c35f623eaa21 (head) | ✓ PASS |
| No debt markers (TBD/FIXME/XXX) in any modified file | `grep -rn "TBD\|FIXME\|XXX" <all modified files>` | No output | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — no `scripts/*/tests/probe-*.sh` probes declared or present for this phase. Phase verification relies on the pytest suite above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PIPE-01 | 02-01 | System syncs Pipedrive deals (stages, value, products, custom fields) into local SQLite on a schedule + manual sync now | ✓ SATISFIED | `sync_pipedrive(db)` in jobs.py; hourly scheduler; POST /sync/pipedrive (202); 476 deals synced live |
| PIPE-02 | 02-01 | System maps deal product → talent and computes 70% fixed commission per deal | ✓ SATISFIED | `talent_id_by_product_id` lookup in jobs.py; `commission_amount = value * COMMISSION_RATE` where `COMMISSION_RATE = 0.70`; unmatched → `talent_id=NULL` (D-17, not dropped) |
| PIPE-03 | 02-01 | System classifies deals with $0 MXN as "Sin cotizar" | ✓ SATISFIED | `is_sin_cotizar = value == 0` in jobs.py; `Deal.is_sin_cotizar` column confirmed in models.py |
| PIPE-04 | 02-01 | System captures custom fields: razón de pérdida, categoría de marca, fecha de cobro esperada | ✓ SATISFIED | `resolve_custom_field()` in pipedrive.py resolves integer option IDs to Spanish labels; stored in `loss_reason`, `brand_category`, `expected_collection_date` on Deal rows |
| PIPE-05 | 02-01/02-02 | System tracks the 6 funnel stages per deal | ✓ SATISFIED (partial scope noted) | `STAGES` constant in funnel.py has all 6 stages in canonical order; `funnel_overview()` always emits all 6 (En ejecución/Cobranza show 0 until Phase 4 Trello data) — this is documented intentional behavior in jobs.py and funnel.py |
| DASH-01 | 02-02 | Resumen ejecutivo — global KPIs, talent ranking by revenue, recent activity feed | ✓ SATISFIED | `/dashboard/summary` returns 4 KPI tiles + ranking with Sin-talento bucket + activity feed from DealStageEvent |
| DASH-02 | 02-03 | Por talento — (Phase 2 portion) KPIs, individual funnel, lost opportunities, brand category breakdown | ✓ SATISFIED (Phase 2 scope only) | `/dashboard/talents/{id}` returns TalentDetail with per-talent KPIs, 6-stage funnel, lost_summary, lost_opportunities, brand_categories. Revenue projection/collection calendar/campaign table deferred to Phase 4 per ROADMAP SC #6. REQUIREMENTS.md correctly leaves DASH-02 unchecked. |
| DASH-03 | 02-02 | Funnel completo — 6 stages with deal count and amount, bottleneck detection | ✓ SATISFIED | `/dashboard/funnel` returns `FunnelOverview` with all 6 `StageBucket` entries + bottleneck (or `insufficient_data=True` when < 10 deals) |

**ORPHANED REQUIREMENTS CHECK:** REQUIREMENTS.md maps all 8 required IDs (PIPE-01..05, DASH-01, DASH-02, DASH-03) to Phase 2. All are claimed by at least one of plans 02-01, 02-02, or 02-03. No orphans.

Note on DASH-02 partial delivery: REQUIREMENTS.md maps DASH-02 to Phase 4 in the traceability table and leaves it unchecked. The Phase 2 ROADMAP explicitly defers the revenue projection/collection calendar/campaign table portions to Phase 4. The Phase 2 ROADMAP Success Criteria #6 correctly narrows the Phase 2 scope of DASH-02. This is not a gap — it is the designed split-delivery across Phases 2 and 4.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/css/styles.css` | 92, 160, 355, 374, 399, 482, 689 | `font-weight: 600` on various elements | ℹ️ Info | These are NOT on `.kpi-val` — they are on other elements (nav, tab, rank-num, f-n, etc.) where 600 weight is appropriate. `.kpi-val` correctly uses 500. No violation. |

No blockers. No TBD/FIXME/XXX markers in any modified file. No stub implementations. Empty state strings are defined in render functions, not in static HTML placeholders.

### Human Verification Required

6 items require human testing in a running browser session. These correspond to blocking `checkpoint:human-verify` tasks from all three plans that cannot be automated:

---

**1. Resumen Tab — KPI Colors, Tile Layout, and Ranking Arithmetic**

**Test:** Open the dashboard at `/` after logging in. Confirm the Resumen tab shows Pipeline total KPI in orange (accent color), exactly 3 other KPI tiles in amber/purple/green, and the single accent tile is Pipeline total only. Cross-check: the sum of all talent ranking revenue values + the "Sin talento asignado" row revenue should equal the Pipeline total KPI (Pitfall 4 / DASH-01).

**Expected:** Pipeline total in accent (orange), 3 semantic tiles, ranking revenues reconcile with global total, Sin talento row appears last when unmapped-product deals exist.

**Why human:** Color accuracy, medal rendering (gold/silver/bronze), and arithmetic reconciliation across live data require a browser with 476 real synced deals.

---

**2. Funnel Tab — Stage Order, Bottleneck Copy, No "Industria"**

**Test:** Open the Funnel tab. Confirm all 6 stages render in order: Llamada → Cotización → Negociación → Contrato → En ejecución → Cobranza. En ejecución and Cobranza should show count=0. Confirm the bottleneck alert reads "Cuello de botella detectado: solo el X% de los deals en {EtapaA} avanzan a {EtapaB}." (amber) or "Datos insuficientes para detectar cuellos de botella" (blue info). No "industria" text should appear.

**Expected:** 6 stages in canonical order, last 2 at 0, correct bottleneck copy, no "industria" word anywhere.

**Why human:** Bar fill widths, alert variant (warn vs info), and visually confirming stage ordering require browser inspection.

---

**3. Por Talento Tab — Talent Selector and D-28 Section Order**

**Test:** Click the Por talento tab. Confirm a horizontal talent selector renders. Click a talent card and confirm the detail sections appear. Verify section order is exactly: KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas. Confirm there is NO "Fuente de leads" section anywhere.

**Expected:** Talent selector populates, clicking loads that talent's data, D-28 order enforced, Fuente de leads absent.

**Why human:** Interactive selector behavior and visual section ordering require browser interaction.

---

**4. Por Talento Tab — Lost Opportunities Label Pills**

**Test:** Select a talent with lost deals. Confirm the Oportunidades perdidas section shows a per-reason summary line (e.g. "3 por Presupuesto insuficiente, 2 por No respondieron") above a list of lost deals. Each lost deal row must show a colored `.pill` with a SPANISH LABEL (e.g. "Presupuesto insuficiente"), never a raw integer. Select a talent with no lost deals and confirm "Sin oportunidades perdidas este periodo" appears.

**Expected:** Spanish label pills, "{N} por {razón}" summary format, empty state copy exact match.

**Why human:** Confirming labels are Spanish (not integers) in live data requires inspection with actual Pipedrive-sourced loss reason values.

---

**5. Por Talento Tab — Brand Category Donut (% by Deal Count)**

**Test:** In the Por talento tab, select a talent with categorized deals. Confirm the Categorías de marca section renders a donut chart and legend. Each legend row should read "{Categoría} — {pct}% ({count} deals)". The percentages must be based on DEAL COUNT, not revenue. Select a talent with no categorized deals and confirm "Sin categorías de marca registradas todavía" appears.

**Expected:** Donut rendered, legend format matches UI-SPEC, percentages are by count (cross-verify 2-3 categories sum to ~100%), empty state copy exact.

**Why human:** Donut visual rendering and verifying % basis (count vs revenue) requires cross-checking rendered numbers against known DB values.

---

**6. Sync Button UI Behavior**

**Test:** Click "Sincronizar ahora". Confirm the button label changes to "Sincronizando...", then the "Última sync: hace X min" indicator updates and a completion toast appears. While a sync is in progress, click again — the response should be "Ya hay una sincronización en curso" toast (no second sync started).

**Expected:** Button state transitions, live-pill text updates, toast on completion, concurrency no-op on double-click.

**Why human:** Async UI timing and state transitions (button disable/enable, toast display, live-pill animation) require real browser interaction.

---

### Gaps Summary

No automated gaps. All 6 observable truths are VERIFIED by codebase inspection + passing tests (65/65). All 13 required artifacts exist, are substantive, and are wired. All 10 key links are confirmed. No debt markers. No stubs.

The `status: human_needed` is because all three plans included `checkpoint:human-verify` tasks (blocking gates) that cannot be resolved programmatically. The 6 human verification items above map directly to those blocking checkpoints across plans 02-01, 02-02, and 02-03.

**PIPE-05 note:** The SUMMARY correctly documents that only 4 real Pipedrive stages exist (IDs 6=Llamada, 7=Cotización, 8=Negociación, 9=Contrato y factura). "En ejecución" and "Cobranza" emit 0 counts until Phase 4 provides Trello data. This is intentional design, not a stub — the STAGES constant is canonical and the zero-count behavior is tested (`test_stages_with_zero_count`).

---

_Verified: 2026-06-14T21:10:00Z_
_Verifier: Claude (gsd-verifier)_
