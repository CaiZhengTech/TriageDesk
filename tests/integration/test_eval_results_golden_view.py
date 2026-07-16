"""Migration round-trip test for the eval_results_golden view (Hardening
Task 2, issue #45, revision b2a3edf4a55a). Runs Alembic upgrade/downgrade
against the shared TEST_DATABASE_URL branch, gated behind the same skipif as
every other Neon-backed integration test -- DDL only (CREATE/DROP VIEW), no
Anthropic/Voyage calls."""
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from tests.conftest import integration
from triagedesk.config import settings

_VIEW_PARENT_REVISION = "868d4d9166da"  # the revision immediately before this one


def _view_exists(test_db) -> bool:
    return test_db.execute(
        text("SELECT to_regclass('eval_results_golden') IS NOT NULL")
    ).scalar_one()


@integration
def test_eval_results_golden_view_upgrade_downgrade_round_trips(test_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", settings.test_database_url)
    cfg = Config("alembic.ini")

    # test_db's own transaction must be ended after each DDL change made
    # through alembic's separate connection, or the session's existing
    # transaction snapshot won't see it (each check re-establishes a fresh
    # snapshot via commit() -- there's nothing pending to commit, this is
    # purely to close out the transaction).
    command.upgrade(cfg, "head")  # bring the branch to head (idempotent if already there)
    test_db.commit()
    assert _view_exists(test_db) is True

    command.downgrade(cfg, _VIEW_PARENT_REVISION)
    test_db.commit()
    assert _view_exists(test_db) is False

    command.upgrade(cfg, "head")  # restore head so other integration tests aren't affected
    test_db.commit()
    assert _view_exists(test_db) is True
