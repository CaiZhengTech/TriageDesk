# Week 1 — task reports

Engineering evidence per task: what was built, the TDD proof, review findings, fix loops.
Written by the implementing agent, then checked by an independent reviewer before merge.

| Report | Issue | What it covers |
|---|---|---|
| [`task-1-scaffolding-ci.md`](task-1-scaffolding-ci.md) | #1 | Project skeleton, pytest/ruff, GitHub Actions CI |
| [`task-7-kb-retrieval.md`](task-7-kb-retrieval.md) | #5 | 15 KB docs, Voyage embeddings, pgvector retrieval (k=3) |
| [`task-8-act-loop.md`](task-8-act-loop.md) | #6 | Hand-written tool loop + the parallel-tool-call ordering fix |
| [`task-9-gate-cli-e2e-checkpoint.md`](task-9-gate-cli-e2e-checkpoint.md) | #7 | Confidence gate, runner, CLI, and the live end-to-end checkpoint |
| [`qa-hardening.md`](qa-hardening.md) | #28 | Post-merge audit: the "show your receipt" gate fix, fail-closed cost typing, gitleaks in CI |

**Missing reports (2–6) — an honest note.** The reports for Week 1 tasks 2–6 (DB + ingest,
tracing, schemas + LLM client, precheck/classify) were lost: they lived in a git-ignored
scratch folder under generic `task-N-report.md` names, and Week 2's tasks — numbered 1–7 —
silently overwrote them. Nothing else was lost: those tasks' decisions, findings, and
evidence survive in their **GitHub issue closeout comments** (#2, #3, #4), in
[`../STORY.md`](../STORY.md), and in the commit history. The naming convention was fixed
afterwards (reports now live here, in the repo, named by week and topic) and this folder
exists so it can't happen again.
