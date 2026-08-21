from fastapi.testclient import TestClient

from triagedesk.app import app


def test_health_returns_200_with_config_diagnostics():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # These two exist so a misconfigured deploy is diagnosable from outside.
    # CORS unset renders a console whose pages load but whose buttons silently
    # fail; an unset admin token 503s every review POST. Both were previously
    # invisible without shell access to the container.
    assert "cors_configured" in body
    assert "admin_token_configured" in body
    assert isinstance(body["cors_configured"], bool)
    assert isinstance(body["admin_token_configured"], bool)
