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
