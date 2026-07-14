# Judge calibration

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
