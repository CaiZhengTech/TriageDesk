# Judge calibration

> ⚠️ **Versioned file — two judge versions and two human labeling rounds live here.
> Never quote a kappa without saying which pair it comes from** (see the reliability
> analysis below — the 2×2 table is the only honest summary).

## Official judge-v2 calibration (2026-07-17, fresh labeling round 2)

- Judge prompt version: **2** (bumped whenever the judge's
  grading context changes -- pre/post-fix kappas are never conflated)
- Labels compared (solo): **41**
- Raw agreement: **0.488**
- **Cohen's kappa: 0.133**
- **Weighted kappa (linear, ordinal fail<needs_review<pass): 0.164**
- 95% bootstrap CI: [-0.052, 0.349] (n_boot=2000, seed=0)

Blind solo labeling; friend labels (chore #19) merged if they arrive.
Judge = claude-sonnet-4-6 @ temperature 0. Verdicts are debugging aids,
never ground truth.

## Reliability analysis — the finding of the recalibration (READ THIS, not just the headline)

The v2 kappa (0.133) is LOWER than v1's (0.279) despite the judge demonstrably improving.
The recalibration exposed a deeper issue: **the human label standard itself is unstable.**
Cai labeled the SAME 41 replies twice (round 1 = 2026-07-14 for judge v1; round 2 =
2026-07-17 for judge v2, replies recognized from round 1 — not naive):

| Comparison | Raw agreement | Kappa | Weighted |
|---|---|---|---|
| **Human round 1 vs human round 2 (self-agreement)** | **0.659** | **0.212** | 0.243 |
| Judge v1 vs labels round 1 (official v1) | 0.512 | 0.279 | 0.390 |
| Judge v2 vs labels round 1 | 0.634 | 0.418 | 0.551 |
| Judge v1 vs labels round 2 | 0.317 | 0.038 | 0.074 |
| Judge v2 vs labels round 2 (official v2) | 0.488 | 0.133 | 0.164 |

Three conclusions the table forces:

1. **The tool-evidence fix genuinely improved the judge**: v2 beats v1 against BOTH
   labeling rounds (0.279 → 0.418 on round 1; 0.038 → 0.133 on round 2). The improvement
   is invariant to which human standard you pick.
2. **The human is the unstable component**: self-agreement kappa 0.212 is *lower than the
   judge's agreement with either round*. 14/41 labels flipped between rounds (9 fail→pass —
   round 2 is markedly more lenient; marginals went 26/13/2 → 34/5/2 pass/fail/nr, and that
   skew also mechanically depresses kappa via the prevalence effect). A single self-rater
   has hit the reliability ceiling — the fix is a second rater (chore #19) and/or an
   adjudicated gold-label pass, not more judge tuning.
3. **One residual judge blind spot is real (not label noise): negative entitlement
   claims.** Rows 193/195/199/200/203/207: replies stating a feature is NOT in the
   customer's plan (e.g. "custom integrations are not included in your Pro plan" — TRUE
   per `PLAN_ENTITLEMENTS`, pro lacks `custom_integrations`). Judge v2 fails these as
   "invented policy": it verifies positive facts against the account block but does not
   reason "absent from the entitlement list = a verifiable exclusion" (closed-world
   inference). Cai's round-2 pass labels are CORRECT on these; his round-1 fail labels
   agreed with the judge's error. Fix candidate for a future judge v3: state the
   entitlement list as exhaustive in the account-facts block.

## Confusion matrix (rows = human, cols = judge)

| human \ judge | pass | fail | needs_review |
|---|---|---|---|
| pass | 16 | 7 | 11 |
| fail | 1 | 3 | 1 |
| needs_review | 1 | 0 | 1 |

## Disagreements (judge vs human)

Where the LLM judge diverged from human judgment -- the highest-value
artifact of this calibration pass.

| result_id | human_label | judge_verdict | judge_reason |
|---|---|---|---|
| 168 | fail | needs_review | The reply is mostly grounded (status page check and log steps come from KB), but the Elasticsearch/analytics dashboard issue is not covered by any KB article, and the agent's suggestion to check the client log and version is loosely adapted from the software-installation article rather than directly applicable — making it ambiguous whether the steps are genuinely helpful or slightly off-topic for this specific issue. |
| 170 | pass | needs_review | The reply is largely grounded in KB articles (status page, security steps, MFA) but includes an unverified claim that the ticket is being 'escalated to a senior technical specialist' with a follow-up, which is not supported by any KB article or account fact, making it a borderline grounding issue that warrants review rather than a clear fail. |
| 175 | fail | pass | The reply is fully grounded in the KB articles and verified account facts, correctly addresses the ticket by providing billing cycle details and directing the customer to sales for plan/pricing comparisons, and maintains a professional tone without over-promising. |
| 176 | pass | needs_review | The reply is grounded in the KB for the status-page advice and is professionally toned, but the claim about escalating to a 'Data Analytics Product Support team' and the specific information requests (asset class, time horizon, etc.) are not supported by any KB article or account facts, making the grounding ambiguous rather than clearly invented. |
| 179 | pass | needs_review | The reply is well-grounded in the KB article and helpful, but the customer's account is currently suspended, which may affect their ability to access services or receive support — the agent's reply does not acknowledge this and may be misleading in that context. |
| 184 | pass | needs_review | The reply is grounded in KB content for the immediate security steps, but the ticket appears to be a generic/misdirected request about medical data encryption that doesn't clearly relate to a Northbeam account, and the agent's claim of escalating to 'security and engineering leadership' for a platform-wide encryption plan is not supported by any KB article or account fact, making the overall grounding ambiguous rather than clearly violated. |
| 187 | pass | needs_review | The reply is reasonable and professional, but the escalation process and data/product engineering team are not mentioned in any KB article or account facts, making the grounding ambiguous rather than clearly invented — the ticket topic itself (investment projections) is also entirely outside the provided KB scope. |
| 189 | pass | needs_review | The reply is polite and avoids inventing steps, but the KB articles don't cover product feedback or UI enhancement requests at all, so it's unclear whether routing to a 'product team' is a grounded claim or an invented process; however, the response is also not clearly harmful or wrong enough to fail outright. |
| 193 | pass | fail | The reply invents a policy that Basic plan excludes third-party integration support and that upgrading to 'Pro or Enterprise' unlocks it — none of this appears in the KB articles or verified account facts, making it an ungrounded fabrication. |
| 195 | pass | fail | The agent's claim that 'custom integrations are not included in your current Pro plan' is not supported by any KB article or verified account fact — this is an invented policy statement. |
| 196 | pass | needs_review | The KB articles provided contain no system specifications for project management software, so the agent correctly cannot answer the question, but the reply invents an escalation path ('routing to a specialist') that is not grounded in any KB article or account fact. |
| 197 | pass | fail | The reply invents a RAID-controller/storage-infrastructure specialist escalation path and troubleshooting steps that have no basis in any of the provided KB articles, which cover only password reset, security concerns, and VPN connectivity. |
| 198 | pass | needs_review | The reply correctly identifies the account suspension from verified facts and gives reasonable guidance, but the KB articles do not cover account suspension or reinstatement procedures, so the claim that 'a human support agent has been assigned' and the described reinstatement process are not grounded in the provided KB — however, the core account-status fact is verified, making this genuinely ambiguous rather than a clear grounding failure. |
| 199 | pass | fail | The reply invents policies and procedures (specialist escalation team, billing review path, Cassandra optimization support) that have no basis in the provided KB articles, which cover only API keys, data export, and service status — none of which are relevant to Cassandra integration. |
| 200 | pass | fail | The reply invents an escalation process and troubleshooting steps for a Cassandra/Investments Dashboard issue that are not grounded in any of the provided KB articles, which cover only security concerns, service status, and software installation/updates. |
| 201 | needs_review | pass | The agent correctly acknowledges it lacks the relevant KB information to answer the system specifications question and escalates appropriately, without inventing any specs or making unsupported claims. |
| 202 | pass | needs_review | The agent's reply is plausible and grounded in the verified account fact (suspended status), but none of the KB articles cover project syncing, account suspension, or reactivation procedures, making it impossible to confirm the steps are fully grounded or that suspension actually causes sync issues. |
| 203 | pass | fail | The reply promises 'priority review' and escalation to a senior technical specialist, but the account is on a Basic plan with only standard_support entitlement, and nothing in the KB or account facts supports offering priority handling or specialist escalation. |
| 205 | pass | needs_review | The ticket is about QuickBooks software accuracy, which is entirely outside the scope of the provided KB articles (billing, security, service status) and Northbeam's apparent product domain; the reply neither invents grounded steps nor addresses anything in the KB, making it impossible to verify whether escalating to a 'Product Support specialist' is a real process or an invented one. |
| 207 | pass | fail | The agent's claim that integration/compatibility troubleshooting is unavailable on the Basic plan and requires a Pro/Enterprise upgrade is not supported by any KB article or the verified account facts — this is an invented policy. |
| 208 | pass | needs_review | The reply is mostly grounded in KB articles (status page check, lockout steps), but it promises escalation to a 'senior technical support engineer' which is not supported by any KB article or account fact, and the account is on a basic/delinquent plan with only standard_support entitlement — however, the escalation claim is borderline invented rather than clearly contradicted, making this genuinely ambiguous. |

## Judge v1 (tool-blind) — the original calibration

- Labels compared (solo): **41**
- Raw agreement: **0.512**
- **Cohen's kappa: 0.279**

Blind solo labeling; friend labels (chore #19) merged if they arrive.
Judge = claude-sonnet-4-6 @ temperature 0. Verdicts are debugging aids,
never ground truth.

## Confusion matrix (rows = human, cols = judge)

| human \ judge | pass | fail | needs_review |
|---|---|---|---|
| pass | 9 | 5 | 12 |
| fail | 1 | 12 | 0 |
| needs_review | 1 | 1 | 0 |

## Disagreements (judge vs human)

Where the LLM judge diverged from human judgment -- the highest-value
artifact of this calibration pass.

| result_id | human_label | judge_verdict | judge_reason |
|---|---|---|---|
| 27 | pass | needs_review | The reply is largely grounded in the KB but includes an invented claim that 'your account is currently in a suspended state,' which is not mentioned in the ticket or supported by any KB article, making it a potentially fabricated assertion that warrants review rather than a clear fail. |
| 29 | pass | needs_review | The reply is largely grounded in the KB articles (status page, security steps, MFA, API key revocation) but includes an unverified claim about escalating to a 'senior technical specialist' that is not supported by any KB article, making it borderline on grounding without being a clear fabrication of policy. |
| 34 | fail | pass | All steps and claims in the reply are grounded in the KB articles (invoice location, line item types, payment method path, billed-in-error refund policy), the tone is professional without over-promising, and the reply concretely addresses the billing discrepancy ticket. |
| 36 | pass | needs_review | The status page check is grounded in the KB, but the claim about the customer being on a 'Pro plan' and the escalation to a 'Data Analytics Product Support team' are not supported by any KB article, though they may be reasonable operational steps that aren't strictly contradicted either. |
| 38 | pass | needs_review | The agent correctly acknowledges the topic is outside the available KB and avoids inventing steps, but the claim that the customer is on a 'Pro plan' is not grounded in any KB article or ticket information, which is a minor grounding concern that warrants review rather than an outright fail. |
| 41 | pass | fail | The agent's reply claims the customer's account is 'currently suspended,' which is not mentioned anywhere in the KB articles and appears to be an invented detail. |
| 43 | pass | fail | The agent claims the customer is on the Pro plan, which is invented information not found in any KB article. |
| 44 | pass | fail | The agent's reply invents claims not found in any KB article, including the assertion that the customer is on an Enterprise plan, that there is a 'digital campaign analytics team,' and that Enterprise plan users receive prioritized handling for this type of issue — none of these are grounded in the provided KB articles. |
| 45 | pass | needs_review | The reply is partially grounded (the immediate steps come from the KB) but the claim about escalating to 'security and engineering leadership teams' for a platform-wide encryption and policy review is not supported by any KB article, making the grounding ambiguous rather than clearly invented. |
| 51 | pass | needs_review | The reply is reasonable and professional, but it references account status ('active and in good standing on the Pro plan') and an escalation process not grounded in any of the provided KB articles, which only cover billing, cancellation, and service status — none of which address investment projections or data analysis models. |
| 53 | pass | needs_review | The ticket is a product enhancement request that falls outside the scope of the KB articles provided, so the agent's response cannot be grounded in or contradicted by the available KB content, making it genuinely ambiguous whether the reply is appropriate. |
| 54 | pass | needs_review | The reply is largely grounded in the KB but step 1 directs the user to 'Account → Settings → Password' to change their password, whereas the KB instructs users to use the 'Forgot password?' flow on the login page — a minor but potentially misleading navigation discrepancy that warrants review rather than a clear pass or fail. |
| 55 | pass | needs_review | The agent claims the customer is on the Basic plan ('I checked your account and can see you're currently on our Basic plan'), but the ticket contains no account information and the KB does not support this specific claim — it's an invented account detail that cannot be verified from the provided context. |
| 59 | pass | needs_review | The reply is mostly grounded in KB articles (status page steps, software update details), but the claim about escalating to a 'senior support engineer' and the promise of being 'contacted shortly' are not supported by any KB article, making it borderline on grounding without being a clear fabrication of a specific policy or number. |
| 61 | pass | needs_review | The KB articles provided contain no system specifications for project management software, so the agent correctly cannot answer from the KB, but the reply invents an escalation/routing process not documented in any KB article, making it ambiguous whether this constitutes a grounding violation or a reasonable deflection. |
| 62 | pass | fail | The agent's reply invents a RAID-controller firmware escalation process and requests specific technical details (make/model, firmware version, system logs) that are not grounded in any of the provided KB articles, which cover only password resets, security concerns, and VPN troubleshooting. |
| 63 | needs_review | fail | The agent claims the account is 'suspended' and references account-specific details (e.g., 'customer-2') not found in any KB article; the KB articles cover lockouts, MFA issues, and security concerns but say nothing about account suspensions, making this a grounding violation. |
| 70 | needs_review | pass | All steps and claims in the reply are grounded in the KB articles (status page URL, error codes, rate limits, key rotation steps), the response is helpful and concrete, and the tone is professional without over-promising. |
| 71 | pass | fail | The agent's reply references the customer's account plan ('Enterprise plan') and a 'Product Support team' escalation path, neither of which appear in any of the provided KB articles, making these claims ungrounded. |
| 72 | pass | needs_review | The reply is well-grounded in the KB articles and follows the correct steps, but it references 'medical data exposure' and frames this as a 'high-priority security incident' involving sensitive health data — a characterization that goes slightly beyond what the KB supports and could imply regulatory obligations (e.g., HIPAA) that the agent has no basis to confirm or address, making this genuinely ambiguous. |
