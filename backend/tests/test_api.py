import json

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


def test_conversation_response_stream_is_incremental_and_persisted():
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": "U001", "access_code": "demo"})
        conversation = client.post("/api/conversations", json={}).json()
        with client.stream(
            "POST",
            f"/api/conversations/{conversation['id']}/messages/stream",
            json={"request_id": "test-stream-request", "text": "What is my total portfolio value?"},
        ) as response:
            events = [json.loads(line) for line in response.iter_lines() if line]
        assert response.status_code == 200
        assert events[0]["type"] == "status"
        assert any(event["type"] == "delta" for event in events)
        completed = events[-1]
        assert completed["type"] == "done"
        assert "₹29.70 Cr" in completed["message"]["text"]
        stored = client.get(f"/api/conversations/{conversation['id']}").json()["messages"]
        assert stored[-1]["text"] == completed["message"]["text"]


def test_conversation_delete_is_owner_scoped():
    with TestClient(app) as client:
        client.post("/api/session", json={"user_id": "U001", "access_code": "demo"})
        conversation = client.post("/api/conversations", json={}).json()
        client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"request_id": "delete-test-message", "text": "Hello"},
        )
        client.post("/api/session", json={"user_id": "U002", "access_code": "demo"})
        foreign_delete = client.delete(f"/api/conversations/{conversation['id']}")
        assert foreign_delete.status_code == 404
        client.post("/api/session", json={"user_id": "U001", "access_code": "demo"})
        assert client.delete(f"/api/conversations/{conversation['id']}").status_code == 204
        assert client.get(f"/api/conversations/{conversation['id']}").status_code == 404
