# Fase 8 — Leads interactivos

**Fecha de planeación**: 30 de junio 2026, post-Fase 7
**Branch**: `fase-8-leads-interactivos`
**Estimado**: 4-6 horas (8.1-8.5). Drill-down y clasificador son ampliaciones opcionales.
**Prerequisito**: Fase 5 + 6 + 7 mergeadas a main ✅

---

## Contexto

En la reunión del 25 de junio, Luis pidió poder hacer clic en un lead para ver el cuerpo del correo y entender por qué se aprobó o bloqueó. Hoy la pestaña Leads muestra una lista con remitente, asunto y status, sin forma de inspeccionar el detalle. Esto le dificulta:

- Validar si el clasificador está siendo correcto (problema en H-07-04)
- Decidir qué hacer con leads en estado "En revisión 35"
- Identificar leads bloqueados injustamente

Fase 8 expone el detalle completo de cada lead y agrega navegación por talento.

---

## Estado del Google Sheet (verificado 30 jun 2026)

Las dos columnas que necesitamos **ya existen** en el Sheet de leads (`1LKdDo7IqMCpBg7nNVVCeNyjrHjPXxmkdt9Oa5zTwais`, pestaña "Leads"):

- **`Email_Completo`** — cuerpo del email en **texto plano**, sin saltos de línea preservados (párrafos pegados, ej. `"muy bienSoy Pame"`)
- **`Razon_Validacion`** — explicación del clasificador (ej. `"industria prohibida (casino)"`)

Esto significa: NO se necesita modificar n8n ni el Sheet para Fase 8. Solo extender el sync para leer las nuevas columnas.

---

## Decisiones de producto (D1-D11)

### D1 — Cuerpo del email se guarda completo en SQLite

Estimación: 813 leads × ~5 KB promedio = ~4 MB total. SQLite trivial.

### D2 — Todos los leads son inspeccionables

Aprobados, en revisión y bloqueados — todos abren el modal. Especialmente los bloqueados, porque ahí es donde Luis valida si el clasificador erró.

### D3 — Texto plano con heurística de reformateado en frontend

`Email_Completo` viene como texto plano sin saltos de línea preservados. El frontend aplica heurísticas para reformatearlo legible.

**No es HTML real**: la decisión inicial de "HTML formateado" se ajusta a la realidad de los datos.

### D4 — Sanitización defensiva con bleach

Aunque el cuerpo es texto plano de origen (riesgo XSS bajo), se mantiene `bleach` como defensa por si en el futuro n8n empieza a guardar HTML. Sanitiza al guardar (write-time).

El frontend NUNCA usa `innerHTML` con el contenido del email. Usa `textContent` después de aplicar heurística + reemplazos controlados (`\n` → `<br>`).

### D5 — Verificación de orgs en n8n NO toca repo

8.5 vive en n8n. Solo se documenta en `N8N_CHANGES.md`. No se aplica.

### D6 — Sanitización al sync (write-time)

`bleach.clean()` se aplica una sola vez al sincronizar. DB guarda texto ya seguro.

### D7 — Fallback si no hay cuerpo

Si `email_completo` es NULL → "Cuerpo del email no disponible para este lead". Si `razon_validacion` es NULL → "Sin razón registrada".

### D8 — Tamaño máximo del email

Límite 1 MB. Si excede, truncar y marcar `email_truncated=True`. Loggear.

### D9 — Bleach: configuración restrictiva

Como el contenido es texto plano:

```python
ALLOWED_TAGS = []  # No permitir ningún tag
ALLOWED_ATTRIBUTES = {}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']
STRIP = True  # Quitar tags en lugar de escaparlos
```

Si n8n empieza a guardar HTML, expandir esta lista después.

### D10 — Índice en Lead.talent_id

Verificar en discovery. Si no existe, agregar en la misma migración.

### D11 — Heurística de reformateado en frontend

**Reglas (en orden, en JS)**:

1. `\s+` múltiple → 1 espacio (normalizar)
2. `,([A-ZÁÉÍÓÚÑ])` → `,\n\n$1` (coma + mayúscula sin espacio)
3. `\.([A-ZÁÉÍÓÚÑ])` → `.\n\n$1` (punto + mayúscula sin espacio)
4. `([a-záéíóúñ])([A-ZÁÉÍÓÚÑ])` → `$1\n\n$2` (caso "bienSoy")
5. Líneas que empiezan con "Abrazo,", "Saludos,", "Atentamente,", "Best," → `\n\n` antes
6. `\*(.+?)\*` → `<strong>$1</strong>` (markdown bold)
7. `\n` → `<br>` al renderizar

**Aceptable**: falsos positivos en nombres compuestos ("McDonalds" → "Mc\n\nDonalds"). Iteramos si Luis se queja.

**Implementación**: función `formatLeadEmail(text)` en `frontend/js/leads.js`. Construir HTML con escape básico, NO `innerHTML` directo del input.

---

## Estado actual del código (a verificar en discovery)

### Modelo Lead

Confirmar columnas existentes. Mínimo esperado:
- `id`, `pipedrive_lead_id` o equivalente
- `email_remitente`, `nombre_remitente`, `asunto`
- `talent_id` (FK nullable)
- `status_filtrado`, `score_calidad`, `categoria_detectada`
- `fecha_recepcion`

### Columnas a agregar (migración)

- `email_completo` (TEXT, nullable)
- `razon_validacion` (TEXT, nullable)
- `email_truncated` (BOOLEAN, default False)

### Sync de Sheets

Verificar lectura actual y agregar las dos nuevas. Aplicar bleach.

### Endpoints actuales

- `GET /leads` — lista (ya existe)
- `GET /leads/summary` — KPIs (ya existe)
- (Falta) `GET /leads/{id}` — detalle

### Frontend

- `frontend/index.html` — pestaña Leads
- `frontend/js/leads.js` (o equivalente)

---

## Objetivos

### 8.1 Migración + extender Lead + sync de Sheets

**Migración Alembic reversible**:
- Agregar `email_completo`, `razon_validacion`, `email_truncated`.
- Si `Lead.talent_id` no tiene índice, agregarlo (D10).

**Sync**:
- Extender lectura para incluir `Email_Completo` y `Razon_Validacion`.
- Si una columna no existe en Sheets, loggear warning y continuar.
- Aplicar `bleach.clean()` con D9 al guardar.
- Truncar a 1 MB si excede, marcar flag.

**Dependencia**: `bleach>=6.0.0`.

**Tests**: sync con email vacío, con email >1MB, con HTML inyectado.

### 8.2 Endpoint GET /leads/{id}

Devuelve todos los campos del Lead + `talent_name`. JWT auth. 404 si no existe.

**Tests**: lead existente, inexistente, sin email_completo.

### 8.3 Modal frontend

**UI**:
- Click en fila abre modal centrado ~60-70% viewport.
- Header: nombre/email remitente, fecha, status pill.
- Sección "Email": asunto + cuerpo reformateado.
- Sección "Clasificación": status, score, razón, talento, categoría.
- Cerrar: X, ESC, clic fuera.
- Dark mode coherente.

**Reformateado**:
- `formatLeadEmail(text)` aplica D11.
- `email_completo` NULL → fallback.
- `email_truncated` True → banner amarillo "Cuerpo truncado por tamaño (>1 MB)".

### 8.4 Click en talento → filtrar

**UI**:
- Talento en cada fila es clickable.
- Click filtra lista.
- Chip "Talento: <nombre> [×]" arriba de la lista.

**Backend**:
- `GET /leads?talent_id=X` — query param opcional.
- 400 si inválido. Lista vacía si sin leads.

**Tests**: filtro válido, inválido, talent_id sin leads.

### 8.5 Documentación n8n (sin aplicar)

`.planning/phases/08-leads-interactivos/N8N_CHANGES.md`:
- Flujo actual de n8n (best guess).
- Cambio: mover create-org ANTES del filtro de bloqueo, blacklist (SHEIN) ANTES del create-org.
- Plan de aplicación cuando Luis dé OK.

---

## Reglas de operación

1. Discovery primero.
2. Un commit por sub-objetivo.
3. Migración reversible: probar `alembic downgrade -1` antes de merge.
4. Backup local: `sqlite3 seg.db ".backup seg.db.backup-pre-fase-8"`.
5. No tocar producción hasta validación local.
6. Lectura sobre Pipedrive/Trello/Sheets, escritura solo a SQLite local.
7. Si surge decisión no cubierta por D1-D11, pausar y preguntar.
8. Pausa después de 8.5.

---

## Definición de "Fase 8 completa"

- [ ] 8.1: Migración + sync + bleach
- [ ] 8.2: Endpoint detalle
- [ ] 8.3: Modal con heurística
- [ ] 8.4: Filtro por talento
- [ ] 8.5: `N8N_CHANGES.md`
- [ ] D8-D11 aplicadas
- [ ] 210+ tests verdes
- [ ] Branch con commits granulares
- [ ] Validación visual local
- [ ] SUMMARY y HALLAZGOS en `.planning/phases/08-leads-interactivos/`

---

## Orden de implementación

1. Discovery
2. 8.1: Migración + sync + bleach
3. 8.2: Endpoint detalle
4. 8.3: Modal + heurística D11
5. 8.4: Filtro por talento
6. 8.5: Documentación n8n
7. Pausa — opcionales

---

**Documento generado**: 30 de junio 2026, post-Fase 7. Decisiones D1-D11 cerradas.
