from app.scripts.seed_talents import TALENT_NAMES, seed_talents
from tests.conftest import TestSessionLocal


def test_talents_require_auth(client):
    response = client.get("/talents")

    assert response.status_code == 401


def test_create_talent(auth_client):
    response = auth_client.post(
        "/talents",
        json={"name": "Test Talent", "active": True},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Test Talent"
    assert "id" in body

    list_response = auth_client.get("/talents")
    assert list_response.status_code == 200
    names = [t["name"] for t in list_response.json()]
    assert "Test Talent" in names


def test_update_talent(auth_client):
    create_response = auth_client.post(
        "/talents",
        json={"name": "Update Me", "active": True, "category": "Original"},
    )
    assert create_response.status_code == 201
    talent_id = create_response.json()["id"]

    patch_response = auth_client.patch(
        f"/talents/{talent_id}",
        json={"category": "Updated"},
    )

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["category"] == "Updated"
    # Fields not provided in the PATCH must remain unchanged.
    assert body["name"] == "Update Me"
    assert body["active"] is True


def test_add_talent_product(auth_client):
    create_response = auth_client.post(
        "/talents",
        json={"name": "Product Talent", "active": True},
    )
    assert create_response.status_code == 201
    talent_id = create_response.json()["id"]

    add_response = auth_client.post(
        f"/talents/{talent_id}/products",
        json={"pipedrive_product_id": 12345},
    )

    assert add_response.status_code == 201
    product_body = add_response.json()
    assert product_body["pipedrive_product_id"] == 12345
    assert "id" in product_body

    list_response = auth_client.get(f"/talents/{talent_id}/products")
    assert list_response.status_code == 200
    products = list_response.json()
    assert any(p["pipedrive_product_id"] == 12345 for p in products)


def test_seeded_talents_present(auth_client):
    seed_talents(session_factory=TestSessionLocal)

    response = auth_client.get("/talents")
    assert response.status_code == 200
    talents = response.json()

    assert len(talents) >= len(TALENT_NAMES)
    names = {t["name"] for t in talents}
    assert "Navarretes Show" in names
    assert "Casandra Salinas" in names

    count_after_first_seed = len(talents)

    # Idempotency: re-running the seed must not create duplicates.
    seed_talents(session_factory=TestSessionLocal)

    response_again = auth_client.get("/talents")
    assert response_again.status_code == 200
    assert len(response_again.json()) == count_after_first_seed


def test_don_silverio_wicho_is_single_merged_talent():
    """5.2: Don Silverio y Don Wicho is one merged entry, never two separate
    talents (Luis, 25-jun)."""
    from app.scripts.match_talent_products import MANUAL_PRODUCT_MATCHES

    assert "Don Silverio y Don Wicho" in TALENT_NAMES
    assert "Don Silverio" not in TALENT_NAMES
    assert "Don Wicho" not in TALENT_NAMES

    # The merged talent maps to the single shared Pipedrive product.
    assert MANUAL_PRODUCT_MATCHES == {"Don Silverio y Don Wicho": "Don Silverio y Don Wicho"}


# ---------------------------------------------------------------------------
# fix(fase-8) — resolve_talent_id_smart: layered Sheet→talent matching
# ---------------------------------------------------------------------------

import logging
import pytest


def _maps(pairs):
    """Build (talent_map_normalized, canonical_names) from [(name, id), ...]."""
    from app.services.talents import normalize_talent_name
    tmn = {normalize_talent_name(n): i for n, i in pairs}
    names = [n for n, i in pairs]
    return tmn, names


# The real canonical names that the 8 failing Sheet values must resolve to.
_REAL_TALENTS = [
    ("Emicanico", 1),
    ("Navarretes Show", 2),
    ("Deliberracion", 3),
    ("Mama mecanic", 4),
    ("Mariana Sanchez", 5),
    ("Don Silverio y Don Wicho", 6),
    ("Dr Fitness", 7),
    ("Edgar Cardenas", 8),
    ("Ale Voale", 9),
]


def _resolve(raw, pairs=_REAL_TALENTS):
    from app.services.talents import resolve_talent_id_smart, TALENT_ALIASES
    tmn, names = _maps(pairs)
    return resolve_talent_id_smart(raw, tmn, TALENT_ALIASES, names)


def test_resolve_exact_match():
    assert _resolve("Emicanico") == (1, "exact")


def test_resolve_case_insensitive():
    assert _resolve("navarretes show") == (2, "exact")


def test_resolve_deaccent():
    assert _resolve("Deliberración") == (3, "exact")


def test_resolve_no_spaces():
    assert _resolve("Mamamecanic") == (4, "no_spaces")


def test_resolve_prefix_partial():
    assert _resolve("Mariana") == (5, "prefix")


def test_resolve_prefix_two_words():
    assert _resolve("Don Silverio") == (6, "prefix")


def test_resolve_prefix_ambiguous_returns_miss_with_warning(caplog):
    pairs = [("Mariana Sanchez", 5), ("Mariana Lopez", 50)]
    from app.services.talents import resolve_talent_id_smart, TALENT_ALIASES
    tmn, names = _maps(pairs)
    with caplog.at_level(logging.WARNING):
        result = resolve_talent_id_smart("Mariana", tmn, TALENT_ALIASES, names)
    assert result == (None, "miss")
    assert any("ambiguous" in r.message.lower() or "ambiguous" in r.getMessage().lower()
               for r in caplog.records)


def test_resolve_alias_doc_fitness():
    assert _resolve("Doc Fitness") == (7, "alias")


def test_resolve_miss_logs_warning(caplog):
    with caplog.at_level(logging.WARNING):
        result = _resolve("Random Talento Inventado")
    assert result == (None, "miss")
    assert any("not_resolved" in r.getMessage() for r in caplog.records)


def test_resolve_empty_returns_miss_without_warning(caplog):
    with caplog.at_level(logging.WARNING):
        assert _resolve("") == (None, "miss")
        assert _resolve(None) == (None, "miss")
    # empty input is the legitimate "Sin talento" bucket — must NOT spam warnings
    assert len(caplog.records) == 0


def test_resolve_whitespace_only_returns_miss():
    assert _resolve("   ") == (None, "miss")
