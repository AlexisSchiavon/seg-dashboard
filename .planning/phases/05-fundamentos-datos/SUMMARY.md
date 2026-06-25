# Fase 5 — Fundamentos de datos · Resumen de cambios

**Branch**: `fase-5-fundamentos-datos` · **Fecha**: 25-jun-2026
**Estado**: completo y validado en local — NO mergeado a `main` (pendiente revisión conjunta).
**Tests**: 165 passed, 0 failed. **Migraciones**: head = `c3e4a5b6d7f8` (3 nuevas, reversibles).

Backup previo: `seg.db.backup-pre-fase-5`.

## Commits (uno por sub-objetivo)

| Commit | Sub-obj | Cambio |
|--------|---------|--------|
| `2d22d44` | 5.3 | `won_time` (DateTime tz-aware, indexado) en `Deal` + parser UTC en sync + migración `a1c2e3f4b5d6` |
| `d1d62c2` | 5.1 | `flujo_dinero_kpis` "Campañas firmadas" → `status='won'` (no etapa Contrato) |
| `1461ea9` | 5.2 | Fusión Don Silverio + Don Wicho en un talento + migración de datos `b2d3f4a5c6e7` |
| `85b6a4b` | 5.5.1 | Login case-insensitive + normalización en escritura + migración `c3e4a5b6d7f8` |
| `9fd18fe` | 5.5.2 | `SyncStatus` serializa timestamps con offset UTC (arregla "hace 0 min") |
| `75ce9d5` | 5.4 | Tool `deals_won_in_period` + definiciones de negocio en el prompt del agente |

## Decisiones aprobadas (D1–D6)

- **D1**: "firmado" = "ganado" = `status='won'` exclusivamente. "Pendiente por cobrar" = won − cobrado (verificado coherente).
- **D2**: Opción A — migración remapea deals/leads/deal_stage_events/talent_products al talento fusionado y borra los viejos. Downgrade imperfecto pero reversible estructuralmente.
- **D3**: nueva tool read-only `deals_won_in_period(start, end, talent_id=None)`.
- **D4**: re-sync full local ejecutado (read-only sobre Pipedrive).
- **D5**: normalización en login + escritura + migración (sin colisiones de case en `users`).
- **D6**: `won_time` como `DateTime(timezone=True)`.

## Hallazgos de discovery (vs. supuestos del brief)

- **5.1 era más chico**: `global_kpis`, `talent_detail`, reports y Top 3 ya usaban `status='won'`. El único ofensor real era `flujo_dinero_kpis` (construido en Fase 8 el día anterior).
- **5.4 era más grande**: el agente no tenía herramienta de filtro por fecha; cambiar solo el prompt no bastaba (de ahí D3).
- **5.2 causa raíz**: ambos talentos compartían el mismo `pipedrive_product_id`, colapsando el dict `talent_id_by_product_id` → todos los deals (77) en un talento, los leads (59) en el otro.
- **5.5.2 causa raíz**: `finished_at` se guarda UTC pero SQLite lo devuelve naive; sin offset, el JS lo interpretaba como hora local → futuro → `max(0, delta)=0`.

## Validación con datos reales (post re-sync, 484 deals)

- 5.3: 112 deals `won`, los 112 con `won_time` no nulo (0 NULL).
- 5.2: talento fusionado id=2 con 77 deals, sin huérfanos.
- 5.4: 26 deals firmados en junio 2026 ($4.72M) — consultable por el agente.
- 5.5.2: `finished_at` real serializa como `...+00:00`.

## Notas / pendientes (no bloqueantes)

- En producción, los dos usuarios (`admin@santillanent.com`, `santillan@talentagency.mx`) tienen `is_admin=0`. No se modificó data de prod; si se requiere crear usuarios desde la UI, habrá que promover un admin (correr `seed_admin` o un UPDATE puntual). Fuera de alcance de Fase 5.
- El re-sync se forzó nullificando `finished_at` de los SyncLog `success`. El gate de full-sync es source-agnóstico — comportamiento conocido, no modificado en esta fase.

## Para validación visual en local (antes de mergear)

`DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`

1. Por Talento → "Flujo de dinero": "Campañas firmadas" debe contar solo ganados.
2. Resumen → ranking: "Don Silverio y Don Wicho" como una sola fila.
3. Header: "Última sync: hace N min" con N real (no 0).
4. Login con email en MAYÚSCULAS funciona.
5. Agente: "¿cuántos deals se firmaron en junio 2026?" → ~26 deals.
