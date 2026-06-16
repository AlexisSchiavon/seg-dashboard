---
phase: 5
slug: ai-generated-pdf-reports
status: draft
shadcn_initialized: false
preset: none
created: 2026-06-15
---

# Phase 5 — UI Design Contract

> Visual and interaction contract para el tab Reportes (DASH-05). Generado por gsd-ui-researcher. Verificado por gsd-ui-checker.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Vanilla HTML + CSS, sin framework de componentes) |
| Preset | not applicable |
| Component library | none — clases CSS propias definidas en `frontend/css/styles.css` |
| Icon library | SVG inline (mismo patrón que botones existentes en el mockup) |
| Font | DM Sans (body/UI), DM Mono (números/monospace), Sora (headings/labels uppercase) — ya en `<link>` de index.html |

**shadcn gate:** No aplica. El stack es HTML + CSS + Vanilla JS; no hay React/Next.js/Vite en este proyecto.

**Fuente:** `frontend/index.html` línea 7, `frontend/css/styles.css` `:root` y reglas tipográficas.

---

## Spacing Scale

Escala de 4 puntos. Todos los valores extraídos de `styles.css` (`.section`, `.card`, `.btn`, `.pdf-section`).

| Token | Value | Usage en Phase 5 |
|-------|-------|-----------------|
| xs | 4px | Gap entre icono y label dentro de `.ai-badge`; `padding-top` en `.section-title` |
| sm | 8px | Gap interno de filas en historial (`.deal-row` gap); gap entre select dropdowns |
| md | 16px | Padding horizontal de `.pdf-section`; padding de `.card` |
| lg | 24px | Padding bottom de `.pdf-section`; padding de `.pdf-preview-header` (14px vertical × 18px horizontal — excepción documentada abajo) |
| xl | 32px | No usado directamente en Phase 5 |
| 2xl | 48px | No usado directamente en Phase 5 |
| 3xl | 64px | No usado directamente en Phase 5 |

**Excepción documentada:**
- `.pdf-preview-header`: padding `14px 18px` (no es múltiplo exacto de 8, es el valor real del mockup — mantener para consistencia visual con `.nav` y `.talent-header` que usan el mismo padding)
- `.pdf-body`: padding `18px` (mismo caso — valor del mockup, mantener)
- `.spacer`: `height: 16px` (token md — ya existe en styles.css)

**Fuente:** `frontend/css/styles.css` + `.planning/reference/mockup.html` estilos CSS inline de `.pdf-*`.

---

## Typography

Todos los roles ya establecidos en `frontend/css/styles.css`. Phase 5 reutiliza los mismos sin variaciones. Dos pesos únicamente.

| Role | Size | Weight | Line Height | Font | Uso en Phase 5 |
|------|------|--------|-------------|------|----------------|
| Body | 14px | 400 (regular) | 1.5 | DM Sans | Texto de `.btn`, texto del cuerpo del tab |
| Label / caption | 11–13px | 400 (regular) | 1.5 | DM Sans | `.pdf-text` (13px), `.pdf-preview-sub` (11px), `.deal-tipo` (11px), subtítulos de historial |
| Heading / label uppercase | 10px | 600 (semibold) | 1.2 | Sora | `.section-title` (10px Sora uppercase), `.pdf-block-title` (10px uppercase) |
| Display / número grande | 11–13px mono | 400 (regular) | 1.5 | DM Mono | `.deal-amt`, `.th-report-date`, timestamp de generación en historial |

**Regla de 2 pesos:**
- Peso 400 (regular): todo texto de lectura (body, labels, captions, monospace)
- Peso 500 (medium): `.pdf-preview-title` (13px/500), nombres de deals en historial (`.deal-brand`), texto de botones (`.btn`)
- Peso 600 (semibold): `.section-title`, `.pdf-block-title`, `.ai-badge` implícito — reservado para etiquetas uppercase que identifican secciones

> Nota: el CSS existente usa tres valores de `font-weight` (400, 500, 600). El contrato de fase mantiene esta convención establecida. 500 se trata como "énfasis leve" y 600 como "etiqueta de sección". No se introducen pesos nuevos (700 solo en `.nav-logo` / Sora — ya existente, no nuevo en Phase 5).

**Fuente:** `frontend/css/styles.css` líneas 28–32 (body), líneas 259–267 (`.section-title`), mockup `.pdf-preview-title`, `.pdf-block-title`, `.pdf-text`.

---

## Color

Extraído de `frontend/css/styles.css` `:root`. No se introducen variables nuevas — Phase 5 reutiliza el sistema existente al 100%.

| Role | Value (CSS var) | Hex | Usage en Phase 5 |
|------|-----------------|-----|-----------------|
| Dominant (60%) | `var(--bg)` | `#0c0c0e` | Fondo de página del tab Reportes |
| Secondary (30%) | `var(--bg3)` / `var(--bg4)` | `#18181c` / `#1f1f24` | `.pdf-preview` card background (`--bg3`), `.pdf-preview-header` background (`--bg4`), `.card` del historial (`--bg3`) |
| Accent (10%) | `var(--accent)` | `#e8520a` | RESERVADO para: (1) botón "Generar reporte con IA" (`.btn.primary`), (2) tab "Reportes" activo en tabbar, (3) nombre del talento en `.pdf-preview-title` cuando se resalta, (4) headers/highlights en la plantilla PDF light-theme |
| Purple semantic | `var(--purple)` / `var(--purpleD)` / `var(--purpleT)` | `#6b54d6` / `rgba(107,84,214,0.12)` / `#a594f0` | RESERVADO para: `.ai-badge` (background `--purpleD`, texto `--purpleT`, border `rgba(107,84,214,0.2)`) |
| Blue semantic | `var(--blue)` / `var(--blueD)` / `var(--blueT)` | | RESERVADO para: pill "PDF" en filas del historial (`background: var(--blueD); color: var(--blueT)`) |
| Destructive | `var(--red)` / `var(--redT)` | `#c43232` / `#f07070` | No hay acciones destructivas en Phase 5 — no se usa |

**Accent reservado para (lista explícita):**
1. Botón primario "Generar reporte con IA" (`.btn.primary`)
2. Tab "Reportes" en estado activo (`.tab.active`)
3. Highlighted text en `.act-main strong` si se muestra actividad de generación en feed
4. Encabezados y línea decorativa de portada en la plantilla PDF (`reports/template.html`)

**Accent NO se usa para:** links genéricos, hover de cards del historial, iconos decorativos.

**Fuente:** `frontend/css/styles.css` `:root` líneas 8–17; mockup `.ai-badge` y `.pdf-preview` CSS.

---

## Component Inventory

Componentes que Phase 5 **añade** a `frontend/css/styles.css`. Los que ya existen se reutilizan sin modificación.

### Componentes existentes reutilizados sin cambios

| Clase | Archivo | Uso en Phase 5 |
|-------|---------|----------------|
| `.section`, `.section-title` | styles.css | Encabezados "Generar reporte con IA" y "Reportes anteriores" |
| `.card` | styles.css | Contenedor de lista del historial de reportes |
| `.btn`, `.btn.primary` | styles.css | "Generar reporte con IA" (primary), "Descargar PDF" (default) |
| `.sel` (select) | styles.css | Dropdown de talentos, dropdown de meses |
| `.deal-row`, `.deal-l`, `.deal-r`, `.deal-brand`, `.deal-tipo` | styles.css | Filas del historial de reportes (patrón existente) |
| `.pill` | styles.css | Badge "PDF" en cada fila del historial |
| `.divider` | styles.css | Separador entre formulario de generación e historial |
| `.spacer` | styles.css | Padding top del tab |
| `.alert.info` | styles.css | Estado vacío cuando no hay meses disponibles |

### Componentes nuevos a añadir en `frontend/css/styles.css`

Las definiciones exactas se copian del mockup — no inventar valores.

| Clase | Propiedades | Descripción |
|-------|-------------|-------------|
| `.pdf-section` | `padding: 0 16px 24px` | Wrapper del formulario + preview del tab Reportes |
| `.pdf-preview` | `background: var(--bg3); border: 1px solid var(--border); border-radius: var(--rL); overflow: hidden; margin-bottom: 14px` | Card oscura de preview in-page del reporte generado |
| `.pdf-preview-header` | `background: var(--bg4); padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between` | Header de la card de preview |
| `.pdf-preview-title` | `font-size: 13px; font-weight: 500` | Título dentro del header del preview |
| `.pdf-preview-sub` | `font-size: 11px; color: var(--text3)` | Subtítulo "YYYY-MM · Generado con IA" |
| `.pdf-body` | `padding: 18px` | Contenedor de los 3 bloques narrativos |
| `.pdf-block` | `margin-bottom: 14px` | Wrapper de cada sección narrativa de Claude |
| `.pdf-block-title` | `font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text3); margin-bottom: 6px` | Label de sección (RESUMEN EJECUTIVO, etc.) |
| `.pdf-text` | `font-size: 13px; color: var(--text2); line-height: 1.6` | Texto narrativo de Claude |
| `.pdf-text strong` | `color: var(--text); font-weight: 500` | Énfasis dentro del texto narrativo |
| `.ai-badge` | `display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--purpleT); background: var(--purpleD); border: 1px solid rgba(107,84,214,0.2); border-radius: 20px; padding: 3px 10px; margin-bottom: 14px` | Badge "✦ Claude AI" en el header del preview |

**Fuente:** Directamente extraído del CSS inline del mockup — sin modificaciones.

---

## Interaction Contract

### Estado 1 — Tab cargando (on `setPage('reports', event)`)

- La tab se activa con clase `.tab.active` (`.accent` background)
- `loadReportTalents()` se llama: el `<select id="report-talent">` se puebla con los 21 talentos activos
- `loadReportHistory()` se llama: la lista de historial se puebla
- El dropdown de meses (`<select id="report-month">`) permanece vacío y deshabilitado hasta que el usuario elija un talento

### Estado 2 — Talento seleccionado

- `onChange` en `#report-talent` llama `loadReportMonths(talentId)`
- Si hay meses disponibles: dropdown `#report-month` se puebla con strings "YYYY-MM" formateados como "Mayo 2025"
- Botón "Generar reporte con IA" se habilita
- Si no hay meses (sin deals): `#report-month` permanece deshabilitado; botón permanece deshabilitado; mostrar `.alert.info` con copy del empty state

### Estado 3 — Generación en curso (D-58)

- Botón "Generar reporte con IA": `disabled = true`, texto cambia a spinner + "Generando..." (SVG spinner animado inline o clase `.spinner`)
- El card `.pdf-preview` muestra un estado de carga: los `.pdf-block` se rellenan con líneas de skeleton (div con `background: var(--bg5); height: 12px; border-radius: 4px; animation: pulse 1.5s infinite`)
- Duración esperada: 3–10 segundos (backend síncrono: Claude API + WeasyPrint)

### Estado 4 — Reporte generado (D-59)

- Botón "Generar reporte con IA" se reactiva con texto original
- Botón "Descargar PDF" se habilita (si estaba deshabilitado)
- El card `.pdf-preview` se puebla con los 3 bloques narrativos:
  - `.pdf-preview-title`: `"Reporte mensual · {nombre_talento}"`
  - `.pdf-preview-sub`: `"{mes formateado} · Generado con IA"`
  - Badge `.ai-badge`: `"✦ Claude AI"`
  - Tres `.pdf-block` con títulos y texto narrativo (escapado con `escHtml()` — ver regla XSS)
- La fila nueva aparece al tope de la lista de historial `#report-history` sin recargar la página
- `showToast("Reporte generado correctamente")` (patrón D-23 de Phase 4)

### Estado 5 — Descarga de PDF

- Botón "Descargar PDF": `<a href="/reports/{id}/download" download>` o `window.location.href` con el JWT en header via `apiFetch`
- El archivo se descarga con nombre `reporte-{nombre}-{YYYY-MM}.pdf` (establecido por el backend en `Content-Disposition`)

### Estado 6 — Error de generación

- El botón "Generar reporte con IA" se reactiva
- Se muestra `showToast("Error al generar el reporte. Intenta de nuevo.")` (patrón existente)
- El `.pdf-preview` retorna al estado vacío inicial (sin skeleton, sin contenido)

### Reglas de interacción importantes

- **XSS obligatorio:** En `reports.js`, toda string proveniente de Claude (`.resumen_ejecutivo`, `.deals_destacados`, `.recomendacion`) DEBE ser escapada con `escHtml()` antes de asignarse a `innerHTML`. Usar `textContent` para texto plano donde sea posible.
- **Botón Descargar PDF:** Inicia deshabilitado. Se habilita solo después de una generación exitosa en la sesión actual O si el historial tiene al menos un reporte (en cuyo caso el download es por fila del historial, no el botón principal).
- **Sin botón WhatsApp:** Deferred (D-67). No incluir.
- **Overwrite silencioso (D-64):** Si el mismo talento + mes ya existe, el backend sobreescribe. El frontend no necesita confirmación — el toast de éxito es suficiente.

---

## Copywriting Contract

| Elemento | Copy exacto |
|----------|-------------|
| Título de sección generación | `Generar reporte con IA` |
| Placeholder dropdown talentos | `Selecciona un talento` |
| Placeholder dropdown meses | `Selecciona un mes` |
| Botón primario CTA | `Generar reporte con IA` |
| Botón en estado loading | `Generando...` |
| Botón descarga | `Descargar PDF` |
| Badge IA | `✦ Claude AI` |
| Preview title | `Reporte mensual · {Nombre Talento}` |
| Preview sub | `{Mes YYYY} · Generado con IA` (ej: `Mayo 2025 · Generado con IA`) |
| Sección historial | `Reportes anteriores` |
| Fila historial nombre | `{Nombre Talento} · {Mes YYYY}` (ej: `Mariana García · Abril 2025`) |
| Fila historial meta | `Generado el {D MMM} · {N} páginas` (ej: `Generado el 1 may · 2 páginas`) |
| Badge PDF en historial | `PDF` |
| Toast éxito | `Reporte generado correctamente` |
| Toast error | `Error al generar el reporte. Intenta de nuevo.` |
| Empty state heading (sin meses) | `Sin datos disponibles` |
| Empty state body (sin meses) | `Este talento no tiene deals con fecha registrada. Sincroniza Pipedrive primero.` |
| Empty state historial vacío | `Aún no hay reportes generados.` |
| Sección narrativa 1 | `Resumen ejecutivo` |
| Sección narrativa 2 | `Deals destacados` |
| Sección narrativa 3 | `Recomendación` |

**Acciones destructivas en Phase 5:** Ninguna. No hay eliminación de reportes en esta fase.

**Fuente:** CONTEXT.md D-55, D-58, D-59, D-67; mockup `page-reportes` — copy extraído literalmente donde coincide, extendido por discretion donde el mockup no especifica.

---

## HTML Structure Contract

Estructura exacta del nuevo `<div id="page-reportes">` a añadir en `frontend/index.html`:

```html
<!-- Tab bar: añadir a .tabbar -->
<div class="tab" onclick="setPage('reports', event)">Reportes</div>

<!-- ========== REPORTES TAB ========== -->
<div class="page" id="page-reportes">
  <div class="spacer"></div>
  <div class="pdf-section">

    <!-- Formulario de generación -->
    <div class="section-title" style="padding:0 0 12px;">Generar reporte con IA</div>
    <div style="display:flex;gap:10px;margin-bottom:14px;">
      <select class="sel" style="flex:1;" id="report-talent">
        <option value="">Selecciona un talento</option>
      </select>
      <select class="sel" style="flex:1;" id="report-month" disabled>
        <option value="">Selecciona un mes</option>
      </select>
    </div>

    <!-- Empty state (sin meses disponibles) — hidden por defecto -->
    <div id="report-no-months" style="display:none;">
      <!-- .alert.info con copy del empty state -->
    </div>

    <!-- Preview card (inicialmente vacía) -->
    <div class="pdf-preview" id="pdf-preview-card" style="display:none;">
      <div class="pdf-preview-header">
        <div>
          <div class="pdf-preview-title" id="pdf-preview-title"></div>
          <div class="pdf-preview-sub" id="pdf-preview-sub"></div>
        </div>
        <span class="ai-badge">✦ Claude AI</span>
      </div>
      <div class="pdf-body" id="pdf-body">
        <!-- Poblado por generateReport() en reports.js -->
      </div>
    </div>

    <!-- Botones de acción -->
    <button class="btn primary" id="btn-generate" onclick="generateReport()" disabled>
      <!-- SVG inline + "Generar reporte con IA" -->
    </button>
    <button class="btn" id="btn-download" disabled>
      <!-- SVG inline + "Descargar PDF" -->
    </button>

    <div class="divider"></div>

    <!-- Historial -->
    <div class="section-title" style="padding:0 0 12px;">Reportes anteriores</div>
    <div class="card" id="report-history" style="padding:14px 16px;">
      <!-- Poblado por loadReportHistory() en reports.js -->
    </div>

  </div>
</div>
```

**Orden de scripts en `frontend/index.html`** (añadir al final del body):
```html
<script src="/js/reports.js"></script>
```

---

## PDF Template Visual Contract (light theme)

El archivo `templates/reports/template.html` (Jinja2) usa tema claro — independiente del dashboard oscuro.

| Propiedad | Valor |
|-----------|-------|
| Fondo | `#ffffff` |
| Color de texto principal | `#1a1a1a` |
| Color de texto secundario | `#555555` |
| Color accent (SEG) | `#e8520a` |
| Color purple (badge IA) | `#6b54d6` |
| Fondo badge IA | `#f4e8ff` |
| Font | `sans-serif` (system font — WeasyPrint no puede cargar Google Fonts sin internet; usar stack system: `'Helvetica Neue', Arial, sans-serif`) |
| Portada: padding | `80px 40px` |
| Portada: título talento | `font-size: 28px; font-weight: 700; color: #e8520a` |
| Portada: línea decorativa | `border-bottom: 3px solid #e8520a` |
| Sección: padding | `32px 40px` |
| Sección título | `font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #e8520a; font-weight: 600` |
| Sección texto | `font-size: 14px; line-height: 1.7; color: #333333` |
| Apéndice tabla: header | `background: #f5f5f5; font-weight: 600` |
| Apéndice tabla: celda | `border: 1px solid #dddddd; padding: 8px 12px` |

**Secciones en orden:**
1. Portada: nombre talento, mes, badge "✦ Generado con Claude AI"
2. Resumen ejecutivo (texto de Claude)
3. Deals destacados (texto de Claude)
4. Recomendación (texto de Claude)
5. Apéndice de datos: tabla KPI (Pipeline, Cerrados count+valor, Comisión, Leads totales, Leads calificados)

**Fuente:** CONTEXT.md D-60, D-61; RESEARCH.md Pattern 1 (Jinja2 template code example).

---

## JS Module Contract

Archivo: `frontend/js/reports.js`

Funciones a implementar (siguiendo el patrón de `leads.js`):

| Función | Trigger | API call | DOM target |
|---------|---------|----------|------------|
| `loadReportTalents()` | `setPage('reports')` | `GET /reports/talents` | `#report-talent` (populate options) |
| `loadReportMonths(talentId)` | `onChange #report-talent` | `GET /reports/months?talent_id={id}` | `#report-month` (populate/enable/disable) |
| `generateReport()` | click `#btn-generate` | `POST /reports/generate` | `#pdf-preview-card`, `#pdf-body`, `#btn-download`, `#report-history` |
| `loadReportHistory()` | `setPage('reports')` | `GET /reports/` | `#report-history` |
| `downloadReport(reportId)` | click en fila del historial | `GET /reports/{id}/download` | window location / anchor tag |

**Reglas obligatorias para el ejecutor:**
- Usar `apiFetch` (definido en `auth.js`) para todas las llamadas — nunca `fetch` directo
- Usar `escHtml()` (definido en `dashboard.js`) para todo string de Claude antes de `innerHTML`
- Usar `showToast()` (definido en `dashboard.js`) para toasts de éxito/error
- `setPage('reports', event)` en `dashboard.js` debe llamar `loadReportTalents()` y `loadReportHistory()` en el branch de reports

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | ninguno — no aplica (Vanilla CSS) | not required |
| Terceros | ninguno | not applicable |

No hay registries de terceros. Los únicos componentes nuevos son clases CSS añadidas a `styles.css`, copiadas directamente del mockup del proyecto.

---

## Pre-Population Log

| Campo | Fuente | Confianza |
|-------|--------|-----------|
| Design system: none | CLAUDE.md stack (HTML + CSS + Vanilla JS) | HIGH |
| Spacing tokens | `frontend/css/styles.css` `:root` y reglas de layout | HIGH |
| Typography: DM Sans / DM Mono / Sora | `frontend/index.html` `<link>` + `styles.css` | HIGH |
| Color tokens (todos) | `frontend/css/styles.css` `:root` líneas 8–17 | HIGH |
| PDF-section CSS classes | `.planning/reference/mockup.html` estilo inline extraído | HIGH |
| ai-badge CSS | `.planning/reference/mockup.html` estilo inline extraído | HIGH |
| Copywriting: CTAs, section titles | mockup `page-reportes` + CONTEXT.md D-55, D-58, D-67 | HIGH |
| Empty state copy | Default razonado — no especificado en mockup | MEDIUM (default) |
| Error state copy | Patrón D-23 de Phase 4 (toast de error) | HIGH |
| 5th tab label "Reportes" | CONTEXT.md D-65 | HIGH |
| No WhatsApp button | CONTEXT.md D-67 (deferred) | HIGH |
| PDF light theme | CONTEXT.md D-60, RESEARCH.md Pattern Jinja2 | HIGH |
| JS module pattern | RESEARCH.md Pattern 7 (`reports.js`) | HIGH |
| Report history row pattern | mockup `.deal-row` pattern | HIGH |

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

*Generado: 2026-06-15*
*Fuentes primarias: `frontend/css/styles.css`, `.planning/reference/mockup.html`, `05-CONTEXT.md`, `05-RESEARCH.md`*
*Preguntas al usuario: ninguna — todo resuelto por artefactos upstream y codebase scan*
