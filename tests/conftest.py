import os
import tempfile

# Set test env vars BEFORE importing anything that loads app.config.settings,
# so `uv run pytest` is self-contained and doesn't depend on a developer .env file.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-not-for-prod")
# NOTE: email-validator rejects the IANA "special-use" .test TLD as
# non-deliverable, so use example.com (RFC 2606 reserved, accepted by
# email-validator) for the test admin account.
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("COOKIE_SECURE", "False")

# `app.database.engine` (module-level, used directly by test_database.py) must be a
# real file-backed SQLite DB so PRAGMA journal_mode=WAL takes effect (":memory:"/
# "sqlite://" report journal_mode "memory" and ignore WAL).
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "seg_dashboard_test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.auth.security import get_password_hash
from app.config import settings

# Isolated in-memory SQLite test DB shared across connections via StaticPool.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seed_test_user(db_session):
    user = db_session.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if user is None:
        user = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def auth_client(client, seed_test_user):
    response = client.post(
        "/auth/login",
        data={"username": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client
