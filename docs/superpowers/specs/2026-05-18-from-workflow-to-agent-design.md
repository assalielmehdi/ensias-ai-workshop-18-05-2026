# From Workflow to Agent — Workshop Repo Design

**Date:** 2026-05-18
**Repo:** `from-workflow-to-agent`
**Audience:** Undergraduate SWE students, 2-hour workshop.

## Goal

Teach the difference between an *agentic workflow* (predefined LLM-using pipeline) and a *true agent* (LLM-driven loop with tools) by building a customer-support ticket triage bot first as the former, then refactoring to the latter. Add production guardrails and a FastAPI entrypoint along the way.

## Narrative Arc (mirrors workshop timing)

1. **Workflow v1** — fixed LangGraph: `classify → route → retrieve → draft → safety`. Predictable, hard to extend.
2. **Limitations demo** — multi-intent, missing-info, and policy-edge tickets break the pipeline.
3. **Agent v2** — LangGraph ReAct loop: `agent ↔ tools`, max 6 iterations.
4. **Backend service** — FastAPI exposes `/health`, `/workflow/tickets`, `/agent/tickets`, `/tickets`.
5. **Guardrails** — refund tool returns eligibility (never approves), safety check forces human escalation on legal/threat language, agent iteration cap, structured logging, eval set, tests.

## Tech & Defaults

- Python 3.13, `uv` for env/lockfile management.
- LLM client: `langchain-openai.ChatOpenAI` pointed at any OpenAI-compatible base URL.
- Default provider: OpenRouter (`https://openrouter.ai/api/v1`), default model `deepseek/deepseek-v3.2`.
- `LLM_MODE` env var: `mock` (deterministic stub), `openrouter` (default), `openai` (any OpenAI-compatible).
- Mock mode lets tests + demos run with no API key.

## Module Map

| File | Purpose |
|---|---|
| `config.py` | `pydantic-settings` Settings (.env loaded) |
| `models.py` | Pydantic types: `TicketRequest`, `TicketResponse`, `TicketCategory`, `Urgency` enums |
| `tools.py` | Four LangChain tools backed by `data/*.json` and `knowledge_base.md` |
| `prompts.py` | System prompts (classifier, drafter, safety, agent) |
| `workflow_graph.py` | Fixed 5-node LangGraph |
| `agent_graph.py` | LangGraph agent loop (LLM ↔ tools, capped) |
| `api.py` | FastAPI app, 4 endpoints, shared response shape |
| `main.py` | CLI runner with rich output, `--mode {workflow,agent}` |
| `evals.py` | Runs 5 sample tickets through both, prints comparison |

## Tools

- `search_knowledge_base(query)` — keyword search over `data/knowledge_base.md`.
- `check_order_status(order_id)` — lookup in `data/orders.json`.
- `check_refund_policy(product_type, days_since_purchase)` — returns *eligibility*, never an approval.
- `escalate_to_human(reason)` — flags ticket for human and stops the loop.

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| POST | `/workflow/tickets` | `TicketRequest` | `TicketResponse` |
| POST | `/agent/tickets` | `TicketRequest` | `TicketResponse` |
| POST | `/tickets` | `TicketRequest + {"mode":"workflow"\|"agent"}` | `TicketResponse` |

`TicketResponse` = `{category, urgency, customer_response, needs_human, tools_used, reasoning_summary}`.

## Checkpoint Branches

Linear forward progression on `main`. Each `step-XX-*` branch is a tag of the corresponding commit on main.

- `step-00-starter` — scaffolding, data, TODOs, no working logic.
- `step-01-workflow-chatbot` — workflow_graph.py + supporting modules.
- `step-02-workflow-limitations` — demo script with broken cases.
- `step-03-agent-loop` — agent_graph.py.
- `step-04-fastapi-entrypoint` — api.py + main.py.
- `step-05-production-guardrails` — logging, guardrails, evals, full tests.
- `main` — complete working version + slides + README + workshop.md.

## Guardrails (step-05)

- Refund tool returns `{eligible: bool, reason: str}`, NEVER approves payment.
- Safety node detects legal/threat keywords → forces `needs_human=true`.
- Agent loop has `MAX_ITER=6`; on overflow returns structured fallback that escalates.
- All LLM calls and tool invocations logged via `logging` (one JSON-ish line each).
- API responses never leak internal reasoning verbatim — `reasoning_summary` is sanitized.

## Slides (`slides/index.html`)

16-slide hand-rolled HTML deck: one `<section>` per slide, arrow keys for nav, `n` toggles speaker notes drawer. SVG diagrams inline. Zero external dependencies.

## Out of Scope

- No real payment integration.
- No persistent ticket store (in-memory only).
- No auth on FastAPI endpoints.
- No streaming responses.
