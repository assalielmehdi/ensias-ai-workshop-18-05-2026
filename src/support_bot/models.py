"""Pydantic models — the typed contract between every layer of the bot.

Keep these small and self-explanatory. Every layer (graphs, API, tests) speaks
in these types, which is what makes the system easy to reason about.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TicketCategory(str, Enum):
    REFUND_REQUEST = "refund_request"
    DELIVERY_ISSUE = "delivery_issue"
    BILLING_ISSUE = "billing_issue"
    TECHNICAL_ISSUE = "technical_issue"
    GENERAL_QUESTION = "general_question"
    ESCALATION_REQUIRED = "escalation_required"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TicketRequest(BaseModel):
    """Input from the customer / API client."""

    message: str = Field(..., description="Raw ticket text from the customer.")
    customer_id: Optional[str] = Field(None, description="Optional customer id.")
    order_id: Optional[str] = Field(None, description="Optional order reference.")


class TicketResponse(BaseModel):
    """Structured output from either the workflow or the agent."""

    category: TicketCategory
    urgency: Urgency
    customer_response: str = Field(..., description="The reply we would send to the customer.")
    needs_human: bool = Field(..., description="True if a human must take over.")
    tools_used: list[str] = Field(default_factory=list)
    reasoning_summary: str = Field(
        ...,
        description="Short, user-safe explanation of how the bot decided. Never leak chain-of-thought.",
    )


class TicketRequestWithMode(TicketRequest):
    """Convenience body for POST /tickets — picks workflow vs agent."""

    mode: Literal["workflow", "agent"] = "workflow"
