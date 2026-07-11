from fastapi.testclient import TestClient

from tests.conftest import integration
from triagedesk.app import app
from triagedesk.db import get_db
from triagedesk.models import Ticket


@integration
def test_ticket_roundtrips_through_api(test_db):
    ticket = Ticket(
        subject="My VPN keeps disconnecting",
        body="Client demo at 3pm and my VPN drops every few minutes.",
        queue="IT Support",
        language="en",
        source="demo",
    )
    test_db.add(ticket)
    test_db.commit()

    def _override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        resp = client.get(f"/tickets/{ticket.id}")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"] == "My VPN keeps disconnecting"
    assert body["queue"] == "IT Support"
