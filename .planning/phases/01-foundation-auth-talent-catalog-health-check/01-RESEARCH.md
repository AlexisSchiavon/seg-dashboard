# Phase 1: Foundation — Auth, Talent Catalog & Health Check - Research

**Researched:** 2026-06-10
**Domain:** FastAPI app scaffolding, JWT cookie auth (PyJWT + pwdlib[argon2]), SQLAlchemy 2.0 + Alembic + SQLite (WAL), seed scripts, minimal dark-theme login UI (Vanilla JS)
**Confidence:** HIGH

## Summary

Phase 1 stands up the entire foundation: a FastAPI app following the predefined `app/` layout, SQLite via SQLAlchemy 2.0 (declarative `Mapped`/`mapped_column` style) with WAL mode + busy_timeout configured from the first connection, Alembic migrations on a sync engine, JWT auth delivered via a secure httpOnly cookie (PyJWT + `pwdlib[argon2]`), a single-admin seed script, a `talents` + `talent_products` schema seeded with the 21 real talent names, and a minimal but real dark-themed login page matching `mockup.html`'s design tokens.

All core libraries (FastAPI 0.136.3, SQLAlchemy 2.0.50, Alembic 1.18.4, PyJWT 2.13.0, pwdlib 0.3.0, pydantic-settings 2.14.1, httpx 0.28.1, python-dotenv 1.2.2, python-multipart 0.0.32, uvicorn 0.49.0) were re-verified live against PyPI on 2026-06-10 and match (or slightly exceed) the versions already pinned in `CLAUDE.md`'s stack research from yesterday — no version drift to flag. `requires-python` for `fastapi`, `uvicorn`, `alembic`, `pydantic-settings`, `python-dotenv`, and `python-multipart` is now `>=3.10`, which is satisfied by the project's target Python 3.12 (current `.python-version`/`pyproject.toml` say 3.9 and must be bumped — this is explicitly called out in CONTEXT.md as required, non-discretionary work).

**Primary recommendation:** Build `app/` exactly per the CLAUDE.md folder structure with a thin `auth/` package (security.py, dependencies.py, router.py) for all JWT/cookie/password logic, configure SQLite WAL+busy_timeout via a SQLAlchemy `connect` event listener in `database.py` from the very first commit, model `Talent`/`TalentProduct`/`User` with SQLAlchemy 2.0 declarative style, drive the schema via Alembic (sync engine) from migration #1, and seed both the admin user and the 21 talents via idempotent scripts that read from `.env` / a static seed list — not hardcoded into route handlers.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Login (email/password → JWT cookie) | API / Backend | Browser (login form UI) | Credential verification, password hashing, and JWT signing must happen server-side; browser only submits the form and stores the resulting httpOnly cookie automatically. |
| Session validation on protected routes | API / Backend | — | `get_current_user` dependency runs server-side per request; browser has no visibility into token validity beyond receiving 401s. |
| Auto-redirect to login on 401 | Browser / Client | — | Pure client-side `fetch()` response-interceptor behavior (D-03); no server involvement beyond returning 401. |
| `/health` endpoint | API / Backend | Database | Process-up check is pure backend; optional `SELECT 1` touches the DB tier. |
| Talent catalog CRUD (`/talents`, `/talents/{id}/products`) | API / Backend | Database / Storage | Standard REST CRUD over SQLAlchemy models; no business logic beyond validation. |
| Talent catalog persistence (talents, talent_products, users) | Database / Storage | — | SQLite via SQLAlchemy 2.0; source of truth for Phase 2+ joins. |
| Password hashing & verification | API / Backend | — | `pwdlib[argon2]` runs server-side only; never exposed to client. |
| Login page UI (centered card, dark theme) | Browser / Client | Frontend Server (static serving) | Static HTML/CSS/JS served by FastAPI's `StaticFiles`/`Jinja2Templates`; no SSR logic beyond serving the file. |
| Seed scripts (admin user, 21 talents) | API / Backend (one-off scripts) | Database / Storage | Run via `python -m app.scripts.seed_*` against the same SQLAlchemy session/engine as the app — not part of the request/response cycle. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.x | Runtime | Fixed by CLAUDE.md. Repo currently has `.python-version`=3.9 and `pyproject.toml` `requires-python=">=3.9"` — both must be updated to 3.12 in this phase (non-discretionary, called out in CONTEXT.md). [VERIFIED: codebase] |
| FastAPI | `0.136.3` (`fastapi[standard]`) | Web framework | [VERIFIED: PyPI registry, 2026-06-10] Current stable; `requires_python>=3.10`, satisfied by 3.12. `[standard]` extra pulls in uvicorn[standard], httpx, jinja2, python-multipart, pydantic-settings, email-validator automatically. |
| Uvicorn | `0.49.0` (`uvicorn[standard]`) | ASGI server | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.10`. Pulled transitively by `fastapi[standard]`. |
| SQLAlchemy | `2.0.50` | ORM / DB layer | [VERIFIED: PyPI registry, 2026-06-10] 2.0.x line, `Mapped[]`/`mapped_column()` declarative style is current standard. `requires_python>=3.7`. |
| SQLite | bundled (`sqlite3` stdlib) | Database | Project constraint (`DATABASE_URL=sqlite:///./seg.db`). [ASSUMED — path convention from PITFALLS.md, not yet locked in CONTEXT.md beyond the env var name]. |
| Alembic | `1.18.4` | DB migrations | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.10`. Use sync engine in `env.py` (standard, documented pattern). |
| Pydantic | ships with FastAPI 0.136.3 (v2.x) | Data validation / schemas | Transitive via FastAPI. |
| pydantic-settings | `2.14.1` | `config.py` env loading | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.10`. `BaseSettings` subclass — fail fast on missing `SECRET_KEY`. |
| python-dotenv | `1.2.2` | `.env` loading for scripts/CLI | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.10`. Useful for seed scripts run outside `uvicorn`. |
| httpx | `0.28.1` | HTTP client (used by future integrations; FastAPI TestClient in M1 tests) | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.8`. Pulled transitively by `fastapi[standard]`; also needed directly for `pytest` + `ASGITransport`. |

### Supporting (Auth)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyJWT | `2.13.0` (`pyjwt>=2.10,<3.0`) | Encode/decode/verify JWT | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.9`. Use `jwt.encode(payload, SECRET_KEY, algorithm="HS256")` / `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])`. Do NOT use `python-jose`. |
| pwdlib[argon2] | `0.3.0` (pwdlib) + `argon2-cffi` `25.1.0` | Password hashing | [VERIFIED: PyPI registry, 2026-06-10] `pwdlib requires_python>=3.10`; `argon2-cffi requires_python>=3.8`. `pwdlib`'s `argon2` extra pins `argon2-cffi<26,>=23.1.0` — 25.1.0 satisfies this. Use `PasswordHash.recommended()`. |
| python-multipart | `0.0.32` (`>=0.0.18`) | Form parsing for `OAuth2PasswordRequestForm` | [VERIFIED: PyPI registry, 2026-06-10] `requires_python>=3.10`. Pulled transitively by `fastapi[standard]`, list explicitly in `pyproject.toml` for clarity. |

### Supporting (Dev/Test)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest 8.x (verify at install time) | Test runner | Phase 1 establishes the test suite — auth roundtrip, health check, talent CRUD. |
| ruff | latest | Lint + format | Optional per STACK.md but recommended; configure in `pyproject.toml`. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | Never — unmaintained since 2021, vulnerable `ecdsa` dep, FastAPI removing from official docs (PR #13917). Already excluded by CLAUDE.md. |
| pwdlib[argon2] | passlib[bcrypt] | passlib unmaintained (last release 2020), breaks with `bcrypt>=4.1` (`AttributeError: module 'bcrypt' has no attribute '__about__'`). Already excluded by CLAUDE.md. |
| Sync SQLAlchemy | Async SQLAlchemy + aiosqlite | Adds async session/Alembic complexity with no payoff for low-concurrency SQLite; revisit only if M6 agent needs concurrent fan-out. Already excluded by CLAUDE.md. |
| Cookie-based custom OAuth2 dependency | `fastapi-users` or similar auth framework | Overkill for a single-admin-account system with no roles (FUT-03 deferred); a ~150-line `auth/` package is simpler and matches ARCHITECTURE.md's modular plan. |

**Installation:**
```bash
uv add "fastapi[standard]" sqlalchemy alembic pydantic-settings python-dotenv httpx \
  pyjwt "pwdlib[argon2]" python-multipart
uv add --dev pytest ruff
```

**Version verification:** All versions above were checked live against `https://pypi.org/pypi/<pkg>/json` on 2026-06-10. These match or slightly exceed `.planning/research/STACK.md`'s versions from 2026-06-09 (e.g., pydantic-settings 2.14.1 vs STACK.md's unspecified version, pyjwt 2.13.0 matches exactly, pwdlib 0.3.0 matches exactly). No drift requiring re-discussion.

**Note on `fastapi[standard]` transitive deps:** As of FastAPI 0.136.3, the `standard` extra now includes `fastar>=0.9.0` (a Rust-tar binding used by `fastapi-cli` for its dev-server tooling) in addition to the previously-known `fastapi-cli`, `httpx`, `jinja2`, `python-multipart`, `email-validator`, `uvicorn[standard]`, `pydantic-settings`, `pydantic-extra-types`. `fastar` is a legitimate package (12 releases since Oct 2025, real GitHub repo `DoctorJohn/fastar`) — it is pulled in automatically and does not need to be referenced or audited separately; flagged here only so it isn't mistaken for an anomaly during install. [VERIFIED: PyPI registry, 2026-06-10]

## Package Legitimacy Audit

`slopcheck` could not be installed in this research environment (`pip` not available; `pip3 install slopcheck --break-system-packages` failed with externally-managed-environment / no network install path). Per the graceful-degradation protocol, **all packages below are tagged `[ASSUMED]`** for legitimacy purposes — the planner must gate the initial `uv add` install step behind a `checkpoint:human-verify` task. Note: PyPI registry existence and version numbers ARE verified live (see Standard Stack table) — only the slopcheck malicious-package screen is unavailable.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| fastapi | PyPI | ~7 yrs (since 2018) | very high (>50M/mo class) | github.com/fastapi/fastapi | [ASSUMED — slopcheck unavailable] | Approved, human-verify before install |
| uvicorn | PyPI | ~7 yrs | very high | github.com/encode/uvicorn | [ASSUMED] | Approved, human-verify before install |
| sqlalchemy | PyPI | ~20 yrs | very high | github.com/sqlalchemy/sqlalchemy | [ASSUMED] | Approved, human-verify before install |
| alembic | PyPI | ~13 yrs | very high | github.com/sqlalchemy/alembic | [ASSUMED] | Approved, human-verify before install |
| pydantic-settings | PyPI | ~3 yrs | very high | github.com/pydantic/pydantic-settings | [ASSUMED] | Approved, human-verify before install |
| python-dotenv | PyPI | ~12 yrs | very high | github.com/theskumar/python-dotenv | [ASSUMED] | Approved, human-verify before install |
| httpx | PyPI | ~6 yrs | very high | github.com/encode/httpx | [ASSUMED] | Approved, human-verify before install |
| pyjwt | PyPI | ~13 yrs | very high | github.com/jpadilla/pyjwt | [ASSUMED] | Approved, human-verify before install |
| pwdlib | PyPI | ~2 yrs | growing | github.com/frankie567/pwdlib | [ASSUMED] | Approved, human-verify before install |
| argon2-cffi | PyPI | ~10 yrs | very high (transitive via pwdlib[argon2]) | github.com/hynek/argon2-cffi | [ASSUMED] | Approved, human-verify before install |
| python-multipart | PyPI | ~10 yrs | very high (transitive) | github.com/Kludex/python-multipart | [ASSUMED] | Approved, human-verify before install |

**Packages removed due to slopcheck [SLOP] verdict:** none (slopcheck not run)
**Packages flagged as suspicious [SUS]:** none (slopcheck not run)

*slopcheck was unavailable at research time — all packages above are tagged `[ASSUMED]` and the planner must gate the install step behind a `checkpoint:human-verify` task. All of these are extremely well-established, long-lived packages (7-20 years on PyPI, official orgs/maintainers with verifiable GitHub repos) — risk is LOW in practice, but the gate is included per protocol.*

## Architecture Patterns

### System Architecture Diagram

```
Browser (login page + future dashboard)
   |
   | 1. POST /auth/login (email, password as form data)
   v
+-----------------------------------------------------+
| FastAPI app (app/main.py)                            |
|                                                       |
|  routers/auth.py                                     |
|   - POST /auth/login   -> verify password (pwdlib)   |
|                          -> issue JWT (PyJWT)         |
|                          -> set httpOnly cookie       |
|   - POST /auth/logout  -> clear cookie                |
|   - POST /auth/change-password (protected)           |
|   - POST /auth/users   (protected, admin-style)       |
|                                                       |
|  auth/dependencies.py                                |
|   - get_current_user(request) reads cookie           |
|     -> jwt.decode -> 401 if missing/expired/invalid  |
|                                                       |
|  routers/talents.py  (all routes Depends(get_current_user)) |
|   - GET/POST /talents                                |
|   - PATCH /talents/{id}                              |
|   - GET/POST/DELETE /talents/{id}/products           |
|                                                       |
|  routers/health.py                                   |
|   - GET /health  (public, optional SELECT 1)         |
|                                                       |
|  database.py                                         |
|   - engine (SQLite, WAL + busy_timeout via listener) |
|   - SessionLocal, get_db() dependency                |
+-----------------------------------------------------+
   |
   v
seg.db (SQLite file, WAL mode)
   - users
   - talents
   - talent_products

Alembic (offline, CLI-driven)
   - alembic/env.py -> sync engine -> Base.metadata
   - migrations create users, talents, talent_products tables

Seed scripts (offline, CLI-driven, idempotent)
   - app/scripts/seed_admin.py   (reads ADMIN_EMAIL/ADMIN_PASSWORD from .env)
   - app/scripts/seed_talents.py (reads static 21-name list)
```

A reader can trace the primary use case (login -> protected talent list) by following: browser POST /auth/login -> auth/router.py verifies credentials via pwdlib + queries `users` table via `get_db()` -> issues JWT via PyJWT -> sets httpOnly cookie -> browser's subsequent GET /talents includes cookie automatically -> `get_current_user` dependency decodes JWT -> talents router queries `talents`/`talent_products` tables -> returns Pydantic schema JSON.

### Recommended Project Structure

This phase establishes the structure from CLAUDE.md plus the `auth/` and `schemas/` packages recommended by `.planning/research/ARCHITECTURE.md` (both are additive to, not in conflict with, the CLAUDE.md-mandated layout):

```
app/
├── main.py                  # App factory: creates FastAPI(), registers routers, mounts static frontend
├── config.py                # pydantic-settings BaseSettings — ALL env vars from .env.example, fail-fast on missing SECRET_KEY
├── database.py              # engine (WAL+busy_timeout via event listener), SessionLocal, get_db(), Base
├── models.py                # SQLAlchemy 2.0 declarative models: User, Talent, TalentProduct
├── schemas/
│   ├── __init__.py
│   ├── auth.py              # LoginRequest (if not using OAuth2PasswordRequestForm), TokenResponse, ChangePasswordRequest, UserCreate
│   └── talent.py            # TalentCreate, TalentUpdate, TalentRead, TalentProductCreate/Read
├── auth/
│   ├── __init__.py
│   ├── security.py          # PasswordHash.recommended(), create_access_token(), decode_access_token()
│   ├── dependencies.py       # get_current_user(request) -> User, reads cookie
│   └── router.py             # /auth/login, /auth/logout, /auth/change-password, /auth/users (POST)
├── routers/
│   ├── __init__.py
│   ├── health.py             # GET /health
│   └── talents.py            # /talents CRUD + /talents/{id}/products
├── scripts/
│   ├── __init__.py
│   ├── seed_admin.py          # idempotent: create-or-update admin user from .env
│   └── seed_talents.py         # idempotent: insert 21 talents by name if not exists
└── integrations/              # empty placeholder package for Phase 2+ (per CLAUDE.md structure)
    └── __init__.py

alembic/
├── env.py                      # sync engine, target_metadata = Base.metadata
├── script.py.mako
└── versions/
    └── <rev>_initial_schema.py # users, talents, talent_products tables

frontend/
├── login.html                  # standalone centered card, dark theme per mockup.html tokens
├── css/
│   └── styles.css              # extracted dark-theme CSS variables/tokens from mockup.html
└── js/
    └── auth.js                 # login form submit, 401 redirect handler, logout, change-password

alembic.ini
pyproject.toml                  # bump requires-python to >=3.12, add dependencies
.python-version                 # bump to 3.12
.env.example                    # SECRET_KEY, DATABASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, ... (M2-M5 vars as placeholders per ARCHITECTURE.md M1 guidance)
```

### Pattern 1: SQLite WAL + busy_timeout via SQLAlchemy connect event listener

**What:** Configure `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=...` on every new DBAPI connection using `@event.listens_for(engine, "connect")`, NOT as one-time manual commands.

**When to use:** From the very first commit of `database.py` — PITFALLS.md Pitfall #3 and ARCHITECTURE.md both flag this as "cheap now, painful to retrofit."

**Example:**
```python
# Source: SQLAlchemy 2.0 official docs (docs.sqlalchemy.org/en/20/dialects/sqlite.html), verified 2026-06-10
from sqlalchemy import create_engine, event

engine = create_engine(
    "sqlite:///./seg.db",
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")  # 10s, per PITFALLS.md recommendation (5-10s)
    cursor.close()
```

### Pattern 2: JWT via httpOnly cookie with custom OAuth2 dependency

**What:** A custom `OAuth2PasswordBearerWithCookie`-style class (or a plain `Depends` function) reads the JWT from `request.cookies` instead of the `Authorization` header. Login sets the cookie via `Response.set_cookie()`; logout clears it via `Response.delete_cookie()`.

**When to use:** Required by D-01 (httpOnly cookie, not Authorization header + localStorage).

**Example:**
```python
# Source: FastAPI official OAuth2/JWT tutorial (fastapi.tiangolo.com/tutorial/security/oauth2-jwt/, verified 2026-06-10)
# + community pattern from fastapi/fastapi discussion #9142 (cookie-based JWT), verified 2026-06-10
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User

ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
    token = request.cookies.get("access_token")
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user
```

```python
# app/auth/router.py — login sets httpOnly cookie (D-01, D-02: 7-day expiry)
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.auth.security import verify_password
from app.auth.dependencies import create_access_token, get_current_user
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE = timedelta(days=7)  # D-02

@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        # D-06: generic message, do not reveal whether email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": user.email}, ACCESS_TOKEN_EXPIRE)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,       # see Cookie Security Defaults pitfall below for dev override
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
        path="/",
    )
    return {"status": "ok"}

@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")  # D-05
    return {"status": "ok"}
```

### Pattern 3: SQLAlchemy 2.0 declarative models for Talent + TalentProduct (D-13, D-14)

**What:** `Talent` (name, active, category, photo_url nullable) with a one-to-many `TalentProduct` join table holding Pipedrive product IDs — not a comma-separated text field (D-14).

**Example:**
```python
# Source: SQLAlchemy 2.0 declarative style, per CLAUDE.md/STACK.md mandate
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Talent(Base):
    __tablename__ = "talents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)          # D-13
    active: Mapped[bool] = mapped_column(Boolean, default=True)                  # D-13
    category: Mapped[str | None] = mapped_column(String, nullable=True)          # D-13 (niche)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)         # Claude's discretion — included

    products: Mapped[list["TalentProduct"]] = relationship(
        back_populates="talent", cascade="all, delete-orphan"
    )

class TalentProduct(Base):
    __tablename__ = "talent_products"                                            # D-14
    id: Mapped[int] = mapped_column(primary_key=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("talents.id"), index=True)
    pipedrive_product_id: Mapped[int | None] = mapped_column(nullable=True)      # D-15: null in Phase 1

    talent: Mapped["Talent"] = relationship(back_populates="products")
```

### Pattern 4: Alembic with sync engine + autogenerate

**What:** `alembic/env.py` imports `Base.metadata` from `app.models` and uses a sync engine (even though the rest of the app could theoretically go async later — Alembic stays sync, this is the documented standard).

**Example:**
```python
# Source: Alembic official tutorial pattern (alembic.sqlalchemy.org/en/latest/tutorial.html)
# alembic/env.py (relevant excerpt)
from app.models import Base
from app.config import settings

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

```bash
alembic init alembic
alembic revision --autogenerate -m "initial schema: users, talents, talent_products"
alembic upgrade head
```

### Pattern 5: Idempotent seed scripts (D-08, D-09, D-10, D-15)

**What:** `seed_admin.py` reads `ADMIN_EMAIL`/`ADMIN_PASSWORD` from settings, queries for an existing user by email — `UPDATE` if found (password rotation, D-10), `INSERT` if not (D-08, D-09: only one account). `seed_talents.py` inserts the 21 talents by name only if they don't already exist (`INSERT ... WHERE NOT EXISTS` or query-then-insert).

**Example:**
```python
# app/scripts/seed_admin.py
from app.database import SessionLocal
from app.models import User
from app.auth.security import get_password_hash
from app.config import settings

def seed_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        hashed = get_password_hash(settings.ADMIN_PASSWORD)
        if user:
            user.hashed_password = hashed   # D-10: idempotent password rotation
        else:
            user = User(email=settings.ADMIN_EMAIL, hashed_password=hashed)
            db.add(user)
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
```

```python
# app/scripts/seed_talents.py — D-15: 21 names from PROJECT.md, products left null
TALENT_NAMES = [
    "Navarretes Show", "Don Silverio", "Don Wicho", "Deliberración", "Emicanico",
    "Abelito", "Mamamecanic", "Alan Lopez", "Karamella", "Mariana", "Ale", "Elisa",
    "Edgar", "Dulce", "Reborujados", "Victor Halfon", "Doc Fitness", "Lalo Escalante",
    "Tony Franco", "Moni", "Casandra Salinas",
]

def seed_talents():
    db = SessionLocal()
    try:
        existing = {t.name for t in db.query(Talent).all()}
        for name in TALENT_NAMES:
            if name not in existing:
                db.add(Talent(name=name, active=True))
        db.commit()
    finally:
        db.close()
```

### Anti-Patterns to Avoid
- **Storing JWT in localStorage / Authorization header for this phase:** Explicitly overridden by D-01 — use httpOnly cookie only.
- **Hardcoding the 21 talent names as a Python enum/constant used directly by routers/services:** Per PITFALLS.md Pitfall #12 — seed into the `talents` table via a script; routers always query the DB.
- **Comma-separated `pipedrive_product_ids` text column on `Talent`:** Explicitly overridden by D-14 — use the `talent_products` join table.
- **Using `passlib`/`python-jose`:** Excluded by CLAUDE.md and STACK.md — use `pwdlib[argon2]` and `PyJWT`.
- **Returning SQLAlchemy ORM objects directly from route handlers:** Per ARCHITECTURE.md Anti-Pattern 3 — always convert to Pydantic schemas via `model_validate(obj, from_attributes=True)` or `response_model=`.
- **Long-held DB transactions across requests:** Keep session-per-request via `Depends(get_db)`, commit/close promptly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Password hashing | Custom Argon2/bcrypt wrapper | `pwdlib[argon2]` `PasswordHash.recommended()` | Handles algorithm selection, parameter tuning, and future migration (e.g., adding a fallback hasher) correctly — hand-rolled hashing is a classic security footgun. |
| JWT encode/decode | Manual base64+HMAC signing | `PyJWT` `jwt.encode`/`jwt.decode` | Correctly handles `exp` claim validation, algorithm allowlisting (`algorithms=["HS256"]` prevents `alg=none` attacks), and clock-skew edge cases. |
| DB schema migrations | Manual `ALTER TABLE` scripts or `Base.metadata.create_all()` in production | Alembic | `create_all()` cannot evolve schemas (no ALTER support); Alembic gives versioned, reversible migrations needed from M2 onward as the schema grows (Deal, Lead, Campaign tables). |
| Env var loading/validation | `os.environ.get()` scattered across files | `pydantic-settings` `BaseSettings` | Centralizes all env vars (including M2-M5 placeholders per ARCHITECTURE.md), validates types, fails fast at startup if `SECRET_KEY` missing. |
| SQLite concurrency tuning | Ad-hoc retry loops around `OperationalError` | `PRAGMA journal_mode=WAL` + `busy_timeout` via connect event listener | Documented, standard SQLite-level fix; retry loops are a symptom-level patch that doesn't address the root contention. |
| OAuth2 form parsing | Manual `request.form()` parsing for login | `OAuth2PasswordRequestForm` (requires `python-multipart`) | Standard FastAPI dependency, handles `application/x-www-form-urlencoded` correctly, integrates with FastAPI's OpenAPI docs "Authorize" button for testing. |

**Key insight:** Every "don't hand-roll" item above is precisely the set of things PITFALLS.md flags as "looks done but isn't" — auth and SQLite config are the two areas where shortcuts taken in M1 compound across all 6 remaining phases.

## Common Pitfalls

### Pitfall 1: bcrypt/passlib breakage on Python 3.12
**What goes wrong:** The classic FastAPI tutorial using `passlib[bcrypt]` + `CryptContext` is broken on fresh installs — `passlib` is unmaintained, and `bcrypt>=4.1`/`5.0+` removed the `__about__` attribute passlib's backend detection relies on, plus bcrypt's 72-byte password limit now raises instead of truncating.
**Why it happens:** Copying the official tutorial verbatim without checking current dependency compatibility — training-data staleness trap.
**How to avoid:** Use `pwdlib[argon2]` exclusively (already mandated by CLAUDE.md/STACK.md). Write a unit test that does a hash→verify roundtrip on a clean install as the first auth test.
**Warning signs:** `ImportError`/`AttributeError` mentioning `__about__`, or `DeprecationWarning` about the `crypt` module at startup.
**Phase to address:** Phase 1 (this phase) — verify before building anything on top.

### Pitfall 2: JWT secret/expiry decisions left implicit
**What goes wrong:** `SECRET_KEY` hardcoded, committed, or weak; token expiry chosen ad hoc with no documented rationale.
**Why it happens:** "JWT auth" feels like solved boilerplate at M1.
**How to avoid:** Generate `SECRET_KEY` via `openssl rand -hex 32`, store only in `.env` (gitignored from commit 1), document placeholder in `.env.example`, load via `pydantic-settings`. D-02 already locks the 7-day expiry as a deliberate decision (documented, not an oversight) — note this explicitly in code comments near `ACCESS_TOKEN_EXPIRE`.
**Warning signs:** `.env` appears in `git status` as tracked; `SECRET_KEY` is a short/predictable string.
**Phase to address:** Phase 1.

### Pitfall 3: SQLite "database is locked" errors (deferred but must be configured now)
**What goes wrong:** Default SQLite settings (rollback journal, busy_timeout=0) work fine with zero concurrent writers in Phase 1, but Phase 2's sync jobs will introduce a second writer, causing intermittent `OperationalError: database is locked`.
**Why it happens:** No errors appear until M2 introduces background writes — by then it's "discovered late."
**How to avoid:** Configure WAL mode + `busy_timeout=10000` via the `connect` event listener in `database.py` from the first commit (Pattern 1 above) — zero functional difference for Phase 1's single-writer case, but eliminates a class of M2+ bugs.
**Warning signs:** None visible in Phase 1 itself — this is preventive.
**Phase to address:** Phase 1 (configuration), verified again in Phase 2 (when sync jobs are added).

### Pitfall 4: Cookie security defaults (Secure flag) breaking local HTTP development
**What goes wrong:** `Secure=True` cookies are only sent over HTTPS. Local dev typically runs `http://localhost:8000` — if `secure=True` is hardcoded, the login cookie is silently never sent back by the browser, and every "protected" request appears unauthenticated (401) even immediately after a successful login, with no obvious error.
**Why it happens:** Tutorials that show `secure=True` assume an HTTPS-fronted deployment; copying this verbatim into local dev breaks auth invisibly (the login POST returns 200, but the cookie never round-trips).
**How to avoid:** Make the `secure` flag environment-dependent — derive it from a `pydantic-settings` field (e.g., `COOKIE_SECURE: bool = True` in `.env`, overridden to `False` for local dev via `.env` — NOT hardcoded `False` in source). Document this clearly in `.env.example` with a comment. `samesite="lax"` is a reasonable default for both dev and prod (D-07 explicitly defers CSRF/rate-limiting hardening, but `lax` SameSite is a near-zero-cost mitigation worth including from the start).
**Warning signs:** Login returns 200 but the very next request to a protected endpoint returns 401; browser devtools show the `Set-Cookie` header was sent but the cookie doesn't appear in subsequent `Cookie` headers (check for `Secure` flag mismatch with `http://` origin).
**Phase to address:** Phase 1 — this is exactly the "Cookie implementation details" item left to Claude's discretion in CONTEXT.md.

### Pitfall 5: Talent catalog modeled implicitly instead of as first-class entity
**What goes wrong:** Tempting to defer the `talents`/`talent_products` tables since Pipedrive sync (Phase 2) is what will "really" populate product mappings — but if Phase 1 doesn't establish this schema, Phase 2-4 retrofit becomes expensive (every join/filter touches it).
**Why it happens:** "No UI yet, build the table later" feels like reasonable MVP scoping.
**How to avoid:** Already addressed by D-13/D-14/D-15 and the roadmap explicitly placing TAL-01/TAL-02 in Phase 1. Just ensure the Alembic migration for `talents`/`talent_products` ships in Phase 1, seeded via script (not hardcoded in route handlers).
**Warning signs:** Talent names appear as string literals in router/service code instead of DB rows.
**Phase to address:** Phase 1 (this phase) — already scoped correctly per CONTEXT.md.

### Pitfall 6: `.python-version` / `pyproject.toml` mismatch causing `uv` to use the wrong interpreter
**What goes wrong:** Repo currently has `.python-version`=`3.9` and `pyproject.toml` `requires-python=">=3.9"`. Several Phase 1 dependencies (`fastapi`, `uvicorn`, `alembic`, `pydantic-settings`, `python-dotenv`, `python-multipart`) now require `>=3.10`. If these files aren't updated to 3.12 FIRST, `uv add`/`uv sync` will either fail to resolve or silently install into a 3.9 venv where these packages can't be installed at all.
**Why it happens:** The repo's `uv init` scaffold predates the stack decision; nobody revisits these files until install fails.
**How to avoid:** First task of Phase 1: update `.python-version` to `3.12`, update `pyproject.toml` `requires-python = ">=3.12"`, run `uv python pin 3.12` (or equivalent) and recreate `.venv` if needed, THEN add dependencies.
**Warning signs:** `uv add fastapi` fails with a resolution error mentioning Python version constraints.
**Phase to address:** Phase 1, Wave 0 / first task — this is a hard blocker for everything else.

## Code Examples

### Health check with optional DB connectivity check
```python
# Source: pattern derived from STACK.md M1 guidance ("simple GET /health returning {"status": "ok"} plus a DB connectivity check")
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter()

@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "database": db_status}
```

### app/config.py — pydantic-settings with fail-fast SECRET_KEY
```python
# Source: pydantic-settings official pattern (BaseSettings), verified against PyPI 2.14.1 metadata 2026-06-10
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SECRET_KEY: str  # required — app fails to start if missing
    DATABASE_URL: str = "sqlite:///./seg.db"
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    COOKIE_SECURE: bool = True

    # Placeholders for M2-M5 (per ARCHITECTURE.md M1 build-order guidance — define now, unused until later)
    PIPEDRIVE_API_TOKEN: str = ""
    PIPEDRIVE_DOMAIN: str = ""
    GOOGLE_SHEETS_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    TRELLO_API_KEY: str = ""
    TRELLO_TOKEN: str = ""
    TRELLO_BOARD_IDS: str = ""
    ANTHROPIC_API_KEY: str = ""

settings = Settings()
```

### app/database.py — engine, session, get_db dependency
```python
# Source: SQLAlchemy 2.0 + FastAPI official "SQL (Relational) Databases" tutorial pattern, combined with WAL pragma listener
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

class Base(DeclarativeBase):
    pass

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `passlib[bcrypt]` + `CryptContext` (FastAPI's old official tutorial) | `pwdlib[argon2]` + `PasswordHash.recommended()` | FastAPI PR #13917 (in-progress doc migration, ~2025-2026) | Old tutorial code will fail to import or behave incorrectly on current `bcrypt` versions; must use `pwdlib` from the start. |
| `python-jose` for JWT | `PyJWT` | FastAPI discussions #11345/#9587 (ongoing) | `python-jose` unmaintained, vulnerable transitive dep; `PyJWT` is the now-current official recommendation. |
| SQLAlchemy 1.x `Column`/`declarative_base()` | SQLAlchemy 2.0 `Mapped[]`/`mapped_column()` | SQLAlchemy 2.0 (2023) | Already mandated by CLAUDE.md; relevant because many tutorials online still show 1.x style. |
| `fastapi[standard]` extra without `fastar` | `fastapi[standard]` now includes `fastar>=0.9.0` (Rust tar bindings for fastapi-cli) | Sometime between FastAPI's last training-data-known version and 0.136.3 (fastar's first release was Oct 2025) | No code impact — purely a transitive dependency for `fastapi dev`/`fastapi-cli` tooling. Mentioned only to avoid confusion during `uv add` if the dependency tree looks unfamiliar. |

**Deprecated/outdated:**
- `passlib`, `python-jose`: both excluded per CLAUDE.md "What NOT to Use" — confirmed still correct as of 2026-06-10.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `DATABASE_URL=sqlite:///./seg.db` (relative path, project root) is the correct convention for Phase 1, with the `/data/seg.db` absolute-path convention from PITFALLS.md (Pitfall #4) deferred to Phase 7 (Docker/EasyPanel) | Standard Stack, Project Structure | LOW — if Phase 7 wants `/data/seg.db` from the start, this is a one-line env var change + Docker volume mount; SQLite path itself doesn't leak into business logic if `DATABASE_URL` is the single source of truth via `config.py`. |
| A2 | `samesite="lax"` is an acceptable default for the auth cookie in Phase 1 (D-07 defers CSRF/rate-limiting, but SameSite=Lax is presented here as a near-zero-cost addition, not a discussed decision) | Pitfall 4, Pattern 2 | LOW — if the user wants `samesite="strict"` or explicitly no SameSite restriction for some integration reason, this is a one-line change in the login endpoint. |
| A3 | `COOKIE_SECURE` should be an env-configurable setting (default `True`, overridden to `False` for local dev via `.env`) rather than auto-detected from request scheme | Pitfall 4 | LOW — alternative is to detect `request.url.scheme == "https"` at runtime; env var is simpler and matches the project's existing `.env`-driven config pattern, but either works. |
| A4 | A dedicated talent admin UI is NOT built in Phase 1 (per CONTEXT.md Claude's Discretion default) — TAL-01 satisfied via protected CRUD endpoints only | Architecture, Phase Requirements | LOW — CONTEXT.md explicitly allows the planner to add a minimal admin UI "if trivially cheap given the walking-skeleton UI work already needed for login," so this is a planner judgment call already anticipated, not a hidden risk. |

## Open Questions

1. **Exact cookie name and `/auth/users` endpoint shape**
   - What we know: D-12 specifies a protected `POST /auth/users` endpoint for adding future team members, with "no dedicated UI required."
   - What's unclear: Whether `/auth/users` should require any special privilege beyond "is authenticated" (since FUT-03 RBAC is fully out of scope, any authenticated user — i.e., the single admin — can call it). CONTEXT.md doesn't specify a request/response schema.
   - Recommendation: Planner defines `POST /auth/users` accepting `{email, password}`, protected by the same `get_current_user` dependency as all other routes (no separate admin check needed since there's only one user/role tier in v1). Document this as a Phase 1 implementation detail, not a new decision requiring discussion.

2. **`/health` DB check failure mode**
   - What we know: PITFALLS.md recommends a `SELECT 1` check; CONTEXT.md leaves scope to planner/research.
   - What's unclear: Should `/health` return HTTP 200 with `{"database": "error"}` (always 200, status in body) or HTTP 503 if the DB check fails?
   - Recommendation: Return HTTP 200 always with `{"status": "ok", "database": "ok"|"error"}` — this matches common health-check conventions (load balancers often only check 2xx) and avoids the health endpoint itself becoming unreachable during a DB hiccup. The Code Examples section above implements this.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (system) | Runtime baseline check | check 3.12 via uv | 3.9.6 (system `python3`) — but `uv` manages its own interpreters | `uv python pin 3.12` / `uv python install 3.12` if not already available to uv |
| uv | Dependency management, venv | Yes | 0.11.14 | — |
| sqlite3 CLI | Manual DB inspection during dev | Yes | 3.43.2 | — |
| Node.js | Not required for this phase (frontend is vanilla JS, no build step) | Yes (v26.0.0) | — | N/A — not used by Phase 1 |
| pip | Used only for slopcheck attempt; not needed for app dependency management (uv handles it) | pip3 present, `pip` absent | — | `uv` is the primary dependency manager per CLAUDE.md; no fallback needed |

**Missing dependencies with no fallback:**
- None. All Phase 1 dependencies are installable via `uv add` regardless of system Python/pip state, since `uv` manages its own Python interpreters and virtual environment.

**Missing dependencies with fallback:**
- System Python is 3.9.6, but `uv` can install/pin Python 3.12 independently — `.python-version` should be set to `3.12` and `uv python install 3.12` (or `uv sync`, which will fetch the pinned version) run as part of Phase 1's first task. This was already identified as required work in CONTEXT.md.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest 8.x) + httpx `ASGITransport`/FastAPI `TestClient` |
| Config file | none yet — Wave 0 creates `pyproject.toml` `[tool.pytest.ini_options]` or `pytest.ini` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| AUTH-01 | Login with correct email/password returns 200 + sets `access_token` cookie | integration | `uv run pytest tests/test_auth.py::test_login_success -x` | Wave 0 |
| AUTH-01 | Login with wrong password returns 401 with generic message (D-06) | integration | `uv run pytest tests/test_auth.py::test_login_invalid_credentials -x` | Wave 0 |
| AUTH-02 | Protected endpoint without cookie returns 401 | integration | `uv run pytest tests/test_auth.py::test_protected_requires_auth -x` | Wave 0 |
| AUTH-02 | Protected endpoint with expired/invalid JWT returns 401 | integration | `uv run pytest tests/test_auth.py::test_protected_rejects_invalid_token -x` | Wave 0 |
| AUTH-02 | Logout clears cookie; subsequent protected request returns 401 | integration | `uv run pytest tests/test_auth.py::test_logout_clears_session -x` | Wave 0 |
| AUTH-02 | Authenticated user can change password via change-password endpoint (D-11) | integration | `uv run pytest tests/test_auth.py::test_change_password -x` | Wave 0 |
| AUTH-03 | `GET /health` returns 200 without authentication | integration | `uv run pytest tests/test_health.py::test_health_no_auth -x` | Wave 0 |
| AUTH-03 | `GET /health` reflects DB connectivity status | unit/integration | `uv run pytest tests/test_health.py::test_health_db_check -x` | Wave 0 |
| TAL-01 | Talent CRUD (create/list/edit) works without code changes — seeded 21 talents present | integration | `uv run pytest tests/test_talents.py::test_seeded_talents_present -x` | Wave 0 |
| TAL-01 | Adding a new talent via POST /talents persists and appears in GET /talents | integration | `uv run pytest tests/test_talents.py::test_create_talent -x` | Wave 0 |
| TAL-02 | Talent can have one or more `talent_products` rows added/listed via API | integration | `uv run pytest tests/test_talents.py::test_add_talent_product -x` | Wave 0 |
| (foundation) | Password hash/verify roundtrip works on clean install (Pitfall 1) | unit | `uv run pytest tests/test_security.py::test_password_hash_roundtrip -x` | Wave 0 |
| (foundation) | SQLite WAL mode + busy_timeout pragmas are active on the engine connection (Pitfall 3) | unit | `uv run pytest tests/test_database.py::test_sqlite_pragmas -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q` (fast subset relevant to the task)
- **Per wave merge:** `uv run pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` or `pytest.ini` — pytest config + test path
- [ ] `tests/conftest.py` — shared fixtures: test DB engine (separate SQLite file or `:memory:` with `StaticPool`), `TestClient`/`ASGITransport` app fixture, seeded test user fixture
- [ ] `tests/test_auth.py`, `tests/test_health.py`, `tests/test_talents.py`, `tests/test_security.py`, `tests/test_database.py` — all new
- [ ] Framework install: `uv add --dev pytest` (httpx already present via fastapi[standard])

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|---------------------|
| V2 Authentication | yes | PyJWT (HS256) + `pwdlib[argon2]` for credential storage; generic error message on failed login (D-06) addresses ASVS 2.2.1 (no user enumeration via error messages) |
| V3 Session Management | yes | httpOnly, SameSite=Lax cookie with `Secure` flag (env-configurable for dev), 7-day expiry (D-02, documented deliberate tradeoff per PITFALLS.md), server-side logout via cookie clearing (D-05) |
| V4 Access Control | yes (minimal) | `Depends(get_current_user)` on all non-health routes; no role hierarchy needed (FUT-03 deferred) — single authenticated tier |
| V5 Input Validation | yes | Pydantic v2 schemas for all request bodies (`schemas/auth.py`, `schemas/talent.py`); FastAPI validates automatically, returns 422 on invalid input |
| V6 Cryptography | yes | `pwdlib[argon2]` (Argon2id via argon2-cffi) for password hashing — never hand-rolled; `SECRET_KEY` generated via `openssl rand -hex 32`, loaded from `.env` (gitignored) |

### Known Threat Patterns for FastAPI + JWT-cookie + SQLite

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Brute-force login attempts | Spoofing | D-07 explicitly defers rate limiting to a later security pass — documented as accepted risk for Phase 1 (small internal team, not yet public-facing until Phase 7 deploy) |
| User enumeration via login error messages | Information Disclosure | D-06: generic "Invalid email or password" for both nonexistent-user and wrong-password cases; consider constant-time comparison / dummy-hash verification (FastAPI official tutorial pattern: hash a dummy password even when user doesn't exist, to avoid timing differences) |
| CSRF via cookie-based auth | Tampering | `SameSite=Lax` on the auth cookie (near-zero-cost mitigation, included per Assumption A2); full CSRF token scheme explicitly out of scope for Phase 1 per D-07's spirit (deferred hardening) |
| JWT algorithm confusion (`alg=none` or RS256/HS256 confusion) | Tampering | `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])` — always pass explicit `algorithms=` allowlist, never trust the `alg` header from the token itself |
| SQL injection | Tampering | SQLAlchemy ORM with parameterized queries by default (`db.query(Model).filter(Model.field == value)`) — never use raw string-formatted SQL |
| Secrets committed to git | Information Disclosure | `.env` gitignored from commit 1 (this phase); `.env.example` with placeholders only |

## Sources

### Primary (HIGH confidence)
- [PyPI registry — fastapi 0.136.3](https://pypi.org/pypi/fastapi/json) — version, requires_python, requires_dist (incl. `fastar` extra dep), checked live 2026-06-10
- [PyPI registry — uvicorn 0.49.0, sqlalchemy 2.0.50, alembic 1.18.4, pydantic-settings 2.14.1, python-dotenv 1.2.2, httpx 0.28.1, pyjwt 2.13.0, pwdlib 0.3.0, python-multipart 0.0.32, argon2-cffi 25.1.0, fastapi-cli 0.0.24, fastar 0.11.0](https://pypi.org/) — all checked live 2026-06-10
- [SQLAlchemy 2.0 SQLite dialect docs](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) — WAL/pragma event listener pattern, check_same_thread defaults
- [FastAPI official OAuth2/JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — current pwdlib-based pattern, PyJWT encode/decode, get_current_user dependency, OAuth2PasswordRequestForm login

### Secondary (MEDIUM confidence)
- [fastapi/fastapi Discussion #9142 — Cookie based JWT tokens](https://github.com/fastapi/fastapi/discussions/9142) — custom OAuth2PasswordBearerWithCookie pattern, set_cookie/delete_cookie usage
- [pwdlib official docs / fvoron.com blog — Introducing pwdlib](https://www.fvoron.com/blog/introducing-pwdlib-a-modern-password-hash-helper-for-python/) — `PasswordHash.recommended()` usage
- [Alembic official tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — sync engine env.py pattern, target_metadata = Base.metadata

### Tertiary (LOW confidence)
- None requiring validation — all critical claims cross-verified against official docs or live PyPI registry.

### Carried forward from prior research (already committed, re-confirmed not stale)
- `.planning/research/STACK.md` (2026-06-09) — version pins re-verified live, no drift
- `.planning/research/ARCHITECTURE.md` (2026-06-09) — modular monolith structure, auth/ package design
- `.planning/research/PITFALLS.md` (2026-06-09) — Pitfalls #1-4, #12 directly applicable to Phase 1

## Project Constraints (from CLAUDE.md)

The following directives from `./CLAUDE.md` are binding for Phase 1 planning:

- **Backend stack fixed:** Python 3.12 + FastAPI + SQLite (SQLAlchemy) + python-dotenv + httpx — no framework substitution.
- **Frontend stack fixed:** HTML + CSS + Vanilla JS, dark mode, mobile-first — no JS frameworks (login page must follow this).
- **Folder structure predefined:** `app/main.py`, `app/config.py`, `app/models.py`, `app/database.py`, `app/integrations/`, `app/services/`, `app/routers/`, `frontend/` — Phase 1 must establish this skeleton (research adds `app/auth/`, `app/schemas/`, `app/scripts/` as documented extensions consistent with ARCHITECTURE.md, not replacements).
- **Required env vars:** `PIPEDRIVE_API_TOKEN`, `PIPEDRIVE_DOMAIN`, `GOOGLE_SHEETS_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_IDS`, `ANTHROPIC_API_KEY`, `SECRET_KEY`, `DATABASE_URL=sqlite:///./seg.db` — `.env.example` should define ALL of these now (per ARCHITECTURE.md M1 guidance), even though most are unused until M2-M5.
- **Extensibility:** New talents addable via data/config, never requiring code changes — satisfied by `talents`/`talent_products` tables + seed scripts (no hardcoded talent lists in app code).
- **Build order:** Strictly incremental M1 -> M7, validate each module before advancing — Phase 1 is M1; no M2+ integration code should be started.
- **GSD workflow enforcement:** All file-changing work must go through `/gsd-execute-phase` (or other GSD entry points) — not direct edits outside the workflow.
- **PyJWT not python-jose; pwdlib[argon2] not passlib; SQLAlchemy 2.0 declarative not 1.x style; sync SQLAlchemy not async** — all reconfirmed current and correct as of 2026-06-10 (see State of the Art section).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|---------------------|
| AUTH-01 | User can log in with email/password and receive a JWT | Pattern 2 (httpOnly cookie JWT login), `auth/router.py` example, `auth/security.py` (pwdlib hashing) — D-01/D-02/D-06/D-08-D-10 all addressed |
| AUTH-02 | Protected endpoints validate the JWT and reject unauthenticated requests | Pattern 2 `get_current_user` dependency (cookie-based), 401 on missing/invalid/expired token; D-03 (frontend redirect on 401), D-05 (logout), D-11 (change-password), D-12 (`/auth/users`) |
| AUTH-03 | System exposes a `/health` endpoint reporting service status | Code Examples "Health check with optional DB connectivity check" — public route, optional `SELECT 1`, always-200 design (Open Question 2) |
| TAL-01 | System stores the talent catalog in the DB (21 initial talents), addable/editable without code changes | Pattern 3 (`Talent` model), Pattern 5 (`seed_talents.py` idempotent seed of 21 names from PROJECT.md), CRUD endpoints in `routers/talents.py` (D-13, D-15, Pitfall 5) |
| TAL-02 | Each talent maps to one or more Pipedrive products for revenue attribution | Pattern 3 (`TalentProduct` join table, D-14), `pipedrive_product_id` nullable in Phase 1 per D-15, `/talents/{id}/products` endpoints |
</phase_requirements>

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified live against PyPI registry on 2026-06-10, consistent with prior STACK.md research from 2026-06-09 (no drift)
- Architecture: HIGH — FastAPI/SQLAlchemy/Alembic patterns verified against official docs; cookie-JWT pattern verified against FastAPI official tutorial + community discussion #9142, both consistent
- Pitfalls: HIGH — Pitfalls 1-3, 5, 6 verified against official docs (SQLAlchemy SQLite dialect, FastAPI security tutorial) and prior PITFALLS.md research; Pitfall 4 (cookie Secure flag) is a well-known FastAPI gotcha cross-referenced across multiple tutorial sources

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (30 days — core stack is stable; re-verify package versions if planning is delayed past this window, especially `anthropic` SDK pin for later phases per STACK.md note about frequent releases)
