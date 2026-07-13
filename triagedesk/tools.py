"""Simulated account tools. The model never touches real systems — these read
seed data. customer_ref is derived deterministically from the ticket id so
demo runs are reproducible."""

import json
from pathlib import Path

_SEED = json.loads((Path(__file__).parent / "seed_accounts.json").read_text())

# Must match kb/plans-and-entitlements.md
PLAN_ENTITLEMENTS = {
    "basic": {"standard_support", "email_setup"},
    "pro": {"standard_support", "email_setup", "priority_vpn_support", "api_access",
            "data_export"},
    "enterprise": {"standard_support", "email_setup", "priority_vpn_support", "api_access",
                   "data_export", "dedicated_ip", "custom_integrations"},
}


def customer_ref_for(ticket) -> str:
    return f"customer-{ticket.id % 12}"


def lookup_account_status(customer_ref: str) -> dict:
    account = _SEED.get(customer_ref)
    if account is None:
        raise KeyError(f"unknown customer_ref {customer_ref!r}")
    return {"customer_ref": customer_ref, "status": account["status"], "plan": account["plan"]}


def check_entitlement(customer_ref: str, feature: str) -> dict:
    account = _SEED.get(customer_ref)
    if account is None:
        raise KeyError(f"unknown customer_ref {customer_ref!r}")
    covered = feature in PLAN_ENTITLEMENTS[account["plan"]]
    return {"customer_ref": customer_ref, "feature": feature,
            "plan": account["plan"], "covered": covered}


TOOL_DEFS = [
    {
        "name": "lookup_account_status",
        "description": "Look up a customer's account status (active/suspended/delinquent) "
                       "and plan (basic/pro/enterprise). Call before proposing any "
                       "account-specific fix.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_ref": {"type": "string"}},
            "required": ["customer_ref"],
        },
    },
    {
        "name": "check_entitlement",
        "description": "Check whether the customer's plan covers a feature. Features: "
                       "standard_support, email_setup, priority_vpn_support, api_access, "
                       "data_export, dedicated_ip, custom_integrations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_ref": {"type": "string"},
                "feature": {"type": "string"},
            },
            "required": ["customer_ref", "feature"],
        },
    },
    {
        "name": "submit_resolution",
        "description": "Submit your final resolution for this ticket. Call exactly once, "
                       "when you have enough information.",
        "strict": True,
        "cache_control": {"type": "ephemeral"},
        "input_schema": {
            "type": "object",
            "properties": {
                "resolution_type": {"type": "string", "enum": ["solve", "deny", "needs_human"]},
                "customer_reply": {"type": "string"},
                "internal_rationale": {"type": "string"},
            },
            "required": ["resolution_type", "customer_reply", "internal_rationale"],
            "additionalProperties": False,
        },
    },
]

_IMPLS = {"lookup_account_status": lookup_account_status, "check_entitlement": check_entitlement}


def execute_tool(name: str, tool_input: dict) -> dict:
    return _IMPLS[name](**tool_input)
