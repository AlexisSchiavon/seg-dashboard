# Hallazgos — Fase 8 (leads interactivos)

Hallazgos durante la implementación. Anotados para retomar o para corregir el brief.

## H-08-01 — Header real es `Razon_validacion` (v minúscula), no `Razon_Validacion`

**Detectado**: 30 jun 2026, durante el primer sync real de 8.1.
**Severidad**: media (rompía la feature de razón silenciosamente — el warning-log lo cazó).
**Detalle**: El brief afirmaba que la columna `Razon_Validacion` (V mayúscula) estaba verificada en el Sheet. El sync real disparó el warning-log (P3) y `razon_validacion` quedó NULL en los 814 leads. Al listar los headers live, el nombre real es **`Razon_validacion`** (v minúscula). Corregido el constante `_VALIDATION_REASON_HEADER` en `app/integrations/sheets.py`. Tras la corrección: 814/814 leads con razón.
**Confirmación de que el warning-log sirvió**: la decisión P3 ("confiar + warning-log") convirtió un mismatch silencioso en una señal visible en logs, exactamente como se diseñó.

## H-08-02 — `Categoria_Detectada` SÍ existe en el Sheet — categoría agregada a 8.1

**Detectado**: 30 jun 2026, al listar los headers live del Sheet.
**Severidad**: media (premisa de decisión incorrecta).
**Detalle**: En discovery se reportó que no existía campo de categoría (sin acceso al Sheet live entonces), y por eso en **P1** se decidió omitir "categoría" del modal. Los headers reales muestran **`Categoria_Detectada`** (columna 8). Con la premisa corregida, Alexis decidió **incluir** `categoria_detectada`. Se agregó como 4ª columna en la misma migración no-commiteada de 8.1 (modelo + migración + `SheetLeadRow` + sync). Tras el sync real: 814/814 leads con categoría (ej. "B2B Válido"). El modal de 8.3 mostrará categoría.

## H-08-03 — `Email_Completo` SÍ preserva saltos de línea `\n` — revisar heurística D11 en 8.3

**Detectado**: 30 jun 2026, en el preview del cuerpo de email tras el sync real.
**Severidad**: media (afecta diseño de 8.3, no a 8.1).
**Detalle**: El brief (D3/D11) asumía que `Email_Completo` venía como texto plano **sin** saltos de línea ("párrafos pegados, ej. `muy bienSoy Pame`"). Los datos reales **SÍ** traen `\n` (ej. `"Hola,\n\nEspero que estén muy bien\nSoy Pame, de Optimist,..."`). La heurística D11, diseñada para re-insertar saltos donde no los hay, podría **sobre-fragmentar** texto que ya está bien formateado.
**Acción (8.3)**: replantear D11 — probablemente respetar los `\n`/`\n\n` existentes y aplicar las reglas de split (coma+Mayús, punto+Mayús, minús+Mayús pegadas) solo como complemento, no como mecanismo principal. Decisión a tomar al implementar 8.3.

**Resuelto en 8.3**: `formatLeadEmail` aplica Regla 0 — si el texto contiene `\n`, respeta los saltos existentes y omite las reglas de split (1-5); solo el fallback sin `\n` (leads viejos/malformados) recibe la heurística completa. Reglas 6-7 (bold + `\n`→`<br>`) siempre corren.

### H-08-03b — El bold markdown `*X*` no cruza saltos de línea (subcaso de H-08-03)

**Detectado**: 30 jun 2026, en el render real del lead id=1.
**Severidad**: baja (cosmético).
**Detalle**: El regex de bold markdown `*X*` (D11 paso 6) no cruza saltos de línea en JS por diseño (sin flag `/s`, `.` no matchea `\n`). Casos como `*"texto\ncon \n saltos"*` renderizan los asteriscos literales en lugar de `<strong>`. Se considera comportamiento **aceptable**: el asterisco visible se lee como énfasis. Cambiar a regex multilínea abre riesgo de mal-render con asteriscos no balanceados (un `*` suelto envolvería medio email). Si Luis se queja, ajustar.

## H-08-04 — Mojibake (unicode malcodificado) en algunos cuerpos de email

**Detectado**: 30 jun 2026, durante validación visual del modal (8.3).
**Severidad**: baja-media (cosmético en el cuerpo del email; no afecta funcionalidad).
**Detalle**: Algunos `email_completo` muestran mojibake — UTF-8 interpretado como Latin-1 en algún punto del pipeline. Ejemplo en el lead "Karla Martinez": "disposiciÃ³n" en vez de "disposición", "pÃ¡gina" en vez de "página". Causa probable: doble codificación / encoding incorrecto en n8n o en la captura a Sheets (upstream del sync). **NO se corrige en Fase 8** — es preexistente al sync de leads y no lo introduce nuestro código.
**Solución diferida**: (a) detectar mojibake en el sync (heurística tipo `ftfy`, o regex de patrones comunes `Ã³/Ã¡/Ã©/Â`) y arreglar antes de guardar; o (b) corregir el encoding en n8n upstream (preferible — arreglar en la fuente). Evaluar junto con H-07-04 (revisión del workflow de n8n).

## H-08-05 — Bug crítico: 501/819 leads con talent_id NULL por matching exacto en el sync (RESUELTO)

**Detectado**: 30 jun 2026, tras 8.4, al notar que el filtro por talento no mostraba la mayoría de los leads.
**Severidad**: alta (inutilizaba "Leads por talento" y el filtro de 8.4 para el 61% del dataset).
**Estado**: **RESUELTO** en local — commit `fix(fase-8)` `833b070`.

**Causa raíz**: `sync_sheets` asignaba `talent_id` con un lookup de igualdad EXACTA (`dict.get`) entre `Talento_Mencionado` (Sheet) y `Talent.name` (DB), sin normalización ni alias, y sin log en el miss. El Sheet usa formas informales que nunca igualan el nombre canónico completo. Las 501 fallas se explican con 8 valores distintos:

| # | Sheet | Canónico | Tipo |
|---:|---|---|---|
| 146 | `Navarretes show` | `Navarretes Show` | mayúscula |
| 93 | `Mariana` | `Mariana Sanchez` | nombre de pila |
| 67 | `Mamamecanic` | `Mama mecanic` | sin espacio |
| 61 | `Edgar` | `Edgar Cardenas` | nombre de pila |
| 59 | `Don Silverio` | `Don Silverio y Don Wicho` | parcial |
| 51 | `Ale` | `Ale Voale` | nombre de pila |
| 12 | `Deliberración` | `Deliberracion` | acento |
| 12 | `Doc Fitness` | `Dr Fitness` | alias real |

**Fix**: nuevo `app/services/talents.py::resolve_talent_id_smart` — matching en capas (normalizar deaccent+casefold+collapse-space → exact → no-spaces → prefix con guardia de unicidad → alias map mínimo → miss+warning). Integrado en `sync_sheets` con summary log por sync. **El fix vive en el dashboard, NO en n8n** (ver H-08-05 ref en N8N_CHANGES.md).

**Resultado del re-sync real**: `exact=477 no_spaces=67 prefix=264 alias=12 miss=0` → 820 leads, **0 NULL** (antes 501). +12 tests (suite 237).

**Robustez a futuro**: la guardia de unicidad del prefix evita mis-atribución (ej. si se agrega "Mariana López", "Mariana" se vuelve ambiguo → `talent_ambiguous` log + NULL); cualquier forma nueva no resuelta sube el contador `miss` y dispara `talent_not_resolved` en logs.

## H-08-06 — Proyección de ingresos vacía en meses futuros para talentos con TrelloCards no actualizadas

**Detectado**: 30 jun 2026, al revisar la proyección de Don Silverio y Don Wicho.
**Severidad**: media (problema de datos operativos en Trello, NO bug del dashboard).
**Estado**: diagnóstico confirmado; acciones diferidas (fuera de Fase 8).

**Descripción**: La proyección de ingresos por mes (Jul–Oct 2026) muestra $0 para Don Silverio y Don Wicho a pesar de que el widget "Pendiente por cobrar" indica $2.5M. **El dashboard NO está roto** — refleja fielmente lo que hay en Trello.

**Causa raíz** (confirmada por query directo a producción, 30 jun 2026):

Estado de los deals ganados de Don Silverio y Don Wicho (14 deals, ~$4.66M histórico):
- **3 deals ($1.18M) sin TrelloCard asignada**: Dutton Ranch $225K, Nu3 Gallos $175K, Huevos San Juan Mundial $780K.
- **11 deals con TrelloCard, pero TODAS las `collection_date` son de meses pasados** (Dic 2025 a Jun 2026).
- **0 deals con `collection_date >= 2026-07-01`** → por eso la ventana Jul–Oct sale en $0.

Deals operativamente atorados (`list_state != 'cerrado'` con `collection_date` pasada):
- 3 Hermanos MM+DsDw $200K — en cobranza, fecha Dic 2025 (7 meses vencido).
- 3 Hermanos Nov-Dic $300K — en ejecución, fecha Feb 2026 (5 meses vencido).
- Telcel $200K, Coppel $400K, Nariz Roja $75K, Nu3 Gallos $175K — todos con fecha May 2026 (2 meses vencidos).

**Implicación**:
- La proyección vacía en Jul–Oct 2026 es **correcta** bajo los datos existentes. El dashboard es SOLO LECTURA sobre Trello y muestra lo que hay.
- El gap está en el **proceso operativo de Trello**: (a) actualizar `collection_date` cuando la fecha original se vence, o (b) crear tarjetas para los 3 deals que no las tienen.

**Acciones diferidas (NO en Fase 8)**:
1. **Comunicar a Luis**: los $2.5M pendientes de Don Silverio incluyen $700K+ en deals vencidos operativamente. Necesitan seguimiento humano de cobranza.
2. Considerar en una fase futura un widget de **"Deals vencidos"** o **"TrelloCards sin fecha de cobro futura"** para hacer visible este gap automáticamente.
3. Considerar en **Fase 11 (automatizaciones)** un flow que marque `collection_date` vencidas y sugiera una nueva fecha.

**Nota**: un hallazgo similar probablemente exista para otros talentos — este diagnóstico se hizo solo sobre Don Silverio y Don Wicho.
