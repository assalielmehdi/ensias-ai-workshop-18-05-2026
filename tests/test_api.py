"""Tests for the FastAPI surface (uses TestClient, no network)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from support_bot.api import app


client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm_mode" in body


def test_workflow_endpoint_returns_typed_response():
    r = client.post(
        "/workflow/tickets",
        json={
            "message": "My headphones arrived broken, I want a refund.",
            "order_id": "ORD-1007",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "refund_request"
    assert "search_knowledge_base" in body["tools_used"]


def test_agent_endpoint_escalates_legal_threat():
    r = client.post(
        "/agent/tickets",
        json={"message": "I'm considering legal action against your company."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["needs_human"] is True
    assert body["category"] == "escalation_required"


def test_tickets_convenience_endpoint_workflow_mode():
    r = client.post(
        "/tickets",
        json={"message": "Do you sell gift cards?", "mode": "workflow"},
    )
    assert r.status_code == 200
    assert r.json()["category"] in {"general_question", "refund_request"}


def test_tickets_convenience_endpoint_agent_mode():
    r = client.post(
        "/tickets",
        json={
            "message": "My headphones arrived broken, I want a refund. Order ORD-1007.",
            "order_id": "ORD-1007",
            "mode": "agent",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "refund_request"
    assert "check_order_status" in body["tools_used"]
