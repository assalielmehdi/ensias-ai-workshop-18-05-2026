"""Fixed LangGraph workflow — version 1 of the support bot.

START → classify_ticket → route_by_category → retrieve_context
      → draft_response → safety_check → END

Each node is a small function that takes the shared state, does ONE thing,
and returns an update. The graph wiring is what makes the path predictable:
the LLM never decides what step comes next.

That predictability is the whole point. Workflows like this are easy to
reason about and easy to test — but they cannot adapt when the path the
customer takes is not the one we designed for.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from .llm import get_chat_model
from .models import TicketCategory, TicketRequest, TicketResponse, Urgency
from .prompts import CLASSIFIER_PROMPT, DRAFTER_PROMPT, SAFETY_PROMPT
from .tools import check_order_status, search_knowledge_base

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    """State the workflow nodes read from and write to."""

    request: TicketRequest
    category: TicketCategory
    urgency: Urgency
    context: str
    draft: str
    needs_human: bool
    tools_used: list[str]
    reasoning_summary: str


# Nodes --------------------------------------------------------------------


def classify_ticket(state: WorkflowState) -> WorkflowState:
    """Call the LLM to assign a category + urgency."""

    req = state["request"]
    llm = get_chat_model()
    resp = llm.invoke(
        [SystemMessage(content=CLASSIFIER_PROMPT), HumanMessage(content=req.message)]
    )
    parsed = _safe_json(resp.content) or {}
    category = TicketCategory(parsed.get("category", "general_question"))
    urgency = Urgency(parsed.get("urgency", "low"))
    logger.info("classify category=%s urgency=%s", category.value, urgency.value)
    return {"category": category, "urgency": urgency, "tools_used": []}


def route_by_category(state: WorkflowState) -> WorkflowState:
    """Pure routing node — no LLM. Returns no state changes.

    The category set by `classify_ticket` decides which retrieval queries
    we'll run in the next step. We keep the explicit node so the graph reads
    cleanly to students.
    """
    logger.info("route_by_category category=%s", state["category"].value)
    return {}


def retrieve_context(state: WorkflowState) -> WorkflowState:
    """Pull KB snippets and (optionally) order info based on the category."""

    req = state["request"]
    category = state["category"]
    pieces: list[str] = []
    tools_used: list[str] = list(state.get("tools_used", []))

    # Choose a KB query per category.
    kb_query = {
        TicketCategory.REFUND_REQUEST: "refund policy electronics apparel",
        TicketCategory.DELIVERY_ISSUE: "shipping delivery tracking",
        TicketCategory.BILLING_ISSUE: "billing duplicate charge",
        TicketCategory.TECHNICAL_ISSUE: "technical headphones reset",
        TicketCategory.GENERAL_QUESTION: "policy",
        TicketCategory.ESCALATION_REQUIRED: "escalation",
    }[category]
    pieces.append(search_knowledge_base.invoke({"query": kb_query}))
    tools_used.append("search_knowledge_base")

    # If the customer gave us an order ID, fetch it.
    if req.order_id:
        pieces.append(check_order_status.invoke({"order_id": req.order_id}))
        tools_used.append("check_order_status")

    return {"context": "\n\n".join(pieces), "tools_used": tools_used}


def draft_response(state: WorkflowState) -> WorkflowState:
    """Call the LLM to draft a reply using the customer message + context."""

    req = state["request"]
    context = state.get("context", "")
    llm = get_chat_model()
    human = (
        f"Customer message:\n{req.message}\n\n"
        f"Context retrieved from our systems:\n{context}\n\n"
        f"Write the reply now."
    )
    resp = llm.invoke(
        [SystemMessage(content=DRAFTER_PROMPT), HumanMessage(content=human)]
    )
    draft = (resp.content or "").strip()
    return {"draft": draft}


def safety_check(state: WorkflowState) -> WorkflowState:
    """Last gate: decide whether the draft is safe to send or needs a human."""

    req = state["request"]
    draft = state.get("draft", "")
    llm = get_chat_model()
    human = (
        f"Customer message:\n{req.message}\n\nDraft reply:\n{draft}\n\n"
        "Decide now."
    )
    resp = llm.invoke(
        [SystemMessage(content=SAFETY_PROMPT), HumanMessage(content=human)]
    )
    parsed = _safe_json(resp.content) or {"needs_human": False, "reason": ""}
    needs_human = bool(parsed.get("needs_human", False))

    # If a human is needed, swap the draft for a safe boilerplate.
    if needs_human:
        draft = (
            "Thank you for reaching out. I want to make sure you get the right "
            "help here, so I've flagged this for a teammate — they'll follow up "
            "with you shortly. We're sorry for the inconvenience."
        )

    summary = (
        f"Workflow path: classify → retrieve → draft → safety_check "
        f"(needs_human={needs_human})."
    )
    return {
        "draft": draft,
        "needs_human": needs_human,
        "reasoning_summary": summary,
    }


# Helpers ------------------------------------------------------------------


def _safe_json(s: str) -> Optional[dict]:
    """Pull a JSON object out of an LLM response, tolerant of stray prose."""

    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except Exception:
            return None
    return None


# Graph construction -------------------------------------------------------


def build_workflow_graph():
    """Wire up the 5-node workflow.

    We compile and return it. Callers run it with `.invoke({"request": ...})`.
    """

    builder = StateGraph(WorkflowState)
    builder.add_node("classify_ticket", classify_ticket)
    builder.add_node("route_by_category", route_by_category)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("draft_response", draft_response)
    builder.add_node("safety_check", safety_check)

    builder.add_edge(START, "classify_ticket")
    builder.add_edge("classify_ticket", "route_by_category")
    builder.add_edge("route_by_category", "retrieve_context")
    builder.add_edge("retrieve_context", "draft_response")
    builder.add_edge("draft_response", "safety_check")
    builder.add_edge("safety_check", END)

    return builder.compile()


# Public entrypoint --------------------------------------------------------


def run_workflow(req: TicketRequest) -> TicketResponse:
    """Run the workflow end-to-end and return a typed response."""

    graph = build_workflow_graph()
    final: WorkflowState = graph.invoke({"request": req})
    return TicketResponse(
        category=final["category"],
        urgency=final["urgency"],
        customer_response=final["draft"],
        needs_human=final["needs_human"],
        tools_used=final.get("tools_used", []),
        reasoning_summary=final["reasoning_summary"],
    )
