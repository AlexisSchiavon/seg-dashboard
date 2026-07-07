---
title: "Manual Técnico — SEG Talent Intelligence Dashboard"
subtitle: "Documentación para personal técnico interno"
date: "6 de julio de 2026"
lang: es
---

# 1. Introducción

## 1.1 Propósito del sistema

El **SEG Talent Intelligence Dashboard** es una plataforma web de inteligencia
comercial para Santillán Entertainment Group (SEG / Talent Agency). Consolida en
un solo lugar los datos de tres fuentes de verdad existentes del cliente —
**Pipedrive** (CRM / funnel comercial), **Google Sheets** (leads entrantes por
correo) y **Trello** (ejecución de campañas y cobranza) — y los expone mediante:

- Un **dashboard web** con cinco secciones (Resumen, Por talento, Funnel, Leads,
  Reportes).
- **Reportes PDF** ejecutivos por talento y periodo.
- Un **agente conversacional** en lenguaje natural (español) construido sobre la
  API de Claude.

El sistema es **de solo lectura** frente a las tres integraciones externas: nunca
crea, modifica ni elimina datos en Pipedrive, Trello o Google Sheets. La única
escritura permitida es sobre su propia base de datos local SQLite (`seg.db`).

## 1.2 Alcance del manual

Este documento está dirigido a **desarrolladores, personal de DevOps y personal
técnico interno** de SEG que deba operar, mantener, diagnosticar o extender la
plataforma. Asume familiaridad con Python, HTTP/REST, SQL básico y contenedores
Docker.

Para la guía de uso no técnica (equipo comercial de SEG) consúltese el documento
separado **Manual Operativo**.

## 1.3 Convenciones tipográficas

- `código monoespaciado`: nombres de archivos, variables de entorno, comandos,
  rutas y endpoints.
- **Negritas**: conceptos clave o advertencias.
- `[PENDIENTE]`: información que debe completar el responsable del proyecto antes
  de la entrega final (decisiones de negocio o datos operativos externos al
  código).

---

# 2. Arquitectura general

## 2.1 Diagrama textual del sistema

```
                        ┌───────────────────────────────────────────┐
   Fuentes externas     │              SEG Dashboard                │
  (solo lectura)        │            (FastAPI · Python 3.12)        │
                        │                                           │
  Pipedrive API v2 ───▶ │  app/integrations/pipedrive.py ─┐         │
  Trello API       ───▶ │  app/integrations/trello.py     ├─▶ Sync  │
  Google Sheets    ───▶ │  app/integrations/sheets.py     ┘   jobs  │
                        │            (APScheduler, cada 30 min)     │
                        │                     │                     │
                        │                     ▼                     │
                        │            SQLite  seg.db  (SQLAlchemy)   │
                        │                     │                     │
                        │        ┌────────────┼────────────┐        │
                        │        ▼            ▼            ▼         │
                        │   app/services  app/services  app/services│
                        │    (kpis,        (reports →    (agent →   │
                        │     funnel,       WeasyPrint)   Claude)   │
                        │     leads…)          │            │       │
                        │        │             │            │       │
                        │        ▼             ▼            ▼        │
                        │   Routers REST (dashboard, leads, reports, │
                        │              agent, talents, sync, health) │
                        │                     │                     │
                        └─────────────────────┼─────────────────────┘
                                              ▼
                        Frontend estático (HTML + CSS + Vanilla JS)
                        servido por FastAPI en "/"  ·  PDFs  ·  Chat
                                              │
                                              ▼
                                   Claude API (Anthropic) — solo agente
```

## 2.2 Stack tecnológico (versiones exactas)

Leídas de `pyproject.toml` (`requires-python = ">=3.12"`):

| Componente | Paquete / versión | Rol |
|---|---|---|
| Lenguaje | Python 3.12 | Runtime |
| Framework web | `fastapi[standard] >= 0.136.3` | API + servidor estático |
| ORM | `sqlalchemy >= 2.0.50` | Capa de datos (estilo 2.0 tipado) |
| Migraciones | `alembic >= 1.18.4` | Versionado del schema |
| Config | `pydantic-settings >= 2.14.1` | Carga tipada de variables de entorno |
| Cliente HTTP | `httpx >= 0.28.1` | Pipedrive y Trello |
| Google Sheets | `gspread >= 6.1,<7.0` + `google-auth >= 2.40,<3.0` | Leads |
| IA | `anthropic >= 0.79,<1.0` | Agente conversacional (Claude) |
| PDF | `weasyprint >= 66,<70` + `jinja2 >= 3.1` | Reportes |
| Scheduler | `apscheduler >= 3.11.2` | Sync periódico |
| Auth | `pyjwt >= 2.13.0` + `pwdlib[argon2] >= 0.3.0` + `python-multipart` | JWT + hashing |
| Sanitización | `bleach >= 6.0.0` | Limpieza de HTML en leads |
| Fuzzy matching | `rapidfuzz >= 3.14.5` | Resolución de nombres (leads) |
| Testing / lint | `pytest >= 9.0.3`, `respx >= 0.23.1`, `ruff >= 0.15.17`, `pdfplumber >= 0.11` | Desarrollo |

## 2.3 Flujo de datos

1. **Ingesta (pull).** Cada 30 minutos (APScheduler) el sistema llama por HTTP GET
   a Pipedrive, Trello y Google Sheets y hace *upsert* en `seg.db`. Nunca escribe
   en las fuentes.
2. **Cómputo.** La capa `app/services/` calcula KPIs, funnel, proyecciones,
   comisiones (70 %), estados de cobranza, etc., a partir de las tablas locales.
3. **Exposición.**
   - El **frontend** consume los routers REST y renderiza el dashboard.
   - Los **reportes PDF** se generan bajo demanda (WeasyPrint + Jinja2) y se
     transmiten como *stream*; su metadata se guarda en la tabla `reports`.
   - El **agente** recibe preguntas en español, ejecuta *tools* de solo lectura
     sobre la misma capa de servicios y sintetiza la respuesta con Claude.

---

# 3. Estructura del repositorio

Árbol a nivel 2 de profundidad (carpetas principales):

```
seg-dashboard/
├── app/
│   ├── main.py               # Punto de entrada FastAPI, lifespan, montaje de routers
│   ├── config.py             # Settings (pydantic-settings) — variables de entorno
│   ├── database.py           # Engine SQLAlchemy, sessionmaker, Base, get_db
│   ├── models.py             # Modelos ORM (todas las tablas)
│   ├── auth/                 # Login, JWT, hashing, dependencias de sesión
│   ├── integrations/         # Clientes externos: pipedrive.py, trello.py, sheets.py, base.py
│   ├── routers/              # Endpoints REST: dashboard, talents, leads, reports, agent, sync, health
│   ├── schemas/              # Modelos Pydantic (request/response) por dominio
│   ├── services/             # Lógica de negocio: kpis, funnel, reports, agent, trello_service, leads, periods, talents, report_charts
│   ├── sync/                 # jobs.py (upserts) + scheduler.py (APScheduler)
│   ├── scripts/              # seed_admin, seed_talents, match_talent_products
│   ├── templates/reports/    # Plantillas Jinja del PDF (base, cover, talent_page, report.css)
│   └── static/fonts/         # Inter.woff2 (fuente embebida en el PDF)
├── alembic/versions/         # 12 migraciones de schema
├── frontend/                 # index.html, login.html, css/, js/ (Vanilla JS)
├── tests/                    # Suite pytest (270 pruebas)
├── docs/                     # Documentación (este manual, mockup aprobado, auditorías)
├── Dockerfile                # Build multi-stage (builder + runtime)
├── docker-compose.yml        # Servicio web + volúmenes seg_data / seg_reports
├── entrypoint.sh             # Arranque: migración + seed admin + uvicorn
├── alembic.ini               # Config de Alembic
├── pyproject.toml            # Dependencias y metadatos
└── .env.example              # Plantilla de variables de entorno (sin valores)
```

## 3.1 Rol de cada módulo en `app/`

- **`integrations/`**: adaptadores de solo lectura a cada API externa. Devuelven
  datos crudos/normalizados; no contienen lógica de negocio.
- **`sync/`**: orquestación de la ingesta. `jobs.py` hace los *upserts* a la DB;
  `scheduler.py` programa la ejecución periódica.
- **`services/`**: única fuente de verdad de la lógica de negocio (comisión 70 %,
  etapas del funnel, estados de cobranza). Tanto el dashboard como el agente y los
  PDFs consumen esta capa, evitando duplicar reglas.
- **`routers/`**: capa HTTP. Traduce peticiones a llamadas de servicios y aplica
  autenticación.
- **`schemas/`**: contratos de datos (Pydantic v2) para validación de entrada y
  serialización de salida.
- **`auth/`**: emisión y verificación de tokens JWT; hashing de contraseñas.

## 3.2 Ubicación de artefactos

- **Tests**: `tests/` (pytest). Ejecutar con
  `DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run pytest` en macOS (WeasyPrint
  requiere las libs de Homebrew localmente).
- **Migraciones**: `alembic/versions/`.
- **Plantillas PDF**: `app/templates/reports/`.
- **Estáticos del frontend**: `frontend/` (servido por FastAPI en `/`).

---

# 4. Modelo de datos

Base de datos **SQLite** (`seg.db`), gestionada con SQLAlchemy 2.0. La siguiente
documentación proviene de introspección real del schema (PRAGMA) al 6-jul-2026.
Se documentan **10 tablas** (9 de aplicación + `alembic_version`).

## 4.1 `talents`
Catálogo de talentos representados por la agencia.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `name` | VARCHAR | No | Único (índice `ix_talents_name`) |
| `active` | BOOLEAN | No | Talento activo |
| `category` | VARCHAR | Sí | Nicho / categoría |
| `photo_url` | VARCHAR | Sí | Opcional |

Relaciones: referenciada por `deals`, `leads`, `talent_products`, `reports`,
`deal_stage_events`. Filas actuales: 20.

## 4.2 `talent_products`
Mapeo talento ↔ producto de Pipedrive (mecanismo actual de atribución vía sync).

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `talent_id` | INTEGER | No | FK → `talents.id` (índice) |
| `pipedrive_product_id` | INTEGER | Sí | ID del producto en Pipedrive |

Filas actuales: 17. Véase la nota de atribución en §5.1.

## 4.3 `deals`
Deals sincronizados desde Pipedrive.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK local (**volátil**; no usar como clave estable) |
| `pipedrive_id` | INTEGER | No | ID estable de Pipedrive (**clave de negocio**) |
| `title` | VARCHAR | No | Título del deal |
| `value` | FLOAT | No | Valor (venta total) |
| `currency` | VARCHAR | No | Por defecto MXN |
| `stage_id` | INTEGER | No | Etapa Pipedrive |
| `stage_name` | VARCHAR | No | Nombre de etapa |
| `status` | VARCHAR | No | open / won / lost |
| `talent_id` | INTEGER | Sí | FK → `talents.id`; NULL = "sin talento" |
| `commission_amount` | FLOAT | No | 70 % del `value` (comisión talento) |
| `is_sin_cotizar` | BOOLEAN | No | `value == 0` |
| `loss_reason` | VARCHAR | Sí | Razón de pérdida |
| `brand_category` | VARCHAR | Sí | Categoría de marca (campo personalizado) |
| `expected_collection_date` | VARCHAR | Sí | Campo personalizado |
| `stage_entered_at` | DATETIME | Sí | Entrada a la etapa actual |
| `update_time` | VARCHAR | No | Para filtro `updated_since` |
| `add_time` | VARCHAR | Sí | Fecha de creación en Pipedrive |
| `won_time` | DATETIME (tz) | Sí | Momento de ganado (índice `ix_deals_won_time`) |

FK: `talent_id → talents.id`. Filas actuales: 517.

## 4.4 `deal_stage_events`
Historial de cambios de etapa/estado detectados entre syncs.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `deal_pipedrive_id` | INTEGER | No | Índice |
| `talent_id` | INTEGER | Sí | FK → `talents.id` (índice) |
| `from_stage` / `to_stage` | VARCHAR | Sí / No | Transición de etapa |
| `from_status` / `to_status` | VARCHAR | Sí / No | Transición de estado |
| `detected_at` | DATETIME | No | Momento de detección |

Filas actuales: 47.

## 4.5 `trello_cards`
Tarjetas de Trello sincronizadas (board Admin TA).

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `trello_card_id` | VARCHAR | No | ID inmutable de Trello (único) |
| `name` | VARCHAR | No | Nombre de la tarjeta |
| `list_id` / `list_name` | VARCHAR | No | Columna de Trello |
| `list_state` | VARCHAR | No | ejecucion / cobranza / cerrado / omitido |
| `deal_id` | INTEGER | Sí | FK → `deals.id` (PK local, no pipedrive_id) |
| `pipedrive_deal_id_desc` | INTEGER | Sí | ID extraído de la descripción |
| `collection_date` | DATE | Sí | Fecha de cobro (due) |
| `synced_at` | DATETIME | No | Última sincronización |

FK: `deal_id → deals.id`. Filas actuales: 221.

## 4.6 `leads`
Leads entrantes desde Google Sheets.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `sheet_row_id` | INTEGER | No | Clave natural (número de fila del sheet) |
| `remitente_email` / `remitente_nombre` / `asunto` | VARCHAR | No | Datos del correo |
| `fecha_recepcion` | DATETIME (tz) | Sí | Fecha de recepción |
| `talent_id` | INTEGER | Sí | FK → `talents.id` (índice) |
| `status_filtrado` | VARCHAR | No | Estado del lead |
| `fuente` | VARCHAR | No | Por defecto "Gmail" |
| `score_calidad` | INTEGER | Sí | Puntuación |
| `bloqueado` / `convertido_a_prospecto` | BOOLEAN | No | Banderas |
| `email_completo` / `razon_validacion` | TEXT | Sí | Cuerpo + razón (sanitizados con bleach) |
| `categoria_detectada` | VARCHAR | Sí | Categoría del clasificador |
| `email_truncated` | BOOLEAN | No | Marca de truncado (>1 MB) |

FK: `talent_id → talents.id`. Filas actuales: 867.

## 4.7 `reports`
Metadata de reportes PDF generados (los PDF se regeneran bajo demanda; no se
persisten en disco desde Fase 9.5).

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `talent_id` | INTEGER | Sí | FK → `talents.id`; NULL en consolidados |
| `month` | VARCHAR | No | "YYYY-MM" o "YYYY-QN" |
| `generated_at` | DATETIME | No | Fecha de generación |
| `file_path` | VARCHAR | Sí | Histórico (hoy NULL) |
| `file_size_bytes` | INTEGER | No | Tamaño del último render |
| `talent_ids` | VARCHAR | Sí | Clave de regeneración ("all" / "10,11") |
| `content_hash` | VARCHAR | Sí | sha256 del PDF |

FK: `talent_id → talents.id`. Filas actuales: 5.

## 4.8 `sync_logs`
Bitácora de sincronizaciones.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `source` | VARCHAR | No | pipedrive / trello / sheets |
| `started_at` | DATETIME | No | Inicio |
| `finished_at` | DATETIME | Sí | Fin |
| `status` | VARCHAR | No | running / success / error |
| `records_synced` | INTEGER | No | Registros procesados |
| `error_message` | VARCHAR | Sí | Detalle de error |

Filas actuales: 276.

## 4.9 `users`
Usuarios del dashboard.

| Columna | Tipo | Nulo | Notas |
|---|---|---|---|
| `id` | INTEGER | No | PK |
| `email` | VARCHAR | No | Único (`ix_users_email`), en minúsculas |
| `hashed_password` | VARCHAR | No | Hash Argon2 (pwdlib) |
| `created_at` | DATETIME | No | Alta |
| `is_admin` | BOOLEAN | No | Rol administrador |

Filas actuales: 2.

## 4.10 `alembic_version`
Tabla interna de Alembic. Contiene la revisión aplicada
(hoy `a7f3c1b2d4e5`).

## 4.11 Migraciones Alembic

Ubicación: `alembic/versions/`. **12 migraciones** hasta la cabecera actual
`a7f3c1b2d4e5` (report metadata multitalent). Orden histórico principal:
`324116cbf0dd` (schema inicial) → `c35f623eaa21` (deals + eventos + logs) →
`ee55974a0232` (trello) → `afc2f8425aa0` (reports) → `d48d69b17ea6` (leads) →
`a1c2e3f4b5d6` (won_time) → `f3a1b2c4d5e6` (is_admin) → `e1f2a3b4c5d6` (cuerpo de
email) → `a7f3c1b2d4e5` (metadata multitalent). Existen también migraciones de
merge y de datos (`b2d3f4a5c6e7`, `c3e4a5b6d7f8`, `d9955ae215ef`).

Comandos:

```bash
alembic current          # revisión aplicada
alembic history          # historial completo
alembic upgrade head     # aplicar migraciones pendientes
alembic downgrade -1     # revertir la última
alembic downgrade <rev>  # revertir hasta una revisión concreta
```

**Nota de deploy:** `entrypoint.sh` ejecuta `alembic upgrade head`
**automáticamente** al arrancar el contenedor (véase §10), por lo que en un deploy
normal no es necesario correr la migración a mano.

---

# 5. Integraciones

Todas las integraciones son **de solo lectura**. Si se detecta que un cliente
incluye métodos de escritura (p. ej. `create_card`), no deben invocarse.

## 5.1 Pipedrive

- **Cliente:** `app/integrations/pipedrive.py`.
- **API:** v2. `BASE_URL = https://{PIPEDRIVE_DOMAIN}.pipedrive.com/api/v2`.
- **Autenticación:** token en el header `x-api-token` (v2 — **no** por query
  `?api_token=`).
- **Endpoints usados (GET):** `/deals` (paginado, `status=open,won,lost`),
  `/deals/products` (bulk, hasta 100 IDs), `/products`, `/stages`, `/dealFields`
  (para resolver campos personalizados y opciones), `/users` (nombres de owner).
- **Método de atribución de talento:** `[PENDIENTE — decisión de Luis]`. El sync
  actual atribuye el talento de un deal **por su producto** (`talent_products.
  pipedrive_product_id`). Sin embargo, la auditoría del 6-jul-2026 confirmó que en
  Pipedrive el talento se marca mediante un **label** (`label_ids`, campo tipo
  *set* con 14 opciones), no siempre por producto. Esta discrepancia es la causa
  raíz de deals "sin talento" en el dashboard. Debe definirse si el sync migra a
  leer labels, productos, o ambos. Documentar aquí la decisión final.
  **Nota:** la decisión sobre el método de atribución (label vs product vs dual)
  está pendiente de resolución con EL CLIENTE. Una vez resuelta, esta sección se
  actualiza.
- **Cadencia de sincronización:** cada 30 minutos (§8).
- **Rate limiting (429):** el cliente usa un helper con reintentos
  (`get_with_retry` / `_paginate`) que respeta la política de reintentos ante
  respuestas transitorias.
- **Trato de errores:** los errores de red/HTTP se registran en `sync_logs` con
  `status='error'` y `error_message`; el sync no aborta el resto de fuentes.

## 5.2 Trello

- **Cliente:** `app/integrations/trello.py`. `BASE_URL = https://api.trello.com/1`.
- **Autenticación:** por query params `key` + `token` (sin header).
- **Boards sincronizados:** **únicamente el board "Admin TA"**
  (`69312a9d5523703a1ce1a413`). La organización `talentagency3` tiene **12 boards**
  (incluyendo boards por talento: Mariana Sanchez, Reborujados, Elissa, etc.); los
  **11 restantes NO se sincronizan** hoy (deuda técnica, §13).
- **`LIST_STATE_MAP`:** mapea el `list_id` de cada columna de Trello a un estado
  canónico usado en `trello_cards.list_state`:

  | Columna Trello | list_state |
  |---|---|
  | Contrato / Firmar contrato todos / Enviar factura | `ejecucion` |
  | Cobrar | `cobranza` |
  | Enviar encuesta / Finalizados | `cerrado` |
  | Otros pendientes | `omitido` (excluido de todo cálculo) |

  El estado `omitido` se introdujo en Fase 9.8 para excluir tarjetas
  administrativas; "Enviar encuesta" se reclasificó a `cerrado` (es post-cobro).
- **Flag `TRELLO_AUTO_CREATE_ENABLED` (`app/sync/jobs.py`):** controla la
  automatización "al ganar un deal, crear tarjeta en Trello". **Está en `False` de
  forma permanente**: esa creación la maneja un sistema previo del cliente ("Fase 2
  Talent"). El dashboard es solo lectura para Trello; `trello.create_card()` lanza
  `RuntimeError` si se invoca.

## 5.3 Google Sheets

- **Cliente:** `app/integrations/sheets.py` (gspread + `google-auth`).
- **Autenticación:** service account (JSON en `GOOGLE_SERVICE_ACCOUNT_JSON`).
- **Sheet configurado:** variable `GOOGLE_SHEETS_ID` (worksheet **"Leads"**).
  *Nota:* el contrato/algunos documentos la mencionan como
  `GOOGLE_SHEETS_LEADS_ID`; el nombre real en `config.py` y `.env` es
  `GOOGLE_SHEETS_ID`.
- **Estructura de columnas esperada (18):** `ID_Lead`, `Email_Completo`,
  `Remitente_Email`, `Remitente_Nombre`, `Asunto`, `Fecha_Recepcion`,
  `Talento_Mencionado`, `Status_Filtrado`, `Categoria_Detectada`,
  `Razon_validacion`, `Score_Calidad`, `Bloqueado`, `Respuesta_Enviada`,
  `Fecha_Respuesta`, `Link_WhatsApp_Generado`, `Convertido_a_Prospecto`,
  `ID_Prospecto`, `Threadid`.
- **Frecuencia de pull:** cada 30 minutos (§8). La lectura usa
  `ws.get_all_values()` con timeout de 30 s; solo lectura.
- **Clave natural:** número de fila del sheet (`sheet_row_id`); la columna
  `ID_Lead` está vacía en las filas reales.

## 5.4 Claude (Anthropic API)

- **Uso:** exclusivamente el **agente conversacional** del Módulo 6
  (`app/routers/agent.py`, `app/services/agent.py`).
- **Modelo:** `claude-sonnet-4-6` (leído de `app/services/agent.py`).
- **Patrón:** bucle *tool-use* agentic. Claude nunca inventa cifras: recibe los
  resultados de *tools* de solo lectura y solo sintetiza prosa.
- **Los 12 tools de solo lectura:** `global_kpis`, `talent_ranking`,
  `talent_detail`, `funnel_overview`, `talent_funnel`, `recent_activity`,
  `income_projection`, `payment_calendar`, `deals_for_talent`, `leads_summary`,
  `leads_by_talent`, `deals_won_in_period`. Cada tool envuelve la misma capa
  `app/services/` que alimenta el dashboard (única fuente de verdad).
- **Token limits / retries:** el endpoint `chat()` está declarado como `def`
  (no `async def`) porque el SDK de Anthropic es bloqueante; FastAPI lo ejecuta en
  su threadpool. Los fallos de la API (`anthropic.APIError`) o estructuras
  inesperadas se traducen a **HTTP 502**.
- **Nota importante:** el **Módulo 5 (Reportes PDF) NO usa Claude**. Es un pivote
  documentado de Fase 9.5a: el reporte es 100 % calculado en Python (sin narrativa
  de IA). Véase §13 y la auditoría de contrato.

---

# 6. Autenticación y sesiones

- **Módulo:** `app/auth/` (`router.py`, `security.py`, `dependencies.py`).
- **Mecanismo:** JWT (PyJWT, HS256) transportado en **cookie** `access_token`
  (`HttpOnly`; `Secure` según `COOKIE_SECURE`). Hashing de contraseñas con
  **Argon2** vía `pwdlib`.
- **Endpoints:**
  - `POST /auth/login` — valida credenciales (`OAuth2PasswordRequestForm`), emite
    el token y lo fija como cookie.
  - `POST /auth/logout` — elimina la cookie `access_token`.
  - `GET /auth/me` — devuelve el usuario autenticado (`UserRead`).
  - No hay endpoint de *refresh* explícito; la expiración se controla con
    `ACCESS_TOKEN_EXPIRE`.
- **Dependencia de protección:** `get_current_user` protege los routers de datos.
- **Gestión de usuarios:** se crean por *seed* al arrancar el contenedor
  (`app/scripts/seed_admin.py`, usando `ADMIN_EMAIL` / `ADMIN_PASSWORD`). Para
  altas adicionales se ejecuta el mismo script o un `INSERT` controlado con hash
  Argon2. Los emails se almacenan en minúsculas.

---

# 7. Generación de reportes PDF

- **Stack:** WeasyPrint (`>=66,<70`) + Jinja2 + fuente **Inter**.
- **Plantillas:** `app/templates/reports/` — `base.html`, `cover.html`,
  `talent_page.html`, `report.css`. Los gráficos (funnel, barras de proyección,
  donuts) se generan como **SVG inline** en `app/services/report_charts.py`.
- **Endpoints (`app/routers/reports.py`, protegidos):**
  - `GET /reports/talents` — talentos disponibles.
  - `GET /reports/months`, `GET /reports/quarters` — periodos disponibles.
  - `POST /reports/generate` — genera y transmite el PDF (individual con
    `talent_id`, o consolidado con `talent_ids=["all"]` o lista). Es `def`
    (WeasyPrint es I/O bloqueante).
  - `GET /reports/` — historial (tabla `reports`).
  - `GET /reports/{id}/download` — regenera y descarga desde la metadata.
- **Persistencia:** los PDF **no se guardan en disco**; se regeneran bajo demanda
  a partir de la fila en `reports` (Fase 9.5). `content_hash` (sha256) permite
  detectar cambios.
- **Fuente Inter:** es un único archivo variable `app/static/fonts/Inter.woff2`.
  WeasyPrint (<70) no resuelve ejes variables, por lo que `report.css` declara
  **dos `@font-face` separados** (regular y bold) apuntando al mismo `.woff2`. La
  `url()` se resuelve con `base_url="."` desde la raíz del repo.
- **Audiencia (pivote Fase 9.7):** el PDF está diseñado para el **talento** (no
  para SEG). Omite deliberadamente funnel, comisión interna y oportunidades
  perdidas. Véase la auditoría de contrato.

---

# 8. Sincronización de datos

- **Ubicación:** `app/sync/jobs.py` (upserts) y `app/sync/scheduler.py`
  (programación). *Nota:* no existe `app/services/sync.py`; la lógica vive en
  `app/sync/`.
- **Cadencia:** **cada 30 minutos** (`scheduler.add_job(..., "interval",
  minutes=30)`), función `_run_all_syncs` (Pipedrive → Trello → Sheets).
- **Ciclo de vida (APScheduler):** `start()` se llama en el *lifespan* de FastAPI
  al arrancar (`app/main.py`); `shutdown(wait=False)` al apagar.
- **Disparo manual:** endpoint autenticado en `app/routers/sync.py` (botón
  "Sincronizar ahora" del dashboard). También puede invocarse el job desde consola
  (§11).
- **Bitácora:** cada corrida escribe en `sync_logs` (`source`, `started_at`,
  `finished_at`, `status`, `records_synced`, `error_message`).

---

# 9. Variables de entorno

Declaradas en `app/config.py` (pydantic-settings) y plantilladas en `.env.example`.
**Nunca incluir valores reales en documentación ni en el repositorio.**

| Variable | Descripción | Requerida | Ejemplo / obtención |
|---|---|---|---|
| `SECRET_KEY` | Secreto para firmar JWT | Sí | `secrets.token_urlsafe(64)` |
| `DATABASE_URL` | Cadena de conexión SQLite | No (default `sqlite:///./seg.db`) | `sqlite:////data/seg.db` en prod |
| `ADMIN_EMAIL` | Email del admin inicial (seed) | Sí | correo interno de SEG |
| `ADMIN_PASSWORD` | Contraseña del admin inicial | Sí | contraseña fuerte |
| `COOKIE_SECURE` | Cookie solo por HTTPS | No (default `True`) | `True` en prod |
| `PIPEDRIVE_API_TOKEN` | Token API v2 | Sí | Pipedrive → Settings → API |
| `PIPEDRIVE_DOMAIN` | Subdominio de la cuenta | Sí | `talentagency` |
| `PIPEDRIVE_PIPELINE_ID` | ID del pipeline comercial | No (default `None`) | entero |
| `PIPEDRIVE_STAGE_CONTRATO_ID` | ID de la etapa "Contrato" | No (default `None`) | entero |
| `GOOGLE_SHEETS_ID` | ID del sheet de leads | Sí | ID de la URL del Google Sheet |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON del service account (string) | Sí | descargado de Google Cloud |
| `TRELLO_API_KEY` | API key de Trello | Sí | trello.com/app-key |
| `TRELLO_TOKEN` | Token de Trello | Sí | generado desde la API key |
| `TRELLO_BOARD_IDS` | IDs de boards a considerar | Sí | lista separada por comas |
| `TRELLO_ORG_ID` | ID/nombre de la organización de Trello | No (default `""`) | `talentagency3` |
| `TRELLO_WORKSPACE_NAME` | Nombre del workspace de Trello | No (default `""`) | texto |
| `ANTHROPIC_API_KEY` | API key de Claude | Sí | console.anthropic.com |

**Nota:** las variables `PIPEDRIVE_PIPELINE_ID`, `PIPEDRIVE_STAGE_CONTRATO_ID`,
`TRELLO_ORG_ID` y `TRELLO_WORKSPACE_NAME` **ya están declaradas en `config.py`**
(commit de fix de configuración) y son legibles vía `settings`. Anteriormente
estaban presentes en `.env` pero ausentes en `Settings`, lo que producía
`AttributeError` al leerlas. Todas tienen valor por defecto, por lo que son
opcionales.

---

# 10. Deploy

- **Plataforma:** EasyPanel sobre el servidor existente de SEG. URL de producción:
  `https://automatizacion-dashboard-seg.slt9e0.easypanel.host/`.
- **Imagen:** `Dockerfile` multi-stage — *builder* (uv sync de dependencias) +
  *runtime* (`python:3.12-slim` con libs de sistema para WeasyPrint: Pango, Cairo,
  GDK-Pixbuf, libffi, fontconfig; usuario no-root `app`).
- **`docker-compose.yml`:** servicio `web` en el puerto 8000, `env_file: .env`,
  override de `DATABASE_URL` a `sqlite:////data/seg.db`, volúmenes
  **`seg_data:/data`** (DB persistente) y **`seg_reports:/app/reports`**, y
  healthcheck (`curl -f http://localhost:8000/health`).
- **`entrypoint.sh`:** al arrancar el contenedor: crea `/data` y `/app/reports`,
  ejecuta **`alembic upgrade head`**, corre `seed_admin`, y lanza Uvicorn
  (`--proxy-headers`). **Las migraciones se aplican automáticamente en cada
  arranque.**
- **Health check:** `GET /health` → `{"status":"ok","database":"ok|error"}`
  (siempre HTTP 200; la conectividad a DB se prueba con `SELECT 1`).
- **Procedimiento de deploy (manual):**
  1. `git push origin main`.
  2. En EasyPanel, botón **"Implementar"** sobre el servicio
     `automatizacion-dashboard-seg`. **No hay autodeploy configurado.**
  3. Esperar el build (~2–5 min) y verificar healthcheck verde.
  4. La migración corre sola vía `entrypoint.sh`; verificar en logs
     (`alembic upgrade head`).
- **Migración manual (solo si se requiere fuera del arranque):** en la consola del
  contenedor, `alembic current` y `alembic upgrade head`.
- **Rollback:**
  1. Restaurar backup de la DB:
     `cp /data/seg.db.backup-<ts> /data/seg.db` (y borrar `-shm`/`-wal` si existen).
  2. `alembic downgrade -1` si la migración causó el problema.
  3. Redeploy del commit anterior estable en EasyPanel.
  4. Verificar healthcheck 200.
- **Fecha del deploy inicial a producción:** 3 de julio de 2026 (Fase 9 completa
  a producción, commit `1f675b8`).

---

# 11. Procedimientos de mantenimiento

Los comandos de contenedor se ejecutan desde la **consola web de EasyPanel** del
servicio. La imagen **no incluye el CLI `sqlite3`**; para consultar la DB se usa
Python.

- **Backup de la DB (producción):**
  ```bash
  cp /data/seg.db /data/seg.db.backup-$(date +%Y%m%d-%H%M)
  ls -la /data/seg.db.backup*
  ```
- **Restaurar un backup:**
  ```bash
  cp /data/seg.db.backup-<timestamp> /data/seg.db
  rm -f /data/seg.db-shm /data/seg.db-wal
  ```
  (Reiniciar el servicio para que la app tome la DB restaurada.)
- **Query ad-hoc contra la DB (sin CLI sqlite3):**
  ```bash
  python3 -c "import sqlite3; c=sqlite3.connect('/data/seg.db'); \
  print(c.execute('SELECT COUNT(*) FROM deals WHERE status=\"won\"').fetchone())"
  ```
- **Revisar logs del servicio:** pestaña *Logs* del servicio en EasyPanel.
- **Forzar re-sincronización manual:** botón "Sincronizar ahora" en el dashboard,
  o invocando el job desde consola:
  ```bash
  python3 -c "from app.database import SessionLocal; from app.sync.jobs import sync_pipedrive; \
  db=SessionLocal(); print(sync_pipedrive(db)); db.close()"
  ```
- **Diagnóstico de problemas típicos:**
  - *El sync falla:* revisar `sync_logs` (`status='error'`, `error_message`) y
    validar credenciales del `.env`. Un `429` es rate limit de Pipedrive; reintenta
    solo.
  - *El PDF no genera:* típicamente faltan libs de sistema de WeasyPrint (revisar
    que la imagen runtime las incluya) o el periodo no tiene datos.
  - *El agente no responde (HTTP 502):* validar `ANTHROPIC_API_KEY` y cuota de la
    cuenta de Anthropic; revisar logs del router `agent`.

---

# 12. Consideraciones de seguridad

- **Rotación de secretos:** rotar `SECRET_KEY`, tokens de Pipedrive/Trello y la
  API key de Anthropic **cada 6 meses o al cambiar personal con acceso, lo que
  ocurra primero**. Rotar `SECRET_KEY` invalida las sesiones existentes.
- **Backups automáticos:** **hoy no existen.** Recomendación: configurar un backup
  periódico del volumen `seg_data` (snapshot de EasyPanel o cron externo que copie
  `/data/seg.db`), reteniendo al menos 7 días.
- **Datos sensibles:** `seg.db` contiene información comercial de talentos,
  contactos (leads con emails), montos y razones de pérdida. Tratar la DB y los
  backups como **confidenciales**; no compartir fuera de SEG.
- **Superficie de escritura:** las integraciones son solo lectura por diseño; la
  única escritura es la DB local. No habilitar `TRELLO_AUTO_CREATE_ENABLED`.
- **Acceso al repositorio:** repositorio privado de GitHub en
  `AlexisSchiavon/seg-dashboard`. Acceso actual: Alexis Zamora (Lumixia, owner).
  Cualquier acceso adicional se otorga previa solicitud escrita de EL CLIENTE.
  Conforme a la Cláusula Tercera del contrato, el cliente recibe acceso completo al
  código al liquidar la contraprestación.

---

# 13. Roadmap técnico y deuda conocida

Sección honesta del estado a 6-jul-2026.

- **Atribución de talento (raíz):** Pipedrive marca el talento por **label**
  (`label_ids`), pero el sync lo resuelve por **producto**. Resultado: deals
  ganados sin talento en el dashboard (auditoría: ~84 deals / ~$10.1M históricos
  sin label). Decisión pendiente de Luis sobre migrar el sync (§5.1).
- **H-09-03 — widget "sin talento" del dashboard interno:** ciertos widgets de la
  vista interna (`income_projection`, "cobrado de flujo") comparten un patrón
  *status-agnóstico* que puede inflar la vista interna; no afecta los PDF
  talent-facing (ya corregidos en 9.8f). Fix pendiente.
- **Trello — 11 de 12 boards no sincronizados:** solo "Admin TA" se ingiere; los
  boards por talento quedan fuera. Evaluar si el calendario de cobranza debe
  leerlos.
- **Cards de cobranza sin fecha:** en la auditoría, 22 de 23 tarjetas en columnas
  de cobro carecían de `due`. Depende de acción de TA (véase Manual Operativo).
- **Batch histórico 2025-12-08:** ~117 deals sin label creados ese día (posible
  importación/seed). Requiere decisión de limpieza en Pipedrive (acción de TA).
- **Pivotes de alcance sin formalizar:** PDF sin Claude (9.5a), audiencia PDF →
  talento (9.7), Trello auto-create desactivado. Requieren convenio modificatorio
  (Cláusula 13). Véase la auditoría de contrato.
- **Variables de entorno:** `TRELLO_ORG_ID`, `PIPEDRIVE_PIPELINE_ID`,
  `PIPEDRIVE_STAGE_CONTRATO_ID` y `TRELLO_WORKSPACE_NAME` ya fueron **declaradas en
  `config.py`** (resuelto). Véase §9.

---

# 14. Contacto y soporte

- **Periodo de garantía:** 60 días naturales posteriores al deploy final
  (Cláusula Sexta), durante los cuales se atienden correcciones dentro del alcance
  de la Cláusula Primera.
- **SLA de respuesta (Cláusula Décima Quinta):** **24 horas hábiles** para fallas
  críticas y **72 horas hábiles** para fallas menores.
- **Canal preferido:** WhatsApp o correo electrónico a Alexis Zamora.
  - WhatsApp: +522211747662
  - Email: alexis.schiavon@gmail.com
- **Prestador:** Alexis Ahkin Schiavon Zamora (desarrollador del sistema).

---

*Documento técnico generado el 6 de julio de 2026 a partir de introspección real
del repositorio (rama `main`). Los apartados marcados `[PENDIENTE]` requieren
confirmación del responsable del proyecto antes de la entrega final.*
