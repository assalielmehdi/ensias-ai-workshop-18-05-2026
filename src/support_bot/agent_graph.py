"""LangGraph agent loop — version 2 of the support bot.

START → agent → should_continue?
   - if tool needed: tools → agent
   - if done:        END

The LLM decides at every step whether to call a tool or finish. We do NOT
hand-write the path; we hand-write the *contract* (system prompt + tool
docstrings + a hard iteration cap) and let the model choose.

This is the smallest possible "true agent": one LLM node, one tool node, one
conditional edge between them. Everything else is guardrails.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import settings
from .llm import _as_text, get_chat_model
from .models import TicketCategory, TicketRequest, TicketResponse, Urgency
from .prompts import AGENT_SYSTEM_PROMPT
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Conversation state. `add_messages` appends rather than overwriting."""

    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int


# Nodes --------------------------------------------------------------------


def agent_node(state: AgentState) -> AgentState:
    """One LLM turn. Bind the tools so the model can request a call."""

    llm = get_chat_model().bind_tools(ALL_TOOLS)
    response = llm.invoke(state["messages"])
    iters = state.get("iterations", 0) + 1
    if isinstance(response, AIMessage) and response.tool_calls:
        names = ", ".join(tc["name"] for tc in response.tool_calls)
        logger.info("agent iter=%d tool_calls=[%s]", iters, names)
    else:
        logger.info("agent iter=%d final_answer", iters)
    return {"messages": [response], "iterations": iters}


def should_continue(state: AgentState) -> str:
    """Decide whether to call tools, stop, or hit the iteration cap."""

    if state.get("iterations", 0) >= settings.agent_max_iterations:
        logger.warning("Agent hit max iterations (%d); stopping.", settings.agent_max_iterations)
        return "end"
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


# Graph construction -------------------------------------------------------


def build_agent_graph():
    """Wire up the agent loop."""

    # AgentState IS a TypedDict; LangGraph's generic bound is overly strict
    # and rejects external TypedDict subclasses. Safe to ignore.
    builder = StateGraph(AgentState)  # ty: ignore[invalid-argument-type]
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    builder.add_edge("tools", "agent")

    return builder.compile()


# Public entrypoint --------------------------------------------------------


def run_agent(req: TicketRequest) -> TicketResponse:
    """Run the agent end-to-end and return a typed response.

    The agent's final AIMessage is expected to contain a JSON object on its
    own line. We parse that and map it into our TicketResponse model.
    """

    graph = build_agent_graph()
    initial: AgentState = {
        "messages": [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            HumanMessage(content=_format_user_msg(req)),
        ],
        "iterations": 0,
    }
    final: AgentState = graph.invoke(initial)

    tools_used = _collect_tool_names(final["messages"])
    last_ai = next((m for m in reversed(final["messages"]) if isinstance(m, AIMessage)), None)
    parsed = _parse_final(_as_text(last_ai.content) if last_ai else "")

    # Guardrail: if the model never produced a structured answer (e.g. we hit
    # the iteration cap), fall back to a safe human-escalation reply.
    if not parsed:
        return TicketResponse(
            category=TicketCategory.ESCALATION_REQUIRED,
            urgency=Urgency.HIGH,
            customer_response=(
                "Thanks for reaching out — I want to make sure this gets handled "
                "carefully, so I've passed it to a human teammate who will follow up shortly."
            ),
            needs_human=True,
            tools_used=tools_used,
            reasoning_summary="Agent did not produce structured output; escalated.",
        )

    return TicketResponse(
        category=TicketCategory(parsed.get("category", "general_question")),
        urgency=Urgency(parsed.get("urgency", "low")),
        customer_response=parsed.get("customer_response", ""),
        needs_human=bool(parsed.get("needs_human", False)),
        tools_used=tools_used,
        reasoning_summary=parsed.get("reasoning_summary", ""),
    )


# Helpers ------------------------------------------------------------------


def _format_user_msg(req: TicketRequest) -> str:
    parts = [f"Ticket from customer:\n{req.message}"]
    if req.customer_id:
        parts.append(f"customer_id: {req.customer_id}")
    if req.order_id:
        parts.append(f"order_id: {req.order_id}")
    return "\n".join(parts)


def _collect_tool_names(messages: list[BaseMessage]) -> list[str]:
    """Walk the message history and pull out every tool that was called."""

    from langchain_core.messages import ToolMessage

    seen: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name and m.name not in seen:
            seen.append(m.name)
    return seen


def _parse_final(content: str) -> Optional[dict]:
    """Find the last JSON object in the model's reply."""

    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        pass
    # Some models add prose around the JSON; grab the last {...} block.
    end = content.rfind("}")
    if end == -1:
        return None
    depth = 0
    for i in range(end, -1, -1):
        ch = content[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[i : end + 1])
                except Exception:
                    return None
    return None
