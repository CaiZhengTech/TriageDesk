"""The public demo's ticket pool — authored, pinned, and repo-owned (issue #64).

WHY THIS FILE EXISTS
--------------------
The original pool (ids 12023 / 12027 / 12039) was created by hand in a Neon dev
branch and reached production only because the prod branch was cut copy-on-write
from dev. No seed script was ever written — `docs/week-3-console/reports/task-6-deploy.md`
records the moment the planned "seed the prod demo pool" step was skipped for
exactly that reason. When the free-tier branches expired, the pool was gone, and
nothing in the repo could rebuild it. Ticket 12027 was also a golden-set case, so
the eval set lost a member too.

Same lesson as the Railway start command in #63: configuration that lives outside
the repo is not real. The pool is now data in version control.

WHY THE IDs LOOK LIKE THAT
--------------------------
Two constraints fix them:

1. They sit far above the Kaggle ingest range (11,922 rows) so the pinned ids can
   never collide with an auto-increment id. The 90000+ band is already taken by
   `triagedesk/evals/adversarial.py`, so the pool uses 80000+.
2. `triagedesk.tools.customer_ref_for` is `customer-{id % 12}` — a ticket's id
   silently selects whose account, and therefore whose PLAN, the act loop reads.
   Each id below is chosen so it lands on the customer the scenario needs.
   `tests/unit/test_demo_pool.py` asserts this rather than trusting the arithmetic;
   the Week-1 checkpoint had to insert filler tickets by hand to steer `id % 12`,
   which is precisely the manual step this replaces.

ON `expected_gate_outcome`
--------------------------
It records **design intent**, not a promise. These are inputs chosen so that each
of the gate's layers is reachable — nothing here tunes the gate, and no threshold,
prompt, or rule may be adjusted to make a ticket land the way this file says it
should (the council's hold-out rule). If a ticket labelled `auto_resolve` still
escalates in a live run, that is a finding to write up, not a knob to turn.
"""

DEMO_POOL: list[dict] = [
    {
        # id % 12 == 3 -> customer-3, Dana Fuentes, basic, active.
        "ticket_id": 80007,
        "subject": "My VPN keeps disconnecting — client demo at 3pm",
        "body": (
            "Hi, my Northbeam VPN has been dropping every few minutes all morning. "
            "It reconnects on its own after 20-30 seconds but I lose whatever I was "
            "doing. I have a client demo at 3pm today that I have to run over the "
            "VPN and I cannot have it cutting out in the middle. I have already "
            "restarted the client and my laptop. Can someone look at this urgently?"
        ),
        "queue": "IT Support",
        "expected_customer_ref": "customer-3",
        "entitlement_feature": "priority_vpn_support",
        "expected_gate_outcome": "escalate",
        "why": (
            "The project's recurring worked example. The KB's VPN article ends by "
            "naming priority VPN support as the Pro/Enterprise path for urgent VPN "
            "tickets, so the act loop checks it; Dana is on basic, the check returns "
            "covered=False, and the adverse-action rule escalates unconditionally. "
            "The customer still gets real troubleshooting steps — they are just held "
            "for a human rather than auto-sent, because the reply carries an implicit "
            "'no' about the urgency she asked for."
        ),
    },
    {
        # id % 12 == 6 -> customer-6, Morgan Lee, pro, active.
        "ticket_id": 80010,
        "subject": "VPN drops every few minutes on my home wifi",
        "body": (
            "Since the weekend my VPN connection has been dropping every few minutes "
            "when I work from home. It seems to happen most often after my laptop "
            "wakes from sleep. It is fine when I am in the office. I have not changed "
            "any settings. What should I try?"
        ),
        "queue": "IT Support",
        "expected_customer_ref": "customer-6",
        "entitlement_feature": "priority_vpn_support",
        "expected_gate_outcome": "auto_resolve",
        "why": (
            "The deliberate counterpart to Dana's ticket, and the answer to issue #62: "
            "the same complaint from a Pro-plan customer. check_entitlement returns "
            "covered=True, so there is positive entitlement evidence and no denial — "
            "the two layers that stop Dana. The symptom (drops after waking from "
            "sleep) is answered verbatim by the KB's 'Reconnect on network change' "
            "step, so retrieval should be strong. Same agent, same question, different "
            "plan, different exit: that pair is the demo's whole argument."
        ),
    },
    {
        # id % 12 == 7 -> customer-7, Taylor Brooks, basic, active.
        "ticket_id": 80011,
        "subject": "Locked out after too many password attempts",
        "body": (
            "I mistyped my password a few times this morning and now the portal says "
            "my account is locked. I am not trying to reset it to anything fancy, I "
            "just need to get back in. Is there a self-service way to unlock it or do "
            "you have to do it on your end?"
        ),
        "queue": "IT Support",
        "expected_customer_ref": "customer-7",
        "entitlement_feature": "standard_support",
        "expected_gate_outcome": "auto_resolve",
        "why": (
            "A second auto-resolve candidate that does not depend on plan tier at all: "
            "password reset and account unlock are Basic-inclusive, so standard_support "
            "comes back covered even for a basic customer. Deliberate redundancy — if "
            "the VPN pair's margin signal turns out to be marginal in live runs, this "
            "ticket still demonstrates that auto-resolve is reachable."
        ),
    },
    {
        # id % 12 == 3 -> customer-3, Dana Fuentes, basic, active.
        "ticket_id": 80019,
        "subject": "Please assign us a dedicated IP address",
        "body": (
            "Our security team wants all of our VPN and API traffic to come from a "
            "single fixed IP address so they can allowlist it on their firewall. Can "
            "you set up a dedicated IP for our account? Let me know if you need "
            "anything from us to get it provisioned."
        ),
        "queue": "IT Support",
        "expected_customer_ref": "customer-3",
        "entitlement_feature": "dedicated_ip",
        "expected_gate_outcome": "escalate",
        "why": (
            "The unambiguous denial, and the clearest demonstration of the "
            "adverse-action rule. dedicated_ip is Enterprise-only and Dana is on "
            "basic, so the honest answer is 'no, that needs an upgrade'. The agent is "
            "never allowed to deliver that itself, however confident it is — the "
            "refusal is written, logged with its rationale, and routed to a human."
        ),
    },
]
