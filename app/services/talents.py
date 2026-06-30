"""Talent name resolution from informal Sheet values (fix/fase-8).

The leads Sheet stores `Talento_Mencionado` as informal short forms — first
names ("Mariana"), partials ("Don Silverio"), no-space ("Mamamecanic"), and
case/accent variants ("Navarretes show", "Deliberración") — plus a couple of
true aliases ("Doc Fitness" -> "Dr Fitness"). The original sync used an exact
`dict.get(name)` against `Talent.name`, so 501/819 leads silently fell to NULL.

resolve_talent_id_smart matches in ordered layers and reports which layer hit,
so the sync can log resolution health and surface unmatched values (instead of
silent NULLs). Kept here (service, not sync/jobs.py) so it is unit-testable.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Aliases that NO normalization or prefix rule can derive (Doc != Dr).
# Keys are already normalized (see normalize_talent_name); values are the exact
# canonical Talent.name. Keep this minimal — prefer prefix-matching over hand
# maintenance; only add genuinely non-derivable forms here.
TALENT_ALIASES: dict[str, str] = {
    "doc fitness": "Dr Fitness",
}


def normalize_talent_name(s: str | None) -> str:
    """Deaccent (NFKD + drop combining marks), casefold, collapse whitespace, strip.

    Returns "" for None/empty/whitespace-only input.
    """
    if not s:
        return ""
    decomposed = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_accents.casefold()).strip()


def resolve_talent_id_smart(
    raw_value: str | None,
    talent_map_normalized: dict[str, int],
    alias_map: dict[str, str],
    canonical_names: list[str],
) -> tuple[int | None, str]:
    """Resolve an informal Sheet talent value to a talent_id via ordered layers.

    Returns (talent_id, match_layer) where match_layer is one of:
    'exact', 'no_spaces', 'prefix', 'alias', 'miss'.

    Args:
      raw_value: the raw Sheet `Talento_Mencionado` cell.
      talent_map_normalized: {normalize_talent_name(name): talent_id}.
      alias_map: {normalized_informal_name: canonical Talent.name}.
      canonical_names: list of raw Talent.name values (for prefix matching).
    """
    normalized_input = normalize_talent_name(raw_value)
    if not normalized_input:
        # Empty/whitespace = legitimate "Sin talento asignado" bucket — no warning.
        return None, "miss"

    # Layer 2 — exact (normalized): "navarretes show", "deliberración".
    if normalized_input in talent_map_normalized:
        return talent_map_normalized[normalized_input], "exact"

    # Layer 3 — no spaces: "Mamamecanic" -> "Mama mecanic".
    input_nospace = normalized_input.replace(" ", "")
    nospace_map = {key.replace(" ", ""): tid for key, tid in talent_map_normalized.items()}
    if input_nospace in nospace_map:
        return nospace_map[input_nospace], "no_spaces"

    # Layer 4 — word-prefix with a uniqueness guard: "Mariana" -> "Mariana Sanchez".
    input_words = normalized_input.split()
    matches = [
        name
        for name in canonical_names
        if normalize_talent_name(name).split()[: len(input_words)] == input_words
    ]
    if len(matches) == 1:
        return talent_map_normalized[normalize_talent_name(matches[0])], "prefix"
    if len(matches) > 1:
        logger.warning("talent_ambiguous: raw=%r candidates=%r", raw_value, matches)
        return None, "miss"

    # Layer 5 — explicit alias map (minimal): "Doc Fitness" -> "Dr Fitness".
    if normalized_input in alias_map:
        canonical = alias_map[normalized_input]
        tid = talent_map_normalized.get(normalize_talent_name(canonical))
        if tid is not None:
            return tid, "alias"

    # Layer 6 — miss: surface the unmatched value so new short forms get noticed.
    logger.warning(
        "talent_not_resolved: raw=%r normalized=%r", raw_value, normalized_input
    )
    return None, "miss"
