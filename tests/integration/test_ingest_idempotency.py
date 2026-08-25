"""Ingesting twice must not silently corrupt the ticket-id space (#61).

Ticket ids are auto-increment, so they encode INSERTION ORDER, and
golden_expectations.json names tickets by id. A second ingest pass appends a
whole second copy at ids 11923+; anything that then samples source='kaggle' --
scripts/build_calibration_pool.py in particular -- draws from a pool that is
half phantoms.

This is not hypothetical. Seeding the eval branch hit it: bootstrap failed at
the KB-embedding step, was re-run with --force, and 14 of 25 calibration cases
ended up pointing at duplicate rows. The golden 20 survived only because their
ids were already committed to a file.
"""

import pytest
from sqlalchemy import func, select

from tests.conftest import integration
from triagedesk.models import Ticket


def _kaggle_count(session) -> int:
    return session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.source == "kaggle")
    )


@integration
def test_second_ingest_is_refused(test_db, monkeypatch, tmp_path):
    """The guard: with kaggle tickets already present, ingest exits non-zero and
    leaves the table untouched."""
    import scripts.ingest_tickets as ingest

    test_db.add(Ticket(subject="s", body="b", queue="IT Support",
                       language="en", source="kaggle"))
    test_db.commit()
    before = _kaggle_count(test_db)

    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "subject,body,queue,type,priority,language\n"
        "new,new body,IT Support,Incident,low,en\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["ingest", "--csv", str(csv_path)])
    monkeypatch.setattr(ingest, "SessionLocal", lambda: test_db)

    with pytest.raises(SystemExit) as exc:
        ingest.main()
    assert exc.value.code == 1
    assert _kaggle_count(test_db) == before, "refused run must not insert"


@integration
def test_reingest_flag_overrides_the_guard(test_db, monkeypatch, tmp_path):
    """The escape hatch still works -- the guard is a speed bump against the
    accidental case, not a lock."""
    import scripts.ingest_tickets as ingest

    test_db.add(Ticket(subject="s", body="b", queue="IT Support",
                       language="en", source="kaggle"))
    test_db.commit()
    before = _kaggle_count(test_db)

    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "subject,body,queue,type,priority,language\n"
        "new,new body,IT Support,Incident,low,en\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["ingest", "--csv", str(csv_path), "--reingest"])
    monkeypatch.setattr(ingest, "SessionLocal", lambda: test_db)

    ingest.main()
    assert _kaggle_count(test_db) == before + 1


@integration
def test_first_ingest_into_an_empty_table_works(test_db, monkeypatch, tmp_path):
    """The guard must not break the case bootstrap actually needs."""
    import scripts.ingest_tickets as ingest

    assert _kaggle_count(test_db) == 0
    csv_path = tmp_path / "t.csv"
    csv_path.write_text(
        "subject,body,queue,type,priority,language\n"
        "a,body a,IT Support,Incident,low,en\n"
        "b,body b,Billing and Payments,Request,high,en\n"
        "c,body c,IT Support,Incident,low,de\n",  # non-English: filtered out
        encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["ingest", "--csv", str(csv_path)])
    monkeypatch.setattr(ingest, "SessionLocal", lambda: test_db)

    ingest.main()
    assert _kaggle_count(test_db) == 2
