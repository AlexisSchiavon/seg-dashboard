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

from app.database import Base, engine, get_db
from app.main import app
from app.models import Deal, DealStageEvent, Lead, Report, Talent, TalentProduct, User
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

# app/sync/scheduler.py and app/routers/sync.py's background tasks construct
# their own `SessionLocal()` (bound to `app.database.engine`, i.e. DATABASE_URL)
# rather than using the overridden `get_db` dependency -- this is the documented
# pattern for background/scheduled code (02-PATTERNS.md). So the file-backed
# test DB also needs its schema created, or sync_pipedrive's first query
# (SyncLog concurrency guard) raises "no such table: sync_logs".
Base.metadata.create_all(bind=engine)


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


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables after each test.

    The test DB uses a shared in-memory SQLite engine (StaticPool) so rows
    persist across tests within the same session. Fixtures like
    seed_talent_products/seed_deals insert rows with unique constraints
    (e.g. talents.name), which collide across tests without this cleanup.
    """
    yield
    db = TestSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
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
            is_admin=True,  # admin so /auth/users (is_admin guard) is testable
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
        "field_code": "razon_perdida_hash",
        "field_name": "Razón de pérdida",
        "options": [
            {"id": 1, "label": "Presupuesto insuficiente"},
            {"id": 2, "label": "Sin respuesta"},
            {"id": 3, "label": "Eligió competencia"},
            {"id": 4, "label": "Talento no disponible"},
            {"id": 5, "label": "Otro"},
        ],
    },
    {
        "field_code": "categoria_marca_hash",
        "field_name": "Categoría de marca",
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
        "field_code": "fecha_cobro_hash",
        "field_name": "Fecha de cobro esperada",
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
        {"id": 1, "deal_id": 1001, "product_id": 101, "name": "Producto Talento Uno"},
        {"id": 2, "deal_id": 1002, "product_id": 202, "name": "Producto Talento Dos"},
    ],
    "additional_data": {"next_cursor": None},
}


@pytest.fixture()
def seed_leads(db_session, seed_talent_products):
    """Create Lead rows covering the three Status_Filtrado values (SHEET-01/SHEET-02).

    Three rows:
    - lead_aprobado: linked to talent_a, status = QUALIFIED_STATUS
    - lead_bloqueado: linked to talent_b, status = 'Remitente bloqueado'
    - lead_revision: talent_id=None (Sin talento asignado), status = 'En revisión'
    """
    talent_a = seed_talent_products["talent_a"]
    talent_b = seed_talent_products["talent_b"]

    lead_aprobado = Lead(
        sheet_row_id=2,
        remitente_email="aprobado@example.com",
        remitente_nombre="Remitente Aprobado",
        asunto="Colaboración pagada TikTok",
        talent_id=talent_a.id,
        status_filtrado="✅ Aprobado - Respuesta enviada",
        fuente="Gmail",
        score_calidad=80,
        bloqueado=False,
        convertido_a_prospecto=False,
    )
    lead_bloqueado = Lead(
        sheet_row_id=3,
        remitente_email="spam@example.com",
        remitente_nombre="Spam Sender",
        asunto="Oferta sospechosa",
        talent_id=talent_b.id,
        status_filtrado="🚫 Remitente bloqueado",
        fuente="Gmail",
        score_calidad=5,
        bloqueado=True,
        convertido_a_prospecto=False,
    )
    lead_revision = Lead(
        sheet_row_id=4,
        remitente_email="revision@example.com",
        remitente_nombre="Pendiente Review",
        asunto="Propuesta de colaboración",
        talent_id=None,
        status_filtrado="En revisión",
        fuente="Gmail",
        score_calidad=45,
        bloqueado=False,
        convertido_a_prospecto=False,
    )
    db_session.add_all([lead_aprobado, lead_bloqueado, lead_revision])
    db_session.commit()
    for lead in (lead_aprobado, lead_bloqueado, lead_revision):
        db_session.refresh(lead)

    return {
        "lead_aprobado": lead_aprobado,
        "lead_bloqueado": lead_bloqueado,
        "lead_revision": lead_revision,
    }


@pytest.fixture()
def mock_sheets_rows(monkeypatch):
    """Replace sheets.get_leads_rows() with a list of SheetLeadRow fixtures.

    Covers all 3 Status_Filtrado values from RESEARCH.md live data.
    One row has talento_mencionado="" to exercise the Sin-talento path.
    Uses monkeypatch on the jobs module (NOT httpx.MockTransport —
    gspread is NOT an httpx client).
    """
    from app.integrations.sheets import SheetLeadRow

    sample = [
        SheetLeadRow(
            sheet_row_id=2,
            remitente_email="a@example.com",
            remitente_nombre="A",
            asunto="Collab TikTok",
            fecha_recepcion="2026-04-01T10:00:00Z",
            talento_mencionado="Emicanico",
            status_filtrado="✅ Aprobado - Respuesta enviada",
            score_calidad=85,
            bloqueado=False,
            convertido_a_prospecto=False,
        ),
        SheetLeadRow(
            sheet_row_id=3,
            remitente_email="b@example.com",
            remitente_nombre="B",
            asunto="Spam promo",
            fecha_recepcion="2026-04-02T10:00:00Z",
            talento_mencionado="Mariana",
            status_filtrado="🚫 Remitente bloqueado",
            score_calidad=10,
            bloqueado=False,
            convertido_a_prospecto=False,
        ),
        SheetLeadRow(
            sheet_row_id=4,
            remitente_email="c@example.com",
            remitente_nombre="C",
            asunto="Propuesta",
            fecha_recepcion="2026-04-03T10:00:00Z",
            talento_mencionado="",
            status_filtrado="En revisión",
            score_calidad=45,
            bloqueado=False,
            convertido_a_prospecto=False,
        ),
    ]
    import app.sync.jobs as jobs_module

    # Use staticmethod so Python doesn't inject 'self' when called on an instance
    monkeypatch.setattr(
        jobs_module,
        "sheets",
        type("_MockSheets", (), {"get_leads_rows": staticmethod(lambda: sample)})(),
    )
    return sample


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
        if path.endswith("/deals/products"):
            return httpx.Response(200, json=PIPEDRIVE_DEAL_PRODUCTS)
        if path.endswith("/products"):
            return httpx.Response(200, json=PIPEDRIVE_PRODUCTS)
        if path.endswith("/stages"):
            return httpx.Response(
                200,
                json={"success": True, "data": PIPEDRIVE_STAGES, "additional_data": {"next_cursor": None}},
            )
        return httpx.Response(404, json={"success": False, "error": f"unmocked path: {path}"})

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Phase 4 — Trello fixtures
# ---------------------------------------------------------------------------

# Minimal card payloads matching the fields requested by get_list_cards:
# fields=id,name,due,desc
TRELLO_CARD_EJECUCION = {
    "id": "card-ejecucion-001",
    "name": "Campaña Talento Uno — Contrato",
    "due": "2026-08-15T12:00:00.000Z",
    "desc": "[seg:deal_id=1001]",
}

TRELLO_CARD_COBRANZA = {
    "id": "card-cobranza-001",
    "name": "Campaña Talento Dos — Cobrar",
    "due": None,
    "desc": "[seg:deal_id=1002]",
}

TRELLO_CARD_CERRADO = {
    "id": "card-cerrado-001",
    "name": "Campaña Sin Talento — Finalizado",
    "due": "2026-07-01T12:00:00.000Z",
    "desc": "[seg:deal_id=1003]",
}

# Card in Otros pendientes (list_id 6996256c42ccdae7f69e4814) — must be ignored
TRELLO_CARD_OTROS = {
    "id": "card-otros-001",
    "name": "Pendiente ignorado",
    "due": None,
    "desc": "",
}

# Created-card response shape (Trello POST /cards response)
TRELLO_CREATED_CARD = {
    "id": "card-new-001",
    "name": "New Card",
    "idList": "69312ac640ae158381706ff8",
    "due": None,
    "desc": "",
}


@pytest.fixture()
def mock_trello_transport():
    """httpx.MockTransport serving recorded Trello API JSON for list cards and card creation.

    Mirrors mock_pipedrive_transport pattern. Handler matches:
    - GET /lists/{id}/cards → card list for that list (key/token query params ignored)
    - POST /cards → created-card dict

    Six active lists return their respective sample cards; Otros pendientes
    returns its card (the sync job must filter it via LIST_STATE_MAP).
    """
    list_cards: dict[str, list[dict]] = {
        "69312ac640ae158381706ff8": [TRELLO_CARD_EJECUCION],   # Contrato
        "69312acb534b0e80508bf4e5": [],                        # Firmar contrato todos (empty)
        "69312ad08fe346b82da12e1d": [],                        # Enviar factura (empty)
        "69312ad63829ef3ac9967d1a": [TRELLO_CARD_COBRANZA],   # Cobrar
        "69312adeac51905b84f53c35": [],                        # Enviar encuesta (empty)
        "69d8336e46709e935f4307fe": [TRELLO_CARD_CERRADO],    # Finalizados
        "6996256c42ccdae7f69e4814": [TRELLO_CARD_OTROS],      # Otros pendientes (ignored)
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        # key and token query params are intentionally ignored (test credentials)

        # GET /lists/{list_id}/cards
        if "/lists/" in path and path.endswith("/cards"):
            list_id = path.split("/lists/")[1].split("/")[0]
            cards = list_cards.get(list_id, [])
            return httpx.Response(200, json=cards)

        # POST /cards
        if path == "/cards" or path.endswith("/cards"):
            if request.method == "POST":
                return httpx.Response(200, json=TRELLO_CREATED_CARD)

        return httpx.Response(404, json={"error": f"unmocked Trello path: {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture()
def seed_trello_cards(db_session, seed_deals):
    """Create TrelloCard rows linked to seed_deals for service-layer tests.

    Mirrors seed_leads pattern. Three cards:
    - card_ejecucion: linked to deal_open (ejecucion state)
    - card_cobranza: linked to deal_sin_cotizar (cobranza state)
    - card_cerrado: linked to deal_sin_talento (cerrado state)

    deal_lost is intentionally NOT linked to any card (for no-duplicate tests).
    """
    from datetime import date

    from app.models import TrelloCard

    deal_open = seed_deals["deal_open"]
    deal_sin_cotizar = seed_deals["deal_sin_cotizar"]
    deal_sin_talento = seed_deals["deal_sin_talento"]

    card_ejecucion = TrelloCard(
        trello_card_id="card-ejecucion-001",
        name="Campaña Talento Uno — Contrato",
        list_id="69312ac640ae158381706ff8",
        list_name="Contrato",
        list_state="ejecucion",
        deal_id=deal_open.id,
        pipedrive_deal_id_desc=deal_open.pipedrive_id,
        collection_date=date(2026, 8, 15),
    )
    card_cobranza = TrelloCard(
        trello_card_id="card-cobranza-001",
        name="Campaña Talento Dos — Cobrar",
        list_id="69312ad63829ef3ac9967d1a",
        list_name="Cobrar",
        list_state="cobranza",
        deal_id=deal_sin_cotizar.id,
        pipedrive_deal_id_desc=deal_sin_cotizar.pipedrive_id,
        collection_date=None,
    )
    card_cerrado = TrelloCard(
        trello_card_id="card-cerrado-001",
        name="Campaña Sin Talento — Finalizado",
        list_id="69d8336e46709e935f4307fe",
        list_name="Finalizados",
        list_state="cerrado",
        deal_id=deal_sin_talento.id,
        pipedrive_deal_id_desc=deal_sin_talento.pipedrive_id,
        collection_date=date(2026, 7, 1),
    )

    db_session.add_all([card_ejecucion, card_cobranza, card_cerrado])
    db_session.commit()
    for card in (card_ejecucion, card_cobranza, card_cerrado):
        db_session.refresh(card)

    return {
        "card_ejecucion": card_ejecucion,
        "card_cobranza": card_cobranza,
        "card_cerrado": card_cerrado,
    }


# ---------------------------------------------------------------------------
# Phase 5 — Report mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_anthropic(monkeypatch):
    """Return a mock Anthropic client that returns a fixed narrative JSON response.

    Monkeypatches app.services.reports.anthropic.Anthropic so no real API
    calls are made. The fake response matches the 3-section JSON contract
    expected by _call_claude() in app/services/reports.py.
    """
    from unittest.mock import MagicMock

    fake_response = MagicMock()
    fake_response.content = [MagicMock(
        type="text",
        text=(
            '{"resumen_ejecutivo":"Resumen de prueba.",'
            '"deals_destacados":"Deals de prueba.",'
            '"recomendacion":"Recomendacion de prueba."}'
        ),
    )]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    monkeypatch.setattr("app.services.reports.anthropic.Anthropic", lambda **kwargs: mock_client)
    return mock_client


@pytest.fixture()
def mock_weasyprint(monkeypatch, tmp_path):
    """Replace weasyprint.HTML with a stub that writes a minimal PDF marker.

    Monkeypatches app.services.reports.HTML so no Pango/Cairo system libs
    are required locally. The fake PDF write creates a minimal %PDF-1.4 marker
    at the given path, satisfying file_size_bytes > 0 assertions.
    """
    from unittest.mock import MagicMock

    def fake_write_pdf(path_or_none=None):
        if path_or_none:
            os.makedirs(os.path.dirname(path_or_none), exist_ok=True)
            with open(path_or_none, "wb") as f:
                f.write(b"%PDF-1.4")
        return b"%PDF-1.4"

    mock_html_cls = MagicMock()
    mock_html_cls.return_value.write_pdf = fake_write_pdf
    monkeypatch.setattr("app.services.reports.HTML", mock_html_cls)
    return mock_html_cls
