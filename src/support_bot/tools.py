"""Tools the bot can call.

Each tool is a small, pure function with a clear docstring. The docstring is
what the LLM sees when it decides whether to call the tool, so it must
describe inputs, outputs, and when the tool is useful.

We use LangChain's @tool decorator so the same functions plug into the agent
without any extra glue. The workflow version calls these tools directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# Small helpers ------------------------------------------------------------


def _load_orders() -> dict[str, dict[str, Any]]:
    with (DATA_DIR / "orders.json").open() as f:
        return json.load(f)


def _load_knowledge_base() -> str:
    return (DATA_DIR / "knowledge_base.md").read_text()


# Tools --------------------------------------------------------------------


@tool
def search_knowledge_base(query: str) -> str:
    """Search the support knowledge base for policies, procedures, and FAQ entries.

    Use this when the customer asks about refund rules, shipping times,
    billing behaviour, technical fixes, or anything policy-related.

    Args:
        query: A short keyword query (e.g. "refund electronics", "duplicate charge").

    Returns:
        Up to three matching paragraphs from the KB, or a "no matches" string.
    """
    logger.info("tool=search_knowledge_base query=%r", query)
    kb = _load_knowledge_base()
    paragraphs = [p.strip() for p in kb.split("\n\n") if p.strip()]
    terms = [t.lower() for t in query.split() if len(t) > 2]
    scored = []
    for p in paragraphs:
        lower = p.lower()
        score = sum(1 for t in terms if t in lower)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return "No matching entries found in the knowledge base."
    return "\n\n---\n\n".join(p for _, p in scored[:3])


@tool
def check_order_status(order_id: str) -> str:
    """Look up an order by its ID and return its current status and contents.

    Use this whenever the customer mentions an order ID (e.g. "ORD-1007").

    Args:
        order_id: The full order id, including the "ORD-" prefix.

    Returns:
        A short human-readable summary, or "Order not found" if the id is unknown.
    """
    logger.info("tool=check_order_status order_id=%r", order_id)
    orders = _load_orders()
    order = orders.get(order_id.strip().upper())
    if not order:
        return f"Order not found: {order_id}"
    items = ", ".join(f"{i['qty']}x {i['name']}" for i in order["items"])
    delivered = order.get("delivered_at") or "not yet delivered"
    return (
        f"Order {order['order_id']} — status: {order['status']}, "
        f"ordered: {order['ordered_at']}, delivered: {delivered}, "
        f"items: {items}, total: ${order['total_usd']:.2f}"
    )


@tool
def check_refund_policy(product_type: str, days_since_purchase: int) -> str:
    """Check whether a product is eligible for a refund based on category and age.

    IMPORTANT: this tool only tells you about *eligibility*. It does NOT
    approve a refund. Approvals must be made by a human after this check.

    Args:
        product_type: One of "electronics", "apparel", "accessory", "gift",
            "perishable", or "personalized".
        days_since_purchase: How many days ago the customer received the item.

    Returns:
        A short eligibility verdict including the relevant policy window.
    """
    logger.info(
        "tool=check_refund_policy product_type=%r days_since_purchase=%d",
        product_type,
        days_since_purchase,
    )
    pt = product_type.lower().strip()
    if pt in {"perishable", "personalized"}:
        return (
            f"Not eligible: {pt} items are non-refundable except when damaged on arrival. "
            "A human teammate must confirm any exception."
        )
    if pt == "gift":
        window = 45
    elif pt == "electronics":
        window = 14
    else:
        window = 30
    if days_since_purchase <= window:
        return (
            f"Eligible: {pt} items are returnable within {window} days; the customer is "
            f"at day {days_since_purchase}. A human must approve the actual refund."
        )
    return (
        f"Not eligible by standard policy: {pt} items must be returned within {window} days; "
        f"the customer is at day {days_since_purchase}. A human may grant an exception."
    )


@tool
def escalate_to_human(reason: str) -> str:
    """Flag this ticket for a human teammate and stop trying to resolve it automatically.

    Use this when:
    - The customer mentions legal action, lawsuits, or threats.
    - You detect a duplicate-charge complaint that needs billing access.
    - Information is missing AND the customer is highly distressed.
    - The customer explicitly asks for a manager.

    Args:
        reason: A short, internal-facing reason (e.g. "legal threat", "duplicate charge").

    Returns:
        A confirmation string. After calling this, return a final reply that
        tells the customer a human teammate will follow up shortly.
    """
    logger.info("tool=escalate_to_human reason=%r", reason)
    return f"Ticket escalated to a human teammate. Reason: {reason}"


# Convenient list for the agent graph --------------------------------------

ALL_TOOLS = [
    search_knowledge_base,
    check_order_status,
    check_refund_policy,
    escalate_to_human,
]
