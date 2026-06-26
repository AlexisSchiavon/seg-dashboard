# Fase 6 — Trello al funnel · Resumen de cambios

**Branch**: `fase-6-trello-al-funnel` · **Fecha**: 26-jun-2026
**Estado**: completo y validado en local — NO mergeado a `main` (pendiente revisión conjunta).
**Tests**: 170 passed, 0 failed. **Migraciones**: ninguna (solo lectura sobre tablas existentes).
**APIs externas**: ninguna tocada — solo queries sobre SQLite local.

Backup previo: `seg.db.backup-pre-fase-6`.

## Commits (uno por sub-objetivo)

| Commit | Sub-obj | Cambio |
|--------|---------|--------|
| `221afd6` | 6.1 | Conectar TrelloCard al funnel: `funnel_overview()` y `talent_funnel()` muestran "En ejecución" y "Cobranza" con count + amount reales |
| `4d05907` | 6.2 | Toast "X deals actualizados" usa `/sync/status?source=pipedrive` (deals, no cards de Trello) |
| 6.3 | — | Regresión verificada (sin cambio de código necesario) |

## Decisiones aplicadas (D1-D5 + P1-P3)

- **D1**: amount de etapas Trello = `SUM(COALESCE(Deal.value, 0))` vía `TrelloCard.deal_id`.
- **D2**: cards huérfanas (sin `deal_id`) cuentan en `count`, aportan 0 al `amount` (LEFT JOIN global).
- **D3**: bottleneck recalculado con las 6 etapas; mezcla intencional documentada (Pipedrive = counts all-status de Deal; Trello = counts de cards).
- **D4**: per-talento filtra por `Deal.talent_id` (INNER JOIN); huérfanas y deals sin talento excluidos de la vista por talento.
- **D5**: cards `cerrado` NO entran al funnel.
- **P1**: `/sync/status` default sigue cross-source (pill/banner conservan visibilidad de errores Trello/Sheets); solo el toast usa `?source=pipedrive`.
- **P2**: mezcla semántica del bottleneck mantenida + comentario explicativo en código.
- **P3**: query duplicada de funnel en `reports.py` → fuera de scope, documentada en `HALLAZGOS.md` (H-04, diferida a Fase 9).

## Validación con datos reales (local, 26-jun)

**Funnel global** (antes: En ejecución 0 / Cobranza 0):
| Etapa | count | amount |
|-------|------:|-------:|
| En ejecución | 100 | $9,278,696 |
| Cobranza | 59 | $2,112,500 |

- Bottleneck recalculado: **"En ejecución → Cobranza 37.1%"** (antes el engañoso "Contrato → En ejecución 0%").
- `cerrado` (31 cards) correctamente excluido del funnel.

**Funnel por talento** (ej. Mariana Sanchez): En ejecución 14/$916,460, Cobranza 3/$250,000. `talent_detail` (usado por "Por Talento" y el agente) incluye las etapas Trello.

## Riesgos mitigados

- **Performance**: 1 query agregada extra por función; `TrelloCard.deal_id` indexado; sin N+1.
- **Bottleneck con etapa Trello en 0**: cubierto por la guarda `if denom == 0: continue` + test explícito.
- **Tests que asumían "En ejecución"=0**: no siembran TrelloCards → siguen pasando. Se agregaron 4 tests nuevos que sí siembran cards.

## 6.3 — Regresión verificada (sin cambio de código)

- Badge "vía Trello" sigue visible: keyea por nombre de etapa (`TRELLO_STAGES.includes(stage.stage)` en `dashboard.js:421/634`), independiente de count/amount.
- `renderFunnel` escala las barras por `count` (no por `amount`), así que `amount=0` con `count>0` renderiza sin división por cero.
- 6 etapas siguen renderizando; `StageBucket` valida `{stage, count, amount}` sin cambios.

## Para validación visual en local (antes de mergear)

`DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`

1. Resumen → Funnel: "En ejecución" ~100 con amount ~$9.3M; "Cobranza" ~59 con ~$2.1M.
2. Badge "vía Trello" sigue en esas dos etapas.
3. Alerta de cuello de botella ahora tiene sentido (En ejecución → Cobranza), no "Contrato → En ejecución 0%".
4. Por Talento (ej. Mariana Sanchez): funnel muestra etapas Trello con datos.
5. Sincronizar ahora → el toast muestra el conteo de **deals** de Pipedrive (no ~190 cards).
6. Sin errores en consola del navegador.
