"""The bootstrap sequence's ORDER is the thing worth testing (issue #64).

Each individual step already has its own tests. What bootstrap adds is a claim
about ordering, and a wrong order fails in confusing ways rather than loudly:
seeding the golden set before ingest silently references ticket ids that don't
exist yet, and embedding the KB before migrations fails on a missing pgvector
extension.
"""

from scripts.bootstrap import STEPS


def _index_of(name: str) -> int:
    for i, (step_name, _, _) in enumerate(STEPS):
        if step_name == name:
            return i
    raise AssertionError(f"no bootstrap step named {name!r}")


def test_every_step_is_well_formed():
    for name, cmd, why in STEPS:
        assert name and why, name
        assert len(cmd) >= 2, name


def test_migrations_run_first():
    # Nothing can be written before the tables and the pgvector extension exist.
    assert _index_of("migrations") == 0


def test_ingest_precedes_everything_that_references_a_ticket_id():
    # Kaggle tickets take auto-increment ids 1..11922. golden_expectations.json
    # names ids in that range, so ingest has to have happened first.
    ingest = _index_of("kaggle tickets")
    assert ingest < _index_of("golden set")
    assert ingest < _index_of("calibration pool")
    assert ingest < _index_of("demo pool")


def test_kb_embeddings_precede_no_seeding_but_follow_migrations():
    # kb_docs.embedding is a pgvector column; the extension arrives with the
    # migrations, so this only has an ordering constraint on that one step.
    assert _index_of("migrations") < _index_of("kb embeddings")


def test_calibration_pool_is_seed_only():
    # The calibration pool's default mode runs the pipeline AND the judge live,
    # which is ~$0.90 of real API spend. Bootstrap must never trigger that
    # implicitly — a rebuild is a $0 operation apart from KB embeddings.
    _, cmd, _ = STEPS[_index_of("calibration pool")]
    assert "--seed-only" in cmd


def test_no_step_is_destructive_by_default():
    # --reset-history flags delete runs, spans, and eval_results. A bootstrap
    # aimed at an empty database never needs them, and a bootstrap aimed by
    # accident at a populated one must not quietly wipe it.
    for name, cmd, _ in STEPS:
        assert "--reset-history" not in cmd, name
        assert "--force" not in cmd, name
