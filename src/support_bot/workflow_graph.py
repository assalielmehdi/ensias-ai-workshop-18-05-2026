"""STARTER STUB — to be filled in during step-01-workflow-chatbot.

Goal: build a fixed LangGraph workflow:

    START → classify_ticket → route_by_category → retrieve_context
          → draft_response → safety_check → END

TODOs for students:
1. Define a `WorkflowState` TypedDict with the fields each node reads/writes.
2. Write five small node functions (one per step). Each takes `state` and
   returns the keys it wants to update.
3. Wire them up with `langgraph.graph.StateGraph` and compile.
4. Expose a `run_workflow(req)` entrypoint that returns a `TicketResponse`.

See workshop.md (section "0:25 - 0:45") for the live-coding walkthrough.
"""

from __future__ import annotations

from .models import TicketRequest, TicketResponse


def run_workflow(req: TicketRequest) -> TicketResponse:
    """Run the fixed workflow. Not implemented yet — see step-01."""

    _ = req  # silence "unused argument" — students will use it once implemented
    raise NotImplementedError(
        "run_workflow is not implemented yet. "
        "Switch to branch step-01-workflow-chatbot or fill it in yourself."
    )
