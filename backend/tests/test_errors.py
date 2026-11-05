from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import Conflict, TooManyRequests, register_error_handlers

app = FastAPI()
register_error_handlers(app)


@app.get("/conflict")
async def conflict() -> None:
    raise Conflict("Email is already registered")


@app.get("/limited")
async def limited() -> None:
    raise TooManyRequests(retry_after=30)


client = TestClient(app)


def test_domain_error_gives_its_status_and_detail() -> None:
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


def test_too_many_requests_sets_retry_after() -> None:
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert response.json() == {"detail": "Too many attempts. Try again later."}
