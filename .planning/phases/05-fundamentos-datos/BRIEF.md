# Fase 5 — Fundamentos de datos + bugs menores

**Fecha de planeación**: 25 de junio 2026, post-reunión con cliente
**Branch**: `fase-5-fundamentos-datos`
**Estimado**: 7-9 horas
**Prerequisito**: ninguno (es la base de las fases siguientes)

---

## Contexto

Hoy tuve una reunión de revisión del dashboard con Luis Santillán, CEO de Talent Agency (SEG). El dashboard ya está desplegado en EasyPanel (`automatizacion-dashboard-seg.slt9e0.easypanel.host`) y operando con datos reales: 482 deals, 21 talentos, 179 TrelloCards.

Durante la sesión Luis identificó que varios datos no reflejan correctamente su operación. El segundo pago ($4,650 + IVA) no se cobró porque considera que el MVP aún no satisface su definición de "listo". El cobro de los $9,300 + IVA restantes queda contra entrega de las fases acordadas.

De la reunión surgieron 17 ajustes agrupados en 7 fases. Esta sesión cubre **únicamente la Fase 5** — los fundamentos de datos, sin los cuales todo lo demás muestra cifras equivocadas. Adicionalmente incluye una sección 5.5 con bugs menores conocidos de versiones anteriores que conviene resolver en este mismo barrido.

---

## Lo que Luis dijo textualmente (citas de la reunión)

**Sobre la lógica de "Ganado"**:
> "Ganado, Alexis, no es ¿qué que hayan pagado? Ganado significa que ya firmaron el contrato. Si está aquí en contrato y factura es porque está en proceso de firma, pero no significa que ya esté ganado ni que esté firmado."
> "Entonces sí hay que corregir eso porque si no, los datos van a estar mal interpretados."

**Sobre Don Silverio y Don Wicho**:
> "Hay que cambiar eso de Don Silverio Don Wicho para que siempre salga Don Silverio y Wicho, porque nunca se venden aparte. O sea, siempre están juntos."

**Sobre la fecha de cierre**:
> "Los datos de CRM, no incluyen la fecha de cierre de firma de contratos, pero que puedo filtrar desde junio de 2026, que son los ganados, se los está poniendo como ganados. Don Silverio, contrato dice... este ya pasó, no es de junio."

**Sobre el agente AI**:
> "Habíamos quedado tú y yo que cuando están enganados significa que está cerrado el contrato. Entonces si este no está ganado, o no aparece ganado, ¿por qué lo aparece aquí?"

---

## Objetivos de Fase 5

### 5.1 Lógica "Ganado" correcta

**Problema**: Hoy varios queries tratan `Deal.stage_name == 'Contrato'` como ganado/cerrado. Esto incluye deals que en realidad están en proceso de firma. Resultado: KPIs inflados, Top 3 contaminado, agente reporta deals no firmados como ganados.

**Definición correcta de "Ganado"**: `Deal.status == 'won'` (y solo eso).

**Archivos potencialmente afectados** (a confirmar en discovery):
- `app/services/kpis.py` — KPIs de Resumen y Por Talento (especialmente la vista de Flujo de dinero)
- `app/services/reports.py` — Top 3, totales del reporte
- `app/services/funnel.py` — revisar si el conteo cuadra
- `app/services/agent.py` o donde viva la lógica del agente
- `app/routers/*.py` — cualquier endpoint que filtre por cerrado

**Tests a correr**: validar que el total de "ganados" del dashboard coincida con el total de deals con `status='won'` en Pipedrive (consultable vía API).

---

### 5.2 Don Silverio + Don Wicho fusionados

**Problema**: En el ranking aparece solo "Don Wicho", no "Don Silverio". Luis confirmó que jamás se venden por separado — siempre como dúo.

**Estado actual**: Ya están mapeados al mismo `pipedrive_product_id` (producto "Don Silverio y Don Wicho" en Pipedrive). Ver `app/scripts/match_talent_products.py`, sección `MANUAL_PRODUCT_MATCHES`.

**Lo que falta**: En `app/scripts/seed_talents.py`, la lista `TALENT_NAMES` tiene "Don Silverio" y "Don Wicho" como dos entradas separadas. Debe ser una sola: "Don Silverio y Don Wicho".

**Pasos**:
1. Modificar `seed_talents.py`: combinar las dos entradas en una "Don Silverio y Don Wicho".
2. Actualizar `MANUAL_PRODUCT_MATCHES` en `match_talent_products.py` para reflejar el nuevo nombre.
3. Decidir qué hacer con los deals históricos asignados al `talent_id` viejo de "Don Silverio" o "Don Wicho":
   - Opción A: re-mapear todos los deals al nuevo talent_id fusionado.
   - Opción B: dejarlos huérfanos y considerar solo deals nuevos.
   - **Recomendado**: Opción A — escribir migración Alembic que re-mapee y luego borre los talent_ids viejos.
4. Verificar que el ranking de Resumen muestre la entrada fusionada.

**Cuidado**: este cambio impacta cualquier vista que filtre por talento. Probar el dashboard completo después del cambio (Resumen, Por Talento, Reportes, Agente).

---

### 5.3 Fecha de cierre/firma en modelo Deal

**Problema**: El modelo `Deal` no tiene un campo que represente cuándo se firmó el contrato. Esto impide que el agente filtre correctamente por "firmados en junio 2026".

**Pipedrive v2** entrega los siguientes campos relevantes:
- `won_time` — timestamp ISO cuando el deal pasó a status=won
- `close_time` — timestamp de cierre (won o lost)
- `local_won_date` — fecha en zona horaria local

**Recomendación**: usar `won_time` (es el más universal y explícito).

**Pasos**:
1. Agregar columna `won_time` (DateTime, nullable) al modelo `Deal` en `app/models.py`.
2. Crear migración Alembic: `alembic revision --autogenerate -m "add won_time to Deal"`.
3. Modificar `app/sync/jobs.py::sync_pipedrive` para extraer `won_time` del payload y persistirlo.
4. Actualizar `app/schemas/` donde corresponda para exponer el campo.
5. Re-sincronizar deals en local para poblar `won_time`.
6. Tests: verificar que los deals con `status=won` tienen `won_time` no nulo.

**Cuidado con timezone**: Pipedrive envía UTC. Guardar UTC. Convertir a `America/Mexico_City` solo al renderizar.

---

### 5.4 Agente actualizado

**Problema**: El agente AI del dashboard usa lógica de "cerrado" que incluye deals en stage "Contrato" (incorrecto). Resultado: cuando Luis pregunta "¿qué cerramos en junio?", el agente le devuelve deals que aún no están firmados.

**Archivos involucrados**: el agente probablemente vive en `app/services/agent.py` o similar, con un prompt que el LLM interpreta. Confirmar en discovery.

**Cambios al prompt** (a aplicar tras 5.1 y 5.3):
- Definir explícitamente qué significa "ganado", "firmado", "cerrado": `Deal.status == 'won'`.
- Definir qué significa "cobrado": viene de Trello, lista "cerrado" o equivalente.
- Indicar al agente que use `won_time` (no `update_time` ni `add_time`) cuando el usuario pida filtros por fecha de cierre.
- Agregar al prompt un ejemplo claro: si el usuario pregunta "deals firmados en junio 2026", el agente debe filtrar por `status='won' AND won_time BETWEEN '2026-06-01' AND '2026-06-30'`.

**Tests**: pedirle al agente "¿cuántos deals se firmaron en mayo 2026?" y verificar que la respuesta coincida con el conteo manual en Pipedrive.

---

### 5.5 Bugs menores conocidos (limpieza en el mismo barrido)

Estos bugs son rápidos individualmente pero acumulados degradan la percepción de calidad. Se resuelven en este mismo branch porque caen bien junto con los cambios de datos.

#### 5.5.1 Login case-sensitive

**Problema**: Al hacer login, si el usuario fue registrado como `santillan@talentagency.mx` y se escribe `Santillan@talentagency.mx` (con mayúscula), el sistema lo rechaza. Este comportamiento es incorrecto: el email NO es case-sensitive en la práctica.

**Solución**: en `app/auth.py` o donde se valide el login, normalizar el username/email a lowercase antes de comparar contra DB. También normalizar al momento de crear usuario para que toda la DB esté en lowercase.

**Cuidado**:
- Si la contraseña hashed se generó usando el username con mayúsculas (no debería pero verificar), el hash debe seguir coincidiendo porque normalmente se hashea solo el password, no el username.
- La columna `username` o `email` en DB puede ya tener registros con mayúsculas. Si es así, hacer un UPDATE para lowercase-arlos como parte de la migración.
- Tests: probar login con la misma cuenta usando combinaciones de mayúsculas/minúsculas, todas deben funcionar.

**Decisión a tomar en discovery**: ¿el cambio es solo en login (más laxo) o también al crear/actualizar usuarios (normalizar en escritura)? Recomendación: ambos, para mantener DB consistente.

#### 5.5.2 "Última sync: hace 0 min" siempre

**Problema**: El indicador del header arriba a la derecha siempre muestra "hace 0 min" en producción, incluso cuando no ha sincronizado recientemente.

**Solución**: revisar el endpoint `/api/sync-status` (o como se llame) y el JS que lo renderiza. Probablemente está calculando mal el delta o usando timezone incorrecto, o el frontend hace cache del valor.

**Test**: verificar que muestre el tiempo correcto en producción después de un sync manual.

**Nota**: este bug originalmente estaba asignado a Fase 6 en el plan general. Se trae a 5.5 porque es rápido y mejora la percepción de inmediato.

#### 5.5.3 Confirmar: ¿otros bugs menores?

Durante el discovery, si Claude Code encuentra otros bugs pequeños no relacionados con datos (un texto mal escrito, un botón que no funciona, un endpoint que devuelve 500), agregarlos como 5.5.4, 5.5.5, etc. **siempre que sean cambios menores a 30 minutos de implementación**. Cualquier cosa más grande va a `.planning/phases/05-fundamentos-datos/HALLAZGOS.md` para discutir después.

---

## Reglas de operación durante esta sesión

1. **Antes de tocar código**, hacer discovery: leer los archivos potencialmente afectados y proponer un plan concreto. No editar a ciegas.
2. **Un commit por sub-objetivo**. Mensajes claros con prefijo `fix(fase-5.X):` o `feat(fase-5.X):`.
3. **Las migraciones Alembic deben ser reversibles** — incluir `downgrade()` explícito.
4. **Antes de cualquier migración**: backup de `seg.db` local (`cp seg.db seg.db.backup-pre-fase-5`).
5. **No tocar producción** hasta que toda Fase 5 esté validada en local. El deploy a EasyPanel es paso aparte, lo decidiremos juntos.
6. **No fusionar Fase 5 a `main`** hasta validación completa.
7. **No avanzar a Fase 6 ni a otras fases en esta sesión**.
8. **Si surge una decisión arquitectónica importante** (ej. cómo mapear deals huérfanos), pregúntale al usuario antes de decidir solo.

---

## Definición de "Fase 5 terminada"

- [ ] 5.1: KPIs, Top 3, reportes y agente usan `status='won'` exclusivamente (no `stage='Contrato'`).
- [ ] 5.2: Ranking muestra "Don Silverio y Don Wicho" como una sola entrada; deals históricos re-mapeados.
- [ ] 5.3: Modelo Deal tiene `won_time`; migración Alembic reversible; sync poblado.
- [ ] 5.4: Agente filtra correctamente por `won_time` cuando se le pregunta por periodo.
- [ ] 5.5.1: Login case-insensitive funcionando.
- [ ] 5.5.2: Indicador "Última sync" muestra tiempo real.
- [ ] Todos los tests existentes siguen pasando.
- [ ] Branch `fase-5-fundamentos-datos` con commits granulares listos para review.
- [ ] Documentación corta del cambio en `.planning/phases/05-fundamentos-datos/`.

---

## Lo que NO entra en esta fase (para evitar scope creep)

- Conexión de Trello al funnel (Fase 6).
- Filtros por fecha en UI (Fase 7).
- Click en talento/lead (Fase 8).
- Rediseño del reporte PDF (Fase 9).
- Deploy de Fase 2 a producción (Fase 10).
- Automatizaciones nativas en Pipedrive (Fase 11).

Si durante el discovery aparecen otros bugs no relacionados, anotarlos en `.planning/phases/05-fundamentos-datos/HALLAZGOS.md` para discutir después — no arreglar ahora.

---

## Orden de implementación recomendado

1. **5.3 primero** (agregar `won_time` al modelo + migración + sync). Sin esto, 5.4 no puede usar la fecha.
2. **5.1 después** (cambiar lógica de "ganado" en queries). Ya con `won_time` disponible.
3. **5.2 luego** (fusionar Don Silverio y Don Wicho). Es independiente de los anteriores.
4. **5.5.1 y 5.5.2** en cualquier momento — son independientes.
5. **5.4 al final** (actualizar agente). Necesita que 5.1 y 5.3 estén hechos.

---

## Recursos de referencia

- Repo: `~/Developer/projects/lumixia/clients/santillan-ent/seg-dashboard`
- Producción: `https://automatizacion-dashboard-seg.slt9e0.easypanel.host/`
- Variables de entorno producción: en EasyPanel UI (no committeadas)
- Comando para levantar local: `DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn app.main:app --reload --port 8000`
- Comando para correr seed: `python -m app.scripts.seed_talents`
- Comando para correr match: `python -m app.scripts.match_talent_products`

---

**Documento generado**: 25 de junio 2026, tras reunión con cliente.
