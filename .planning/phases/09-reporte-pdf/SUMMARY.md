# Fase 9 — Rediseño del reporte PDF · SUMMARY

**Estado:** cerrada técnicamente (2026-07-02). Branch `fase-9-reporte-pdf`, **NO mergeada, NO pusheada, NO desplegada.** 266 tests verdes, ruff limpio.

## Sub-objetivos y commits

| Sub-obj | Descripción | Commit |
|---|---|---|
| 9.1 | Discovery + brief (motor WeasyPrint confirmado) | `ab32748` |
| 9.2 | Refactor H-04: funnel a helper compartido (H-09-01) | `fd31b0b` |
| 9.3 | Motor base: Inter font embebida, CSS dark tokens, A4 | `2ca8c70` |
| 9.4 | Templates Jinja + widgets SVG (f-strings, sin matplotlib) | `d19b10d` |
| 9.5a | Quitar Claude; PDF single-talento in-memory | `06d1d2d` |
| 9.5b | Endpoint StreamingResponse + `talent_ids: list\|"all"` + migración Alembic + regenerate-on-download | `00c270d` |
| 9.5c | Golden portada + sanity D10 | `908a84d` |
| 9.7a | Helpers talent-facing (70%): `compute_talent_facing_kpis`, `account_status_breakdown` | `9eebbaf` |
| 9.7b | Rediseño talent page (audiencia = talento) + P1/P3/P4 + K/M | `d2d2b2c` |
| 9.7c | Golden regenerado + snapshot talent-facing | `7bc5e78` |
| 9.6 | Frontend: fetch→blob, "Todos los talentos", loader, toasts | `3e2409b` |
| cierre | SUMMARY + HALLAZGOS | (este commit) |

## Giro de scope importante

**El D1 original ("copia 1:1 de Por Talento") fue mal cerrado** al asumir audiencia = TA. La audiencia real es **el talento**. Esto se detectó tras 9.5 y motivó **9.7** (rework de contenido): se retiraron widgets internos (pipeline, comisión, embudo, prospectos/calificados, dona de perdidas, calendario placeholder) y se reconstruyó el reporte con cifras al **70% del talento**, estado de cuentas, tabla de campañas firmadas y proyección forward-only. **9.6** (frontend) se hizo al final, reutilizable (TA descarga en lote).

## Decisiones

**Originales D1-D11** (brief): D1 alcance visual, D2 multi-talento, D3 on-demand, D4 motor (WeasyPrint), D5 charts SVG en Python, D6 branding Inter/dark, D7 contenido, D8 fuera de scope (sin IA), D9 refactor H-04, D10 tests, D11 A4.

**Nuevas:**
- **D1 (corregida):** audiencia = **TALENTO**, no TA.
- **D-9.5-1:** download **regenera on-demand** (sin PDF en disco).
- **D-9.5-2:** esquema Report += `talent_ids` (str "all"/"10,11") + `content_hash`; `talent_id`/`file_path` nullable. **Migración Alembic `a7f3c1b2d4e5`** (batch, round-trip verificado).
- **D-9.5-3 / D-9.6:** frontend en 9.6 (fetch→blob, sin narrativa, sin `#btn-download`).
- **D-9.7 (P1-P4):**
  - **P1** portada branding-only (sin KPIs 100%/all-time).
  - **P2** "Cobrado en el año" — confirmado correcto (no bug).
  - **P3** badge "Cobrado" solo si `cerrado` Y `collection_date` en el mes → alineado al KPI.
  - **P4** proyección forward-only (`>= HOY`, excluye `cerrado`) → consistente con "por cobrar próximos meses".
  - "Tu 70%" = `commission_amount` (verificado = value×0.70). Retraso saneado (excluye `collection_date < add_time`). Sublabel firmadas en formato K/M (≥$1M → "$1.67M").

## Hallazgos

- **H-09-01** — El funnel del PDF ahora incluye etapas Trello (En ejecución/Cobranza). Cobertura movida a `test_report_build.py`/`test_funnel.py` (el funnel se retiró del reporte al talento en 9.7).
- **H-09-02** — "Cobrado este mes" puede leerse como "no me pagaron" (los deals de junio se cobran en 30-90 días). Contextualizar en fase futura (no scope 9.7).

## Deploy pendiente (chat nuevo)

1. Backup `/data/seg.db` → `/data/seg.db.backup-pre-9-5-prod` en EasyPanel **antes** del deploy.
2. Push a main → autodeploy EasyPanel → `alembic upgrade head` en el container.
3. Smoke prod: healthcheck, StreamingResponse, fuente Inter (no PT-Serif vía pdfplumber), migración corrida limpia.
4. Generar los 14 PDFs READY desde prod; mensaje a Luis (diagnóstico + clasificación READY/REVIEW/HOLD).

Ver `FASE_9_CIERRE_CONTEXTO.md` para el detalle de retoma.
