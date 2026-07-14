"""Trello card linkage helpers and collection-date resolution (Phase 4).

Provides:
  - _normalize: unicode-safe lowercase normalization for fuzzy matching
  - _brand_prefix: extract leading brand segment from card name
  - _extract_deal_id_from_desc: parse [seg:deal_id=N] from card description
  - fuzzy_match_deal: SequenceMatcher-based deal title matching (threshold 0.70)
  - resolve_collection_date: fallback chain (due date → add_time+2mo → today)
  - resolve_deal_id: two-step lookup (desc parse first, then fuzzy match)

Security (T-04-04): _extract_deal_id_from_desc accepts ONLY digits via the
bracket pattern. Non-numeric text yields None and never reaches integer lookup.
"""
import calendar
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from app.models import Deal, TrelloCard  # noqa: F401 (TrelloCard imported for type hints)

# Regex that matches the exact deal-id header written by the auto-create job.
# Only all-digit values are captured (T-04-04 — no injection surface).
_DEAL_ID_RE = re.compile(r"\[seg:deal_id=(\d+)\]")


def _normalize(s: str) -> str:
    """NFKD-normalize → ASCII → lowercase → strip whitespace."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    return ascii_str.lower().strip()


def _brand_prefix(card_name: str) -> str:
    """Return the normalized leading brand segment from a card name.

    Splits on ' - ' (hyphen-space) or ' x ' (x-space), takes the first segment.
    Example: 'Nike - Campaña Verano' → 'nike'
             'Adidas x Talento Uno'  → 'adidas'
    """
    name = card_name
    for sep in (" - ", " x "):
        if sep in name:
            name = name.split(sep)[0]
            break
    return _normalize(name)


def _extract_deal_id_from_desc(desc: str | None) -> int | None:
    """Parse [seg:deal_id=N] from a card description, returning N as int or None.

    Security (T-04-04): only digit sequences match — no eval, no injection.
    """
    if not desc:
        return None
    m = _DEAL_ID_RE.search(desc)
    if m is None:
        return None
    return int(m.group(1))


def fuzzy_match_deal(card_name: str, deals: list[Deal]) -> Deal | None:
    """Return the Deal whose title best fuzzy-matches card_name, or None.

    Uses SequenceMatcher ratio on normalized titles.
    The brand-prefix fast path filters candidates where the card's brand prefix
    appears as a substring of the normalized deal title.
    Returns the best match only when best_ratio >= 0.70.
    """
    prefix = _brand_prefix(card_name)
    norm_card = _normalize(card_name)

    best_deal: Deal | None = None
    best_ratio: float = 0.0

    for deal in deals:
        norm_title = _normalize(deal.title)
        # Fast-path: skip if brand prefix is not a substring of the deal title.
        # (Only applied when a meaningful prefix was extracted — i.e., different from full name.)
        if prefix and prefix != norm_card and prefix not in norm_title:
            continue
        ratio = SequenceMatcher(None, norm_card, norm_title).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_deal = deal

    if best_ratio >= 0.70:
        return best_deal
    return None


def resolve_collection_date(card_due: str | None, deal: Deal | None) -> date:
    """Resolve a collection_date for a TrelloCard using the fallback chain.

    Priority:
    1. Trello card due date (ISO 8601, first 10 chars = YYYY-MM-DD).
    2. Linked Deal.add_time month + 2 months → first-of-that-month.
    3. Today's first-of-month.

    Description-month parsing is OUT OF SCOPE (post-MVP, per RESEARCH.md).
    """
    # 1. Card due date present.
    if card_due:
        return date.fromisoformat(card_due[:10])

    # 2. Linked deal add_time + 2 months.
    if deal is not None and deal.add_time:
        try:
            add_date = date.fromisoformat(deal.add_time[:10])
            # Advance by 2 months using divmod to handle month overflow.
            total_months = add_date.month + 2
            year_offset, month = divmod(total_months - 1, 12)
            month += 1  # divmod yields 0-based month index
            new_year = add_date.year + year_offset
            return date(new_year, month, 1)
        except (ValueError, TypeError):
            pass

    # 3. Today's first-of-month.
    today = date.today()
    return date(today.year, today.month, 1)


def _make_card_desc(pipedrive_deal_id: int, extra_desc: str = "") -> str:
    """Build a Trello card description with a [seg:deal_id=N] header.

    The marker format matches _DEAL_ID_RE so that _extract_deal_id_from_desc
    can round-trip the deal id (T-04-08 — only numeric deal_id in the marker,
    no untrusted content injected into the header line).

    Args:
        pipedrive_deal_id: The Pipedrive deal ID (integer) to embed.
        extra_desc: Optional additional text appended after a blank line.

    Returns:
        "[seg:deal_id=N]" if extra_desc is empty, or
        "[seg:deal_id=N]\n\nextra_desc" when extra_desc is non-empty.
    """
    header = f"[seg:deal_id={pipedrive_deal_id}]"
    if extra_desc:
        return f"{header}\n\n{extra_desc}"
    return header


def build_auto_card_desc(deal, talent_name: str | None, pipedrive_domain: str) -> str:
    """Build the auto-created card description: marker + monto + talento + link.

    The [seg:deal_id=N] marker is FIRST (round-trips via _extract_deal_id_from_desc
    for idempotency). No untrusted content goes inside the marker line.
    """
    monto = f"{int(deal.value or 0):,} {deal.currency or 'MXN'}"
    talento = talent_name or "Sin talento asignado"
    link = f"https://{pipedrive_domain}.pipedrive.com/deal/{deal.pipedrive_id}"
    body = "\n".join([
        f"Monto: {monto}",
        f"Talento: {talento}",
        f"Deal en Pipedrive: {link}",
        "",
        "— Tarjeta creada automáticamente por SEG Dashboard —",
    ])
    return _make_card_desc(deal.pipedrive_id, extra_desc=body)


def _month_label(d: date) -> str:
    """Return a 'Mon YYYY' label for a date, e.g. 'Jun 2026'.

    Uses calendar.month_abbr (English 3-letter abbreviation) to match
    the frontend format contract (Pitfall 3 — English abbr, not locale-dependent).
    """
    return f"{calendar.month_abbr[d.month]} {d.year}"


def _sliding_window_months(anchor: date) -> list[date]:
    """Return the four first-of-month dates for the 4-month sliding window.

    Window: [anchor - 1 month, anchor, anchor + 1 month, anchor + 2 months].
    Uses divmod month arithmetic to handle year overflow correctly.

    Args:
        anchor: The reference date (today or a test date).

    Returns:
        List of 4 date objects, each set to the 1st of the respective month.
    """
    result: list[date] = []
    for delta in (0, 1, 2, 3):
        total_months = anchor.month + delta
        year_offset, month_0based = divmod(total_months - 1, 12)
        month = month_0based + 1
        year = anchor.year + year_offset
        result.append(date(year, month, 1))
    return result


def income_projection(db: Session, talent_id: int) -> list[dict[str, Any]]:
    """Return 4-month sliding revenue projection for a talent.

    Each entry: {month: str, cobrado: float, proyeccion: float, pendiente: float}
    where:
      - cobrado     = sum of deal.value for cards with list_state='cerrado'
      - proyeccion  = sum of deal.value for cards with list_state='ejecucion'
      - pendiente   = sum of deal.value for cards with list_state='cobranza'

    Cards are grouped by their resolved collection_date month. Cards whose
    resolved month falls outside the 4-month window are excluded.

    Month labels use English 3-letter abbreviation + year (e.g. 'Jun 2026').
    Amount is deal.value (venta_total per D-47, NOT 70% commission).

    Security: talent_id is an int coerced by FastAPI at the router boundary.
    """
    anchor = date.today()
    window = _sliding_window_months(anchor)
    window_labels = [_month_label(d) for d in window]

    # Build result dict keyed by label (preserves insertion order in Python 3.7+)
    current_label = window_labels[0]
    result: dict[str, dict[str, Any]] = {
        label: {"month": label, "cobrado": 0.0, "proyeccion": 0.0, "pendiente": 0.0,
                "is_current": label == current_label}
        for label in window_labels
    }

    # Query TrelloCard JOIN Deal, filtered by talent
    rows = (
        db.query(TrelloCard, Deal)
        .join(Deal, TrelloCard.deal_id == Deal.id)
        .filter(Deal.talent_id == talent_id)
        .all()
    )

    for card, deal in rows:
        # Resolve collection month for this card
        resolved_date = card.collection_date or resolve_collection_date(None, deal)
        first_of_month = date(resolved_date.year, resolved_date.month, 1)
        label = _month_label(first_of_month)

        if label not in result:
            continue  # Outside the 4-month window — excluded

        value = deal.value or 0.0
        state = card.list_state
        if state == "cerrado":
            result[label]["cobrado"] += value
        elif state == "ejecucion":
            result[label]["proyeccion"] += value
        elif state == "cobranza":
            result[label]["pendiente"] += value

    return list(result.values())


def payment_calendar(db: Session, talent_id: int) -> list[dict[str, Any]]:
    """Return 4-month payment calendar for a talent.

    Each entry: {month: str, amount: float} where amount is the total expected
    collection for that month (cobrado + proyeccion + pendiente per UI-SPEC).

    Returns the same 4-month window as income_projection.
    """
    proj = income_projection(db, talent_id)
    return [
        {
            "month": entry["month"],
            "amount": entry["cobrado"] + entry["proyeccion"] + entry["pendiente"],
        }
        for entry in proj
    ]


def deals_for_talent(db: Session, talent_id: int) -> list[dict[str, Any]]:
    """Return individual deal rows for a talent, sorted by amount descending.

    Each entry: {title: str, amount: float, list_state: str, trello_card_id: str|None}

    - Active deals linked via TrelloCard use the card's list_state
      (ejecucion/cobranza/cerrado).
    - Lost deals (status='lost', no TrelloCard) are included as list_state='perdido'.
    - Deals with no Trello card and not lost are included as list_state='ejecucion'
      (default — they are known deals in the pipeline).

    Sorted by amount descending so the frontend top-3 slice works correctly.

    Security (T-04-12): returns only scalar values; no raw ORM objects exposed.
    """
    rows: list[dict[str, Any]] = []

    # 1. Deals linked to TrelloCards (ejecucion/cobranza/cerrado)
    linked = (
        db.query(TrelloCard, Deal)
        .join(Deal, TrelloCard.deal_id == Deal.id)
        .filter(Deal.talent_id == talent_id)
        .all()
    )
    linked_deal_ids: set[int] = set()
    for card, deal in linked:
        # Fase 9.8a: 'omitido' cards (Trello "Otros pendientes") are administrative
        # garbage, excluded from all talent-facing lists and aggregates.
        if card.list_state == "omitido":
            linked_deal_ids.add(deal.id)  # still mark linked so it's not re-added below
            continue
        linked_deal_ids.add(deal.id)
        rows.append({
            "title": deal.title,
            "amount": deal.value or 0.0,
            "list_state": card.list_state,
            "trello_card_id": card.trello_card_id,
            "stage_name": deal.stage_name,
        })

    # 2. All deals for the talent — add unlinked ones
    all_deals = db.query(Deal).filter(Deal.talent_id == talent_id).all()
    for deal in all_deals:
        if deal.id in linked_deal_ids:
            continue
        # Lost deals show as perdido; others default to their pipeline state
        list_state = "perdido" if deal.status == "lost" else "ejecucion"
        rows.append({
            "title": deal.title,
            "amount": deal.value or 0.0,
            "list_state": list_state,
            "trello_card_id": None,
            "stage_name": deal.stage_name,
        })

    # Sort by amount descending
    rows.sort(key=lambda r: r["amount"], reverse=True)
    return rows


def resolve_deal_id(db: Session, card_desc: str | None, card_name: str) -> int | None:
    """Resolve the local deals.id for a card using a two-step strategy.

    Step 1: parse [seg:deal_id=N] from card description → look up Deal.pipedrive_id == N.
    Step 2: fuzzy match card_name against all Deal.title values.

    Returns the local Deal.id (PK) or None if no match found.
    """
    # Step 1: description header parse.
    pipedrive_id = _extract_deal_id_from_desc(card_desc)
    if pipedrive_id is not None:
        deal = db.query(Deal).filter(Deal.pipedrive_id == pipedrive_id).first()
        if deal is not None:
            return deal.id

    # Step 2: fuzzy match against all deals.
    all_deals = db.query(Deal).all()
    matched = fuzzy_match_deal(card_name, all_deals)
    if matched is not None:
        return matched.id

    return None
