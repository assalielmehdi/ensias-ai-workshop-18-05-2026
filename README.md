# From Workflow to Agent: Building a Customer Support AI Assistant

A 2-hour, hands-on workshop that teaches the difference between an **agentic workflow** (predefined LLM-using pipeline) and a **true agent** (LLM-driven loop with tools), by building a realistic customer-support ticket triage bot for a small e-commerce company.

> **Big idea:** Not every AI system that uses tools is an agent. *Start with a workflow when the path is predictable. Use an agent when the system must dynamically decide what to do next based on observations.*

## Learning objectives

By the end of the workshop you will be able to:

- Explain the difference between an agentic workflow and a true agent (Anthropic's *Building Effective Agents* framing).
- Build a fixed LangGraph workflow with classify → route → retrieve → draft → safety nodes.
- Build a LangGraph agent loop with tool-calling and a hard iteration cap.
- Identify *when* a workflow is enough and *when* an agent is justified.
- Expose an AI bot as a real backend service via FastAPI.
- Add production-minded guardrails: structured output, logging, human-in-the-loop, evals, tests.

## Tech stack

- Python 3.13, [uv](https://github.com/astral-sh/uv)
- LangChain + LangGraph
- FastAPI + Uvicorn
- Pydantic + pydantic-settings + python-dotenv
- pytest, rich
- LLM provider: any OpenAI-compatible API (default: OpenRouter with `deepseek/deepseek-v3.2`). A built-in **mock mode** lets the whole repo run with zero API keys.

## Setup

```bash
git clone git@github.com:assalielmehdi/ensias-ai-workshop-18-05-2026.git
cd ensias-ai-workshop-18-05-2026
uv sync --extra dev
cp .env.example .env
# Edit .env: set LLM_MODE=mock to run without a key, or paste your key.
```

Python 3.13 is required (managed automatically by `uv`).

## Environment variables

See [`.env.example`](.env.example). The most important one:

```ini
LLM_MODE=mock   # or "openrouter", or "openai"
LLM_API_KEY=...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=deepseek/deepseek-v3.2
```

`LLM_MODE=mock` returns deterministic stub responses and is what tests and first-time demos use.

## Run the FastAPI server

```bash
uv run uvicorn support_bot.api:app --reload
```

Then in another shell:

```bash
# Health check
curl http://localhost:8000/health

# Workflow version
curl -X POST http://localhost:8000/workflow/tickets \
  -H 'content-type: application/json' \
  -d '{"message":"My headphones arrived broken, I want a refund.","order_id":"ORD-1007"}'

# Agent version
curl -X POST http://localhost:8000/agent/tickets \
  -H 'content-type: application/json' \
  -d '{"message":"My headphones arrived broken, I want a refund. Order ID: ORD-1007."}'

# Convenience endpoint (pick mode in the body)
curl -X POST http://localhost:8000/tickets \
  -H 'content-type: application/json' \
  -d '{"message":"I was charged twice.","mode":"agent"}'
```

The OpenAPI docs live at <http://localhost:8000/docs>.

## Run CLI demos

```bash
uv run python -m support_bot.main --mode workflow
uv run python -m support_bot.main --mode agent
uv run python -m support_bot.main --mode agent --ticket T-003
uv run python -m support_bot.main --mode workflow --message "Hello, do you sell gift cards?"
```

## Compare workflow vs agent

```bash
uv run python -m support_bot.evals
```

Prints a table and writes `eval_results.json`.

## Run tests

```bash
uv run pytest
```

All tests run in mock-LLM mode — no API key required, no network calls.

## Lint, format, and type-check

The repo ships with [ruff](https://docs.astral.sh/ruff/) (linter + formatter) and [ty](https://docs.astral.sh/ty/) (Astral's type checker). Configuration lives in `pyproject.toml`.

```bash
uv run ruff check        # lint
uv run ruff check --fix  # lint + autofix
uv run ruff format       # format
uv run ty check src      # type-check
```

All three are green on `main` — `pytest && ruff check && ty check src` is the full pre-commit sequence.

## Workshop slides

Open [`slides/index.html`](slides/index.html) in any browser. Arrow keys to navigate, press `n` to toggle speaker notes.

## Repository structure

```
.
├── data/                       # KB, sample orders, sample tickets
├── slides/                     # Browser-based presentation (offline)
├── src/support_bot/
│   ├── config.py               # pydantic-settings config (.env)
│   ├── models.py               # TicketRequest / TicketResponse / enums
│   ├── tools.py                # Four tools (KB search, order, refund policy, escalate)
│   ├── prompts.py              # All system prompts in one place
│   ├── llm.py                  # LLM factory: real (OpenAI-compatible) + mock
│   ├── workflow_graph.py       # Fixed LangGraph: classify → route → retrieve → draft → safety
│   ├── agent_graph.py          # LangGraph agent loop with tools + iteration cap
│   ├── api.py                  # FastAPI app
│   ├── main.py                 # CLI runner
│   └── evals.py                # Workflow vs agent comparison harness
├── tests/                      # pytest, all in mock mode
├── pyproject.toml
├── README.md
└── workshop.md                 # Step-by-step instructor/student guide
```

## Branch / checkpoint guide

Every step of the workshop has its own branch. Checkout the one you want and you have a fully runnable version of that checkpoint.

| Branch | What you get |
|---|---|
| `step-00-starter` | Scaffolding, data, prompts, TODOs. Nothing runs yet. |
| `step-01-workflow-chatbot` | Working fixed LangGraph workflow. |
| `step-02-workflow-limitations` | Same workflow + a demo that shows where it breaks. |
| `step-03-agent-loop` | LangGraph agent loop using the same tools. |
| `step-04-fastapi-entrypoint` | FastAPI server wraps both versions. |
| `step-05-production-guardrails` | Logging, iteration cap, full test suite, evals. |
| `main` | Final, complete version (same as step-05 plus slides + final docs). |

To checkout a step:

```bash
git checkout step-03-agent-loop
```

## Workshop guide

The full step-by-step is in [workshop.md](workshop.md).
