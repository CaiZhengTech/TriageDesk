"""The hand-written agent loop — deliberately no framework.

One lap = model thinks -> requests tools -> we execute -> results go back.
submit_resolution ends the loop. Hard cap MAX_ITERATIONS; exhaustion is an
honest failure (agent_incomplete), never a silent success.
"""

from dataclasses import dataclass

from triagedesk.llm import PIPELINE_MODEL
from triagedesk.llm import client as default_client
from triagedesk.prompts import ACT_SYSTEM, ticket_block
from triagedesk.schemas import Resolution
from triagedesk.tools import TOOL_DEFS, customer_ref_for, execute_tool

MAX_ITERATIONS = 5


class AgentIncompleteError(Exception):
    """Loop exhausted or ended without a submitted resolution."""


class ToolFailedError(Exception):
    """A tool failed twice (initial + one retry)."""


@dataclass
class ActOutcome:
    resolution: Resolution
    entitlement_denied: bool
    entitlement_checked: bool


def _run_tool_twice(name: str, tool_input: dict) -> dict:
    try:
        return execute_tool(name, tool_input)
    except Exception:
        try:
            return execute_tool(name, tool_input)  # exactly one retry
        except Exception as exc:
            raise ToolFailedError(f"{name} failed twice: {exc}") from exc


def run_act(ticket, classify_result, retrieval, tracer, _client=None) -> ActOutcome:
    c = _client or default_client
    customer_ref = customer_ref_for(ticket)
    kb_block = "\n\n".join(
        f"<kb_article slug=\"{d.slug}\">\n# {d.title}\n{d.content}\n</kb_article>"
        for d in retrieval.docs
    )
    messages = [{
        "role": "user",
        "content": (
            f"{ticket_block(ticket)}\n\nRouting queue: {classify_result.queue} "
            f"(sub-category: {classify_result.category})\n"
            f"Customer reference: {customer_ref}\n\n{kb_block}"
        ),
    }]

    entitlement_denied = False
    entitlement_checked = False
    with tracer.span("act") as span:
        for iteration in range(MAX_ITERATIONS):
            response = c.messages.create(
                model=PIPELINE_MODEL,
                max_tokens=4096,  # headroom: adaptive thinking counts against max_tokens
                system=[{"type": "text", "text": ACT_SYSTEM,
                         "cache_control": {"type": "ephemeral"}}],
                tools=TOOL_DEFS,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
            )
            tracer.record_llm_usage(span, response)
            tracer.set_attributes(span, **{"triage.act.iterations": iteration + 1})

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                if response.stop_reason == "pause_turn":
                    messages = messages + [{"role": "assistant", "content": response.content}]
                    continue
                raise AgentIncompleteError(
                    f"model ended turn ({response.stop_reason}) without submit_resolution"
                )

            submit = next((b for b in tool_uses if b.name == "submit_resolution"), None)
            others = [b for b in tool_uses if b.name != "submit_resolution"]

            results = []
            for block in others:  # ALWAYS execute non-submit tools first, regardless of order
                result = _run_tool_twice(block.name, dict(block.input))
                if block.name == "check_entitlement":
                    entitlement_checked = True
                    if result.get("covered") is False:
                        entitlement_denied = True
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

            if submit is not None:
                resolution = Resolution.model_validate(submit.input)
                tracer.set_attributes(
                    span,
                    **{
                        "triage.act.resolution_type": resolution.resolution_type,
                        "triage.act.entitlement_denied": entitlement_denied,
                        "triage.act.entitlement_checked": entitlement_checked,
                    },
                )
                return ActOutcome(resolution=resolution,
                                  entitlement_denied=entitlement_denied,
                                  entitlement_checked=entitlement_checked)

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": results},
            ]

    raise AgentIncompleteError(f"no resolution after {MAX_ITERATIONS} iterations")
