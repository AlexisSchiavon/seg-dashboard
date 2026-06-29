# Fase 6 — Trello al funnel

**Fecha de planeación**: 26 de junio 2026, post-Fase 5
**Branch**: `fase-6-trello-al-funnel`
**Estimado**: 3-5 horas
**Prerequisito**: Fase 5 mergeada a main ✅ (validada en producción)

---

## Contexto

Tras completar Fase 5 (fundamentos de datos) y el hotfix del sync, el dashboard ya muestra datos confiables sobre deals de Pipedrive. Sin embargo, hay un problema visible en el funnel comercial que Luis señaló en la reunión del 25 de junio:

**El funnel muestra `0` en las etapas "En ejecución" y "Cobranza" aunque en Trello hay actividad real.**

La causa raíz está documentada literalmente en `app/services/funnel.py`:

> `# "En ejecución" and "Cobranza" have no Pipedrive data source until Phase 4 (Trello); they are always emitted with count=0, amount=0.0 until then.`

El funnel solo consulta la tabla `Deal` (de Pipedrive). Nunca consulta `TrelloCard`. Las 190 cards que se sincronizan correctamente cada hora se quedan invisibles para el funnel.

El frontend ya muestra badges "VÍA TRELLO" en esas dos etapas (commit `6e3c3d2` de la Fase 8 pre-junta), preparándose para este momento. El badge se queda, pero ahora con datos reales detrás.

---

## Estado actual de los datos (verificado 26 jun 2026)

### Tabla `trello_cards`

**Esquema real**:
```
id (INTEGER, PK)
trello_card_id (VARCHAR)
name (VARCHAR)
list_id (VARCHAR)
list_name (VARCHAR)
list_state (VARCHAR)          ← 'ejecucion', 'cobranza', 'cerrado'
deal_id (INTEGER, FK a deals.id, nullable)
pipedrive_deal_id_desc (INTEGER, nullable)   ← Pipedrive deal_id mencionado en descripción de card
collection_date (DATE, nullable)
synced_at (DATETIME)
```

**Importante**: el link a Deal se llama `deal_id` (no `pipedrive_deal_id`). Es un FK al `id` LOCAL de `deals`, no al `pipedrive_deal_id` de Pipedrive.

**Distribución actual en local**:

| `list_state` | Cards |
|---|---|
| `ejecucion` | 100 |
| `cobranza` | 59 |
| `cerrado` | 31 |
| **Total** | **190** |

**Linking a deals**:
- **124 cards (65%)** tienen `deal_id` poblado → `SUM(Deal.value)` viable
- **66 cards (35%)** tienen `deal_id` NULL → huérfanas
- **84 cards** tienen `pipedrive_deal_id_desc` (mencionado en descripción)
- **106 cards** no tienen ningún link a deal

### Tabla `deals` (estado abierto)

| `stage_name` | Deals |
|---|---|
| Llamada | 53 |
| Cotización | 22 |
| Negociación | 54 |
| Contrato | 11 |

---

## Lo que Luis dijo en la reunión

Aunque no hay una cita textual única sobre el funnel, durante la reunión Luis señaló dos veces que los números del dashboard "no le cuadran" con su operación real. En el funnel hay una alerta de cuello de botella que dice "solo el 0% de los deals en Contrato avanzan a En ejecución". Esta alerta es matemáticamente correcta dado los datos actuales (11 deals en Contrato, 0 en ejecución), pero es engañosa porque ignora que "En ejecución" se mide en Trello, no en Pipedrive.

En el plan post-reunión quedó clara la prioridad: **conectar Trello al funnel es Fase 6, crítica**, junto con Fase 5 y Fase 10 como las tres que más impactan la percepción de "ya funciona".

---

## Objetivos de Fase 6

### 6.1 Conectar TrelloCard al funnel (crítico)

**Problema**: `app/services/funnel.py::funnel_overview()` y `talent_funnel()` solo consultan la tabla `Deal`. Nunca leen `TrelloCard`. Resultado: las 100 cards en ejecución y 59 en cobranza no aparecen en el funnel.

**Definición del mapeo** (ya validado en local y producción):

| TrelloCard `list_state` | Stage del funnel |
|---|---|
| `'ejecucion'` | "En ejecución" |
| `'cobranza'` | "Cobranza" |
| `'cerrado'` | (no se cuenta en funnel — son ya cobrados/cerrados) |

**Archivos afectados** (confirmar en discovery):
- `app/services/funnel.py` — funciones `funnel_overview()` y `talent_funnel()`
- `app/services/kpis.py` — verificar si algún KPI usa el funnel y necesita ajuste
- Tests en `tests/test_funnel.py`

**Decisiones aprobadas (D1-D5)**:

**D1 (cómo calcular el `amount` de las etapas Trello)**:
- **Decisión: Opción A** — Sumar el `Deal.value` de los deals asociados a cada TrelloCard (vía `TrelloCard.deal_id`). Esto refleja "monto en ejecución" real.
- Implementación: `JOIN deals ON trello_cards.deal_id = deals.id WHERE list_state IN ('ejecucion', 'cobranza')`.

**D2 (cómo manejar TrelloCards sin deal asociado — 35% del total)**:
- **Decisión: Opción B** — Incluirlas en `count` pero contribuyen `0` al `amount`.
- Razonamiento: ignorarlas oculta cards reales en ejecución. Inventar su valor es engañoso. Lo más honesto es contarlas con monto 0.
- Implementación: `LEFT JOIN deals ON trello_cards.deal_id = deals.id`, sumar `COALESCE(deals.value, 0)`.

**D3 (cuello de botella tras el fix)**:
- **Decisión**: Recalcular bottleneck con todas las 6 etapas (incluyendo las dos de Trello).
- Razonamiento: para eso existe la heurística — para detectar dónde se atoran los deals end-to-end.
- Verificar que el cálculo no se rompa cuando una etapa Trello tiene `count=0` (puede pasar al inicio de talentos nuevos).

**D4 (talent_funnel y filtros por talento)**:
- **Decisión**: filtrar TrelloCards por talento vía `Deal.talent_id` (joined through `deal_id`).
- Consecuencia: TrelloCards sin `deal_id` NO aparecerán en la vista por talento (no se les puede atribuir un talento). Aceptable porque son "cards huérfanas" que probablemente sean ruido.
- En el funnel global sí aparecen las 66 huérfanas (porque ahí no se filtra por talento).

**D5 (qué pasa con las TrelloCards `cerrado`)**:
- **Decisión**: NO entran al funnel.
- Razonamiento: "Cerrado" en Trello significa ya cobrado y archivado. El funnel solo muestra etapas activas. Si se quisiera "deals cobrados", eso es un KPI distinto, no una etapa del funnel.
- Ya está reflejado en `STAGES = ["Llamada", "Cotización", "Negociación", "Contrato", "En ejecución", "Cobranza"]` (no incluye "Cerrado").

### 6.2 Bug "105 deals actualizados" siempre igual (H-03)

**Problema**: La UI del dashboard muestra arriba un indicador del último sync que siempre dice "105 deals actualizados" o similar, sin importar cuántos deals realmente cambiaron en el sync. Esto degrada la confianza en lo que muestra el dashboard.

**Causa probable**: El número "105" parece ser el conteo de TrelloCards procesadas (no deals). El frontend o el endpoint `/sync/status` muestra ese número como si fueran deals, cuando en realidad es un conteo total de items procesados, posiblemente del último SyncLog (de cualquier source).

**Solución** (a confirmar en discovery):
- Investigar dónde se calcula y muestra ese número en el frontend (`dashboard.js` o `app.js`)
- Investigar qué devuelve `/sync/status` exactamente
- Asegurarse de que el indicador muestre algo significativo. Dos opciones:
  - **Opción A**: Solo mostrar el conteo del último sync de Pipedrive: "X deals actualizados desde Pipedrive"
  - **Opción B**: Mostrar tres números por separado: "Pipedrive: X | Trello: Y | Sheets: Z"
- **Recomendación**: Opción A. Es lo que Luis espera ver: cuántos deals nuevos/cambiados desde el último sync.

**Test**: tras un sync incremental de Pipedrive que traiga 0 deals, el indicador debe mostrar 0 (no 105).

### 6.3 Verificar regresión visual y matemática

**Archivos afectados a regresionar**:
- Badge "VÍA TRELLO" en frontend (`dashboard.js`) debe seguir mostrándose en las dos etapas.
- Frontend de funnel global y de funnel por talento debe seguir renderizando 6 etapas (no romper si una etapa tiene `amount=0`).
- Alerta de cuello de botella debe seguir teniendo sentido con los nuevos datos.

**Tests adicionales a correr** después del cambio:
- `tests/test_funnel.py` — todos siguen pasando + casos nuevos para TrelloCards
- Validación visual: cargar el dashboard local y verificar:
  - "En ejecución" muestra ~100 cards y un `amount` razonable (suma de deals linkeados)
  - "Cobranza" muestra ~59 cards y un `amount` razonable
  - La conversión etapa-a-etapa cuadra
  - El badge VÍA TRELLO sigue ahí
  - Sin errores en consola del navegador

---

## Reglas de operación durante esta sesión

1. **Antes de tocar código**, hacer discovery: leer `funnel.py`, `models.py` (sección TrelloCard), `dashboard.js` (sección funnel), y `test_funnel.py`. Proponer plan concreto.
2. **Un commit por sub-objetivo**. Mensajes: `feat(fase-6.1):`, `fix(fase-6.2):`.
3. **Sin migraciones**. Esta fase es solo lectura sobre tablas existentes. Si Claude Code dice que necesita una migración, pausa y pregunta.
4. **Backup de DB local ya hecho**: `seg.db.backup-pre-fase-6`.
5. **No tocar producción** hasta toda Fase 6 validada en local + merge a main aprobado.
6. **No avanzar a Fase 7 ni a otras fases en esta sesión**.
7. **Si surge una decisión arquitectónica importante**, pregunta antes de decidir solo.
8. **Mantener la regla irrompible**: lectura sobre Pipedrive/Trello/Sheets. Escritura solo a SQLite local.

---

## Definición de "Fase 6 terminada"

- [ ] 6.1: Funnel global muestra count + amount reales en "En ejecución" y "Cobranza".
- [ ] 6.1: Funnel por talento (`talent_funnel`) también muestra esos números, filtrados correctamente.
- [ ] 6.1: Las decisiones D1-D5 reflejadas en el código.
- [ ] 6.2: Indicador "X deals actualizados" muestra el conteo correcto (solo Pipedrive).
- [ ] 6.3: Badge "VÍA TRELLO" sigue visible. Cuello de botella se recalcula correctamente.
- [ ] Todos los tests existentes (165) siguen pasando.
- [ ] Branch `fase-6-trello-al-funnel` con commits granulares listos para review.
- [ ] Validación visual en local antes de mergear.
- [ ] Documentación corta del cambio en `.planning/phases/06-trello-al-funnel/`.

---

## Lo que NO entra en esta fase (para evitar scope creep)

- Filtros por fecha en UI (Fase 7).
- Click en talento/lead en pestaña Leads (Fase 8).
- Rediseño del reporte PDF (Fase 9).
- Deploy de M2 Pipedrive→Trello a producción (Fase 10).
- Automatizaciones nativas en Pipedrive (Fase 11).
- Limpieza de tarjetas duplicadas en Trello (Fase 10.4).
- Mejorar el matching de TrelloCards huérfanas (subir el 65% de linking).

Si durante discovery aparecen otros bugs no relacionados, anotar en `.planning/phases/06-trello-al-funnel/HALLAZGOS.md`.

---

## Recursos de referencia

- Repo: `~/Developer/projects/lumixia/clients/santillan-ent/seg-dashboard`
- Producción: `https://automatizacion-dashboard-seg.slt9e0.easypanel.host/`
- Comando para levantar local: `DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`
- Backup pre-fase: `seg.db.backup-pre-fase-6` (460K, consolidado con `.backup`)
- Conteos verificados en local al 26 jun: TrelloCards `ejecucion: 100, cobranza: 59, cerrado: 31`; 124 con `deal_id`, 66 sin.

---

## Orden de implementación recomendado

1. **6.1 primero**: el cambio central. Modificar `funnel.py`, agregar tests, validar visualmente.
2. **6.2 después**: depende del frontend. Sin esto, Luis sigue viendo "105 actualizados" engañoso.
3. **6.3 al final**: regresión visual y matemática. Ya está implícito en los tests pero vale la pena verificarlo explícitamente.

---

**Documento generado**: 26 de junio 2026, post-Fase 5 + hotfix de sync.
**Última actualización**: misma fecha, con datos reales verificados en local.
