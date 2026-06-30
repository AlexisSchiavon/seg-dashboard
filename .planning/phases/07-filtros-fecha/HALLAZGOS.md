# Hallazgos — Fase 7 (filtros por fecha)

Bugs / deuda técnica detectados durante Fase 7, fuera de scope. Anotados para retomar después.

## H-07-01 — `datetime.utcnow()` deprecado en reports.py

**Detectado**: 30 jun 2026, durante discovery 7.1.
**Severidad**: baja (deuda técnica, no rompe nada hoy).
**Detalle**: La suite arroja 8 `DeprecationWarning` por `datetime.datetime.utcnow()` en `app/services/reports.py:321` (y un eco en `tests/test_reports.py:323`). `utcnow()` está programado para remoción en una versión futura de Python; el reemplazo es `datetime.datetime.now(datetime.UTC)`.
**Decisión**: NO se corrige en Fase 7 (preexistente desde Fase 5, fuera de scope). Retomar en una fase de mantenimiento.

## H-07-02 — `income_projection` / `payment_calendar` son ventana deslizante anclada en hoy, no consultas históricas

**Detectado**: 30 jun 2026, durante discovery 7.1.
**Severidad**: media (afecta cómo se interpreta D4 para esos widgets).
**Detalle**: `app/services/trello_service.py:179` (`income_projection`) y `:237` (`payment_calendar`) NO son históricos por `won_time`. Son una ventana deslizante de 4 meses anclada en `date.today()`, agrupada por `TrelloCard.collection_date`, que reparte `deal.value` en cobrado (cerrado) / proyección (ejecución) / pendiente (cobranza). D4 asume que "histórico de ingresos" filtra por `won_time` y "calendario" por `collection_date` para el periodo elegido, pero la implementación real es forward-looking. Reconciliarlos requiere decisión de producto (ver pregunta abierta planteada a Luis/Alexis en sesión 7.1).

## H-07-03 — `reports_service.available_months` quedó huérfana tras 7.2

**Detectado**: 30 jun 2026, durante 7.2.
**Severidad**: baja (código muerto, tests verdes).
**Detalle**: En 7.2 el endpoint `GET /reports/months` se repuntó a `periods.available_months` (won-based, global) por decisión de producto (el filtro opera sobre `won_time`, el dropdown debe ofrecer solo meses con firmas). La función previa `app/services/reports.py:available_months(db, talent_id)` (basada en `add_time`, per-talent) ya no la consume ningún endpoint, pero se conservó junto con su clase de tests `TestAvailableMonths` para no reducir el conteo de la suite en un commit de frontend. **Decisión**: eliminar `reports_service.available_months` + `TestAvailableMonths` en una limpieza posterior (no en Fase 7).

## H-07-04 — Clasificador de leads requiere ajuste

**Detectado**: 30 jun 2026, durante la validación visual de Fase 7.
**Severidad**: media (afecta calidad de los leads que llegan al equipo; no es bug de Fase 7).

**Patrones detectados:**

1. **Falsos positivos aprobados con score alto:**
   - Yvonne (SHEIN) `kol08@shein.com` — score 88, Aprobado. SHEIN está en blacklist explícita (acordado pre-junta); no debería pasar.
   - `collab@creativault.pro` — score 86, Aprobado. Dominio sospechoso. Hay duplicado en `creativault.mobi` marcado En revisión.
   - Mariah Sanders `@trendboosting.com` — 72, Aprobado. SEO spam clásico.
   - Annie Hill `@enhancefanbase.com` — 48, Aprobado. Mismo patrón.

2. **Falsos negativos (bloqueados que parecen legítimos):**
   - TipsyChat `@inflink.tipsy.chat` — 35, Bloqueado. Subject "PAID collaboration" sugiere negocio real.

3. **Saturación de "En revisión 35":** demasiados leads quedan en estado limbo, sobrecargando al equipo de Luis.

**Acción**: revisar el prompt del clasificador en n8n durante Fase 8 (que ya contempla "verificar creación de orgs aunque el lead esté bloqueado"). Considerar:
- Refrescar blacklist de dominios (SHEIN, casinos, crypto, SEO spam).
- Ajustar thresholds del score.
- Reducir falsos "En revisión 35" con mejor signal extraction.
