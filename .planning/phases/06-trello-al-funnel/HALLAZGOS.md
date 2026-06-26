# Hallazgos — Fase 6 (para discutir/abordar en fase posterior)

Hallazgos descubiertos durante Fase 6 que **NO** se arreglan en esta fase (fuera de
alcance). Documentados para priorizar después.

---

## H-04 — `reports.py` tiene su propia query de funnel; el PDF no muestra etapas Trello

**Severidad**: media (inconsistencia dashboard vs PDF). **Estado**: no resuelto — diferido a Fase 9.

### Qué pasa

Tras Fase 6, el funnel del dashboard (`funnel_overview` / `talent_funnel`) muestra
las etapas "En ejecución" y "Cobranza" con datos reales de Trello. Pero el **reporte
PDF mensual NO** las mostrará, porque `app/services/reports.py::_build_payload`
**no llama** a `funnel_service`; construye su propia query de funnel directamente
sobre `Deal`:

- Path exacto: `app/services/reports.py`, función `_build_payload`, bloque
  "Funnel stages — per-talent, open deals" (la query `db.query(Deal.stage_name, func.count(...), func.coalesce(func.sum(Deal.value),0.0)).filter(Deal.status=='open', Deal.talent_id==..., Deal.add_time.like(month_prefix)).group_by(Deal.stage_name)`).
- Itera sobre `funnel_service.STAGES` pero rellena solo desde `Deal`, así que
  "En ejecución" y "Cobranza" siempre saldrán en 0 en el PDF.

### Por qué se dejó fuera de Fase 6

1. El brief de Fase 6 acota el scope a las **vistas de funnel** (dashboard global y
   por talento), no al PDF.
2. El reporte filtra por **mes** (`add_time.like(month_prefix)`), mientras que las
   TrelloCards no tienen un `add_time` mensual equivalente — integrarlas requiere
   decidir la semántica temporal (¿por `collection_date`? ¿por `synced_at`?), que
   es una decisión de diseño del reporte.
3. La duplicación de la lógica de funnel entre `funnel.py` y `reports.py` es deuda
   técnica preexistente; arreglarla bien implica refactorizar `_build_payload` para
   reusar `funnel_service`.

### Recomendación

Abordar en **Fase 9 (rediseño del reporte PDF)**, donde probablemente se refactorice
`_build_payload` de todas formas. En ese momento:
- Reusar `funnel_service.funnel_overview` / `talent_funnel` en lugar de la query
  duplicada, o
- Definir explícitamente la ventana temporal de las etapas Trello para el reporte
  mensual y documentarla.

**Esfuerzo estimado**: 1-2h dentro del refactor de Fase 9 (no aislado).
