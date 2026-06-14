"""Tests for app/integrations/pipedrive.py (Pipedrive v2 client).

Wave 0 (this plan, Task 1): stub file with xfail-marked placeholders.
Task 2 of this plan implements app/integrations/base.py and
app/integrations/pipedrive.py and turns these into real
RED -> GREEN assertions (TDD).
"""
import pytest


@pytest.mark.xfail(reason="app/integrations/pipedrive.py not implemented until Task 2", strict=False)
def test_client_uses_x_api_token_header(mock_pipedrive_transport, monkeypatch):
    """PipedriveClient must send the `x-api-token` header (v2 auth),
    NOT a `?api_token=` query param (Pitfall 1)."""
    from app.integrations import pipedrive

    captured = {}

    def handler(request):
        captured["headers"] = dict(request.headers)
        captured["params"] = dict(request.url.params)
        return mock_pipedrive_transport.handle_request(request)

    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=httpx.MockTransport(handler),
    ))

    client = pipedrive._client()
    list(pipedrive.get_stages(client))

    assert "x-api-token" in captured["headers"]
    assert "api_token" not in captured["params"]


@pytest.mark.xfail(reason="app/integrations/pipedrive.py not implemented until Task 2", strict=False)
def test_paginate_follows_next_cursor(mock_pipedrive_transport, monkeypatch):
    """_paginate must follow additional_data.next_cursor until null,
    yielding all deals across pages."""
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    client = pipedrive._client()
    deals = list(pipedrive.get_deals(client))

    assert {d["id"] for d in deals} == {1001, 1002, 1003}


@pytest.mark.xfail(reason="app/integrations/pipedrive.py not implemented until Task 2", strict=False)
def test_resolve_custom_fields(mock_pipedrive_transport, monkeypatch):
    """resolve_custom_field must resolve enum custom_fields (hash -> name,
    option id -> label) per PIPE-04. razon de perdida / categoria de marca
    are enum fields; fecha de cobro esperada is a plain value."""
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    client = pipedrive._client()
    key_by_name, option_labels = pipedrive.build_field_maps(client)

    categoria_key = key_by_name["Categoría de marca"]
    fecha_key = key_by_name["Fecha de cobro esperada"]

    deal = {
        "custom_fields": {
            categoria_key: {"value": 10},
            fecha_key: {"value": "2026-07-01"},
        }
    }

    assert pipedrive.resolve_custom_field(deal, categoria_key, option_labels) == "Moda"
    assert pipedrive.resolve_custom_field(deal, fecha_key, option_labels) == "2026-07-01"


@pytest.mark.xfail(reason="app/integrations/pipedrive.py not implemented until Task 2", strict=False)
def test_get_deal_products_bulk_chunks_by_100(mock_pipedrive_transport, monkeypatch):
    """get_deal_products_bulk must chunk deal_ids into batches of 100
    when calling /deals/products?deal_ids=..."""
    from app.integrations import pipedrive
    import httpx

    monkeypatch.setattr(pipedrive, "_client", lambda: httpx.Client(
        base_url=pipedrive.BASE_URL,
        transport=mock_pipedrive_transport,
    ))

    client = pipedrive._client()
    deal_ids = list(range(1, 151))  # 150 ids -> 2 chunks
    result = pipedrive.get_deal_products_bulk(client, deal_ids)

    assert isinstance(result, dict)
