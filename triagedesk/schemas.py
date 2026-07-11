from typing import Literal

from pydantic import BaseModel

QUEUES = (
    "Technical Support",
    "Product Support",
    "Customer Service",
    "IT Support",
    "Billing and Payments",
    "Returns and Exchanges",
    "Service Outages and Maintenance",
    "Sales and Pre-Sales",
    "Human Resources",
    "General Inquiry",
)

Queue = Literal[
    "Technical Support",
    "Product Support",
    "Customer Service",
    "IT Support",
    "Billing and Payments",
    "Returns and Exchanges",
    "Service Outages and Maintenance",
    "Sales and Pre-Sales",
    "Human Resources",
    "General Inquiry",
]


class PrecheckVerdict(BaseModel):
    safe: bool
    category: Literal["injection", "pii", "off_topic"] | None = None
    reason: str | None = None


class ClassifyResult(BaseModel):
    queue: Queue
    category: str  # free-text sub-category, e.g. "vpn"


class Resolution(BaseModel):
    resolution_type: Literal["solve", "deny", "needs_human"]
    customer_reply: str
    internal_rationale: str
