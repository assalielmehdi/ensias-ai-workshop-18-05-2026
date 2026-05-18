"""FastAPI app — the bot exposed as a backend service.

We keep this file thin on purpose: the API is just a typed envelope around
`run_workflow` and `run_agent`. The interesting code lives in the graphs.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .agent_graph import run_agent
from .config import settings
from .models import (
    TicketCategory,
    TicketRequest,
    TicketRequestWithMode,
    TicketResponse,
    Urgency,
)
from .workflow_graph import run_workflow

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Support Bot",
    description="From Workflow to Agent — customer support AI assistant.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""

    return {"status": "ok", "llm_mode": settings.llm_mode, "model": settings.llm_model}


@app.post("/workflow/tickets", response_model=TicketResponse)
def workflow_tickets(req: TicketRequest) -> TicketResponse:
    """Run the fixed workflow version of the bot."""

    logger.info("POST /workflow/tickets order_id=%s", req.order_id)
    try:
        return run_workflow(req)
    except Exception as exc:
        logger.exception("workflow failed")
        return _safe_fallback(str(exc))


@app.post("/agent/tickets", response_model=TicketResponse)
def agent_tickets(req: TicketRequest) -> TicketResponse:
    """Run the agent-loop version of the bot."""

    logger.info("POST /agent/tickets order_id=%s", req.order_id)
    try:
        return run_agent(req)
    except Exception as exc:
        logger.exception("agent failed")
        return _safe_fallback(str(exc))


@app.post("/tickets", response_model=TicketResponse)
def tickets(req: TicketRequestWithMode) -> TicketResponse:
    """Convenience endpoint: pick workflow or agent via a `mode` field."""

    base = TicketRequest(message=req.message, customer_id=req.customer_id, order_id=req.order_id)
    if req.mode == "workflow":
        return workflow_tickets(base)
    if req.mode == "agent":
        return agent_tickets(base)
    raise HTTPException(status_code=400, detail=f"unknown mode: {req.mode}")


def _safe_fallback(_internal_error: str) -> TicketResponse:
    """Never leak stack traces to the customer. Escalate instead."""

    return TicketResponse(
        category=TicketCategory.ESCALATION_REQUIRED,
        urgency=Urgency.HIGH,
        customer_response=(
            "Sorry — something went wrong on our side. A human teammate will "
            "follow up with you shortly."
        ),
        needs_human=True,
        tools_used=[],
        reasoning_summary="Internal error; escalated to human.",
    )
