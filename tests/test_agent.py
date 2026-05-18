"""Tests for the agent loop (run in mock LLM mode).

These rely on the deterministic behaviour of MockChatModel in src/support_bot/llm.py.
"""

from __future__ import annotations

from support_bot.agent_graph import run_agent
from support_bot.models import TicketCategory, TicketRequest, Urgency


def test_agent_happy_path_refund_uses_tools():
    req = TicketRequest(
        message="Hi, I ordered headphones last week. They arrived broken. I want a refund. Order ID: ORD-1007.",
        order_id="ORD-1007",
    )
    out = run_agent(req)
    assert out.category == TicketCategory.REFUND_REQUEST
    assert "check_order_status" in out.tools_used
    assert "check_refund_policy" in out.tools_used
    assert out.needs_human is True


def test_agent_asks_for_missing_information():
    req = TicketRequest(message="My package never arrived and I need this fixed ASAP.")
    out = run_agent(req)
    assert out.category == TicketCategory.DELIVERY_ISSUE
    # The agent should NOT auto-resolve a delivery problem with no order id.
    assert out.needs_human is False
    assert "share" in out.customer_response.lower() or "order id" in out.customer_response.lower()


def test_agent_escalates_legal_threats():
    req = TicketRequest(
        message="I'm furious. I was charged twice and I'm considering legal action."
    )
    out = run_agent(req)
    assert out.category == TicketCategory.ESCALATION_REQUIRED
    assert out.urgency == Urgency.HIGH
    assert out.needs_human is True
    assert "escalate_to_human" in out.tools_used


def test_agent_escalates_duplicate_charge():
    req = TicketRequest(
        message="I was charged twice for my order and want it sorted.",
    )
    out = run_agent(req)
    assert out.needs_human is True
    assert "escalate_to_human" in out.tools_used


def test_agent_respects_iteration_cap(monkeypatch):
    from support_bot.config import settings

    monkeypatch.setattr(settings, "agent_max_iterations", 1)
    req = TicketRequest(
        message="Hi, I ordered headphones last week. They arrived broken. Order ID: ORD-1007.",
        order_id="ORD-1007",
    )
    out = run_agent(req)
    # With only 1 iteration we can't both call a tool and produce a final
    # answer — the guardrail should kick in and escalate.
    assert out.needs_human is True
