"""Shared httpx helpers for outbound integrations (Pipedrive, etc.).

Security note (T-02-01): never log full request/response objects here —
`response.request.headers` carries the `x-api-token` secret. Callers should
catch exceptions and store only `str(exc)`, never `repr(response.request)`.
"""
import time

import httpx


def get_with_retry(
    client: httpx.Client, path: str, params: dict, max_attempts: int = 5
) -> httpx.Response:
    """GET with Retry-After-aware 429 backoff (max 5 attempts)."""
    resp: httpx.Response | None = None
    for attempt in range(max_attempts):
        resp = client.get(path, params=params)
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 2**attempt))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    assert resp is not None
    resp.raise_for_status()
    return resp


def paginate(client: httpx.Client, path: str, params: dict | None = None):
    """Generic cursor-pagination generator for Pipedrive v2 list endpoints.

    Yields each item in `data`, following `additional_data.next_cursor`
    until it is null/absent.
    """
    params = dict(params or {})
    params.setdefault("limit", 500)
    cursor = None
    while True:
        if cursor:
            params["cursor"] = cursor
        resp = get_with_retry(client, path, params)
        payload = resp.json()
        yield from (payload.get("data") or [])
        cursor = (payload.get("additional_data") or {}).get("next_cursor")
        if not cursor:
            break
