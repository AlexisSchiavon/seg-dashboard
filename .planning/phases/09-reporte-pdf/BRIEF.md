# Fase 9 — Rediseño del reporte PDF

**Fecha de planeación**: 30 de junio 2026, post-Fase 8
**Branch**: `fase-9-reporte-pdf`
**Estimado**: 6-8 horas (9.1-9.6). Refactor H-04 incluido.
**Prerequisito**: Fase 5 + 6 + 7 + 8 mergeadas a main ✅

---

## Contexto

En la reunión del 25 de junio, Luis pidió un reporte PDF con calidad visual de nivel — algo que pueda compartir con talentos, en juntas comerciales, o por WhatsApp/email a stakeholders. El reporte actual funciona pero es visualmente pobre comparado con la pestaña Por Talento del dashboard.

Fase 9 replica 1:1 la calidad visual de Por Talento en un PDF profesional, con soporte para reporte de talento individual O consolidado (todos los talentos, uno por página). Además, salda la deuda técnica H-04 (query duplicada de funnel) que quedó abierta desde Fase 7.

---

## Decisiones de producto (D1-D11) — Tomadas antes del brief

### D1 — Alcance visual: copia 1:1 de Por Talento

Los widgets del PDF deben ser visualmente indistinguibles de lo que Luis ve en la pestaña Por Talento del dashboard. Único ajuste permitido: layout adaptado a página A4 en lugar de viewport de navegador.

### D2 — Multi-talento con selector

El usuario elige entre:
- Un talento individual (comportamiento actual)
- Todos los talentos (PDF consolidado con una página por talento + portada global)

Frontend: extensión del selector actual de la pestaña Reporte con opción "Todos los talentos".

### D3 — Generación on-demand

Solo bajo demanda desde el dashboard. Fuera de scope: scheduled reports, envío por email automático, notificaciones. Posibles fases futuras.

### D4 — Motor PDF: mantener el actual si soporta CSS moderno

Verificar en discovery. Si el motor actual es WeasyPrint o pdfkit, se mantiene. Si es ReportLab, pausar y preguntar antes de migrar a WeasyPrint (agrega dependencias del sistema: Cairo, Pango, GDK-PixBuf).

Justificación: cambiar de motor es scope creep si no es estrictamente necesario. La decisión de migración requiere aprobación explícita.

### D5 — Charts en SVG generado en Python

Cada gráfico se genera como SVG con f-strings o `svgwrite`. Justificación:
- WeasyPrint renderiza SVG nativamente con alta fidelidad
- Evita dependencia de matplotlib (~50MB al contenedor)
- SVG escala perfectamente al tamaño de página

Charts a implementar:
- Bar chart (proyección de ingresos por mes, calendario de cobranza)
- Donut chart (deals perdidos por razón)
- Funnel chart (embudo del talento)

### D6 — Branding

- **Logo**: sin logo por ahora. Badge circular con iniciales "TA" (como en el dashboard). Si Luis provee logo después, se agrega en fase futura como refactor menor.
- **Colores**: mismos del dashboard (dark mode). El reporte se lee en pantalla o se imprime a color; el look consistente con el dashboard refuerza el branding.
- **Tipografía**: Inter (Variable Font). Embebida en el PDF vía `@font-face` con archivo local en `app/static/fonts/`.

### D7 — Contenido incluido

**Portada rica** (siempre página 1):
- Header "TA · TALENT AGENCY"
- Título grande: nombre del talento (o "Reporte consolidado" si es multi-talento)
- Periodo destacado (ej. "Junio 2026" o "Q2 2026")
- 3 KPI headline tiles: Campañas firmadas · Cobrado · Pendiente por cobrar
- Fecha de generación pequeña al pie

**Páginas por talento** (una o más por talento):
- Todos los widgets de Por Talento adaptados:
  - Proyección de ingresos por mes
  - Calendario de cobranza
  - Embudo del talento
  - Top campañas firmadas
  - Dona de oportunidades perdidas
- Sección "Deals firmados en el periodo" con lista detallada:
  - Nombre del deal, fecha de firma, valor, cliente
- Footer con "Generado por SEG Dashboard · [timestamp UTC] · página X de Y"

### D8 — Fuera de scope

- Executive summary auto-generado con IA
- "Deals perdidos" con razón detallada listada (la dona resume, no lista)
- "Próximos pagos esperados" en sección separada (ya está en Calendario de cobranza)
- Comentarios/anotaciones de Luis en el PDF
- Personalización por talento (mismo template para todos)
- Firma digital / QR de validación

### D9 — Refactor H-04 incluido

La query duplicada de funnel (identificada en Fase 7 como deuda técnica H-04) se salda en esta fase. Se extrae a un helper compartido en `app/services/funnel.py` (o dentro de `kpis.py` si es más natural).

Callers a actualizar:
- `app/routers/dashboard.py` (endpoint del funnel global)
- `app/services/reports.py` (generación del PDF)
- Tests existentes de ambos

Suite completa (237 tests) debe seguir verde tras el refactor antes de tocar el PDF.

### D10 — Tests

**Tests de integración del endpoint**:
- 200 con parámetros válidos (talento único + mes)
- 200 con `talent_ids="all"` + trimestre
- 400 con formato de periodo inválido
- 404 con talent_id inexistente
- 401 sin auth

**Tests del PDF resultante**:
- Tamaño > 20 KB (sanity check)
- Contiene el nombre del talento seleccionado (extracción de texto vía `pdfplumber` o similar)
- Contiene el periodo en el título
- Contiene la fecha de generación

**Test de golden file** (snapshot):
- Portada estable en estructura para un talento fijo + periodo fijo + fecha inyectada (para determinismo)

**Test del refactor H-04**:
- Todos los tests existentes de funnel/KPIs siguen verdes
- Nuevo test unitario del helper extraído verificando comportamiento equivalente

### D11 — Formato de página

- **Tamaño**: A4 (210mm × 297mm)
- **Orientación**: portrait por defecto. Landscape solo si un widget individual no cabe legible en portrait (a evaluar en discovery — probablemente el embudo del talento)
- **Márgenes**: 15mm todos los lados
- **Densidad**: 1 talento = mínimo 2 páginas (portada + página con widgets). Máximo 4 páginas por talento (si hay muchos deals en la lista detallada)

---

## Estado actual del código (a verificar en discovery)

### Endpoint actual del reporte

- `POST /reports/generate` en `app/routers/reports.py:63`
- Recibe: `talent_id`, `period_type`, `period_value` (post-Fase 7)
- Genera: PDF con estructura visual pobre (a confirmar cuál motor)

### Motor PDF actual

- Ubicación probable: `app/services/reports.py` o `app/services/pdf.py`
- Dependencias en `pyproject.toml`: buscar `weasyprint`, `pdfkit`, `reportlab`, `wkhtmltopdf`
- Templates existentes: revisar `app/templates/` si existe

### Refactor H-04 (query duplicada de funnel)

Query duplicada existe en:
- `app/routers/dashboard.py` (endpoint `/dashboard/funnel`)
- `app/services/reports.py` (generación del PDF actual)

Ambas queries construyen la misma estructura de datos del funnel (STAGES = ["Llamada", "Cotización", "Negociación", "Contrato", "En ejecución", "Cobranza"]).

### Frontend actual

- `frontend/js/reports.js` — lógica de la pestaña Reporte
- `frontend/index.html` — UI de reporte, botón de generar

---

## Objetivos de Fase 9

### 9.1 Discovery + verificación del motor

Salida esperada:
- Motor PDF actual identificado
- CSS support disponible
- Estructura de templates existente
- Confirmación de dependencias en `pyproject.toml`
- Ubicación exacta de la query duplicada del funnel
- **Pausa para confirmar D-P4 (motor)** antes de proceder si es ReportLab

### 9.2 Refactor H-04

- Extraer `funnel_data(db, talent_id=None, period=None) -> FunnelData` a `app/services/funnel.py` (nuevo módulo) o a `kpis.py` si es más natural
- Actualizar callers: `routers/dashboard.py`, `services/reports.py`
- Suite existente debe seguir verde (237 tests)
- Commit: `refactor(fase-9.2): extract funnel query to shared helper`

### 9.3 Setup del motor + fonts + CSS base

- Descargar Inter Variable a `app/static/fonts/Inter.woff2`
- Crear `app/templates/reports/report.css` con variables CSS del dashboard
- Configurar WeasyPrint (o motor actual) para embebir la fuente
- Test smoke: generar un PDF trivial "Hello Talent Agency" con la fuente correcta

### 9.4 Templates Jinja + widgets

Templates en `app/templates/reports/`:

- `base.html` — layout común (head, footer, page numbering)
- `cover.html` — portada rica con 3 KPIs
- `talent_page.html` — página de widgets por talento
- `deals_detail.html` — lista de deals firmados

Widgets como partials en `app/templates/reports/widgets/`:

- `kpi_tile.html` — para los 3 headline tiles
- `projection_bar_chart.svg.html` — SVG generado dinámicamente
- `collection_calendar.html` — tabla + SVG mini-timeline
- `funnel_chart.svg.html` — SVG del embudo
- `top_deals.html` — lista con barras horizontales
- `lost_donut.svg.html` — SVG donut

Cada widget recibe sus datos como contexto Jinja. Ninguna lógica de queries en templates.

### 9.5 Endpoint extendido

- `POST /reports/generate` acepta:
  - `talent_ids: list[int] | Literal["all"]`
  - `period_type: "month" | "quarter"` (heredado de Fase 7)
  - `period_value: str` (heredado de Fase 7)
- Si `talent_ids="all"`, genera PDF consolidado con portada + N páginas
- Si `talent_ids=[X]`, genera PDF individual (comportamiento actual + rediseño visual)
- Retorna `StreamingResponse` con nombre de archivo tipo `reporte-<slug>-<periodo>.pdf`
- Backward compat: si viene `talent_id` (singular, viejo), tratarlo como `talent_ids=[talent_id]`

### 9.6 Frontend actualizado

- Selector de talento en pestaña Reporte con opción "Todos los talentos" al inicio del dropdown
- Botón "Generar reporte" con loader animado durante la generación (puede tomar 5-15s para consolidado)
- Nombre de archivo dinámico:
  - Individual: `reporte-emicanico-2026-06.pdf`
  - Consolidado: `reporte-consolidado-2026-06.pdf`
- Manejo de errores 400/500 con toast user-friendly

---

## Reglas de operación

1. **Discovery primero**: motor PDF, templates existentes, ubicación de queries duplicadas, dependencias del sistema (WeasyPrint requiere Cairo/Pango). Pausar antes de código.
2. **Un commit por sub-objetivo**: `feat(fase-9.1)`, `refactor(fase-9.2)`, etc.
3. **Sin migraciones Alembic** — esta fase no toca DB.
4. **Backup local ya hecho**: `seg.db.backup-pre-fase-9` (2.0M).
5. **No tocar producción** hasta validación local completa.
6. **Regla irrompible**: lectura sobre Pipedrive/Trello/Sheets, escritura solo a SQLite local.
7. **Si surge decisión no cubierta por D1-D11**, pausar y preguntar.
8. **Tests siempre verdes**: 237 base + nuevos de Fase 9. Nunca commitear con tests rojos.
9. **Validación visual obligatoria**: generar PDFs reales con datos reales antes de aprobar cada milestone. No confiar solo en fixtures.
10. **Si el motor actual es ReportLab**, pausar y preguntar antes de migrar. La migración tiene implicaciones de dependencias del contenedor Docker de producción.

---

## Definición de "Fase 9 completa"

- [ ] 9.1: Discovery documentado, motor identificado, decisiones confirmadas
- [ ] 9.2: Refactor H-04 aplicado, suite existente verde
- [ ] 9.3: Motor PDF + Inter font + CSS base funcionando
- [ ] 9.4: Templates + widgets con SVG charts implementados
- [ ] 9.5: Endpoint extendido con multi-talento
- [ ] 9.6: Frontend con selector actualizado + loader
- [ ] D1-D11 aplicadas en código
- [ ] Tests: 237 base + nuevos de reporte + refactor todos verdes
- [ ] Validación visual: PDF individual y PDF consolidado revisados por Alexis
- [ ] Branch `fase-9-reporte-pdf` con commits granulares
- [ ] Documentación en `.planning/phases/09-reporte-pdf/`:
  - BRIEF.md (este archivo)
  - SUMMARY.md (recap al cierre)
  - HALLAZGOS.md (H-09-XX que surjan)

---

## Lo que NO entra en esta fase

- Executive summary con IA (posible Fase 12)
- Envío del PDF por email (posible Fase 11)
- Scheduled reports mensuales (posible Fase 11)
- Firma digital / QR (fuera de scope)
- Personalización visual por talento (mismo template para todos)
- Deploy de M2 Pipedrive→Trello (Fase 10 sigue pendiente)
- Automatizaciones nativas en Pipedrive (Fase 11)

Si durante discovery aparecen otros bugs no relacionados, anotar en `.planning/phases/09-reporte-pdf/HALLAZGOS.md`.

---

## Riesgos identificados

**R1 — Fuentes no embebidas**: si WeasyPrint no encuentra Inter, cae a serif default. Mitigar descargando Inter Variable a `app/static/fonts/` y referenciando por path absoluto.

**R2 — SVG charts complejos**: dona de perdidos y embudo requieren cálculo de coordenadas. Mitigar con `svgwrite` o f-strings simples.

**R3 — PDF consolidado grande**: 20 talentos × 2 páginas × charts SVG puede pesar 2-5 MB. Aceptable. Si excede 10 MB, evaluar compresión.

**R4 — Timeout del endpoint**: generar consolidado puede tomar 15-30s. Mitigar aumentando timeout uvicorn o implementando background task con polling si excede 30s.

**R5 — Refactor H-04 rompe queries**: si extraemos mal, KPIs del dashboard pueden cambiar. Mitigar corriendo suite completa tras cada cambio.

**R6 — WeasyPrint requiere librerías del sistema**: Cairo, Pango, GDK-PixBuf. Verificar en Dockerfile de producción antes del deploy. Si el contenedor actual no las tiene, ajuste al Dockerfile es parte de Fase 9.

---

## Recursos de referencia

- Repo: `~/Developer/projects/lumixia/clients/santillan-ent/seg-dashboard`
- Producción: `https://automatizacion-dashboard-seg.slt9e0.easypanel.host/`
- Comando local: `DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`
- WeasyPrint docs: https://weasyprint.org/
- Inter font: https://rsms.me/inter/
- Backup DB: `seg.db.backup-pre-fase-9` (2.0M, listo)

---

## Orden de implementación

1. **9.1 Discovery** (crítico) — identifica motor, templates, queries duplicadas
2. **9.2 Refactor H-04** — antes de tocar código nuevo del PDF, saldar la deuda técnica
3. **9.3 Setup base** — motor + fonts + CSS variables
4. **9.4 Templates + widgets** — la parte más larga, iterativa con validación visual
5. **9.5 Endpoint** — una vez el HTML se ve bien, exponerlo
6. **9.6 Frontend** — última milla, cerrar el loop UX

---

**Documento generado**: 30 de junio 2026, post-Fase 8. Decisiones D1-D11 cerradas.
