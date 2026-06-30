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
