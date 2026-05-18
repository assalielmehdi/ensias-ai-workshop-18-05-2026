"""Unit tests for the four tools."""

from __future__ import annotations

from support_bot.tools import (
    check_order_status,
    check_refund_policy,
    escalate_to_human,
    search_knowledge_base,
)


def test_search_knowledge_base_finds_refund_policy():
    out = search_knowledge_base.invoke({"query": "refund electronics"})
    assert "electronics" in out.lower()


def test_search_knowledge_base_no_match():
    out = search_knowledge_base.invoke({"query": "asdfqwertyzxcv"})
    assert "no matching" in out.lower()


def test_check_order_status_known():
    out = check_order_status.invoke({"order_id": "ORD-1007"})
    assert "ORD-1007" in out
    assert "delivered" in out.lower()


def test_check_order_status_unknown():
    out = check_order_status.invoke({"order_id": "ORD-9999"})
    assert "not found" in out.lower()


def test_check_refund_policy_eligible_electronics():
    out = check_refund_policy.invoke({"product_type": "electronics", "days_since_purchase": 5})
    assert "eligible" in out.lower()
    assert "human" in out.lower(), "policy tool must never auto-approve refunds"


def test_check_refund_policy_expired_electronics():
    out = check_refund_policy.invoke({"product_type": "electronics", "days_since_purchase": 30})
    assert "not eligible" in out.lower()


def test_check_refund_policy_gift_longer_window():
    out = check_refund_policy.invoke({"product_type": "gift", "days_since_purchase": 35})
    assert "eligible" in out.lower()


def test_escalate_to_human():
    out = escalate_to_human.invoke({"reason": "duplicate charge"})
    assert "escalated" in out.lower()
    assert "duplicate charge" in out.lower()
