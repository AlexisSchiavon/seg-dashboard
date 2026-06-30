# Fase 8 — Leads interactivos · SUMMARY

**Branch**: `fase-8-leads-interactivos` · **Periodo**: 30 jun 2026 · **Estado**: implementada, lista para review/merge.

---

## Qué se entregó

Fase 8 hace los leads **inspeccionables y navegables**, y de paso corrige un bug crítico de atribución de talento descubierto durante la validación.

- **8.1 — Migración + sync + bleach**: 4 columnas nuevas en `Lead` (`email_completo`, `razon_validacion`, `categoria_detectada`, `email_truncated`). El sync de Sheets lee las columnas, sanitiza el cuerpo con `bleach` al guardar (D9), trunca a 1 MB (D8) y loggea warning si falta un header. Migración reversible (`e1f2a3b4c5d6`), probada upgrade→downgrade→upgrade.
- **8.2 — `GET /leads/{id}`**: endpoint de detalle (schema `LeadDetail`) con las 4 columnas + `talent_name`. 404 si no existe; auth heredado.
- **8.3 — Modal + heurística D11**: click en lead → modal (header, email reformateado, clasificación de 5 campos, fallbacks D7). `formatLeadEmail` escapa-primero (seguro), respeta los `\n` reales (D11 revisado por H-08-03). 9 unit tests JS.
- **8.4 — Filtro por talento**: nombre de talento clickable en cada fila → filtra + chip "Talento: \<nombre\> [×]". 404 friendly.
- **8.5 — Doc n8n**: `N8N_CHANGES.md` (cambio propuesto, no aplicado).
- **fix(fase-8) — hotfix**: `resolve_talent_id_smart` corrige 501/819 leads con `talent_id` NULL (matching exacto → matching en capas). Ver H-08-05.

---

## Desviaciones y decisiones (vs. brief)

- **categoría agregada** (P1 revertida): `Categoria_Detectada` SÍ existía en el Sheet (descubierto en sync real) → se añadió como 4ª columna y al modal. (H-08-02)
- **header corregido**: `Razon_validacion` (v minúscula), no `Razon_Validacion`. (H-08-01)
- **D11 revisado**: el `Email_Completo` real trae `\n`, así que la heurística respeta saltos existentes. (H-08-03)
- **D10 no-op**: `ix_leads_talent_id` ya existía; la migración solo agregó columnas.
- **Hotfix de talentos**: bug pre-existente del sync, no del clasificador; resuelto en el dashboard (no en n8n). (H-08-05)

---

## Hallazgos

| ID | Resumen | Estado |
|---|---|---|
| H-08-01 | Header real `Razon_validacion` (v minúscula) | Corregido en 8.1 |
| H-08-02 | `Categoria_Detectada` existe → categoría agregada | Aplicado en 8.1 |
| H-08-03 / H-08-03b | `Email_Completo` trae `\n`; bold `*X*` no cruza saltos | Resuelto/aceptado en 8.3 |
| H-08-04 | Mojibake unicode en algunos cuerpos | Diferido (n8n upstream) |
| H-08-05 | 501 leads NULL por matching exacto | **RESUELTO** (`fix(fase-8)` `833b070`) |

---

## Métricas finales

- **Leads totales en DB**: 820
- **Leads con `talent_id` resuelto**: 820 (**100%**) — antes del hotfix: 318 (39%)
- **Distribución por capa de resolución** (último sync exitoso):
  `exact=477 · no_spaces=67 · prefix=264 · alias=12 · miss=0`
- **Tests totales**: **237** (225 base + 12 nuevos: 11 unit de `resolve_talent_id_smart` + 1 integración 8-patrones→0-NULL; más 9 unit JS de `formatLeadEmail` vía Node)
- **Migración**: `e1f2a3b4c5d6` (reversible, probada)

### Commits de Fase 8 (en orden)

| Commit | Hash | Qué |
|---|---|---|
| `docs(fase-8)` brief | `0a7d21e` | brief de leads interactivos |
| `feat(fase-8.1)` | `ed541d8` | migración + sync + bleach |
| `feat(fase-8.2)` | `a641453` | endpoint detalle `GET /leads/{id}` |
| `feat(fase-8.3)` | `dce307f` | modal + heurística D11 |
| `feat(fase-8.4)` | `05faf6c` | filtro por talento + chip |
| `fix(fase-8)` | `833b070` | **smart talent resolution (hotfix)** |
| `docs(fase-8.5)` | `ab4f07c` | documentación cambio n8n |
| `docs(fase-8)` close | (este commit) | hallazgos + summary |

> **Nota para el review/merge**: Fase 8 incluyó un **hotfix de matching de talentos** (`fix(fase-8)` `833b070`), no solo features — recuperó el 61% del dataset que estaba sin atribuir.

---

## Pendiente (fuera de Fase 8)

- Aplicar el cambio de n8n (`N8N_CHANGES.md`) cuando Luis dé OK.
- Ajustar el prompt del clasificador (H-07-04) y el mojibake upstream (H-08-04) en una sesión de mantenimiento de n8n.
- Drill-down de tiles snapshot (H-07-05) — diferido.
