---
status: issues_found
phase: 05-ai-generated-pdf-reports
reviewed_at: 2026-06-15T23:55:00-06:00
depth: standard
files_reviewed: 12
files_reviewed_list:
  - app/schemas/reports.py
  - app/models.py
  - app/services/reports.py
  - app/routers/reports.py
  - app/main.py
  - templates/reports/template.html
  - tests/test_reports.py
  - tests/conftest.py
  - frontend/js/reports.js
  - frontend/index.html
  - frontend/css/styles.css
  - frontend/js/dashboard.js
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
---

# Phase 5: Code Review Report

**Reviewed:** 2026-06-15T23:55:00-06:00
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Se revisaron los 12 archivos fuente de la Fase 5 (AI-Generated PDF Reports). La estructura general es sólida: separación correcta de capas (schemas, service, router), autenticación a nivel de router, escape XSS en el frontend con `escHtml`, escritura atómica con `.tmp` + `os.replace`, e importación lazy de WeasyPrint. Sin embargo, se identificaron dos bugs críticos de correctitud y cuatro advertencias de robustez.

El bug más grave es semántico: el reporte "mensual" no filtra los datos por el mes solicitado. La función `_build_payload` recibe el parámetro `month` pero lo usa únicamente como etiqueta de texto; todas las consultas (KPIs, funnel, top deals, leads) devuelven datos acumulados de todos los tiempos para el talento. El usuario elige "Mayo 2026" y recibe cifras de toda la historia comercial.

---

## Critical Issues

### CR-01: El parámetro `month` nunca filtra los datos — el reporte es all-time, no mensual

**File:** `app/services/reports.py:83-160`

**Issue:** `_build_payload(db, talent, month)` recibe el mes solicitado pero no lo pasa a ninguna consulta. `kpi_service.talent_detail(db, talent.id)`, `funnel_service.talent_funnel(db, talent.id)`, la query de `top_deals`, y ambas llamadas a `leads_service` no aceptan ni reciben un filtro de fecha. El payload que se envía a Claude y los datos en el apéndice PDF representan la actividad acumulada de todos los tiempos del talento, no el mes indicado. El cover del PDF dice `Reporte mensual — {{ month }}` pero las cifras son históricas.

**Fix:** A corto plazo, hacer explícito en el system prompt que las cifras son acumuladas y renombrar la sección del cover a "Reporte comercial — a {{ month }}" para que no induzca a error. A largo plazo (correcto), extender `talent_detail` y `talent_funnel` para aceptar un `month: str | None` y filtrar `Deal.add_time` con `LIKE '{month}%'`:

```python
# En _build_payload, pasar month a los servicios que soporten filtro:
top_deals_rows = (
    db.query(Deal.title, Deal.value, Deal.stage_name)
    .filter(
        Deal.talent_id == talent.id,
        Deal.status == "open",
        Deal.add_time.like(f"{month}%"),   # filtrar por mes
    )
    .order_by(desc(Deal.value))
    .limit(3)
    .all()
)
```

---

### CR-02: `Content-Disposition` con `filename=` sin comillas y con caracteres no-ASCII

**File:** `app/routers/reports.py:142-147`

**Issue:** El header se construye como:

```python
filename = f"reporte-{safe_name}-{report.month}.pdf"
headers={"Content-Disposition": f"attachment; filename={filename}"}
```

`safe_name` proviene de `talent.name.replace(" ", "-")` sin más transformación. Los nombres de talentos en español (p. ej. "María López" → `reporte-María-López-2026-05.pdf`) contienen caracteres no-ASCII. RFC 7230 prohíbe octetos fuera del rango visible US-ASCII en tokens de header sin codificación. RFC 5987 / RFC 6266 exigen `filename*=UTF-8''...` (percent-encoding) para nombres no-ASCII. Navegadores como Chrome toleran esto, pero Safari y Firefox pueden truncar o corromper el nombre del archivo descargado.

**Fix:** Usar `filename*` con percent-encoding para garantizar compatibilidad RFC:

```python
from urllib.parse import quote

safe_name = talent_name.replace(" ", "-")
filename_ascii = f"reporte-{report.month}.pdf"          # fallback ASCII
filename_utf8 = f"reporte-{safe_name}-{report.month}.pdf"
encoded = quote(filename_utf8, safe="-.")
headers = {
    "Content-Disposition": (
        f"attachment; filename=\"{filename_ascii}\"; "
        f"filename*=UTF-8''{encoded}"
    )
}
```

---

## Warnings

### WR-01: `response.content[0].text` sin guardia — IndexError si Claude devuelve contenido vacío

**File:** `app/services/reports.py:183`

**Issue:** `raw_text = response.content[0].text.strip()` asume que `response.content` tiene al menos un elemento y que el primero es un bloque de texto. Si la API devuelve una lista vacía (error de rate-limit, respuesta truncada con `stop_reason="max_tokens"` sin bloque, o un bloque de tipo `tool_use`), se lanza `IndexError` o `AttributeError`. Ninguno de los dos es capturado; propagarían como HTTP 500 en lugar de 502.

**Fix:**

```python
if not response.content or response.content[0].type != "text":
    raise ValueError("Claude returned non-JSON")
raw_text = response.content[0].text.strip()
```

---

### WR-02: `Pydantic ValidationError` de Claude con JSON incompleto genera 500, no 502

**File:** `app/routers/reports.py:79-101`

**Issue:** Si Claude devuelve un JSON válido pero con una clave faltante (p. ej. sin `"recomendacion"`), `_call_claude` devuelve el dict incompleto sin error. El router llama `ReportOut(narrative=result["narrative"])`, que internamente construye `NarrativeSections(**result["narrative"])`. Pydantic v2 lanza `ValidationError` (no `ValueError`), que **no** es capturado por el bloque `except ValueError`. El resultado es HTTP 500 en producción en vez del 502 documentado.

**Fix:** Capturar también `ValidationError` en el router, o bien validar las claves en `_call_claude` antes de retornar:

```python
# Opción A — en _call_claude, después de json.loads:
required = {"resumen_ejecutivo", "deals_destacados", "recomendacion"}
if not required.issubset(parsed.keys()):
    raise ValueError("Claude returned non-JSON")

# Opción B — en el router:
from pydantic import ValidationError
except (ValueError, ValidationError) as exc:
    raise HTTPException(status_code=502, detail="Error al generar narrativa") from exc
```

---

### WR-03: Archivo `.tmp` no se limpia si `WeasyPrint` lanza excepción

**File:** `app/services/reports.py:227-229`

**Issue:** El write atómico es correcto en el caso feliz, pero no hay manejo de errores alrededor de `write_pdf`:

```python
tmp_path = output_path + ".tmp"
HTML(string=html_str, base_url=".").write_pdf(tmp_path)  # puede fallar
os.replace(tmp_path, output_path)                          # nunca ejecutado
```

Si WeasyPrint falla (por CSS inválido, memoria, etc.) el archivo `.tmp` queda en disco indefinidamente. La siguiente ejecución lo sobreescribirá, pero en un entorno con múltiples workers o si el disco está lleno podría acumularse.

**Fix:**

```python
tmp_path = output_path + ".tmp"
try:
    HTML(string=html_str, base_url=".").write_pdf(tmp_path)
    os.replace(tmp_path, output_path)
except Exception:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    raise
```

---

### WR-04: El regex de `month` acepta valores imposibles (`2026-00`, `2026-99`)

**File:** `app/schemas/reports.py:16`

**Issue:** `pattern=r"^\d{4}-\d{2}$"` valida formato pero no rango semántico. Los valores `2026-00`, `2026-13`, `2026-99` pasan la validación y llegan a `_build_payload`. El `add_time LIKE '2026-99%'` no matcheará nada y el reporte se generará vacío con cifras en cero, sin error explícito al usuario.

**Fix:** Restringir el rango en el regex o añadir un validador Pydantic:

```python
from pydantic import field_validator

class ReportGenerate(BaseModel):
    talent_id: int
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
```

---

## Info

### IN-01: `mock_weasyprint` recibe `tmp_path` pero escribe en el CWD real — contaminación de tests

**File:** `tests/conftest.py:685-704`

**Issue:** El fixture acepta el parámetro `tmp_path` (directorio temporal de pytest) pero `fake_write_pdf` lo ignora completamente. Los archivos se escriben en la ruta relativa `reports/{talent_id}/{month}.pdf` dentro del directorio de trabajo actual (raíz del proyecto). Después de cada test run, el directorio `reports/` acumula archivos PDF de prueba. Aunque `_clean_tables` limpia la base de datos, los archivos en disco permanecen. En teoría esto podría interferir con `test_download_missing_file` si un run anterior dejó un archivo en la ruta que se espera inexistente.

**Fix:** Usar `tmp_path` para redirigir las escrituras:

```python
@pytest.fixture()
def mock_weasyprint(monkeypatch, tmp_path):
    def fake_write_pdf(path_or_none=None):
        if path_or_none:
            # Redirigir a tmp_path para evitar pollución del CWD
            rel = os.path.relpath(path_or_none) if os.path.isabs(path_or_none) else path_or_none
            dest = tmp_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"%PDF-1.4")
        return b"%PDF-1.4"
    ...
```

O más simple: monkeypatch `os.makedirs` y `open` en el servicio para capturar las escrituras.

---

### IN-02: `datetime.utcnow()` deprecado en el servicio de producción

**File:** `app/services/reports.py:270,280`

**Issue:** `datetime.utcnow()` está marcado como deprecated desde Python 3.12 (PEP 615). El prompt del proyecto indica que esto es aceptable en código de tests, pero en `app/services/reports.py` se usa en el upsert de producción de `generate_report`:

```python
existing.generated_at = datetime.utcnow()  # línea 270
generated_at=datetime.utcnow(),            # línea 280
```

**Fix:**

```python
from datetime import datetime, timezone
# ...
existing.generated_at = datetime.now(timezone.utc)
generated_at=datetime.now(timezone.utc),
```

---

## Self-Check

- Autenticación router-level: correcta, todos los endpoints protegidos.
- Escritura atómica: implementada (CR confirmado el cleanup faltante en WR-03).
- XSS: `escHtml` aplicado correctamente en todos los paths de `reports.js`. Jinja2 `autoescape=True` protege el template PDF.
- Path traversal (`_slug`): correcto, usa `str(talent.id)` numérico.
- SSRF WeasyPrint: `base_url="."` es literal, no controlado por usuario.
- Prompt injection: el payload se serializa con `json.dumps`, el único input de usuario en la petición es `talent_id` (int) y `month` (regex-validated). Bajo riesgo.
- `D-65`, `D-69`, `D-70`, `datetime.utcnow()` en tests: conocidos y excluidos per instrucciones.

---

_Reviewed: 2026-06-15T23:55:00-06:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
