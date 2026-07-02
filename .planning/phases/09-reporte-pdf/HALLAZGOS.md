# Hallazgos — Fase 9 (Rediseño del reporte PDF)

## H-09-01 — El funnel del PDF ahora incluye etapas Trello (En ejecución, Cobranza)

**Estado previo:** `reports.py` reimplementaba inline el funnel per-talento usando
solo deals abiertos de Pipedrive, sin overlay Trello. Las etapas "En ejecución" y
"Cobranza" del funnel del PDF siempre mostraban 0.

**Estado nuevo:** `reports.py` llama `funnel_service.talent_funnel(db, talent_id)`
que sí incluye el overlay Trello. Las etapas ahora se pueblan con las TrelloCards
correspondientes del talento en el periodo.

**Impacto:** cambio observable en el PDF, más correcto y consistente con la pestaña
Por Talento del dashboard. Ningún usuario reportó el bug antes porque el PDF actual
visualmente pobre no ponía atención a este apéndice.

**Referencia:** brief Fase 9, refactor H-04. La cobertura H-09-01 se movió a
`tests/test_report_build.py` cuando el funnel se retiró del reporte al talento
(9.7); la lógica del overlay Trello sigue cubierta por `tests/test_funnel.py`.

## H-09-02 — "Cobrado este mes" puede leerse como "no me pagaron" (reporte al talento)

**Contexto:** en el reporte dirigido al talento (Fase 9.7), el KPI "Cobrado este
mes" filtra por fecha de cobro (`collection_date`) dentro del mes del reporte. Como
los deals se firman un mes y se cobran 30-90 días después, es común que "Cobrado
este mes" salga en $0 aunque el talento haya firmado varias campañas ese mes (p.ej.
los 3 talentos de muestra: firmadas en junio, $0 cobrado en junio). El talento puede
interpretarlo como "no me han pagado" cuando en realidad el cobro está en proceso.

**Evidencia:** Mariana/Emicanico/Don Silverio muestran "Cobrado este mes $0" con
campañas firmadas en junio; el pago cae en meses posteriores (visible en "Estado de
tus cuentas → Por cobrar próximos meses / Cobros con retraso").

**Impacto:** riesgo de mala lectura del talento. Los números son correctos; falta
contexto temporal.

**Propuesta (fase futura, NO scope 9.7):** contextualizar en el disclaimer o con un
micro-texto/ widget aparte que explique "las campañas firmadas se cobran típicamente
en 30-90 días; lo cobrado este mes corresponde a firmas de meses anteriores".

**Estado:** documentado, sin fix en 9.7 (decisión de producto).
