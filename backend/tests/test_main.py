"""Tests for the main API application."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_http_200() -> None:
    """The health endpoint should return a successful HTTP status."""
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_ok_status() -> None:
    """The health endpoint should return the expected status payload."""
    response = client.get("/health")

    assert response.json() == {"status": "ok"}
