def test_health_no_auth(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "database" in body


def test_health_db_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "ok"
