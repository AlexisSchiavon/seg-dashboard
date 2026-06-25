"""Pipedrive API v2 client.

CRITICAL (Pitfall 1): v2 requires the API token in the `x-api-token` HTTP
header, NOT a `?api_token=` query parameter. Do not copy v1-shaped
examples — see RESEARCH.md Pattern 1.

Security note (T-02-01): never log full request/response objects — the
`x-api-token` header is a secret. Callers in app/sync/jobs.py must catch
exceptions and persist only `str(exc)`.
"""
import httpx

from app.config import settings
from app.integrations.base import get_with_retry, paginate

BASE_URL = f"https://{settings.PIPEDRIVE_DOMAIN}.pipedrive.com/api/v2"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"x-api-token": settings.PIPEDRIVE_API_TOKEN},
        timeout=30.0,
    )


def _paginate(client: httpx.Client, path: str, params: dict | None = None):
    yield from paginate(client, path, params)


def _get_with_retry(
    client: httpx.Client, path: str, params: dict, max_attempts: int = 5
) -> httpx.Response:
    return get_with_retry(client, path, params, max_attempts)


def get_deals(client: httpx.Client, updated_since: str | None = None):
    """GET /deals (paginated). Omit updated_since for a full first sync.
    Uses status=all_not_deleted to include open, won, and lost deals (default would only return open)."""
    params: dict = {"status": "open,won,lost"}
    if updated_since:
        params["updated_since"] = updated_since  # RFC3339, e.g. 2026-06-11T10:00:00Z
    yield from _paginate(client, "/deals", params)


def get_deal_products_bulk(client: httpx.Client, deal_ids: list[int]) -> dict[int, list[dict]]:
    """GET /deals/products?deal_ids=1,2,3 — up to 100 deal IDs per call."""
    result: dict[int, list[dict]] = {}
    for chunk_start in range(0, len(deal_ids), 100):
        chunk = deal_ids[chunk_start : chunk_start + 100]
        if not chunk:
            continue
        for item in _paginate(client, "/deals/products", {"deal_ids": ",".join(map(str, chunk))}):
            result.setdefault(item["deal_id"], []).append(item)
    return result


def get_products(client: httpx.Client):
    """GET /products (paginated)."""
    yield from _paginate(client, "/products")


def get_stages(client: httpx.Client):
    """GET /stages (paginated) — stage_id -> name/order_nr mapping (PIPE-05)."""
    yield from _paginate(client, "/stages")


def build_field_maps(client: httpx.Client) -> tuple[dict[str, str], dict[str, dict[int, str]]]:
    """Build (field_name -> field_key) and (field_key -> {option_id: label})
    maps from /dealFields, required for PIPE-04 custom field resolution.

    Pitfall 2: enum/set custom fields store an INTEGER option id on the
    deal — `option_labels` resolves that id to its Spanish label.
    """
    fields = list(_paginate(client, "/dealFields"))
    key_by_name = {f["field_name"]: f["field_code"] for f in fields}
    option_labels: dict[str, dict[int, str]] = {}
    for f in fields:
        if f.get("options"):
            option_labels[f["field_code"]] = {opt["id"]: opt["label"] for opt in f["options"]}
    return key_by_name, option_labels


def resolve_custom_field(deal: dict, field_key: str, option_labels: dict[str, dict[int, str]]):
    """Resolve a deal's custom_fields.<field_key>.value.

    For enum/set fields (field_key in option_labels), returns the label
    string (e.g. "Presupuesto insuficiente") instead of the raw integer
    option id. For plain fields (e.g. date), returns the raw value as-is.
    """
    cf = (deal.get("custom_fields") or {}).get(field_key)
    if cf is None:
        return None
    raw = cf.get("value")
    if field_key in option_labels and raw is not None:
        return option_labels[field_key].get(raw)
    return raw
