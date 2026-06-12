# Phase 2: Pipedrive Integration & Core Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 2-pipedrive-integration-core-dashboard
**Areas discussed:** Mapeo talento↔producto Pipedrive, Frecuencia de sync y botón 'sync now', Oportunidades perdidas y categorías de marca

---

## Mapeo talento↔producto Pipedrive

### ¿Cómo se establece el mapeo talento→producto?

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch + revisión manual | Sistema trae catálogo de Pipedrive, usuario revisa/confirma vía CRUD existente | |
| Auto-match por nombre + corrección | Match automático por similitud de nombre como punto de partida, usuario corrige | ✓ |
| Ya tengo los IDs, te los doy ahora | Usuario provee IDs directamente en la conversación | |

**User's choice:** Auto-match por nombre + corrección

### ¿Qué pasa con deals cuyo producto NO calza con ningún talento?

| Option | Description | Selected |
|--------|-------------|----------|
| Bucket 'Sin talento asignado' | Se sincronizan y cuentan en totales globales, agrupados aparte | |
| Se excluyen del sync | Solo se sincronizan deals con producto mapeado | |
| Se sincronizan + lista de revisión | Igual que bucket, más lista de "productos sin mapear" para revisión | ✓ |

**User's choice:** Se sincronizan + lista de revisión

### ¿Cuándo corre el auto-match y cómo se revisan/corrigen resultados?

| Option | Description | Selected |
|--------|-------------|----------|
| Script one-time + CRUD existente | Corre una vez manualmente, reporte de matches/ambigüedades, correcciones vía CRUD de Fase 1 | ✓ |
| Auto en primer sync + mini UI revisión | Corre al activar Pipedrive, pantalla de sugerencias para confirmar | |
| Re-evalúa en cada sync | Cada sync revisa productos nuevos sin mapear | |

**User's choice:** Script one-time + CRUD existente

### ¿Un talento corresponde a UN producto Pipedrive o puede tener varios?

| Option | Description | Selected |
|--------|-------------|----------|
| Un producto por talento (1:1) | Match exacto/casi-exacto por nombre es suficiente | ✓ |
| Pueden ser varios por talento | Match debe buscar todos los productos que contengan el nombre como substring | |
| No estoy seguro — revisemos juntos | Script lista todos los productos primero para decidir | |

**User's choice:** Un producto por talento (1:1)

---

## Frecuencia de sync y botón 'sync now'

### ¿Cada cuánto debe correr el sync automático de Pipedrive?

| Option | Description | Selected |
|--------|-------------|----------|
| Cada 15 minutos | Casi tiempo real, más llamadas a la API | |
| Cada hora | Buen balance, datos "frescos del día" | ✓ |
| 2-3 veces al día (cada 6-8h) | Mínima carga, complementado con sync manual | |

**User's choice:** Cada hora

### ¿Dónde va el botón 'sync now' y el indicador de última sync?

| Option | Description | Selected |
|--------|-------------|----------|
| Reemplazar 'En vivo' en el nav | Indicador "Última sync: hace X min" en el nav, click para forzar sync | |
| Botón dedicado en Resumen | Botón "Sincronizar ahora" + texto de última sync solo en Resumen | |
| Ambos: indicador en nav + botón en Resumen | Nav muestra última sync (read-only, todas las pestañas), Resumen tiene el botón | ✓ |

**User's choice:** Ambos: indicador en nav + botón en Resumen

### ¿Cómo se comporta 'Sincronizar ahora' mientras corre el sync?

| Option | Description | Selected |
|--------|-------------|----------|
| Bloqueante con spinner | Espera hasta terminar, luego refresca | |
| Async en background | Botón cambia a "Sincronizando...", usuario sigue navegando | |
| Async + notificación al terminar | Igual que async, más toast "Sync completado — X deals actualizados" | ✓ |

**User's choice:** Async + notificación al terminar

### Si el sync falla, ¿qué ve el usuario?

| Option | Description | Selected |
|--------|-------------|----------|
| Banner de advertencia + datos viejos | Banner visible "No se pudo sincronizar — mostrando datos de hace X horas" | ✓ |
| Solo el toast reporta el error | Toast "Sync falló: {razón}" con opción de reintentar, sin banner permanente | |
| Silencioso, solo log interno | Sin aviso al usuario, error registrado en logs | |

**User's choice:** Banner de advertencia + datos viejos

---

## Oportunidades perdidas y categorías de marca

### ¿Cómo se muestran las oportunidades perdidas (con razón de pérdida)?

| Option | Description | Selected |
|--------|-------------|----------|
| Lista de deals + razón | Lista tipo "Deals activos" con pill de razón de pérdida | |
| Lista + resumen por razón | La lista anterior, más resumen de conteo por razón arriba | ✓ |
| Solo KPI con contador | KPI simple "X oportunidades perdidas" sin lista | |

**User's choice:** Lista + resumen por razón

### ¿Cómo se muestra el desglose por categoría de marca?

| Option | Description | Selected |
|--------|-------------|----------|
| Donut chart + leyenda | Reutiliza .donut-wrap/.donut-legend ya estilizado en mockup.html | ✓ |
| Lista/tabla simple | Tabla con categoría, # de deals y monto | |
| Bar chart horizontal | Similar al .bar-chart existente pero horizontal | |

**User's choice:** Donut chart + leyenda

### ¿El donut mide por monto o por número de deals?

| Option | Description | Selected |
|--------|-------------|----------|
| Por monto (revenue) | % del revenue total por categoría | |
| Por número de deals | % de deals por categoría, sin importar monto | ✓ |
| Ambos | Leyenda muestra % de deals Y monto | |

**User's choice:** Por número de deals

### ¿Dónde van las nuevas secciones en Por talento?

| Option | Description | Selected |
|--------|-------------|----------|
| Después de Deals activos | Orden: KPIs → Funnel → Deals activos → Categorías de marca → Oportunidades perdidas → (Fuente de leads placeholder) | |
| Reemplazan Fuente de leads por ahora | Esa posición se usa para las nuevas secciones; Fuente de leads llega en Fase 3 | ✓ |
| Después del Funnel | Orden: KPIs → Funnel → Categorías de marca → Oportunidades perdidas → Deals activos → (Fuente de leads placeholder) | |

**User's choice:** Reemplazan Fuente de leads por ahora

---

## Claude's Discretion

- Resumen sections with no data source yet (Insights IA, Leads/Calificados KPIs, Fuente de leads) — area offered but not selected for discussion; left to planner.
- Bottleneck detection definition (DASH-03) — not discussed; researcher/planner to define heuristic.
- "Actividad reciente" feed source/derivation (DASH-01) — not discussed; researcher/planner to define.
- Scheduler mechanism for hourly sync (APScheduler/cron/background task) — researcher/planner decides.

## Deferred Ideas

- None — discussion stayed within Phase 2 scope. The "Resumen sections without data source" question was offered as a 4th gray area but the user chose not to discuss it (noted above as Claude's Discretion, not a deferred new-capability idea).
