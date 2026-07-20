"""Tests for AI insights (Módulo 1 / Resumen). The agent call is monkeypatched
at app.services.insights._call_agent so no real Anthropic call is made."""
from app.models import InsightsCache
from app.services import insights as insights_service

VALID_AGENT_JSON = (
    '{"insights":['
    '{"titulo":"Firmadas al alza","texto":"Julio supera junio en 20%.","tipo":"positivo"},'
    '{"titulo":"Cobranza pesada","texto":"7 cards vencidas por $1.02M.","tipo":"alerta"}'
    ']}'
)


def test_parse_valid_json_returns_insights():
    out = insights_service._parse_insights_json(VALID_AGENT_JSON)
    assert len(out) == 2
    assert out[0]["titulo"] == "Firmadas al alza"
    assert out[0]["tipo"] == "positivo"
    assert out[1]["tipo"] == "alerta"


def test_parse_strips_markdown_json_fences():
    fenced = "```json\n" + VALID_AGENT_JSON + "\n```"
    out = insights_service._parse_insights_json(fenced)
    assert len(out) == 2


def test_parse_coerces_unknown_tipo_to_neutro_and_truncates():
    raw = '{"insights":[{"titulo":"' + "A" * 80 + '","texto":"x","tipo":"raro"}]}'
    out = insights_service._parse_insights_json(raw)
    assert out[0]["tipo"] == "neutro"
    assert len(out[0]["titulo"]) <= 60


def test_parse_truncates_texto_at_word_boundary():
    long_texto = "Palabra " * 40  # ~320 chars
    raw = '{"insights":[{"titulo":"T","texto":"' + long_texto.strip() + '","tipo":"neutro"}]}'
    out = insights_service._parse_insights_json(raw)
    texto = out[0]["texto"]
    assert len(texto) <= 200
    assert texto.endswith("…")
    # no mid-word cut: the part before the ellipsis ends on a complete word
    assert not texto[:-1].rstrip().endswith("Palabr")


def test_parse_malformed_raises():
    import pytest
    with pytest.raises(Exception):
        insights_service._parse_insights_json("no soy json en absoluto")


def test_generate_happy_path(db_session, monkeypatch):
    monkeypatch.setattr(insights_service, "_call_agent", lambda db: VALID_AGENT_JSON)
    out = insights_service.generate_insights(db_session)
    assert len(out) == 2 and out[0]["titulo"] == "Firmadas al alza"


def test_agent_down_returns_empty_with_error(db_session, monkeypatch):
    def boom(db):
        raise RuntimeError("anthropic caído")
    monkeypatch.setattr(insights_service, "_call_agent", boom)
    result = insights_service.get_resumen_insights(db_session)
    assert result["insights"] == []
    assert result["error"] == "no disponible"
    # never raises → Resumen no se rompe


def test_cache_hit_second_call_skips_agent(db_session, monkeypatch):
    calls = {"n": 0}

    def counting(db):
        calls["n"] += 1
        return VALID_AGENT_JSON
    monkeypatch.setattr(insights_service, "_call_agent", counting)

    first = insights_service.get_resumen_insights(db_session)
    assert first["cached"] is False and calls["n"] == 1

    second = insights_service.get_resumen_insights(db_session)
    assert second["cached"] is True and calls["n"] == 1  # agent NOT called again
    assert len(second["insights"]) == 2


def test_regenerate_forces_new_agent_call(db_session, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(insights_service, "_call_agent",
                        lambda db: (calls.__setitem__("n", calls["n"] + 1), VALID_AGENT_JSON)[1])
    insights_service.get_resumen_insights(db_session)
    insights_service.get_resumen_insights(db_session, regenerate=True)
    assert calls["n"] == 2  # regenerate bypasses cache
    # cache row persisted
    assert db_session.query(InsightsCache).filter_by(cache_key="resumen").count() == 1


# --- Endpoint tests -------------------------------------------------------

def test_endpoint_requires_auth(client):
    resp = client.get("/api/insights/resumen")
    assert resp.status_code == 401


def test_endpoint_returns_insights(auth_client, monkeypatch):
    monkeypatch.setattr(insights_service, "_call_agent", lambda db: VALID_AGENT_JSON)
    resp = auth_client.get("/api/insights/resumen")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["insights"]) == 2
    assert body["insights"][0]["tipo"] == "positivo"
    assert body["cached"] is False


def test_endpoint_regenerate_rate_limited(auth_client, monkeypatch):
    from app.routers import insights as insights_router
    insights_router._regen_requests.clear()  # isolate rate-limit state
    monkeypatch.setattr(insights_service, "_call_agent", lambda db: VALID_AGENT_JSON)

    r1 = auth_client.get("/api/insights/resumen?regenerate=true")
    assert r1.status_code == 200
    r2 = auth_client.get("/api/insights/resumen?regenerate=true")
    assert r2.status_code == 429  # 2nd regenerate within 60s blocked
