from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_served() -> None:
    assert client.get("/api/openapi.json").status_code == 200


def test_swagger_page_is_left_to_nginx() -> None:
    assert client.get("/docs").status_code == 404
