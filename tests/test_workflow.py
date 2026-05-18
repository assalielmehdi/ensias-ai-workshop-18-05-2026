"""Tests for the fixed workflow graph (run in mock LLM mode)."""

from __future__ import annotations

from support_bot.models import TicketCategory, TicketRequest, Urgency
from support_bot.workflow_graph import run_workflow


def test_workflow_classifies_refund():
    req = TicketRequest(
        message="My headphones arrived broken, I want a refund. Order ORD-1007",
        order_id="ORD-1007",
    )
    out = run_workflow(req)
    assert out.category == TicketCategory.REFUND_REQUEST
    assert "search_knowledge_base" in out.tools_used
    assert "check_order_status" in out.tools_used


def test_workflow_escalates_legal_threat():
    req = TicketRequest(
        message="I'm considering legal action over this duplicate charge.",
    )
    out = run_workflow(req)
    assert out.needs_human is True
    assert out.urgency == Urgency.HIGH


def test_workflow_handles_missing_order_id():
    req = TicketRequest(message="My package never arrived and I need this fixed ASAP.")
    out = run_workflow(req)
    # Workflow doesn't dynamically ask for missing info — it still drafts a
    # reply, but the bot can't actually look up an order without an ID.
    assert "check_order_status" not in out.tools_used
    assert out.category == TicketCategory.DELIVERY_ISSUE


def test_workflow_returns_response_shape():
    req = TicketRequest(message="Hello, do you sell gift cards?")
    out = run_workflow(req)
    assert isinstance(out.customer_response, str) and out.customer_response
    assert isinstance(out.reasoning_summary, str) and out.reasoning_summary
    assert out.category in TicketCategory
