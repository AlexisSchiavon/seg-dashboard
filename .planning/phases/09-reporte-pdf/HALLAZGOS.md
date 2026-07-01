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

**Referencia:** brief Fase 9, refactor H-04. Cubierto por el test
`tests/test_reports.py::TestGenerateReportPayload::test_payload_funnel_includes_trello_stages`.
