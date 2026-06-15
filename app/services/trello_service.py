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
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

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
