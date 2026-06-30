# Cambio propuesto en el workflow de n8n — Creación de organizaciones

> **Estado: DOCUMENTACIÓN. NO se aplica en esta sesión.**
> Este documento describe un cambio propuesto al workflow de n8n. La aplicación
> ocurre solo cuando Luis dé OK explícito, siguiendo el plan de la sección 4.
> El SEG Dashboard es SOLO LECTURA sobre Pipedrive/Trello/Sheets — este cambio
> vive 100% en n8n, fuera de este repo.

---

## 1. Contexto

En la reunión del 25 de junio, Luis pidió que se cree la **organización en
Pipedrive para todos los leads válidos**, no solo los aprobados, para tener
**trazabilidad de spam / intentos de contacto**. Hoy n8n filtra **antes** de
crear la org, así que los leads bloqueados o en revisión nunca dejan rastro en
Pipedrive — Luis no puede ver quién intentó contactar y fue descartado.

**Excepción**: la **blacklist explícita** (industrias prohibidas — SHEIN,
casinos, crypto scams) **nunca** genera organización. Esos no son "intentos de
contacto legítimos que descartamos", son spam de industrias vetadas.

---

## 2. Flujo actual de n8n (best guess)

> Aproximado, basado en lo que sabemos del sistema. La verificación exacta
> requiere abrir el workflow en la UI de n8n — lo cual **NO** se hace en esta
> sesión (se hace al aplicar el cambio, paso 4a).

```
Gmail trigger
  → Parser email
  → Clasificador GPT  (status + talento + razón + categoría)
  → Filtro 1 (status == Aprobado)
        ↓ Aprobado
      Crear Org Pipedrive
      Crear Person Pipedrive
      Crear Deal Pipedrive
      Responder email

  (en paralelo, para TODOS los leads, sin importar status)
  → Append a Google Sheet   ← por esto el dashboard ve 820 leads
```

Consecuencia actual: solo los **Aprobados** llegan a Pipedrive como org. Los
**Bloqueados** y **En revisión** solo existen en el Sheet (y por tanto en el
dashboard), sin rastro en el CRM.

---

## 3. Cambio propuesto

```
Gmail trigger
  → Parser email
  → Clasificador GPT
  → Filtro 0 (blacklist explícita: SHEIN, casinos, crypto scams)
        ↓ NO está en blacklist
      Crear Org Pipedrive  (con TAG según status)
        ↓
      Filtro 1 (status == Aprobado)
            ↓ Aprobado
          Crear Person + Crear Deal + Responder
            ↓ Bloqueado / En revisión
          Tag org como "BLOCKED_LEAD" o "REVIEW_LEAD"
          (sin responder, sin crear Deal)
        ↑ EN blacklist
      (descartar — NO crear org)
```

**Resultado**: Luis ve en Pipedrive **todas** las organizaciones que intentaron
contacto, con tags claros que distinguen aprobados / bloqueados / en revisión.
La blacklist (SHEIN, etc.) **nunca** genera org.

Cambios concretos sobre el workflow actual:
- **Mover** el nodo "Crear Org" **antes** del filtro de status.
- **Agregar** un Filtro 0 (blacklist) **antes** de "Crear Org".
- **Agregar** tags por status en el nodo "Crear Org" (`BLOCKED_LEAD` / `REVIEW_LEAD`,
  o sin tag especial cuando es Aprobado).

---

## 4. Plan de aplicación (cuando Luis dé OK explícito)

a. **Backup** del workflow actual: export como JSON desde la UI de n8n →
   `.planning/phases/08-leads-interactivos/n8n_backup_YYYYMMDD.json`.
b. **Branch del workflow**: duplicar el workflow en n8n (NO editar el activo).
c. **Aplicar cambios** en el duplicado:
   - Mover "Crear Org" antes del filtro de status.
   - Agregar Filtro 0 (blacklist) antes de "Crear Org".
   - Agregar tags por status en "Crear Org".
d. **Test** con 5-10 leads reales del Sheet (ejecución manual con triggers de prueba).
e. **Verificar en Pipedrive sandbox/staging**:
   - SHEIN **NO** crea org.
   - Lead aprobado crea org **sin** tag especial.
   - Lead bloqueado crea org **con** tag `BLOCKED_LEAD`.
f. **Activar** el workflow nuevo, **desactivar** el viejo.
g. **Monitoreo 24h**: comparar nuevas orgs en Pipedrive vs leads en Sheets,
   verificar que matchean.
h. Si todo OK tras 24h, **eliminar** el workflow viejo.

---

## 5. Hallazgos relacionados (referencias cruzadas)

- **H-07-04** — El clasificador necesita ajuste (SHEIN aprobado erróneamente,
  creator networks aprobados, SEO spam con score alto, saturación de "En revisión
  35"). Ajustar el **prompt del nodo clasificador** en paralelo a este cambio —
  es el mismo nodo GPT.
- **H-08-04** — Mojibake unicode en algunos cuerpos de email (preexistente del
  pipeline n8n→Sheets). Diferido; no es parte de este cambio, pero conviene
  atacarlo en la misma sesión de mantenimiento de n8n (corregir el encoding en
  la fuente es preferible a parchearlo en el sync del dashboard).
- **H-08-05** — Bug de matching de talentos en el sync de Sheets, **resuelto en el
  dashboard** con `resolve_talent_id_smart` (commit `833b070`). **El cambio del
  workflow de n8n NO necesita preocuparse por este problema** — el matching
  informal de `Talento_Mencionado` ya se maneja del lado del dashboard, no en n8n.

---

## 6. Riesgos y consideraciones

- **Volumen en Pipedrive**: crear orgs para todos los leads añade ~820 orgs al
  histórico y ~50/mes en steady state. Verificar el límite de orgs del **plan
  actual de Pipedrive** antes de activar.
- **Límites de plan**: si el plan no soporta el volumen, evaluar archivado
  periódico de orgs bloqueadas o upgrade de plan.
- **Reversibilidad**: el plan (paso f) permite volver al workflow viejo en
  cualquier momento desactivando el nuevo y reactivando el original — sin pérdida
  de datos, ya que el viejo no se elimina hasta el paso h.
