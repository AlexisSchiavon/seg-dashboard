# Phase 3: Google Sheets Leads Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 03-google-sheets-leads-integration
**Areas discussed:** Sheet structure, Talent attribution, Status & source taxonomy, Resumen tab leads KPIs

---

## Sheet Structure

### Q1 — Does the Sheet already exist?

| Option | Description | Selected |
|--------|-------------|----------|
| Already exists with real data | Sheet is live; Gmail is already feeding leads. Read real column names and map to them. | ✓ |
| Needs to be created | Define schema now; Sheet set up as part of Phase 3. | |

**User's choice:** Already exists with real data

---

### Q2 — Column names in the Sheet

| Option | Description | Selected |
|--------|-------------|----------|
| I'll type them | Free-form column list | ✓ |
| Standard: Fecha / De / Asunto / Talento / Fuente / Estado | Common Gmail-fed layout | |
| I don't know — researcher checks | Researcher calls Sheets API | |

**User's choice:** Provided verbatim: `ID_Lead, Email_Completo, Remitente_Email, Remitente_Nombre, Asunto, Fecha_Recepcion, Talento_Mencionado, Status_Filtrado, Categoria_Detectada, Razon_validacion, Score_Calidad, Bloqueado, Respuesta_Enviada, Fecha_Respuesta, Link_WhatsApp_Generado, Convertido_a_Prospecto, ID_Prospecto, Threadid`

---

### Q3 — Which columns to sync?

| Option | Description | Selected |
|--------|-------------|----------|
| Core set — sync only what the UI needs | 10 columns: ID_Lead, Remitente_Nombre, Remitente_Email, Asunto, Fecha_Recepcion, Talento_Mencionado, Status_Filtrado, Score_Calidad, Bloqueado, Convertido_a_Prospecto | ✓ |
| Full set — sync all 18 columns | Future-proof but noisy | |
| You decide — researcher/planner picks minimum | Leave to downstream agents | |

**User's choice:** Core set (recommended)

---

## Talent Attribution

### Q1 — How does Talento_Mencionado map to talent names in the DB?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact or near-exact match — same as Pipedrive D-16 | Name-based auto-match; mismatches → "Sin talento asignado" | ✓ |
| Different naming — Sheet uses aliases | Separate alias/mapping table needed | |
| I'll describe the naming convention | Free-form description | |

**User's choice:** Same name-matching strategy as Pipedrive (D-16)

---

### Q2 — What happens when Talento_Mencionado is empty or unmatched?

| Option | Description | Selected |
|--------|-------------|----------|
| Group under 'Sin talento asignado' — same as D-17 | Consistent with Phase 2; lead synced but not attributed | ✓ |
| Skip the row entirely | Simpler but loses visibility | |
| You decide | Leave to planner | |

**User's choice:** Sin talento asignado bucket (consistent with D-17)

---

## Status & Source Taxonomy

### Q1 — Actual values in Status_Filtrado

| Option | Description | Selected |
|--------|-------------|----------|
| I'll type them | Free-form list | |
| Calificado / No calificado / Spam / Pendiente | Common 4-value taxonomy | |
| I don't know — researcher inspects the Sheet | Researcher reads distinct values before planning | ✓ |

**User's choice:** Researcher determines from live Sheet

---

### Q2 — Should 'fuente' (source) be tracked explicitly?

| Option | Description | Selected |
|--------|-------------|----------|
| Source is always Gmail — no separate dimension | Simpler; add field later if needed | |
| Track source explicitly even if always Gmail | Extensible for Phase 4 prospecting leads | ✓ |
| Categoria_Detectada IS the source | Use that column as fuente | |

**User's choice:** Track explicitly — defaults to "Gmail", extensible later

---

### Q3 — Score_Calidad display in the UI

| Option | Description | Selected |
|--------|-------------|----------|
| Colored pill/badge in lead list | 0–40 red / 41–70 amber / 71–100 green | ✓ |
| Show in detail only — not in list | Cleaner list but score less discoverable | |
| Sync but don't display in Phase 3 | Store and surface later | |

**User's choice:** Colored pill in lead list (recommended)

---

## Resumen Tab Leads KPIs

### Q1 — Wire up Leads totales / Calificados on Resumen tab in Phase 3?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — wire them up in Phase 3 | Data is available; tiles already exist as placeholders | ✓ |
| No — leave as placeholders until Phase 4 | Keeps Phase 3 focused on Leads tab only | |

**User's choice:** Yes — wire up in Phase 3

---

### Q2 — What counts as a "Calificado" lead?

| Option | Description | Selected |
|--------|-------------|----------|
| Researcher determines from real Status_Filtrado values | Enumerate distinct values then identify qualifying status | ✓ |
| Score_Calidad >= 70 | Score-based qualification independent of status | |
| I'll define the qualifying status | Free-form input | |

**User's choice:** Researcher determines from live Sheet data

---

## Claude's Discretion

- **"Leads por talento" bar section** — sorting (by total vs. by qualified), pagination (show all vs. top N) left to planner per mockup reference.
- **`Bloqueado` and `Convertido_a_Prospecto` UI treatment** — synced but not yet explicitly surfaced. Planner decides if a pill/greyed-out state is appropriate.
- **Filtering implementation** — dropdown vs. chip-based, URL param state — follow existing Vanilla JS patterns in `dashboard.js`.

## Deferred Ideas

- `Categoria_Detectada` — potential brand-category column, skip for now, revisit in Phase 4/5.
- `ID_Prospecto` — Sheets↔Pipedrive lead-to-deal join; cross-source conversion tracking future phase.
- `Link_WhatsApp_Generado` — external outreach flow, not relevant to read-only dashboard.
- `Bloqueado` / `Respuesta_Enviada` filter facets — defer until real usage patterns emerge.
