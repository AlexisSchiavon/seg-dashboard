# Fase 7 — Filtros por fecha (mes / trimestre)

**Fecha de planeación**: 30 de junio 2026, post-Fase 6
**Branch**: `fase-7-filtros-fecha`
**Estimado**: 4-6 horas
**Prerequisito**: Fase 5 + Fase 6 mergeadas a main ✅ (validadas en producción)

---

## Contexto

En la reunión del 25 de junio, Luis pidió poder filtrar el dashboard por mes y trimestre. Hoy, la pestaña Por Talento y el Reporte muestran datos "all-time" sin posibilidad de acotar el periodo, lo que dificulta responder preguntas como "¿qué firmamos este mes con Mariana?" o "¿cómo nos fue el Q2?".

Tras Fase 5 (donde se agregó `Deal.won_time`), ya tenemos la base para filtrar correctamente por fecha de firma. Fase 7 expone ese filtro al usuario en las vistas donde tiene sentido de negocio.

---

## Filosofía del filtro (decisiones clave tomadas antes del brief)

Estas decisiones de producto las acordamos antes de escribir el brief y son la guía maestra de la implementación. Si en el discovery algo no encaja con esto, pausar y preguntar.

### D1 — No hay filtro global

No se agrega un filtro global de fecha al header del dashboard. Cada vista que tiene selector lo maneja independientemente.

### D2 — Default siempre es mes actual

Donde haya selector, el valor por defecto es el mes en curso (junio 2026 hoy).

### D3 — Dónde sí hay selector

| Vista | Selector |
|---|---|
| Resumen | NO (mes actual implícito, sin UI) |
| Por Talento | SÍ (mes / trimestre) |
| Funnel global | NO (es snapshot del estado actual) |
| Reporte PDF | SÍ (mes / trimestre) |
| Leads | NO (los leads no se filtran por periodo) |

**Razonamiento del Funnel global sin selector**: el funnel es una herramienta operativa de pipeline ("qué tengo hoy y dónde se atora"), no histórica. Filtrarlo por periodo lo convierte en un reporte de cohort que pierde su utilidad como funnel.

### D4 — Qué métricas se filtran (lo más importante)

**Diferentes métricas usan diferentes campos de fecha**. No todo se filtra por la misma fecha porque cada KPI responde una pregunta de negocio distinta.

Cuando Luis selecciona "Junio 2026" en Por Talento:

| Métrica | Filtro | Campo |
|---|---|---|
| Campañas firmadas | SÍ | `Deal.won_time` |
| Histórico de ingresos por mes | SÍ | `Deal.won_time` |
| Top 3 campañas (firmadas) | SÍ | `Deal.won_time` |
| Oportunidades perdidas (dona) | SÍ | `Deal.close_time` o `lost_time` si está disponible |
| Embudo del talento (pipeline activo) | NO | snapshot del estado |
| Cobrado en el periodo | SÍ | TrelloCard `collection_date` o equivalente |
| Pendiente por cobrar | NO | es un estado, no un periodo |
| Calendario de cobranza | SÍ | TrelloCard `collection_date` |

**Razonamiento**: el "pipeline activo" es un estado vivo del negocio — Luis nunca pregunta "¿qué tan grande era mi pipeline en marzo?". Pregunta "¿qué cerramos en marzo?". Por eso lo abierto (pipeline, pendiente) no se filtra, y lo cerrado (firmado, cobrado, perdido) sí.

### D5 — Granularidad: mes + trimestre, no año ni custom

- **Mes**: año-mes (ej. "2026-06")
- **Trimestre**: año-trimestre (ej. "2026-Q2")
- **No** se agrega selector de año (redundante: ya está implícito al elegir mes/trimestre)
- **No** se agrega rango custom (nice-to-have, fuera de scope)

---

## Estado actual del código (verificado 30 jun 2026)

### Patrón existente que reutilizar

`app/services/reports.py:95` ya filtra por mes usando `month_prefix = f"{month}%"` con `LIKE` sobre `Deal.add_time`. Este patrón funciona, pero usa el campo equivocado para Fase 7 (debe ser `won_time`, no `add_time`).

`app/services/kpis.py:254` ya tiene `deals_won_in_period(start_date, end_date)` creado en Fase 5.4 para el agente. Filtra correctamente por `won_time`. **Este es el patrón canónico a generalizar para Fase 7**.

### Endpoints afectados

- `GET /dashboard/talents/{talent_id}` (`app/routers/dashboard.py:126`) — pestaña Por Talento. Recibirá `period_type` y `period_value` opcionales.
- `POST /reports/generate` (`app/routers/reports.py:63`) — generación del PDF. Ya recibe `month` pero hay que extenderlo a trimestre.
- `GET /reports/months` (`app/routers/reports.py:54`) — lista meses disponibles. Posiblemente agregar `GET /reports/quarters` paralelo.

### Endpoints que NO se tocan

- `GET /dashboard/summary` — sigue mostrando snapshot all-time
- `GET /dashboard/funnel` — sigue siendo snapshot
- `GET /leads` y `GET /leads/summary` — no aplica filtro de periodo

---

## Objetivos de Fase 7

### 7.1 Backend — Parametrizar endpoints con periodo

**Cambios al endpoint `/dashboard/talents/{talent_id}`**:

Aceptar query params:
- `period_type`: `"month"` o `"quarter"` (default: `"month"`)
- `period_value`: string en formato `"2026-06"` para mes o `"2026-Q2"` para trimestre (default: mes actual)

Lógica interna:
1. Parsear `period_value` a `start_date` y `end_date` (UTC).
2. Aplicar el filtro **solo a las métricas que corresponden** según D4:
   - KPI "Campañas firmadas" → filtrar deals por `won_time` en el rango
   - Histórico de ingresos por mes → si se eligió mes, mostrar solo ese mes con valor real + meses circundantes estimados (comportamiento actual). Si se eligió trimestre, mostrar los 3 meses del trimestre con sus valores reales.
   - Top 3 campañas firmadas → filtrar por `won_time` en el rango
   - Dona de perdidos → filtrar por `close_time` o `lost_time` en el rango (verificar qué campo está disponible)
   - **NO** filtrar: embudo del talento, pendiente por cobrar

Crear función helper en `app/services/periods.py` (nuevo módulo):
```python
def parse_period(period_type: str, period_value: str) -> tuple[date, date]:
    """Returns (start_date, end_date) inclusive for a given period."""
```

**Cambios al endpoint `/reports/generate`**:

Aceptar `period_type` y `period_value` igual que arriba. Generar el PDF respetando ese periodo. Mantener compatibilidad: si solo viene `month` (parámetro actual), tratarlo como `period_type=month, period_value=month`.

### 7.2 Frontend — Selectores en Por Talento y Reporte

**En la pestaña Por Talento**:

Agregar arriba del selector de talento (o al lado, según el diseño) dos controles:
- Toggle Mes / Trimestre
- Dropdown del valor específico (lista de meses recientes o lista de trimestres)

Comportamiento:
- Al cambiar el selector, recargar el panel del talento actual con el nuevo periodo
- Mostrar visualmente qué periodo se está viendo (ej. "Mostrando: Junio 2026")
- Para los widgets que NO se filtran (embudo, pendiente), agregar tooltip o label aclaratorio: "Estado actual"

**En la pestaña Reporte**:

Mismo patrón. Selector de mes/trimestre al lado del selector de talento. Default mes actual. Generar PDF con esos parámetros.

**Diseño UI**:
- Discreto, no debe robar protagonismo al selector de talento
- Dark mode consistente con el resto del dashboard
- Estilos en `frontend/css/styles.css` siguiendo convenciones existentes

### 7.3 Helpers compartidos

**`app/services/periods.py`** (nuevo módulo):
- `parse_period(period_type, period_value) -> (start, end)`
- `current_month_value() -> str` (devuelve "2026-06")
- `current_quarter_value() -> str` (devuelve "2026-Q2")
- `available_months(db) -> list[str]` (meses con al menos 1 deal won)
- `available_quarters(db) -> list[str]` (trimestres con al menos 1 deal won)

Tests unitarios para `parse_period` cubriendo edge cases (mes inválido, trimestre inválido, fin de mes, año cambia entre Q4 y Q1).

### 7.4 Refactor controlado de `kpis.deals_won_in_period`

La función existe pero usa `(start_date, end_date)`. Asegurar que el endpoint `/dashboard/talents/{talent_id}` la reutilice (no duplicar lógica). Si hay diferencias en formato, hacer un adapter limpio, no escribir queries nuevas.

---

## Decisiones técnicas (D6-D8) — Aprobadas

**D6 — Formato de `period_value` en API**:
- Mes: `"YYYY-MM"` (ej. `"2026-06"`)
- Trimestre: `"YYYY-QN"` (ej. `"2026-Q2"`)
- Validar con regex en el endpoint y devolver 400 si no cumple.

**D7 — Timezone**:
- Guardamos UTC en DB (ya es así por `DateTime(timezone=True)` de Fase 5.3).
- Las queries de periodo se hacen en UTC.
- "Junio 2026" significa `2026-06-01 00:00:00 UTC` a `2026-06-30 23:59:59 UTC`.
- Aceptable: hay deals firmados a las 23:30 hora México que aparecerán como del día siguiente UTC. Se documenta en código pero no se ajusta — la complejidad de timezone-correct ranges no justifica el beneficio.

**D8 — Compatibilidad de `/reports/generate`**:
- Mantener parámetro `month` como deprecated alias de `period_type=month, period_value=<month>`.
- Si llegan ambos, prevalece `period_type/period_value`.
- En la documentación interna, marcar `month` como deprecated.

---

## Reglas de operación durante esta sesión

1. **Antes de tocar código**, hacer discovery: leer `kpis.deals_won_in_period`, `reports.py` (lógica de `month_prefix`), `dashboard.py:126`, y el frontend de Por Talento + Reporte. Proponer plan concreto.
2. **Un commit por sub-objetivo**. Mensajes: `feat(fase-7.1):`, `feat(fase-7.2):`, `feat(fase-7.3):`.
3. **Sin migraciones**. Esta fase solo lee de `won_time` (que ya existe). Si Claude Code dice que necesita una migración, pausa y pregunta.
4. **Backup local antes de cualquier cambio destructivo**: `sqlite3 seg.db ".backup seg.db.backup-pre-fase-7"`.
5. **No tocar producción** hasta toda Fase 7 validada en local + merge a main aprobado.
6. **No avanzar a Fase 8 ni a otras fases en esta sesión**.
7. **Mantener la regla irrompible**: lectura sobre Pipedrive/Trello/Sheets. Escritura solo a SQLite local.
8. **Si surge una decisión arquitectónica importante no cubierta por D1-D8**, pausa y pregunta antes de decidir solo.

---

## Definición de "Fase 7 terminada"

- [ ] 7.1: `/dashboard/talents/{talent_id}` acepta `period_type` y `period_value`. Aplica filtros según D4.
- [ ] 7.1: `/reports/generate` acepta `period_type` y `period_value`. Genera PDF respetando el periodo.
- [ ] 7.2: Pestaña Por Talento tiene selector mes/trimestre con default mes actual.
- [ ] 7.2: Pestaña Reporte tiene mismo selector.
- [ ] 7.2: Widgets no filtrados (embudo, pendiente) tienen indicador "Estado actual".
- [ ] 7.3: Módulo `app/services/periods.py` con helpers + tests unitarios.
- [ ] 7.4: `kpis.deals_won_in_period` reutilizada en el endpoint nuevo (sin duplicar lógica).
- [ ] D6, D7, D8 reflejadas correctamente en el código.
- [ ] Todos los tests existentes (170+) siguen pasando.
- [ ] Branch `fase-7-filtros-fecha` con commits granulares listos para review.
- [ ] Validación visual en local antes de mergear.
- [ ] Documentación corta del cambio en `.planning/phases/07-filtros-fecha/`.

---

## Lo que NO entra en esta fase

- Filtros en el Funnel global (decisión D3).
- Filtros en Leads (decisión D3).
- Filtros en Resumen como UI (decisión D3, mes actual sigue implícito).
- Rango de fechas custom (D5).
- Click en talento/lead en pestaña Leads (Fase 8).
- Rediseño visual del PDF — solo aplicar el filtro al PDF existente. El rediseño es Fase 9.
- Deploy de M2 Pipedrive→Trello a producción (Fase 10).
- Automatizaciones nativas en Pipedrive (Fase 11).

Si durante discovery aparecen otros bugs no relacionados, anotar en `.planning/phases/07-filtros-fecha/HALLAZGOS.md`.

---

## Recursos de referencia

- Repo: `~/Developer/projects/lumixia/clients/santillan-ent/seg-dashboard`
- Producción: `https://automatizacion-dashboard-seg.slt9e0.easypanel.host/`
- Comando para levantar local: `DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`
- Función de referencia: `app/services/kpis.py:254` (`deals_won_in_period`)
- Patrón existente (sub-óptimo, pero funcional): `app/services/reports.py:95` (`month_prefix`)

---

## Orden de implementación recomendado

1. **7.3 primero** (helpers): construir `periods.py` con `parse_period` y tests unitarios. Sin esto, todo lo demás es ad-hoc.
2. **7.1 después** (backend): aplicar el filtro a los endpoints. Reutilizar `deals_won_in_period`.
3. **7.4 en paralelo a 7.1**: refactor controlado para evitar duplicación.
4. **7.2 al final** (frontend): selectores UI. Una vez backend acepta los parámetros, frontend los envía.

---

**Documento generado**: 30 de junio 2026, post-Fase 6.
