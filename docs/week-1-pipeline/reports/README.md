# Week 1 — task reports

Engineering evidence per task: what was built, the TDD proof, review findings, fix loops.
Written by the implementing agent, then checked by an independent reviewer before merge.

| Report | Issue | What it covers |
|---|---|---|
| [`task-1-scaffolding-ci.md`](task-1-scaffolding-ci.md) | #1 | Project skeleton, pytest/ruff, GitHub Actions CI |
| [`task-2-db-models-alembic.md`](task-2-db-models-alembic.md) *(reconstructed)* | #2 | DB models (`Ticket`/`Run`/`Span`/`KbDoc`), Alembic initial migration, `GET /tickets/{id}` |
| [`task-3-ticket-ingest.md`](task-3-ticket-ingest.md) *(reconstructed)* | #2 | Kaggle CSV ingest script — 11,922 English tickets loaded |
| [`task-4-tracing-layer.md`](task-4-tracing-layer.md) *(reconstructed)* | #3 | OTel-convention spans, run state machine, fail-closed cost cap |
| [`task-5-schemas-llm-client.md`](task-5-schemas-llm-client.md) *(reconstructed)* | #4 | Schemas + shared LLM client — origin of the project's SDK-reality rule |
| [`task-6-precheck-classify.md`](task-6-precheck-classify.md) *(reconstructed)* | #4 | Prompts + pre-check/classify pipeline stages |
| [`task-7-kb-retrieval.md`](task-7-kb-retrieval.md) | #5 | 15 KB docs, Voyage embeddings, pgvector retrieval (k=3) |
| [`task-8-act-loop.md`](task-8-act-loop.md) | #6 | Hand-written tool loop + the parallel-tool-call ordering fix |
| [`task-9-gate-cli-e2e-checkpoint.md`](task-9-gate-cli-e2e-checkpoint.md) | #7 | Confidence gate, runner, CLI, and the live end-to-end checkpoint |
| [`qa-hardening.md`](qa-hardening.md) | #28 | Post-merge audit: the "show your receipt" gate fix, fail-closed cost typing, gitleaks in CI |

**Reports 2–6 are reconstructions — an honest note.** The originals were lost: they lived in a
git-ignored scratch folder under generic `task-N-report.md` names, and Week 2's tasks —
numbered 1–7 — silently overwrote five of them (tasks 2, 3, 4, 5, 6). Nothing else was lost:
those tasks' decisions, findings, and evidence survived in the engineering ledger, their
**GitHub issue closeout comments** (#2, #3, #4), [`../STORY.md`](../STORY.md), and the commit
history, so the five reports above were rebuilt from that surviving evidence and are clearly
labeled as reconstructions at the top of each file. Where a fact couldn't be recovered from any
source, the report says so explicitly (`(not recovered)`) rather than guessing. The naming
convention was fixed afterwards (reports now live here, in the repo, named by week and topic,
never generic `task-N`) and this folder exists so the collision can't happen again.
