"""STARTER STUB — to be filled in during step-04-fastapi-entrypoint.

Goal: expose the bot as a FastAPI service:

    GET  /health
    POST /workflow/tickets
    POST /agent/tickets
    POST /tickets            (convenience, mode in body)

TODOs for students:
1. Create a `FastAPI()` app.
2. Add `/health` returning {"status": "ok"}.
3. Add the three POST endpoints — each takes the typed model and returns
   `TicketResponse`. The body is the work; just call `run_workflow` / `run_agent`.

See workshop.md (section "1:20 – 1:35") for the walkthrough.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Support Bot — starter",
    description="The endpoints are not implemented yet. See step-04.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "note": "Endpoints not implemented in step-00. See step-04-fastapi-entrypoint."}
