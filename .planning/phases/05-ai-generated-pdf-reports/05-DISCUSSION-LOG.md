# Phase 5: AI-Generated PDF Reports - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 5-AI-Generated PDF Reports
**Areas discussed:** Alcance "Todos los talentos", Secciones narrativa IA, UX de generación, Tema PDF, Selector de mes, WhatsApp

---

## Alcance "Todos los talentos"

| Option | Description | Selected |
|--------|-------------|----------|
| Un PDF combinado | Un solo archivo con sección por talento — fácil de compartir, Claude produce resumen global + por talento | |
| 21 PDFs individuales (zip) | Genera un PDF por talento y los empaqueta en .zip | |
| No incluir por ahora | Solo reportes individuales por talento en esta fase | ✓ |

**User's choice:** No incluir por ahora — solo reportes por talento individual.
**Notes:** "Todos los talentos" queda deferred. Mantiene el scope manejable para esta fase.

---

## Secciones narrativa IA (Claude)

| Option | Description | Selected |
|--------|-------------|----------|
| 3 secciones del mockup | Resumen ejecutivo + Deals destacados + Recomendación — Python computa los números, Claude solo escribe prosa | ✓ |
| Solo resumen ejecutivo | Una sola sección narrativa (~5-8 oraciones) | |
| Secciones configurables | El usuario puede activar/desactivar secciones | |

**User's choice:** 3 secciones del mockup.
**Notes:** Alineado con el mockup de referencia. Planner define el prompt exacto; Claude recibe JSON con datos computados por Python.

---

## UX de generación

| Option | Description | Selected |
|--------|-------------|----------|
| Síncrono con spinner | Botón muestra spinner, la página espera, PDF aparece listo | ✓ |
| Async + notificación | Backend genera en background, reporte aparece en historial al terminar | |

**User's choice:** Síncrono con spinner.
**Notes:** Suficiente para uso interno ocasional. Simplifica el backend (no requiere job queue ni polling).

---

## Tema PDF

| Option | Description | Selected |
|--------|-------------|----------|
| Claro / print-friendly | Fondo blanco, texto oscuro — imprime mejor y es más legible en papel | ✓ |
| Oscuro — igual que el dashboard | Mantiene identidad visual, imprime peor | |
| Configurable por usuario | Toggle claro/oscuro al generar — doble template | |

**User's choice:** Claro / print-friendly.
**Notes:** La preview inline en el tab Reportes sigue siendo oscura (estilo del mockup). El archivo PDF descargable es light-themed.

---

## Selector de mes

| Option | Description | Selected |
|--------|-------------|----------|
| Dinámico — meses con datos | Dropdown muestra solo meses que tienen deals en SQLite | ✓ |
| Fijo — 12 meses atrás | Siempre muestra los 12 meses anteriores | |
| Solo mes actual y anterior | 2 opciones fijas | |

**User's choice:** Dinámico — meses con datos.
**Notes:** Python consulta meses distintos de la tabla Deal ordenados descendiente. Si no hay datos, el botón "Generar" se deshabilita.

---

## Compartir por WhatsApp

| Option | Description | Selected |
|--------|-------------|----------|
| No — solo generar y descargar | Scope limitado a REPORT-01/02 | ✓ |
| Sí — incluirlo ahora | Botón que abre wa.me con mensaje + link de descarga | |

**User's choice:** No — solo generar y descargar.
**Notes:** Deferred. El mockup lo muestra pero no está en REPORT-01/02.

---

## Claude's Discretion

- Prompt engineering exacto (system prompt, temperatura, max_tokens) — planner decide
- Contenido del apéndice de datos en el PDF (más allá de las 3 secciones narrativas)
- Estrategia de nombre de archivo para el talent_slug (`talent.name` vs `talent.id`)

## Deferred Ideas

- "Todos los talentos" batch report — un PDF combinado de 21 talentos (o zip de 21 PDFs)
- Compartir por WhatsApp — `wa.me` deep link con mensaje + URL de descarga
- Programación automática de reportes a fin de mes
- Historial versionado por talento/mes (actualmente: sobreescribir)
