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

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Deal, DealStageEvent, Talent, TalentProduct, User
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


@pytest.fixture()
def seed_talent_products(db_session):
    """Create a couple of Talent + TalentProduct rows with known
    pipedrive_product_id values, for talent-matching tests (PIPE-02)."""
    talent_a = Talent(name="Talento Uno", active=True, category="Lifestyle")
    talent_b = Talent(name="Talento Dos", active=True, category="Gaming")
    db_session.add_all([talent_a, talent_b])
    db_session.commit()
    db_session.refresh(talent_a)
    db_session.refresh(talent_b)

    product_a = TalentProduct(talent_id=talent_a.id, pipedrive_product_id=101)
    product_b = TalentProduct(talent_id=talent_b.id, pipedrive_product_id=202)
    db_session.add_all([product_a, product_b])
    db_session.commit()

    return {
        "talent_a": talent_a,
        "talent_b": talent_b,
        "product_a": product_a,
        "product_b": product_b,
    }


@pytest.fixture()
def seed_deals(db_session, seed_talent_products):
    """Create Deal/DealStageEvent rows for service-layer tests
    (funnel, kpis, dashboard, sync diffing)."""
    talent_a = seed_talent_products["talent_a"]
    talent_b = seed_talent_products["talent_b"]

    deal_open = Deal(
        pipedrive_id=1001,
        title="Campaña Talento Uno",
        value=50000.0,
        currency="MXN",
        stage_id=3,
        stage_name="Negociación",
        status="open",
        talent_id=talent_a.id,
        commission_amount=35000.0,
        is_sin_cotizar=False,
        update_time="2026-06-01T10:00:00Z",
        add_time="2026-05-20T09:00:00Z",
    )
    deal_sin_cotizar = Deal(
        pipedrive_id=1002,
        title="Cotización pendiente Talento Dos",
        value=0.0,
        currency="MXN",
        stage_id=1,
        stage_name="Llamada",
        status="open",
        talent_id=talent_b.id,
        commission_amount=0.0,
        is_sin_cotizar=True,
        update_time="2026-06-02T10:00:00Z",
        add_time="2026-05-25T09:00:00Z",
    )
    deal_sin_talento = Deal(
        pipedrive_id=1003,
        title="Lead sin talento asignado",
        value=20000.0,
        currency="MXN",
        stage_id=2,
        stage_name="Cotización",
        status="open",
        talent_id=None,
        commission_amount=14000.0,
        is_sin_cotizar=False,
        update_time="2026-06-03T10:00:00Z",
        add_time="2026-05-28T09:00:00Z",
    )
    deal_lost = Deal(
        pipedrive_id=1004,
        title="Campaña perdida Talento Uno",
        value=15000.0,
        currency="MXN",
        stage_id=3,
        stage_name="Negociación",
        status="lost",
        talent_id=talent_a.id,
        commission_amount=10500.0,
        is_sin_cotizar=False,
        loss_reason="Presupuesto insuficiente",
        brand_category="Moda",
        update_time="2026-06-04T10:00:00Z",
        add_time="2026-05-15T09:00:00Z",
    )
    db_session.add_all([deal_open, deal_sin_cotizar, deal_sin_talento, deal_lost])
    db_session.commit()
    for deal in (deal_open, deal_sin_cotizar, deal_sin_talento, deal_lost):
        db_session.refresh(deal)

    stage_event = DealStageEvent(
        deal_pipedrive_id=deal_open.pipedrive_id,
        talent_id=talent_a.id,
        from_stage="Cotización",
        to_stage="Negociación",
        from_status="open",
        to_status="open",
    )
    db_session.add(stage_event)
    db_session.commit()

    return {
        "deal_open": deal_open,
        "deal_sin_cotizar": deal_sin_cotizar,
        "deal_sin_talento": deal_sin_talento,
        "deal_lost": deal_lost,
        "stage_event": stage_event,
    }


# v2-shaped fixture payloads matching RESEARCH.md Pattern 1/2 response shapes.
PIPEDRIVE_DEAL_FIELDS = [
    {
        "key": "razon_perdida_hash",
        "name": "Razón de pérdida",
        "options": [
            {"id": 1, "label": "Presupuesto insuficiente"},
            {"id": 2, "label": "Sin respuesta"},
            {"id": 3, "label": "Eligió competencia"},
            {"id": 4, "label": "Talento no disponible"},
            {"id": 5, "label": "Otro"},
        ],
    },
    {
        "key": "categoria_marca_hash",
        "name": "Categoría de marca",
        "options": [
            {"id": 10, "label": "Moda"},
            {"id": 11, "label": "Belleza"},
            {"id": 12, "label": "Tecnología"},
            {"id": 13, "label": "Alimentos y bebidas"},
            {"id": 14, "label": "Entretenimiento"},
            {"id": 15, "label": "Otro"},
        ],
    },
    {
        "key": "fecha_cobro_hash",
        "name": "Fecha de cobro esperada",
        "options": None,
    },
]

PIPEDRIVE_STAGES = [
    {"id": 1, "name": "Llamada", "order_nr": 0},
    {"id": 2, "name": "Cotización", "order_nr": 1},
    {"id": 3, "name": "Negociación", "order_nr": 2},
    {"id": 4, "name": "Contrato", "order_nr": 3},
    {"id": 5, "name": "En ejecución", "order_nr": 4},
    {"id": 6, "name": "Cobranza", "order_nr": 5},
]

PIPEDRIVE_DEALS_PAGE_1 = {
    "success": True,
    "data": [
        {
            "id": 1001,
            "title": "Campaña Talento Uno",
            "value": 50000,
            "currency": "MXN",
            "stage_id": 3,
            "status": "open",
            "update_time": "2026-06-01 10:00:00",
            "add_time": "2026-05-20 09:00:00",
            "custom_fields": {
                "razon_perdida_hash": {"value": None},
                "categoria_marca_hash": {"value": 10},
                "fecha_cobro_hash": {"value": "2026-07-01"},
            },
        },
        {
            "id": 1002,
            "title": "Cotización pendiente Talento Dos",
            "value": 0,
            "currency": "MXN",
            "stage_id": 1,
            "status": "open",
            "update_time": "2026-06-02 10:00:00",
            "add_time": "2026-05-25 09:00:00",
            "custom_fields": {},
        },
    ],
    "additional_data": {"next_cursor": "cursor-page-2"},
}

PIPEDRIVE_DEALS_PAGE_2 = {
    "success": True,
    "data": [
        {
            "id": 1003,
            "title": "Lead sin talento asignado",
            "value": 20000,
            "currency": "MXN",
            "stage_id": 2,
            "status": "open",
            "update_time": "2026-06-03 10:00:00",
            "add_time": "2026-05-28 09:00:00",
            "custom_fields": {},
        },
    ],
    "additional_data": {"next_cursor": None},
}

PIPEDRIVE_PRODUCTS = {
    "success": True,
    "data": [
        {"id": 101, "name": "Producto Talento Uno"},
        {"id": 202, "name": "Producto Talento Dos"},
    ],
    "additional_data": {"next_cursor": None},
}

PIPEDRIVE_DEAL_PRODUCTS = {
    "success": True,
    "data": [
        {"id": 1001, "product_id": 101, "name": "Producto Talento Uno"},
        {"id": 1002, "product_id": 202, "name": "Producto Talento Dos"},
    ],
    "additional_data": {"next_cursor": None},
}


@pytest.fixture()
def mock_pipedrive_transport():
    """httpx.MockTransport serving recorded v2-shaped JSON for
    /deals (paginated), /dealFields, /products, /deals/products, /stages."""

    deal_pages = {None: PIPEDRIVE_DEALS_PAGE_1, "cursor-page-2": PIPEDRIVE_DEALS_PAGE_2}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = dict(request.url.params)

        if path.endswith("/deals") and "products" not in path:
            cursor = params.get("cursor")
            return httpx.Response(200, json=deal_pages.get(cursor, PIPEDRIVE_DEALS_PAGE_2))
        if path.endswith("/dealFields"):
            return httpx.Response(
                200,
                json={"success": True, "data": PIPEDRIVE_DEAL_FIELDS, "additional_data": {"next_cursor": None}},
            )
        if path.endswith("/products"):
            return httpx.Response(200, json=PIPEDRIVE_PRODUCTS)
        if path.endswith("/deals/products"):
            return httpx.Response(200, json=PIPEDRIVE_DEAL_PRODUCTS)
        if path.endswith("/stages"):
            return httpx.Response(
                200,
                json={"success": True, "data": PIPEDRIVE_STAGES, "additional_data": {"next_cursor": None}},
            )
        return httpx.Response(404, json={"success": False, "error": f"unmocked path: {path}"})

    return httpx.MockTransport(handler)
