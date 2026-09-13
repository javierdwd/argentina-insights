"""HTTP /api/data bridge — catalog gate, no LLM."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agent.app import app

client = TestClient(app)


def test_api_data_rejects_unknown_path():
    response = client.get("/api/data", params={"path": "/v1/does-not-exist"})
    assert response.status_code == 404
    assert "not in catalog" in response.json()["detail"].lower()


def test_api_data_requires_path():
    response = client.get("/api/data")
    assert response.status_code == 422


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
