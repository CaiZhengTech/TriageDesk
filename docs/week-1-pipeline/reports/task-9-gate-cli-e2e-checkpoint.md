# Task 9 Report — Gate + runner + CLI + Week 1 E2E CHECKPOINT (issue #7)

**Status: COMPLETE — checkpoint GREEN.** Both live E2E scenarios passed. PR: https://github.com/CaiZhengTech/Agentic_Project/pull/27 (not merged; controller merges after checks).

## Commits (branch `feat/07-gate-cli`, from main b2fcfb0)

| SHA | Subject |
|---|---|
| 1d7f3a2 | feat: per-queue centroid embeddings for the gate's margin signal (#7) |
| 7126cfa | feat: confidence gate, adverse-action routing, runner, CLI trace dump (#7) |
| 3a7de3c | fix: two live E2E checkpoint findings (#7) |

## Implemented

1. **`scripts/compute_centroids.py`** — per brief, plus two operational adaptations forced by Voyage's free tier (3 RPM / 10K TPM, no payment method on file): sub-batches of 25 instead of 128 (a 100-ticket batch is ~10K tokens and trips the TPM cap in one request), 21s pacing between requests, and resumability (each finished queue is written to the JSON immediately and skipped on re-run — the full run takes ~15 min and survived a session interruption mid-flight). Ran once; output verified: 10 queue keys, all vectors 1024-dim, 227,002 bytes.
2. **`triagedesk/data/queue_centroids.json`** — committed as a generated code artifact. Required a `.gitignore` change: the pre-existing `data/` rule (for the Kaggle CSV) was also matching `triagedesk/data/`; added a scoped negation (`!triagedesk/data/`, `!triagedesk/data/**`). Verified both directions with `git check-ignore`.
3. **`triagedesk/pipeline/gate.py`** — verbatim per brief (SIM_THRESHOLD=0.45, MARGIN_THRESHOLD=0.02, `classification_margin`, `GateDecision`, `decide` with adverse-action-first ordering, `load_centroids` lru_cached). One deviation: `zip(..., strict=True)` in `_cosine` — the brief's snippet fails the repo's ruff B905 rule; strict=True matches `embed_kb.py`'s existing convention and is semantically correct (mismatched dims should blow up).
4. **`triagedesk/pipeline/runner.py`** — verbatim per brief. Full exception→outcome mapping: BudgetExceededError/CostUnknownError→escalated/budget_breach, RepairFailedError→escalated/validation_failed, LLMRefusalError→escalated/llm_refusal, ToolFailedError→escalated/tool_error, AgentIncompleteError→escalated/agent_incomplete, anthropic.APIError→failed/api_error:<type>. One state transition ever (finish_run enforces).
5. **`triagedesk/cli.py`** — per brief, plus `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (see finding 2 below).
6. **Live-checkpoint fixes in `triagedesk/llm.py`** (upstream file, minimal surgical fix — see finding 1 below).

## TDD evidence

- `tests/unit/test_gate.py`: 8 tests, verbatim from the brief. Red (module missing) → green after implementing gate.py. 8/8 pass.
- `tests/unit/test_runner.py`: 10 tests, fakes only (FakeSession, monkeypatched stages, pinned margin). Covers: precheck-unsafe short-circuit (asserts classify never runs), confident solve→completed, low similarity→low_confidence, deny→adverse_action, and all five exception mappings + anthropic.APIConnectionError→failed. 10/10 pass.
- `tests/unit/test_llm_repair.py::test_schema_objects_forbid_additional_properties`: written red first (KeyError), green after `_strict_schema` fix.
- **Full suite: 48 passed** (was 47; +8 gate, +10 runner, +1 llm schema, over the prior 29 unit + 2 integration... prior suite was 47 with my files at 18). `ruff check .` clean.
- **Zero live calls in any test** — gate/runner/CLI tests are pure fakes; the two integration tests hit only the Neon test branch.

## E2E CHECKPOINT (live, real APIs)

### Scenario 1 — Dana's VPN ticket (id 12027 → customer-3, Dana Fuentes, basic/active)

Inserted 3 filler tickets to land `id % 12 == 3` per the brief. Full CLI trace (verbatim):

```
run 441299f4-b831-4302-9264-936abe04f40e  ticket=12027  state=escalated  reason=adverse_action
model=claude-sonnet-4-6  prompt=w1-v1  cost=$0.0362  gate={'retrieval_similarity': 0.7242, 'classification_margin': -0.00865489118205165}

stage      status        ms  in_tok  out_tok      cost
precheck   ok          3612     522        8 $  0.0017
classify   ok          3087     413       17 $  0.0015
retrieve   ok           919       -        - $  0.0000
act        ok         25462    5715     1059 $  0.0330
gate       ok           246       -        - $  0.0000

--- final reply ---
Hi, I understand you have a critical demo at 3pm — let's get this sorted quickly. Your account is active, so here are the steps most likely to fix frequent VPN drops right away:

**Step 1 (most common fix): Enable "Reconnect on network change"**
Open the VPN client → Settings → Connection → enable **Reconnect on network change**. This resolves the majority of frequent-disconnect cases, especially if the drops coincide with waking from sleep or switching networks.

**Step 2: Enable Keepalive**
In Settings → Connection → **Keepalive**, make sure it's on (default 25s). This prevents routers from timing out the tunnel during brief idle moments.

**Step 3: Check your network**
- If you're on Wi-Fi, try a **wired (Ethernet) connection** if at all possible — this is the most reliable option before a demo.
- If you're on a corporate or public network (e.g., a client site or hotel), try reconnecting to the network fully (re-accept any portal terms) before reconnecting the VPN.

**Step 4: Switch to TCP Fallback mode**
If the above don't help, go to Settings → Connection and enable **TCP fallback**. Some networks block the default UDP port and this often resolves it immediately.

**Step 5: Check the status page**
Quickly verify there's no active VPN outage at **status.northbeamit.com** — if there's a known incident, it will be shown there.

Please try these steps in order and let us know if the issue persists. Good luck with the demo!

--- internal rationale (post-hoc context, not ground truth) ---
The customer is on an active Basic plan, which does not include priority VPN support (Pro/Enterprise only), so they remain in the standard queue. However, their issue — frequent VPN drops every few minutes — is directly addressed by the "Frequent disconnects" section of the VPN troubleshooting KB article. All steps provided are directly sourced from that article. No escalation is needed at this stage; if self-service steps fail, the customer can reopen with their VPN log attached.
```

**Checkpoint criteria met:** all 5 spans ok, terminal state (`escalated` — explicitly fine per the brief), cost $0.0362 << $0.10 cap. Why adverse_action on a solve: the act loop called `check_entitlement(priority_vpn_support)` for Dana's basic plan → covered=False → `entitlement_denied=True` → unconditional escalation, exactly per the adverse-action hardening in a324592. The gate's margin signal (−0.0087 < 0.02) would independently have escalated as low_confidence. The reply is held for review, not auto-sent.

### Scenario 2 — adverse action: Dana requests dedicated IP on basic plan (id 12039 → customer-3)

Next free id mapped to customer-4 (enterprise — dedicated_ip covered, which would defeat the scenario), so inserted 11 fillers to land customer-3 again — also preserves the standing "Dana adverse variant" example. Full CLI trace (verbatim):

```
run 745a67c6-ec7c-4331-9447-670f54fbd260  ticket=12039  state=escalated  reason=adverse_action
model=claude-sonnet-4-6  prompt=w1-v1  cost=$0.0313  gate={'retrieval_similarity': 0.4883, 'classification_margin': -0.008183729115242011}

stage      status        ms  in_tok  out_tok      cost
precheck   ok          4378     512        8 $  0.0017
classify   ok          2133     403       18 $  0.0015
retrieve   ok           857       -        - $  0.0000
act        ok         16450    6044      670 $  0.0282
gate       ok           283       -        - $  0.0000

--- final reply ---
Thank you for reaching out! Unfortunately, a dedicated IP is not included on your current Basic plan — it is an Enterprise-tier feature only.

Here's a quick summary of what's required:

- **Basic** – No dedicated IP
- **Pro** – No dedicated IP
- **Enterprise** – ✅ Dedicated IP included (static IP reserved for your account's VPN and API traffic)

To get a dedicated IP for your home office setup, you would need to upgrade to the Enterprise plan. Support agents are unable to enable this feature without an active Enterprise plan in place.

**Next steps:** Please contact our sales team or visit the plan upgrade page ("Upgrading or downgrading your plan") to discuss moving to Enterprise. Once your plan is upgraded, our team can provision your dedicated IP right away.

Let us know if you have any other questions!

--- internal rationale (post-hoc context, not ground truth) ---
Customer-3 is on an active Basic plan, which does not include the dedicated_ip feature. Per the plans-and-entitlements KB article, dedicated_ip is exclusively an Enterprise entitlement and cannot be granted by support without the appropriate plan. The request is denied and the customer is directed to sales/upgrade path to obtain Enterprise access.
```

**MUST-condition met:** ended `escalated / adverse_action` — never `completed`. The denial is routed to human review.

## Live-run count and spend

| Run | Ticket | Result | Cost |
|---|---|---|---|
| 1 | 12027 (Dana VPN) | failed at precheck — API 400 (schema bug, finding 1) | $0.0000 |
| 2 | 12027 (Dana VPN) | escalated/adverse_action, all 5 stages ok | $0.0362 |
| 3 | 12039 (adverse) | escalated/adverse_action, all 5 stages ok | $0.0313 |

**3 live runs of the ~8 allowed; total Anthropic spend this task ≈ $0.0675** (run 1's request was rejected before processing — $0). Project total ≈ $0.11 of $20. Voyage centroid computation was free-tier, not Anthropic budget.

## Findings the live checkpoint surfaced (the whole point of the checkpoint)

1. **`structured_call` 400'd against the live API** — `output_config.format.schema`: "For 'object' type, 'additionalProperties' must be explicitly set to false". Pydantic's `model_json_schema()` doesn't emit it; every mocked test was green. This is the second instance of the exact failure mode the standing SDK-reality rule describes. Fix: `_strict_schema()` in `triagedesk/llm.py` recursively stamps `additionalProperties: false` onto object types (uses `setdefault`, so an explicit value is never overridden); regression test added red-first. Note: the pre-merge live-SDK spike evidently didn't cover `output_config` structured outputs — worth remembering for Week 2's judge, which will use the same path (it now goes through the fixed code).
2. **CLI crashed printing the model's reply on Windows** — cp1252 console can't encode "→" (UnicodeEncodeError). Fix: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at CLI import. The glass-box tool must never crash on evidence it's displaying.
3. **Voyage free tier is far tighter than the plan assumed** — the brief's "128-batch, ~1 min" script hits both the 10K TPM cap (single 100-ticket batch ≈ 10K tokens) and the 3 RPM cap; real runtime ~15 min with pacing. Also self-inflicted: two background copies of the script briefly ran concurrently and starved each other on the RPM quota before I killed them. The committed JSON means nobody runs this again until the ticket dataset changes.

## Self-review

- **Completeness:** every brief step done (branch, centroids computed+committed, gate TDD 8/8, runner, CLI, both E2E scenarios green, full suite+ruff, push, PR with `Closes #7` + evidence). Steps 8's merge and step 9 (`how-we-got-here`, CLAUDE.md status update) intentionally left to the controller per my task instructions (do NOT merge).
- **Names:** exactly as the brief specifies — Week 2's harness can import `runner.run_ticket`, `gate.decide`, `gate.classification_margin`, `gate.SIM_THRESHOLD`, `gate.MARGIN_THRESHOLD`, `gate.GateDecision`, `gate.load_centroids`.
- **Discipline:** no gate-threshold tuning (0.45/0.02 verbatim); deviations from brief snippets are each traceable to a hard constraint (ruff B905; Voyage rate limits; live API schema requirement; Windows console encoding) and documented above.
- **Budget:** 3 of ~8 allowed live runs, ~$0.07.

## Fix loop 1 — catch-all exception handler

**Reviewer finding:** `run_ticket`'s try block catches only named exception types; any other exception (bug, DB error) propagates uncaught, leaving Run row stranded in state `running` forever.

**Changed:** Added final `except Exception as exc:` clause after `anthropic.APIError` handler, finishing the run as `failed` with reason `f"unexpected:{type(exc).__name__}"`, mirroring the API error handler's pattern (`finish_run`, `_note`).

**Test added:** `test_unexpected_exception_maps_to_failed` in `tests/unit/test_runner.py` — monkeypatches `run_precheck` to raise `RuntimeError("boom")`, asserts run ends in state `failed` with reason `unexpected:RuntimeError` and error logged to `internal_rationale`.

**Test run:**
```
pytest tests/unit/test_runner.py -v
11 passed in 1.69s
```

**Lint:** `ruff check .` — all checks passed.

**Commit:** `c5e3505` (`fix: catch-all in run_ticket so no run is stranded in 'running' (#7)`).

## Concerns / notes for Week 2

- **Both E2E runs had negative classification margin** (−0.0087, −0.0082) — with MARGIN_THRESHOLD=0.02, plausibly *nothing* auto-resolves right now. Expected: query embeddings (input_type="query") vs document-space centroids sit in slightly different spaces, and queue centroids are close together. This is precisely what the Week 2 calibration table (issue dependency) is designed to decide — no tuning done now, per instructions.
- **Dana's VPN ticket escalates rather than completes** because the agent proactively checks `priority_vpn_support`. Correct under the adverse-action rule, but if the demo narrative wants a `completed` example, Week 2/3 may want a demo ticket whose resolution needs no entitlement check (or a customer on pro/enterprise).
- 14 filler demo tickets (12024–12026, 12028–12038) now exist in the dev DB with subject "(filler)", source="demo". Harmless (kaggle-source filters exclude them from centroids), but the Week 3 seeded demo pool should be aware.
- `test_llm_repair.py` count went 4→5; suite 47→48.
