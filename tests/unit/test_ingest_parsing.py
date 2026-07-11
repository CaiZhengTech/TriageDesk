from scripts.ingest_tickets import row_to_ticket

EN_ROW = {
    "subject": "Cannot log in",
    "body": "Password reset link never arrives.",
    "type": "Incident",
    "queue": "Technical Support",
    "priority": "high",
    "language": "en",
}


def test_english_row_maps_to_ticket():
    t = row_to_ticket(EN_ROW)
    assert t is not None
    assert t.subject == "Cannot log in"
    assert t.queue == "Technical Support"
    assert t.ticket_type == "Incident"
    assert t.source == "kaggle"


def test_german_row_is_skipped():
    assert row_to_ticket({**EN_ROW, "language": "de"}) is None


def test_empty_body_is_skipped():
    assert row_to_ticket({**EN_ROW, "body": ""}) is None
