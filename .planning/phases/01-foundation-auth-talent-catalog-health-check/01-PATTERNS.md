# Phase 1: Foundation — Auth, Talent Catalog & Health Check - Pattern Map

**Mapped:** 2026-06-10
**Files analyzed:** 24
**Analogs found:** 0 / 24 (greenfield repo — no `app/` code exists yet)

## Greenfield Notice

This repo is currently a default `uv init` scaffold:
- `main.py` — hello-world placeholder (to be replaced by `app/main.py`)
- `pyproject.toml` — `requires-python = ">=3.9"`, no dependencies
- `.python-version` — `3.9`
- No `app/`, `frontend/`, `alembic/`, or `tests/` directories exist

**There are no existing codebase analogs for any Phase 1 file.** Every "Analog" below is a concrete excerpt from `01-RESEARCH.md` (verified against official docs/PyPI on 2026-06-10) or `.planning/reference/mockup.html` (for the login page design tokens). The planner should treat these RESEARCH.md excerpts as the canonical pattern source — Phase 1 establishes the patterns that Phase 2+ will then have as real analogs.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|----------------|
| `pyproject.toml` | config | batch | n/a (existing scaffold, modify in place) | modify-existing |
| `.python-version` | config | batch | n/a (existing scaffold, modify in place) | modify-existing |
| `.env.example` | config | batch | RESEARCH.md "app/config.py" example | research-pattern |
| `.gitignore` | config | batch | none | research-pattern |
| `app/main.py` | controller (app factory) | request-response | RESEARCH.md System Architecture Diagram | research-pattern |
| `app/config.py` | config | batch | RESEARCH.md "app/config.py — pydantic-settings" | research-pattern |
| `app/database.py` | service (DB session) | CRUD | RESEARCH.md "app/database.py — engine, session, get_db" | research-pattern |
| `app/models.py` | model | CRUD | RESEARCH.md Pattern 3 (SQLAlchemy 2.0 declarative) | research-pattern |
| `app/schemas/__init__.py` | model (schema barrel) | transform | n/a | research-pattern |
| `app/schemas/auth.py` | model (Pydantic schema) | transform | RESEARCH.md Pattern 2 (login/token shapes) | research-pattern |
| `app/schemas/talent.py` | model (Pydantic schema) | transform | RESEARCH.md Pattern 3 (Talent/TalentProduct fields) | research-pattern |
| `app/auth/__init__.py` | provider (package init) | n/a | n/a | research-pattern |
| `app/auth/security.py` | utility (hashing/JWT) | transform | RESEARCH.md Pattern 2 (`create_access_token`, pwdlib) | research-pattern |
| `app/auth/dependencies.py` | middleware (auth guard) | request-response | RESEARCH.md Pattern 2 (`get_current_user`) | research-pattern |
| `app/auth/router.py` | controller (auth routes) | request-response | RESEARCH.md Pattern 2 (`/auth/login`, `/auth/logout`) | research-pattern |
| `app/routers/__init__.py` | route (package init) | n/a | n/a | research-pattern |
| `app/routers/health.py` | controller (health route) | request-response | RESEARCH.md "Health check with optional DB connectivity check" | research-pattern |
| `app/routers/talents.py` | controller (CRUD routes) | CRUD | RESEARCH.md Pattern 3 + Architectural Responsibility Map (talent CRUD) | research-pattern |
| `app/integrations/__init__.py` | service (placeholder package) | n/a | n/a | research-pattern (empty placeholder per CLAUDE.md) |
| `app/scripts/__init__.py` | utility (package init) | n/a | n/a | research-pattern |
| `app/scripts/seed_admin.py` | utility (seed script) | batch | RESEARCH.md Pattern 5 (`seed_admin.py`) | research-pattern |
| `app/scripts/seed_talents.py` | utility (seed script) | batch | RESEARCH.md Pattern 5 (`seed_talents.py`) | research-pattern |
| `alembic/env.py` | migration | batch | RESEARCH.md Pattern 4 (Alembic env.py) | research-pattern |
| `alembic/versions/<rev>_initial_schema.py` | migration | batch | RESEARCH.md Pattern 4 (autogenerate) | research-pattern |
| `frontend/login.html` | component | request-response | `.planning/reference/mockup.html` (design tokens) | design-tokens-only |
| `frontend/css/styles.css` | component (shared styles) | n/a | `.planning/reference/mockup.html` `:root` + `.card`/`.btn` rules | design-tokens-only |
| `frontend/js/auth.js` | hook (client auth logic) | event-driven | RESEARCH.md D-03 (401 redirect), Pattern 2 (cookie auth, no client token handling needed) | research-pattern |
| `tests/conftest.py` | test | batch | RESEARCH.md Validation Architecture (Wave 0 Gaps) | research-pattern |
| `tests/test_auth.py` | test | request-response | RESEARCH.md Phase Requirements -> Test Map (AUTH-01/02) | research-pattern |
| `tests/test_health.py` | test | request-response | RESEARCH.md Phase Requirements -> Test Map (AUTH-03) | research-pattern |
| `tests/test_talents.py` | test | CRUD | RESEARCH.md Phase Requirements -> Test Map (TAL-01/02) | research-pattern |
| `tests/test_security.py` | test | transform | RESEARCH.md Pitfall 1 (hash roundtrip test) | research-pattern |
| `tests/test_database.py` | test | batch | RESEARCH.md Pitfall 3 (pragma test) | research-pattern |

## Pattern Assignments

### `pyproject.toml` and `.python-version` (config, batch)

**Analog:** existing scaffold files (read, then modified in place) — `01-RESEARCH.md` Pitfall 6

**Current state** (must change BEFORE any `uv add`):
```toml
# pyproject.toml (current)
[project]
name = "seg-dashboard"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.9"
dependencies = []
```
```
# .python-version (current)
3.9
```

**Required change** (RESEARCH.md Pitfall 6 — hard blocker for all other Phase 1 work):
- Bump `requires-python = ">=3.12"` in `pyproject.toml`
- Bump `.python-version` to `3.12`
- Run `uv python pin 3.12` then `uv add "fastapi[standard]" sqlalchemy alembic pydantic-settings python-dotenv httpx pyjwt "pwdlib[argon2]" python-multipart` and `uv add --dev pytest ruff`
- Add `[tool.pytest.ini_options]` section (testpaths = ["tests"])

---

### `.env.example` (config, batch)

**Analog:** RESEARCH.md "app/config.py — pydantic-settings with fail-fast SECRET_KEY" (lines 538-563) + Project Constraints section (required env vars list)

**Pattern — must define ALL of these (per CLAUDE.md, even if unused until M2-M5):**
```
SECRET_KEY=                  # generate via: openssl rand -hex 32
DATABASE_URL=sqlite:///./seg.db
ADMIN_EMAIL=
ADMIN_PASSWORD=
COOKIE_SECURE=True            # set to False for local http:// dev (Pitfall 4)

# M2-M5 placeholders (unused in Phase 1, define now per ARCHITECTURE.md)
PIPEDRIVE_API_TOKEN=
PIPEDRIVE_DOMAIN=
GOOGLE_SHEETS_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
TRELLO_API_KEY=
TRELLO_TOKEN=
TRELLO_BOARD_IDS=
ANTHROPIC_API_KEY=
```

**Security note (RESEARCH.md Pitfall 2 / Sources table):** `.env` itself must be gitignored from commit 1; `.env.example` contains placeholders only, never real secrets.

---

### `app/config.py` (config, batch)

**Analog:** `01-RESEARCH.md` lines 538-563 ("app/config.py — pydantic-settings with fail-fast SECRET_KEY")

**Full pattern to copy:**
```python
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

**Note:** `COOKIE_SECURE: bool = True` is the env-configurable flag for Pitfall 4 (Secure cookie breaking local HTTP dev) — `app/auth/router.py` reads `settings.COOKIE_SECURE` for `response.set_cookie(secure=...)`.

---

### `app/database.py` (service, CRUD — DB session provider)

**Analog:** `01-RESEARCH.md` lines 565-595 ("app/database.py — engine, session, get_db dependency") + Pattern 1 (lines 203-225, WAL/busy_timeout listener)

**Full pattern to copy:**
```python
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

**Critical:** The `@event.listens_for(engine, "connect")` pragma listener MUST be present from the first commit (RESEARCH.md Pitfall 3 / Pattern 1) — this is the pattern `tests/test_database.py::test_sqlite_pragmas` will assert against.

---

### `app/models.py` (model, CRUD)

**Analog:** `01-RESEARCH.md` lines 326-366 (Pattern 3 — SQLAlchemy 2.0 declarative models for User/Talent/TalentProduct)

**Full pattern to copy:**
```python
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

**IMPORTANT consistency note:** RESEARCH.md's `app/database.py` example ALSO defines its own `class Base(DeclarativeBase): pass`. There must be exactly ONE `Base` — the planner should declare `Base` in `app/database.py` and have `app/models.py` `from app.database import Base` (do not duplicate the class). This avoids two separate metadata registries that Alembic and `Base.metadata.create_all()` would disagree on.

---

### `app/schemas/auth.py` and `app/schemas/talent.py` (model, transform)

**Analog:** No direct RESEARCH.md code block, but field shapes are fully implied by Pattern 2/3 + Phase Requirements + Anti-Pattern 4.

**Pattern derivation (from RESEARCH.md Anti-Patterns, lines 451-457):**
> "Returning SQLAlchemy ORM objects directly from route handlers ... always convert to Pydantic schemas via `model_validate(obj, from_attributes=True)` or `response_model=`."

**`app/schemas/auth.py` — derive from D-08/D-10/D-11/D-12 + Pattern 2:**
```python
from pydantic import BaseModel, EmailStr

class TokenResponse(BaseModel):
    status: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserRead(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}
```
Note: login itself uses `OAuth2PasswordRequestForm` (no separate `LoginRequest` schema needed — see `app/auth/router.py` pattern below).

**`app/schemas/talent.py` — derive from Pattern 3 model fields + D-13/D-14/D-15:**
```python
from pydantic import BaseModel

class TalentProductRead(BaseModel):
    id: int
    pipedrive_product_id: int | None = None

    model_config = {"from_attributes": True}

class TalentProductCreate(BaseModel):
    pipedrive_product_id: int | None = None

class TalentBase(BaseModel):
    name: str
    active: bool = True
    category: str | None = None
    photo_url: str | None = None

class TalentCreate(TalentBase):
    pass

class TalentUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    category: str | None = None
    photo_url: str | None = None

class TalentRead(TalentBase):
    id: int
    products: list[TalentProductRead] = []

    model_config = {"from_attributes": True}
```

---

### `app/auth/security.py` (utility, transform — hashing + JWT)

**Analog:** `01-RESEARCH.md` Pattern 2 (lines 234-278, `create_access_token`) + "Don't Hand-Roll" table (pwdlib `PasswordHash.recommended()`) + Pattern 5's `get_password_hash` reference (line 409)

**Pattern to copy (combine the JWT helper from Pattern 2 with pwdlib hashing referenced in Pattern 5/Don't-Hand-Roll):**
```python
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.config import settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
```

**Pitfall 1 test obligation:** `tests/test_security.py::test_password_hash_roundtrip` must call `get_password_hash` then `verify_password` on a clean install — first auth test to write (catches passlib/bcrypt-style breakage early).

---

### `app/auth/dependencies.py` (middleware, request-response — auth guard)

**Analog:** `01-RESEARCH.md` Pattern 2 (lines 234-278, `get_current_user`)

**Full pattern to copy:**
```python
from typing import Annotated
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.auth.security import ALGORITHM

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

**Apply to:** Every protected route in `app/auth/router.py` (logout, change-password, `/auth/users`) and ALL routes in `app/routers/talents.py`. `app/routers/health.py` is the ONLY router that does NOT use this dependency (D-03/AUTH-03 — public endpoint).

**Always pass explicit `algorithms=["HS256"]`** — RESEARCH.md Security Domain table flags `alg=none`/algorithm-confusion as a Tampering threat; never omit the allowlist.

---

### `app/auth/router.py` (controller, request-response — auth routes)

**Analog:** `01-RESEARCH.md` Pattern 2 (lines 280-324, `/auth/login` + `/auth/logout`)

**Imports + core login pattern (lines 280-324):**
```python
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.auth.security import verify_password, create_access_token, get_password_hash
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.config import settings

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
        secure=settings.COOKIE_SECURE,   # env-configurable, Pitfall 4 — NOT hardcoded True
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

**Note vs RESEARCH.md raw excerpt:** RESEARCH.md's example hardcodes `secure=True`. Per Pitfall 4 / D-discretion ("Cookie implementation details"), `secure` MUST come from `settings.COOKIE_SECURE` instead — this is the one deliberate deviation from the literal RESEARCH.md excerpt.

**Additional endpoints required by D-11/D-12 (no RESEARCH.md code block — derive from same imports/patterns above):**
```python
from app.schemas.auth import ChangePasswordRequest, UserCreate, UserRead

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "ok"}

@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(get_current_user),  # any authenticated user — single-tier auth, FUT-03 deferred
    db: Session = Depends(get_db),
):
    user = User(email=payload.email, hashed_password=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

---

### `app/routers/health.py` (controller, request-response — public health route)

**Analog:** `01-RESEARCH.md` lines 518-536 ("Health check with optional DB connectivity check")

**Full pattern to copy:**
```python
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

**No auth dependency** — public route per AUTH-03 / Architectural Responsibility Map. Always returns HTTP 200 (Open Question 2 resolution): status info goes in the body, never a 5xx, so load balancers checking for 2xx don't flap.

---

### `app/routers/talents.py` (controller, CRUD — protected talent catalog routes)

**Analog:** No single RESEARCH.md code block exists for this file (it's the one router RESEARCH.md describes structurally but doesn't fully code). Derive from: System Architecture Diagram (lines 124-127), Pattern 3 (models), `app/schemas/talent.py` pattern above, and Anti-Pattern 4 (always convert ORM -> Pydantic).

**Structural description from RESEARCH.md (lines 124-127):**
```
routers/talents.py  (all routes Depends(get_current_user))
   - GET/POST /talents
   - PATCH /talents/{id}
   - GET/POST/DELETE /talents/{id}/products
```

**Derived CRUD pattern (combining `get_db`, `get_current_user`, schemas, and Anti-Pattern 4's `response_model=`):**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import Talent, TalentProduct, User
from app.schemas.talent import TalentCreate, TalentUpdate, TalentRead, TalentProductCreate, TalentProductRead

router = APIRouter(prefix="/talents", tags=["talents"], dependencies=[Depends(get_current_user)])

@router.get("", response_model=list[TalentRead])
def list_talents(db: Session = Depends(get_db)):
    return db.query(Talent).all()

@router.post("", response_model=TalentRead, status_code=status.HTTP_201_CREATED)
def create_talent(payload: TalentCreate, db: Session = Depends(get_db)):
    talent = Talent(**payload.model_dump())
    db.add(talent)
    db.commit()
    db.refresh(talent)
    return talent

@router.patch("/{talent_id}", response_model=TalentRead)
def update_talent(talent_id: int, payload: TalentUpdate, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(talent, field, value)
    db.commit()
    db.refresh(talent)
    return talent

@router.get("/{talent_id}/products", response_model=list[TalentProductRead])
def list_talent_products(talent_id: int, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
    return talent.products

@router.post("/{talent_id}/products", response_model=TalentProductRead, status_code=status.HTTP_201_CREATED)
def add_talent_product(talent_id: int, payload: TalentProductCreate, db: Session = Depends(get_db)):
    talent = db.get(Talent, talent_id)
    if talent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talent not found")
    product = TalentProduct(talent_id=talent_id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.delete("/{talent_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_talent_product(talent_id: int, product_id: int, db: Session = Depends(get_db)):
    product = db.get(TalentProduct, product_id)
    if product is None or product.talent_id != talent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
```

**Auth pattern:** `dependencies=[Depends(get_current_user)]` at the `APIRouter()` level applies the guard to ALL routes in this file in one place — cleaner than repeating `Depends(get_current_user)` per-handler, and matches "all routes" language in the architecture diagram.

---

### `app/scripts/seed_admin.py` and `app/scripts/seed_talents.py` (utility, batch — idempotent seeds)

**Analog:** `01-RESEARCH.md` Pattern 5 (lines 400-449)

**`seed_admin.py` — full pattern to copy (lines 406-428):**
```python
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

**`seed_talents.py` — full pattern to copy (lines 430-449), 21 names from PROJECT.md:**
```python
from app.database import SessionLocal
from app.models import Talent

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

if __name__ == "__main__":
    seed_talents()
```

**Run command (per ARCHITECTURE.md System Diagram):** `python -m app.scripts.seed_admin` and `python -m app.scripts.seed_talents` (or `uv run python -m app.scripts.seed_admin`).

---

### `alembic/env.py` and `alembic/versions/<rev>_initial_schema.py` (migration, batch)

**Analog:** `01-RESEARCH.md` Pattern 4 (lines 368-398)

**`env.py` relevant excerpt to integrate into the standard `alembic init` scaffold:**
```python
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

**Setup commands:**
```bash
alembic init alembic
# edit alembic/env.py per excerpt above (target_metadata, sqlalchemy.url from settings)
alembic revision --autogenerate -m "initial schema: users, talents, talent_products"
alembic upgrade head
```

**Note:** `Base` must be imported from `app/database.py` (single source per the consistency note in the `app/models.py` section above), since `app/models.py` will `from app.database import Base` rather than redefining it.

---

### `frontend/login.html` and `frontend/css/styles.css` (component, request-response / n/a)

**Analog:** `.planning/reference/mockup.html` (design tokens only — mockup has NO login page, per CONTEXT.md)

**Design tokens to extract into `frontend/css/styles.css` `:root`** (verbatim from mockup.html `<style>` block):
```css
:root{
  --bg:#0c0c0e;--bg2:#111114;--bg3:#18181c;--bg4:#1f1f24;--bg5:#26262c;
  --border:rgba(255,255,255,0.06);--borderM:rgba(255,255,255,0.11);--borderH:rgba(255,255,255,0.18);
  --text:#eeede6;--text2:#8a8980;--text3:#4e4e4a;
  --accent:#e8520a;--accentD:rgba(232,82,10,0.12);--accentB:rgba(232,82,10,0.25);
  --green:#1a9e6e;--greenD:rgba(26,158,110,0.12);--greenT:#3dcf96;
  --amber:#c97c14;--amberD:rgba(201,124,20,0.12);--amberT:#f0a93a;
  --blue:#2472c8;--blueD:rgba(36,114,200,0.12);--blueT:#6aabf0;
  --purple:#6b54d6;--purpleD:rgba(107,84,214,0.12);--purpleT:#a594f0;
  --red:#c43232;--redD:rgba(196,50,50,0.12);--redT:#f07070;
  --r:10px;--rL:14px;--rXL:18px;
}
html{background:var(--bg);-webkit-tap-highlight-color:transparent;}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5;overflow-x:hidden;}
```

**Font import** (from mockup `<head>`):
```html
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```

**Card pattern** (mockup `.card` rule — base for the centered login card per D-04):
```css
.card{
  background:var(--bg3);
  border:1px solid var(--border);
  border-radius:var(--rL);
  padding:18px;
  margin-bottom:12px;
}
```

**Button pattern** (mockup `.btn` rule — for the login submit button):
```css
.btn{
  width:100%;display:flex;align-items:center;justify-content:center;gap:8px;
  padding:13px;font-size:14px;font-weight:500;
  border-radius:var(--rL);border:1px solid var(--borderM);
  background:var(--bg4);color:var(--text);
  cursor:pointer;transition: ...;
}
```

**Login page structure (new — no mockup analog, derive from D-04):**
- Standalone HTML page (`frontend/login.html`), NOT part of the SPA shell — `<body>` contains a single centered `.card` (use flexbox `min-height:100vh; display:flex; align-items:center; justify-content:center;` on `body` or a wrapper, since the mockup's `.card` is normally inside a scrollable dashboard layout)
- Form fields: email input, password input, submit button (`.btn` with `--accent` background for primary action, or `.btn` default `--bg4` per mockup's button styling — planner's call on which `.btn` variant to use for primary CTA)
- Error message area for D-06's generic "Invalid email or password" text

**`frontend/js/auth.js` (event-driven, no RESEARCH.md code block — derive from D-03 + Pattern 2):**
```javascript
// Login form submit handler
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const formData = new URLSearchParams();
  formData.set("username", document.getElementById("email").value);
  formData.set("password", document.getElementById("password").value);

  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
    credentials: "same-origin",  // ensure cookie is set/sent
  });

  if (res.ok) {
    window.location.href = "/";  // redirect to dashboard
  } else {
    document.getElementById("error-message").textContent = "Invalid email or password";
  }
});

// D-03: global 401 -> redirect-to-login interceptor (use in dashboard's shared JS, not just login.html)
async function apiFetch(url, options = {}) {
  const res = await fetch(url, { ...options, credentials: "same-origin" });
  if (res.status === 401) {
    window.location.href = "/login.html";
    return;
  }
  return res;
}
```

**Note:** Login POST uses `application/x-www-form-urlencoded` with `username`/`password` field names because the backend uses `OAuth2PasswordRequestForm` (Pattern 2) — field names are fixed by that dependency, not arbitrary.

---

### `app/main.py` (controller, request-response — app factory)

**Analog:** `01-RESEARCH.md` System Architecture Diagram (lines 104-150) + Recommended Project Structure (lines 154-201)

**Derived pattern (no single RESEARCH.md code block, but structure is fully specified):**
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import health, talents
from app.auth import router as auth_router

app = FastAPI(title="SEG Talent Intelligence Dashboard")

app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(talents.router)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
```

**Note:** Static file mount must come AFTER API routers are registered (FastAPI matches routes in registration order; mounting `/` first would shadow `/health`, `/auth/*`, `/talents`).

---

## Shared Patterns

### Database Session (get_db dependency)
**Source:** `01-RESEARCH.md` lines 565-595 (`app/database.py`)
**Apply to:** `app/auth/router.py`, `app/auth/dependencies.py`, `app/routers/health.py`, `app/routers/talents.py`, `app/scripts/seed_admin.py`, `app/scripts/seed_talents.py` (scripts use `SessionLocal()` directly, not `Depends(get_db)`, since they run outside the request cycle)
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Authentication Guard (get_current_user)
**Source:** `01-RESEARCH.md` Pattern 2, lines 255-278
**Apply to:** All routes in `app/routers/talents.py` (router-level `dependencies=[Depends(get_current_user)]`), and `/auth/logout`, `/auth/change-password`, `/auth/users` in `app/auth/router.py`. NOT applied to `/health` or `/auth/login`.
```python
def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

### Error Handling / Response Formatting
**Source:** `01-RESEARCH.md` Anti-Patterns (lines 451-457) + Pattern 2 (D-06 generic error)
**Apply to:** All controller files
- Use `HTTPException(status_code=..., detail="...")` for all error responses — FastAPI converts to `{"detail": "..."}` JSON automatically
- Login failures (D-06): always `401` with the literal string `"Invalid email or password"`, regardless of whether the email exists
- Resource-not-found in `talents.py`: `404` with `{"detail": "Talent not found"}` / `{"detail": "Product not found"}`
- Never return raw SQLAlchemy ORM objects — always `response_model=` Pydantic schemas (Anti-Pattern 4)

### Validation
**Source:** `01-RESEARCH.md` Security Domain V5 (line 693) + `app/schemas/` pattern derivations above
**Apply to:** All POST/PATCH handlers in `app/auth/router.py` and `app/routers/talents.py`
- Request bodies are typed Pydantic v2 models from `app/schemas/auth.py` / `app/schemas/talent.py`
- FastAPI auto-validates and returns `422` on invalid input — no manual validation needed
- `EmailStr` for email fields (requires `email-validator`, pulled in transitively by `fastapi[standard]`)

### Cookie Configuration
**Source:** `01-RESEARCH.md` Pitfall 4 (lines 495-501) + Pattern 2
**Apply to:** `app/auth/router.py` (`/auth/login` set_cookie, `/auth/logout` delete_cookie)
```python
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=settings.COOKIE_SECURE,  # from .env, NOT hardcoded — Pitfall 4
    samesite="lax",
    max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),  # 7 days, D-02
    path="/",
)
```

## No Analog Found

All 24 files have no codebase analog (greenfield repo). All are covered by RESEARCH.md patterns or mockup.html design tokens above — no file is left without a concrete pattern source.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (all 24 files listed in File Classification above) | various | various | Repo contains only a default `uv init` scaffold; `app/`, `frontend/`, `alembic/`, `tests/` directories do not exist yet. RESEARCH.md and mockup.html serve as the pattern source for this phase; Phase 2+ will have real codebase analogs from Phase 1's output. |

## Metadata

**Analog search scope:** Entire repo root (`.`, excluding `.git`, `.claude`, `.venv`) — confirmed via `find . -maxdepth 3`
**Files scanned:** 3 existing files (`main.py`, `pyproject.toml`, `.python-version`) + `.planning/reference/mockup.html` + `.planning/research/01-RESEARCH.md`
**Pattern extraction date:** 2026-06-10
