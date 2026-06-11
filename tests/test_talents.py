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
