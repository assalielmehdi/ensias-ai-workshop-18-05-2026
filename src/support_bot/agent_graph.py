"""STARTER STUB — to be filled in during step-03-agent-loop.

Goal: build a LangGraph agent loop:

    START → agent → should_continue?
       - if tool needed: tools → agent
       - if done:        END

TODOs for students:
1. Define an `AgentState` TypedDict with `messages` and `iterations`.
2. Write `agent_node`: bind ALL_TOOLS to the LLM, invoke on the messages.
3. Write `should_continue`: end if iteration cap hit OR last message has no
   tool calls; otherwise route to "tools".
4. Compile a graph with the `agent` node, a `ToolNode(ALL_TOOLS)`, a
   conditional edge out of `agent`, and an edge from `tools` back to `agent`.
5. Expose `run_agent(req)` that parses the LLM's final JSON into TicketResponse.

See workshop.md (section "0:55 - 1:20") for the live-coding walkthrough.
"""

from __future__ import annotations

from .models import TicketRequest, TicketResponse


def run_agent(req: TicketRequest) -> TicketResponse:
    """Run the agent loop. Not implemented yet — see step-03."""

    _ = req
    raise NotImplementedError(
        "run_agent is not implemented yet. "
        "Switch to branch step-03-agent-loop or fill it in yourself."
    )
