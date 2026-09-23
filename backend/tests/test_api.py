from fastapi.testclient import TestClient

from app.main import app


def test_health_and_demo_session():
    with TestClient(app) as client:
        assert client.get("/health/ready").json()["database"] == "ok"
        users = client.get("/api/demo/users").json()["items"]
        assert len(users) == 4
        response = client.post("/api/session", json={"user_id": "U001", "access_code": "demo"})
        assert response.status_code == 200
        portfolio = client.get("/api/portfolio").json()
        assert portfolio["summary"]["owned_value_inr"] == 297_000_000
        assert len(portfolio["properties"]) == 3


def test_conversation_and_grounded_summary():
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": "U001", "access_code": "demo"})
        conversation = client.post("/api/conversations", json={}).json()
        response = client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"request_id": "test-summary-request", "text": "What is my total portfolio value?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "₹29.70 Cr" in body["message"]["text"]
        assert body["message"]["cards"][0]["type"] == "summary"

