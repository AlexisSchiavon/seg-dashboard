

## ⚠️ RESTRICCIONES CRÍTICAS

**REGLA DE SUPERFICIE DE ESCRITURA (una sola línea):** Pipedrive y Google Sheets: read-only SIEMPRE, sin excepciones. Trello: read-only EXCEPTO `create_card` en la lista whitelisteada (`trello.allowed_create_list_ids()`) bajo `TRELLO_AUTO_CREATE_ENABLED`. La única otra escritura permitida es la base de datos local SQLite (`seg.db`). Esta invariante está blindada por el test estructural `tests/test_write_surface.py`, que truena en rojo si aparece cualquier otra escritura externa en `app/integrations/`.

Pipedrive y Google Sheets son SOLO LECTURA sin excepción: bajo ninguna circunstancia modificar, crear o eliminar datos en ellos. Para Trello la regla es SOLO LECTURA salvo la ÚNICA excepción autorizada descrita abajo (crear cards nuevas de auto-creación).

**REVOCACIÓN (2026-07-13) — auto-creación de cards en Trello vive AQUÍ, gated por `settings.TRELLO_AUTO_CREATE_ENABLED`**
La antigua "decisión permanente" de mantener `TRELLO_AUTO_CREATE_ENABLED = False` para siempre queda REVOCADA. Su premisa era falsa: el discovery del 2026-07-13 encontró que el M2 de fase_2_talent (que supuestamente manejaba esto en producción) **nunca se desplegó** y usaba el trigger incorrecto (stage 9 "Contrato y factura"), cuando la evidencia de `deal_stage_events` muestra que ~25% de los deals se marcan `won` desde etapas anteriores. Por eso a TA "se le escapaban" cards.

La auto-creación ahora vive en seg-dashboard con **alcance estrictamente limitado**:
- Trigger: `Deal.status == 'won'` (reconciliación en `sync_trello`, cada 30 min → inmune a webhooks perdidos / Bug A).
- **Solo CREAR cards nuevas** en la whitelist `trello.allowed_create_list_ids()` (lista Contrato de prod + lista sandbox opcional). Cualquier `list_id` fuera de la whitelist falla con `ValueError` — nunca fallback. NUNCA mover/editar/archivar/borrar cards.
- Idempotencia doble: registro local `trello_cards` + escaneo en vivo del marcador `[seg:deal_id=N]` en Trello.
- Kill switch por env: `TRELLO_AUTO_CREATE_ENABLED` (default `False`). Habilitar en prod es un acto deliberado de configuración tras validación en sandbox (Fase C).
- **Pipedrive y Google Sheets siguen 100% read-only** — a diferencia del M2 de fase_2_talent, esta implementación NO escribe notas de vuelta en Pipedrive.

El M2 de fase_2_talent (`feature/m2-pipedrive-trello`) queda **DEPRECADO / NO DESPLEGAR**: desplegarlo duplicaría cards.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**SEG Talent Intelligence Dashboard**

Una plataforma web de inteligencia comercial para Santillán Entertainment Group (agencia de talentos/influencers en México, 21 talentos actuales). Consolida en un solo dashboard los datos de Pipedrive (CRM/funnel comercial), Google Sheets (leads entrantes por Gmail) y Trello (ejecución de campañas y cobranza), con reportes mensuales generados por IA (Claude) y un agente de lenguaje natural embebido para consultar los datos.

**Core Value:** Dar visibilidad consolidada y en tiempo real del funnel comercial e ingresos por talento — reemplazando el proceso actual donde el equipo revisa Pipedrive, Sheets y Trello por separado y arma reportes a mano.

### Constraints

- **Tech stack (backend)**: Python 3.12 + FastAPI + SQLite (SQLAlchemy) + python-dotenv + httpx — elección fija, no sustituir framework
- **Tech stack (frontend)**: HTML + CSS + Vanilla JS, dark mode, mobile-first — sin frameworks JS
- **Integraciones**: Pipedrive API, Google Sheets API (gspread + google-auth), Trello API
- **IA**: Anthropic Claude API para reportes PDF (M5) y agente de lenguaje natural (M6)
- **Deploy**: EasyPanel + Docker (M7)
- **Estructura de carpetas predefinida**:
  ```
  seg-dashboard/
  ├── app/
  │   ├── main.py
  │   ├── config.py
  │   ├── models.py
  │   ├── database.py
  │   ├── integrations/ (pipedrive.py, sheets.py, trello.py)
  │   ├── services/ (funnel.py, kpis.py, reports.py, agent.py)
  │   └── routers/ (dashboard.py, talents.py, leads.py, reports.py)
  ├── frontend/ (index.html, css/, js/)
  ├── Dockerfile
  ├── docker-compose.yml
  ├── .env.example
  ├── CLAUDE.md
  └── memory.md
  ```
- **Variables de entorno**: PIPEDRIVE_API_TOKEN, PIPEDRIVE_DOMAIN, GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_JSON, TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_IDS, ANTHROPIC_API_KEY, SECRET_KEY, DATABASE_URL=sqlite:///./seg.db
- **Extensibilidad**: agregar talentos nuevos debe ser posible vía datos/configuración, sin tocar código
- **Orden de build**: estrictamente incremental M1 → M7, validando cada módulo antes de avanzar
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | Already fixed by project constraints. Fully supported by every library below; no compatibility blockers found. |
| FastAPI | 0.136.x (`fastapi>=0.115,<0.137`, pin loosely) | Web framework | Already fixed by project constraints. Current stable line as of June 2026. Built-in Pydantic v2 validation, OpenAPI docs, dependency-injection system maps cleanly to the `routers/` + `services/` structure already defined in PROJECT.md. |
| Uvicorn | 0.49.x (`uvicorn[standard]`) | ASGI server | Standard pairing with FastAPI; `[standard]` extra includes `httptools`/`uvloop` for performance and `python-dotenv` support for `--env-file`. |
| SQLAlchemy | 2.0.x (`sqlalchemy>=2.0,<2.1`) | ORM / DB layer | Project constraint. SQLAlchemy 2.0's typed `Mapped[]` / `mapped_column()` declarative style is the current standard — old 1.x `Column()` style is legacy. |
| SQLite | bundled (Python stdlib `sqlite3`) | Database | Project constraint (`DATABASE_URL=sqlite:///./seg.db`). Zero operational overhead for a single-tenant internal tool with ~21 talents and modest deal volume. |
| Alembic | 1.18.x | DB migrations | De-facto standard migration tool for SQLAlchemy. Use a **sync** engine for Alembic even though the app can run sync SQLAlchemy too — see Architecture note below. |
| Pydantic | 2.13.x (ships with FastAPI) | Data validation / schemas | Comes in transitively via FastAPI. Use `pydantic-settings` for `config.py` (env var loading) instead of hand-rolled `os.environ` parsing. |
| python-dotenv | 1.2.x | `.env` loading | Project constraint. Note: if using `pydantic-settings`, it can load `.env` itself — `python-dotenv` is still useful for `uvicorn --env-file` and scripts outside the app context. |
| httpx | 0.28.x | HTTP client for all integrations | Project constraint. Sync **and** async client with the same API — use for Pipedrive, Trello, and any raw REST calls. Modern replacement for `requests` (which FastAPI itself uses internally for its own `TestClient`, but is not recommended for new outbound integration code). |
### Supporting Libraries — Auth (M1)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **PyJWT** | `pyjwt>=2.10,<3.0` | Encode/decode/verify JWT access tokens | Use for **all** JWT handling. Do NOT use `python-jose` (see "What NOT to Use"). |
| **pwdlib[argon2]** | `pwdlib>=0.2,<0.4` | Password hashing | Use for hashing/verifying user passwords. Configure `PasswordHash.recommended()` which defaults to Argon2 with bcrypt fallback for verifying any legacy hashes. This is the path FastAPI's own docs are migrating to (PR #13917, merged into the official OAuth2/JWT tutorial). |
| `python-multipart` | latest (`>=0.0.18`) | Form data parsing | Required by FastAPI for `OAuth2PasswordRequestForm` (the standard `/token` login endpoint pattern uses `application/x-www-form-urlencoded`). |
### Supporting Libraries — Integrations (M2-M4)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **gspread** | `gspread>=6.1,<7.0` (latest 6.2.1) | Google Sheets read/write | M3. Use `gspread.service_account_from_dict()` or `service_account()` with a service-account JSON for server-to-server auth — no OAuth consent flow needed. |
| **google-auth** | `google-auth>=2.40,<3.0` (latest 2.53.0) | Service-account credential handling | M3. `gspread` depends on this transitively, but pin it explicitly since `google-auth` is also the credential layer if you ever touch other Google APIs (Drive, Gmail). |
| `google-auth-oauthlib` | only if needed | OAuth2 user-flow auth | NOT needed for M3 — service account is sufficient for a single shared sheet. Skip unless requirements change to per-user Google login. |
| Pipedrive client | **none — use `httpx` directly** | Pipedrive REST API v1/v2 | M2. See "What NOT to Use" — no maintained official Python SDK exists. Write a thin `app/integrations/pipedrive.py` wrapper around `httpx.AsyncClient` with typed response models (Pydantic) for Deals, Persons, Products, Custom Fields. |
| Trello client | **none — use `httpx` directly** | Trello REST API | M4. `py-trello` (last released June 2024, `requires_python: None`) is effectively unmaintained. Trello's REST API is small and well-documented (key+token query-param auth) — a thin `app/integrations/trello.py` wrapper over `httpx` is less risk than depending on a stale wrapper. |
### Supporting Libraries — AI / Reports (M5-M6)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **anthropic** | `anthropic>=0.79,<1.0` (latest 0.109.1 as of June 2026 — verify pin at build time, this SDK ships frequently) | Claude API client | M5/M6. Requires Python >=3.9, fully compatible with 3.12. |
| **WeasyPrint** | `weasyprint>=66,<70` (latest 69.0, requires Python >=3.10) | HTML/CSS → PDF rendering | M5. Recommended approach: have Claude generate structured report content (JSON or Markdown), render it into an HTML template (Jinja2) styled with CSS matching the dashboard's dark-mode design system, then convert to PDF with WeasyPrint. This reuses frontend CSS knowledge and produces polished, branded PDFs. |
| Jinja2 | `jinja2>=3.1` | HTML templating for reports | M5. Pairs with WeasyPrint — render report data into an HTML template before PDF conversion. FastAPI already depends on it for `Jinja2Templates` if you ever serve server-rendered fragments. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` or `pip` + `requirements.txt` / `pyproject.toml` | Dependency management | Project already has `pyproject.toml` and `.python-version` (3.12) — use `uv` for fast, reproducible installs in Docker builds (single-layer cache-friendly). |
| `ruff` | Linting + formatting | Fast, single-tool replacement for flake8/black/isort. Optional but recommended given solo/small-team velocity. |
| `pytest` + `httpx` (`TestClient`/`ASGITransport`) | Testing | FastAPI's recommended test client is built on `httpx`. Write integration tests per router as modules are built. |
## Installation
# Core (M1)
# Integrations (M2-M4) — added incrementally, no extra clients needed beyond httpx
# AI / Reports (M5-M6)
# Dev dependencies
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| PyJWT | python-jose | Never for new code — `python-jose` is unmaintained since 2021, depends on a vulnerable `ecdsa` package, and FastAPI's own maintainers are removing it from official docs (GitHub discussion #11345). |
| pwdlib[argon2] | passlib[bcrypt] | Only if you need to support legacy hash formats beyond bcrypt/argon2 (e.g., migrating an existing user DB with `pbkdf2_sha256` or `des_crypt` hashes). `passlib` is unmaintained (last release 2020) and breaks with `bcrypt>=4.1` (`AttributeError: module 'bcrypt' has no attribute '__about__'`) unless patched. For a greenfield user table, pwdlib is strictly better. |
| Sync SQLAlchemy + sync FastAPI routes | Async SQLAlchemy (`asyncpg`-style with `aiosqlite`) | If M2-M4 integration calls (Pipedrive/Sheets/Trello) become a bottleneck and you want the whole request pipeline async end-to-end. For a single-tenant internal dashboard with SQLite and modest concurrency, sync SQLAlchemy is simpler, Alembic works natively with it (no async migration env quirks), and `gspread`/Pipedrive-via-httpx calls can still run in FastAPI's threadpool via `def` (not `async def`) endpoints. Revisit if M6's NL agent needs to fan out many concurrent tool calls. |
| httpx wrappers for Pipedrive/Trello | `pipedrive-python-lib`, `pipedrive-client`, `py-trello` | Only as a reference for endpoint shapes/response examples — do not add as a runtime dependency. All are either unofficial, last updated 2023-2024, or have unclear `requires_python` support. A 100-150 line typed wrapper per integration is less maintenance risk than an abandoned dependency, and matches the modular `integrations/` folder structure already planned. |
| WeasyPrint | ReportLab | If reports need precise pixel-level layout control (e.g., complex multi-column financial statements) rather than HTML/CSS-driven design. ReportLab's API is lower-level (drawing primitives) and doesn't reuse the dashboard's existing CSS — more code for a similar visual result here. |
| WeasyPrint | fpdf2 | If Docker image size is a hard constraint. WeasyPrint requires system libraries (Pango, Cairo, GDK-Pixbuf — via `apt-get install` in the Dockerfile). `fpdf2` is pure-Python with zero system deps, but its layout model is much more manual (no CSS), making "AI writes content → polished branded PDF" harder to achieve quickly. |
| `pydantic-settings` for config | raw `os.environ` + `python-dotenv` | If you want zero extra dependencies. `pydantic-settings` (ships as part of the Pydantic ecosystem, install via `pip install pydantic-settings`) gives typed, validated env config (`PIPEDRIVE_API_TOKEN: str`, etc.) which catches missing env vars at startup — valuable given the long list of required env vars in PROJECT.md. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `python-jose[cryptography]` | Unmaintained since 2021, cannot be installed cleanly on Python >=3.10 in some environments, depends on a vulnerable `ecdsa` package with no patch planned. Still appears in older FastAPI tutorials/blog posts but FastAPI maintainers are actively replacing it (PR #13917). | `PyJWT` |
| `passlib` (alone, on bcrypt>=4.1) | Last released 2020; throws `AttributeError: module 'bcrypt' has no attribute '__about__'` with `bcrypt>=4.1` (still functions but logs errors / can break in strict environments). Officially discussed as needing replacement in fastapi/fastapi#11773. | `pwdlib[argon2]` |
| `py-trello` | Last release June 2024, no `requires_python` metadata, thin abstraction that doesn't add much over calling Trello's REST API directly with `httpx` (Trello auth is just `?key=...&token=...` query params). | `httpx` + a small typed wrapper in `app/integrations/trello.py` |
| `pipedrive-python-lib` / `pipedrive-client` (PyPI packages) | Both are community/unofficial, last meaningfully updated 2023, target Pipedrive API v1 only (project needs v1+v2 fields per PROJECT.md custom fields). Pipedrive's "official SDKs" page lists generated clients, but Python is not consistently maintained among them. | `httpx` + a small typed wrapper in `app/integrations/pipedrive.py` against Pipedrive's documented v1/v2 REST endpoints |
| SQLAlchemy 1.x style (`Column`, `declarative_base()` from `sqlalchemy.ext.declarative`) | Legacy API, superseded by SQLAlchemy 2.0's typed `Mapped`/`mapped_column` style which integrates better with Pydantic v2 type hints used throughout FastAPI. | SQLAlchemy 2.0 declarative style (`class Base(DeclarativeBase): pass`, `Mapped[int]`, `mapped_column()`) |
| Async SQLAlchemy + `aiosqlite` for M1 | Adds complexity (async session management, async Alembic env.py with `run_sync`) with no payoff for a low-concurrency internal tool on SQLite, where SQLite itself serializes writes regardless. | Sync SQLAlchemy session per-request via `Depends()`; reserve async for the `httpx` calls to Pipedrive/Sheets/Trello/Anthropic, which are naturally async-friendly even from sync route handlers if needed (or just call `httpx` sync client in `def` endpoints — FastAPI runs these in a threadpool). |
## Stack Patterns by Variant
- Use `fastapi[standard]` + `uvicorn[standard]` + sync SQLAlchemy 2.0 + Alembic + PyJWT + `pwdlib[argon2]`.
- `app/database.py`: `create_engine("sqlite:///./seg.db", connect_args={"check_same_thread": False})`, `sessionmaker`, `Base(DeclarativeBase)`.
- `app/config.py`: `pydantic-settings` `BaseSettings` subclass reading all env vars from PROJECT.md (`SECRET_KEY`, `DATABASE_URL`, etc.) — fail fast if `SECRET_KEY` missing.
- JWT: `/token` (or `/auth/login`) endpoint using `OAuth2PasswordRequestForm`, issue access token with PyJWT (`HS256`, `SECRET_KEY` from env), expose `get_current_user` dependency for protected routes.
- Health check: simple `GET /health` returning `{"status": "ok"}` plus a DB connectivity check (`SELECT 1`).
- Each integration gets its own module in `app/integrations/` returning Pydantic models, not raw dicts — this is what the `services/` layer (funnel.py, kpis.py) will consume.
- Use `httpx.Client` (sync) or `httpx.AsyncClient` consistently — pick one pattern across all three integrations for consistency. Given M1 starts sync, sync `httpx.Client` with connection reuse (module-level client or DI-provided) is the simpler default; revisit only if M6's agent needs concurrent fan-out.
- Cache Pipedrive custom-field metadata (field key → label mapping) on startup or with a short TTL — Pipedrive custom fields are referenced by opaque hash keys, not names.
- Two-step pipeline: (1) Claude call via `anthropic` SDK returns structured JSON (use `output_format` with a Pydantic model via `client.messages.create(..., output_format=ReportModel)` if using a model/SDK version that supports structured outputs — verify availability for the model in use at build time, as this is a newer beta feature) or a well-defined Markdown/JSON contract via prompt engineering as a fallback; (2) render that data into a Jinja2 HTML template styled to match the dashboard, then `weasyprint.HTML(string=html).write_pdf(path)`.
- Store generated PDFs on disk (or a `reports/` volume) with metadata rows in SQLite for the "downloadable history" requirement.
- Use the `anthropic` SDK's tool-use (function calling) pattern: define tools as Python functions (`@beta_tool` decorator, or manual JSON schemas) that call into `app/services/` (funnel.py, kpis.py) — i.e., the agent's "tools" are read-only wrappers around the same service layer the dashboard uses, not direct DB/API access. This keeps a single source of truth for business logic (70% commission calc, funnel stage logic, etc.) and matches the "OpenClaw" modular vision in PROJECT.md.
- Run the tool-use loop server-side (non-streaming `messages.create` loop, or `messages.stream` for a more responsive chat UI) — confirm with current Anthropic docs which Claude model alias to target at M6 build time, since model names rotate (e.g., `claude-sonnet-4-5-...` family was current per SDK examples as of mid-2026).
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| Python 3.12 | All packages listed above | No known 3.12 incompatibilities found for fastapi, sqlalchemy 2.0, alembic, pyjwt, pwdlib, gspread, google-auth, anthropic, weasyprint (>=3.10 required), httpx. |
| `pwdlib[argon2]` | `argon2-cffi` (pulled in transitively) | Argon2 requires a C extension (`argon2-cffi`) — confirm it builds in the Docker base image (slim Python images may need `build-essential` at build stage, or use a wheel-only install which `argon2-cffi` provides for common platforms). |
| WeasyPrint 69.x | System libs: Pango, GDK-Pixbuf, libffi, Cairo | Must be installed via `apt-get install` in the Dockerfile (e.g., `libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev`). This is the main Docker-image-size and build-complexity cost of the recommended PDF approach — budget for it in the M7 Dockerfile, and consider a multi-stage build to keep the final image lean. |
| `gspread>=6.1` | `google-auth>=2.x` | gspread 6.x fully moved off `oauth2client` to `google-auth`; do not mix old `oauth2client`-based tutorials with gspread 6.x — auth API differs (`gspread.service_account_from_dict()` vs old `ServiceAccountCredentials.from_json_keyfile_dict()`). |
| Alembic | Sync SQLAlchemy engine | Even if parts of the app later become async, Alembic's `env.py` is simplest configured against a sync engine/connection string — this is the documented standard pattern, avoids `run_sync` boilerplate. |
| `anthropic` SDK | Frequent releases (multiple per month observed) | Pin a specific version in `pyproject.toml` (e.g., `anthropic==0.109.1` or whatever is current at M5 build time) rather than a loose range — structured-output and tool-use APIs have evolved across recent minor versions; re-verify against Context7/official docs when M5/M6 actually start, don't rely on this research's exact version number months later. |
## Sources
- `/anthropics/anthropic-sdk-python` (Context7, via ctx7 CLI fallback) — verified tool-use loop pattern (`messages.create` with `tools=`, `@beta_tool` decorator), structured output via `output_format=PydanticModel` in `messages.stream` (confidence: MEDIUM — beta feature, version-sensitive).
- [PyPI: anthropic](https://pypi.org/project/anthropic/) — version 0.109.1, `requires_python>=3.9` (confidence: HIGH, checked live June 2026).
- [PyPI: gspread](https://pypi.org/project/gspread/), [PyPI: google-auth](https://pypi.org/project/google-auth/) — versions 6.2.1 / 2.53.0 (confidence: HIGH).
- [PyPI: pyjwt](https://pypi.org/project/pyjwt/), [PyPI: pwdlib](https://pypi.org/project/pwdlib/), [PyPI: passlib](https://pypi.org/project/passlib/) — versions 2.13.0 / 0.3.0 / 1.7.4 (confidence: HIGH).
- [PyPI: weasyprint](https://pypi.org/project/weasyprint/) — version 69.0, `requires_python>=3.10` (confidence: HIGH).
- [PyPI: py-trello](https://pypi.org/project/py-trello/) — version 0.20.1, last upload 2024-06-11, `requires_python: None` (confidence: HIGH — used to support "avoid this dependency" recommendation).
- [fastapi/fastapi PR #13917](https://github.com/fastapi/fastapi/pull/13917) — official docs migration from passlib to pwdlib + Argon2 (confidence: MEDIUM, GitHub PR — describes in-progress doc change).
- [fastapi/fastapi Discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) and [#9587](https://github.com/fastapi/fastapi/discussions/9587) — python-jose deprecation discussion, PyJWT as replacement (confidence: MEDIUM, community discussion but consistent with PyPI/GitHub activity evidence).
- [fastapi/fastapi Discussion #11773](https://github.com/fastapi/fastapi/discussions/11773) — passlib unmaintained status (confidence: MEDIUM).
- [pyca/bcrypt issue #684](https://github.com/pyca/bcrypt/issues/684) — `passlib` + `bcrypt>=4.1` `__about__` AttributeError (confidence: HIGH, reproducible upstream issue).
- WebSearch: "FastAPI SQLAlchemy 2.0 SQLite Alembic project structure best practices 2025" — sync engine for Alembic, naming conventions, domain-driven structure (confidence: MEDIUM, multiple consistent community sources).
- WebSearch: Pipedrive Python SDK landscape — no actively maintained official Python client found; `pipedrive-python-lib` last updated 2023 (confidence: MEDIUM — absence-of-evidence claim, but consistent across Pipedrive's own SDK listing and PyPI).
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
