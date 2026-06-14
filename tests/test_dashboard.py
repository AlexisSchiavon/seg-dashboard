"""Endpoint contract tests for /dashboard/summary and /dashboard/funnel."""

import pytest


CANONICAL_STAGES = [
    "Llamada",
    "Cotización",
    "Negociación",
    "Contrato",
    "En ejecución",
    "Cobranza",
]

EXPECTED_KPI_LABELS = [
    "Pipeline total",
    "En negociación",
    "Cerrados",
    "En campaña",
]


# ---------------------------------------------------------------------------
# Auth guard tests (T-02B-01)
# ---------------------------------------------------------------------------

def test_summary_requires_auth(client):
    """GET /dashboard/summary returns 401 when unauthenticated."""
    response = client.get("/dashboard/summary")
    assert response.status_code == 401


def test_funnel_requires_auth(client):
    """GET /dashboard/funnel returns 401 when unauthenticated."""
    response = client.get("/dashboard/funnel")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Empty state — no deals seeded
# ---------------------------------------------------------------------------

def test_summary_empty_state(auth_client):
    """GET /dashboard/summary returns has_data=False when no deals exist."""
    response = auth_client.get("/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["has_data"] is False
    assert data["kpis"] == []
    assert data["ranking"] == []
    assert data["activity"] == []


def test_funnel_empty_state(auth_client):
    """GET /dashboard/funnel returns has_data=False when no deals exist."""
    response = auth_client.get("/dashboard/funnel")
    assert response.status_code == 200
    data = response.json()
    assert data["has_data"] is False
    assert data["stages"] == []


# ---------------------------------------------------------------------------
# Summary endpoint with seeded data
# ---------------------------------------------------------------------------

def test_summary_endpoint(auth_client, seed_deals):
    """GET /dashboard/summary returns 200 with DashboardSummary shape."""
    response = auth_client.get("/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["has_data"] is True

    # 4 KPI tiles with correct labels
    kpis = data["kpis"]
    assert len(kpis) == 4
    labels = [k["label"] for k in kpis]
    assert labels == EXPECTED_KPI_LABELS

    # Pipeline total variant is "accent"
    pipeline_tile = kpis[0]
    assert pipeline_tile["label"] == "Pipeline total"
    assert pipeline_tile["variant"] == "accent"
    # seed_deals: 50000 + 0 + 20000 + 15000 = 85000
    assert pipeline_tile["value"] == pytest.approx(85000.0)

    # Ranking present
    assert "ranking" in data
    assert isinstance(data["ranking"], list)
    assert len(data["ranking"]) >= 1  # at least one talent + sin-talento

    # Sin-talento row is last
    sin_row = next((r for r in data["ranking"] if r["is_sin_talento"]), None)
    assert sin_row is not None
    assert data["ranking"][-1]["is_sin_talento"] is True

    # Activity present (seed_deals has 1 stage event)
    assert "activity" in data
    assert isinstance(data["activity"], list)


def test_summary_kpi_variants(auth_client, seed_deals):
    """Each KPI tile uses the correct variant color from the UI-SPEC."""
    response = auth_client.get("/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    variants = {k["label"]: k["variant"] for k in data["kpis"]}
    assert variants["Pipeline total"] == "accent"
    assert variants["En negociación"] == "amber"
    assert variants["Cerrados"] == "purple"
    assert variants["En campaña"] == "green"


def test_summary_ranking_total_reconciles(auth_client, seed_deals):
    """Sum of all ranking revenues equals Pipeline total (Pitfall 4)."""
    response = auth_client.get("/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    pipeline_total = next(k["value"] for k in data["kpis"] if k["label"] == "Pipeline total")
    ranking_total = sum(r["revenue"] for r in data["ranking"])
    assert ranking_total == pytest.approx(pipeline_total, rel=1e-6)


# ---------------------------------------------------------------------------
# Funnel endpoint with seeded data
# ---------------------------------------------------------------------------

def test_funnel_endpoint(auth_client, seed_deals):
    """GET /dashboard/funnel returns 200 with exactly 6 stages in canonical order."""
    response = auth_client.get("/dashboard/funnel")
    assert response.status_code == 200
    data = response.json()

    assert data["has_data"] is True

    # Exactly 6 stages in canonical order
    stage_names = [s["stage"] for s in data["stages"]]
    assert stage_names == CANONICAL_STAGES

    # Both fields present
    assert "bottleneck" in data
    assert "insufficient_data" in data

    # seed_deals has 4 deals — insufficient for bottleneck detection
    assert data["insufficient_data"] is True
    assert data["bottleneck"] is None


def test_funnel_all_stages_have_count_and_amount(auth_client, seed_deals):
    """Each stage bucket has count (int) and amount (float)."""
    response = auth_client.get("/dashboard/funnel")
    assert response.status_code == 200
    data = response.json()

    for stage in data["stages"]:
        assert "stage" in stage
        assert "count" in stage
        assert "amount" in stage
        assert isinstance(stage["count"], int)
        assert isinstance(stage["amount"], float)


def test_funnel_bottleneck_detected_with_large_dataset(auth_client, db_session, seed_test_user):
    """Funnel returns bottleneck info when >=10 deals exist."""
    from app.models import Deal

    # Insert 12 deals across stages
    stage_map = {
        "Llamada": 5,
        "Cotización": 3,
        "Negociación": 1,
        "Contrato": 1,
        "En ejecución": 0,
        "Cobranza": 0,
    }
    pid = 9100
    for stage_name, count in stage_map.items():
        for i in range(count):
            db_session.add(Deal(
                pipedrive_id=pid,
                title=f"Deal {stage_name} {i}",
                value=5000.0,
                currency="MXN",
                stage_id=1,
                stage_name=stage_name,
                status="open",
                talent_id=None,
                commission_amount=3500.0,
                is_sin_cotizar=False,
                update_time="2026-06-01T10:00:00Z",
            ))
            pid += 1
    db_session.commit()

    response = auth_client.get("/dashboard/funnel")
    assert response.status_code == 200
    data = response.json()

    assert data["has_data"] is True
    assert data["insufficient_data"] is False
    assert data["bottleneck"] is not None
    bn = data["bottleneck"]
    assert "stage_a" in bn
    assert "stage_b" in bn
    assert "conversion_pct" in bn
    assert 0.0 <= bn["conversion_pct"] <= 100.0
