from fastapi.testclient import TestClient

from stock_agent.api.app import app, create_app
from stock_agent.settings import Settings


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_dependency_readiness_fails_closed() -> None:
    client = TestClient(create_app(Settings(), lambda: (False, "database_unavailable")))
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database_unavailable"}
    assert client.get("/health/live").json() == {"status": "live"}


def test_version_endpoint_is_authenticated_and_secret_safe() -> None:
    configured = Settings(dev_test_token="test-token", git_sha="abc123")  # noqa: S106
    client = TestClient(create_app(configured))
    assert client.get("/api/version").status_code == 401
    response = client.get(
        "/api/version", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "git_commit": "abc123",
        "release_version": "release-v1",
        "policy_version": 1,
        "workflow_version": "workflow-v1",
        "schema_version": "contracts-v1",
    }
