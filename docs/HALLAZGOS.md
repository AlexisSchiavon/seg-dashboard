# Hallazgos técnicos — SEG Dashboard

Registro de hallazgos de calidad de datos / diseño detectados durante el trabajo,
con su estado y si son candidatos a corrección.

---

## 2026-07-17 — `resolve_deal_id` (fuzzy match, umbral 0.70) vincula cards al deal equivocado

**Severidad:** media-alta (afecta atribución de cobranza en el dashboard, no solo el backfill).
**Estado:** detectado durante Fase D (backfill Trello). Candidato a corrección en Fase 10.

### Qué pasó
Durante la verificación del backfill de auto-creación de cards, el matcher
`app/services/trello_service.py::resolve_deal_id` (que usa `SequenceMatcher` con
umbral `0.70` sobre títulos normalizados) **cruzó dos deals distintos**:

- Card Trello **"Evento Plata Card - Emicanico"** (Fee $6,444 USD ≈ **$100,000 + IVA**)
  → pertenece en realidad al **pid=91 "Plata card - Emimecanico"** ($100K).
- Fue fuzzy-matcheada (ratio ≈ **0.71**) contra el **pid=526 "Embajador Plata - Emicanico"**
  ($1,500,000), un deal completamente diferente.

Solo se detectó porque un humano (Alexis) comparó el monto de la descripción de la
card ($100K) contra el valor del deal ($1.5M) y notó la discrepancia. El fuzzy match
de 0.71 no distingue "Embajador Plata" de "Evento Plata Card" cuando comparten
talento y la palabra "Plata".

### Impacto
1. **Backfill:** pid=526 aparecía erróneamente como "ya tiene card" y habría sido
   excluido del backfill. Corregido manualmente: 526 SÍ entra al backfill (488, 519, 526).
2. **Dashboard (más amplio):** `resolve_deal_id` corre en cada `sync_trello` y asigna
   `TrelloCard.deal_id`. Un mal vínculo desvía la **atribución de cobranza / estado de
   la card** (ejecucion/cobranza/cerrado) al deal equivocado, distorsionando
   proyecciones de ingreso y "cobranza vencida" por talento.

### Por qué el umbral 0.70 es frágil aquí
Los títulos de TA comparten mucho vocabulario (nombre de talento + tipo de campaña:
"Plata Card", "Embajador", "x MS"). `SequenceMatcher` sobre estos strings produce
ratios 0.70–0.75 entre deals genuinamente distintos → falsos positivos.

### Candidatos a corrección (Fase 10)
- Subir el umbral y/o exigir señales adicionales (monto aproximado, talento del
  producto, org) antes de aceptar un match fuzzy.
- Preferir el marcador explícito `[seg:deal_id=N]` en la descripción (ya existe para
  cards auto-creadas) y reservar el fuzzy solo como último recurso, con logging de
  cada match < 0.85 para auditoría.
- Reporte de "cards con vínculo fuzzy dudoso" en la pestaña Salud de datos.

### Mitigación ya aplicada
El script de backfill (`app/scripts/backfill_trello_cards.py`) **ignora** el registro
local de vínculos (contaminado por este bug) y se apoya solo en el marcador
`[seg:deal_id=N]` en Trello vivo para idempotencia, más una lista de ids aprobada
manualmente.
