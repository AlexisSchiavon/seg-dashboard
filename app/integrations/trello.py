"""Trello REST API client (Phase 4).

Security note (T-04-01): NEVER log repr(response.request) — Trello
authenticates via key= and token= QUERY PARAMETERS, not a header.
Those parameters appear in request.url and repr(request), so any debug
log of the full request object leaks both secrets. Callers in
app/sync/jobs.py must catch exceptions and persist only str(exc).

Auth model: key + token query params on every request (not Bearer/header).
BASE_URL: https://api.trello.com/1
Free-plan note (D-46): Custom Fields Power-Up is NOT available on the
free plan. No custom-field code path exists here — confirmed by live API
research (RESEARCH.md Pattern 3, 2026-06-14).
"""
import httpx

from app.config import settings
from app.integrations.base import get_with_retry
from app.services.trello_service import _extract_deal_id_from_desc

BASE_URL = "https://api.trello.com/1"

# Entry list for auto-created cards (won deals with no card → create here).
# Decision D-46: CONTRATO_LIST_ID is the first list in the ejecucion state.
CONTRATO_LIST_ID = "69312ac640ae158381706ff8"


def allowed_create_list_ids() -> frozenset[str]:
    """List IDs into which auto-create may write.

    Always includes the prod Contrato list. If TRELLO_AUTOCREATE_LIST_ID is
    set (Phase C sandbox), that list is also allowed. Any create targeting a
    list outside this set is a programming error and must fail hard.
    """
    ids = {CONTRATO_LIST_ID}
    sandbox = (settings.TRELLO_AUTOCREATE_LIST_ID or "").strip()
    if sandbox:
        ids.add(sandbox)
    return frozenset(ids)

# Maps Trello list IDs (from the verified live board 69312a9d5523703a1ce1a413)
# to their canonical state values used in TrelloCard.list_state.
#
# Fase 9.8a (mapeo corregido — verificado con Alexis contra el board real):
#   - "Enviar encuesta" es un estado POST-COBRO (encuesta de satisfacción tras
#     cobrar), NO cobranza pendiente → 'cerrado'. Antes estaba mal como 'cobranza'
#     e inflaba la "cobranza vencida".
#   - "Otros pendientes" es basura administrativa (vuelos, devoluciones, etc.),
#     fuera del flujo comercial → 'omitido'. El estado 'omitido' se EXCLUYE de
#     todos los KPIs, proyecciones, cobranza vencida y widgets.
#   - Solo "Cobrar" (= 'cobranza') representa cobro genuinamente pendiente.
LIST_STATE_MAP: dict[str, str] = {
    "69312ac640ae158381706ff8": "ejecucion",   # Contrato
    "69312acb534b0e80508bf4e5": "ejecucion",   # Firmar contrato todos
    "69312ad08fe346b82da12e1d": "ejecucion",   # Enviar factura
    "69312ad63829ef3ac9967d1a": "cobranza",    # Cobrar
    "69312adeac51905b84f53c35": "cerrado",     # Enviar encuesta (post-cobro, 9.8a)
    "6996256c42ccdae7f69e4814": "omitido",     # Otros pendientes (excluido de todo)
    "69d8336e46709e935f4307fe": "cerrado",     # Finalizados
}


def _client() -> httpx.Client:
    """Return an httpx.Client configured for the Trello REST API.

    No auth header is set — Trello uses query params (see _auth_params).
    """
    return httpx.Client(base_url=BASE_URL, timeout=30.0)


def _auth_params() -> dict[str, str]:
    """Return Trello query-param credentials from settings."""
    return {
        "key": settings.TRELLO_API_KEY,
        "token": settings.TRELLO_TOKEN,
    }


def get_list_cards(client: httpx.Client, list_id: str) -> list[dict]:
    """Fetch all cards in a Trello list.

    Returns the raw JSON array from GET /lists/{list_id}/cards.
    Fields requested: id, name, due, desc (enough for sync + desc parsing).
    """
    params = {**_auth_params(), "fields": "id,name,due,desc"}
    resp = get_with_retry(client, f"/lists/{list_id}/cards", params)
    return resp.json()


def list_marker_pipedrive_ids(client: httpx.Client, list_id: str) -> set[int]:
    """Return the set of pipedrive_ids already present as [seg:deal_id=N]
    markers in the live cards of a Trello list.

    This is the SECOND idempotency check (live Trello) that complements the
    local trello_cards registry — it prevents duplicates even if the local
    registry lost the link.
    """
    ids: set[int] = set()
    for card in get_list_cards(client, list_id):
        pid = _extract_deal_id_from_desc(card.get("desc"))
        if pid is not None:
            ids.add(pid)
    return ids


def create_card(
    client: httpx.Client,
    list_id: str,
    name: str,
    desc: str = "",
    due: str | None = None,
) -> dict:
    """Create ONE Trello card in a whitelisted list (Fase 10 / Módulo 4).

    ALCANCE ESTRICTO: crear cards nuevas SOLO en allowed_create_list_ids().
    Nunca mover/editar/archivar/borrar cards. Cualquier list_id fuera de la
    whitelist FALLA con ValueError (no fallback). Pipedrive/Sheets siguen
    read-only.
    """
    # Guard (a) — list-ID whitelist. UNCONDITIONAL and FIRST: a card can never be
    # created outside allowed_create_list_ids(), regardless of any flag.
    if list_id not in allowed_create_list_ids():
        raise ValueError(
            f"Trello list {list_id!r} is not in the auto-create whitelist "
            f"{sorted(allowed_create_list_ids())}. Refusing to create card."
        )
    # Guard (b) — master kill switch, enforced HERE too (defense in depth), not
    # only in the reconciliation caller. It is impossible to reach the POST below
    # with the flag off, even via a direct create_card() call.
    if not settings.TRELLO_AUTO_CREATE_ENABLED:
        raise RuntimeError(
            "create_card() called while TRELLO_AUTO_CREATE_ENABLED is False. "
            "Auto-create is the ONLY authorized external write and it is disabled."
        )
    body: dict[str, str] = {"idList": list_id, "name": name, "desc": desc, "pos": "top"}
    if due:
        body["due"] = due
    resp = client.post("/cards", params=_auth_params(), json=body)
    resp.raise_for_status()
    return resp.json()
