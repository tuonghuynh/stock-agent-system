from fastapi.testclient import TestClient

from stock_agent.api.app import app


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json() == {"status": "ready"}
