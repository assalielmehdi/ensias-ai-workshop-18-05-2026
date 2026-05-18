# Workshop guide — From Workflow to Agent

A step-by-step companion to the slides. Each section maps to a checkpoint branch.

> **How to use this guide:** read the section, then run the listed commands. Look for `TODO` checkpoints — those are deliberate gaps where you (the student) write a few lines yourself. The fully-working answer is in the next branch.

## Prerequisites (5 min before starting)

```bash
git clone git@github.com:assalielmehdi/ensias-ai-workshop-18-05-2026.git
cd ensias-ai-workshop-18-05-2026
git fetch --all
uv sync --extra dev
cp .env.example .env
# Leave LLM_MODE=mock for now — no key required.
uv run pytest   # confirm baseline
```

If `uv` isn't installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## 0:00 – 0:10 — Business problem and goal (slides 1–3)

Acme E-Commerce is drowning in support tickets. We're going to build an AI assistant that:

- classifies each ticket,
- gathers context (KB, order info, refund policy),
- drafts a reply,
- escalates risky cases to a human.

We'll build it **twice**: first as a fixed workflow, then as a true agent.

```bash
git checkout step-00-starter
ls src/support_bot/
```

You'll see the scaffolding: typed models, prompts, tools, two empty graphs, and a stub FastAPI app. Nothing runs yet — that's intentional.

---

## 0:10 – 0:25 — Workflow vs Agent (slides 4–5, 8)

Read the two concept slides. Key sentence:

> **Workflows** orchestrate LLMs and tools through *predefined code paths*.
> **Agents** let the LLM *dynamically direct* its own process and tool usage.

Both can use tools. The difference is *who decides what comes next*.

---

## 0:25 – 0:45 — Build the workflow chatbot

```bash
git checkout step-01-workflow-chatbot
```

This branch has the workflow filled in. Read `src/support_bot/workflow_graph.py` top to bottom — it's <150 lines. The shape is:

```
START → classify_ticket → route_by_category → retrieve_context → draft_response → safety_check → END
```

**TODO checkpoints you should look for:**
- `classify_ticket` parses LLM JSON output. What happens if the model returns malformed JSON? (Look at `_safe_json`.)
- `retrieve_context` calls tools deterministically. Notice we always call the KB, and only call `check_order_status` when the customer provided an order ID.
- `safety_check` swaps the draft for a boilerplate when escalation is needed. Why don't we just send the LLM's reply?

**Run it:**

```bash
uv run python -m support_bot.main --mode workflow --ticket T-001
```

You should see a structured response with `category=refund_request` and tools used.

---

## 0:45 – 0:55 — Workflow limitations (slide 7)

```bash
git checkout step-02-workflow-limitations
uv run python -m support_bot.main --mode workflow
```

This runs all five sample tickets through the workflow. Watch what happens to:

- **T-002 (missing info)** — drafts a "please give me the order ID" reply, but has no way to react when the customer answers.
- **T-003 (multi-intent: charged twice + damaged)** — classified as one thing. Half the problem is ignored.
- **T-004 (gift, late, return window)** — calls the KB blindly; never calls `check_refund_policy` because the static `retrieve_context` step doesn't know it should.

**TODO discussion:** could you fix these in the workflow? Yes — by adding more branches. But each branch makes the graph harder to reason about, and you still can't react to *what a tool returned*.

That's the cue to move to an agent.

---

## 0:55 – 1:20 — Rebuild as an agent loop (slides 9–11)

```bash
git checkout step-03-agent-loop
```

Open `src/support_bot/agent_graph.py`. The whole graph is ~30 lines:

```python
builder.add_node("agent", agent_node)
builder.add_node("tools", ToolNode(ALL_TOOLS))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue,
                              {"tools": "tools", "end": END})
builder.add_edge("tools", "agent")
```

**TODO checkpoints:**
1. **`agent_node`** binds the tools (`llm.bind_tools(ALL_TOOLS)`) so the model knows they exist. The tool *docstrings* are what the LLM reads — open `tools.py` and read each one out loud.
2. **`should_continue`** returns `"tools"` if the last AI message has tool calls, `"end"` otherwise. *And* it enforces a hard iteration cap.
3. **`_parse_final`** rescues a JSON object out of the model's reply, tolerating prose around it.

**Run it on the same tickets:**

```bash
uv run python -m support_bot.main --mode agent
```

Compare:

| Ticket | Workflow | Agent |
|---|---|---|
| T-001 (refund) | classifies, drafts | calls `check_order_status` AND `check_refund_policy` |
| T-002 (missing info) | drafts a generic ask | asks for the order ID specifically |
| T-003 (multi-intent) | misses half | escalates duplicate charge |
| T-005 (legal threat) | safety node catches it | agent calls `escalate_to_human` immediately |

---

## 1:20 – 1:35 — Expose the bot through FastAPI (slide 12)

```bash
git checkout step-04-fastapi-entrypoint
uv run uvicorn support_bot.api:app --reload
```

Then in another shell:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/agent/tickets \
  -H 'content-type: application/json' \
  -d '{"message":"My headphones arrived broken. Order ORD-1007."}'
```

Or open <http://localhost:8000/docs> and use the Swagger UI.

**TODO checkpoint:** notice how thin `api.py` is. The graphs are reusable Python — the API is just a Pydantic-typed envelope around them. This is exactly how you'd ship a real AI feature.

---

## 1:35 – 1:50 — Production guardrails (slide 13)

```bash
git checkout step-05-production-guardrails
uv run pytest
uv run python -m support_bot.evals
```

What this branch adds:

- **Structured logging** of every LLM call and tool call (`tool=X args=...`).
- **Iteration cap** (`AGENT_MAX_ITERATIONS=6`) with a safe fallback that escalates.
- **`evals.py`** — runs all five sample tickets through both versions, scores them, writes `eval_results.json`.
- **22 tests** in `tests/` — tools, workflow, agent, API. All run in `LLM_MODE=mock` so no key/network needed.

**TODO discussion:**
- The refund tool only returns *eligibility*. Why is "agent approves refund automatically" a bad idea even when the policy clearly allows it?
- The agent's iteration cap exists because LLMs *will* loop forever if you let them. What would you do if the cap is hit in production? (We escalate to a human and log it.)

---

## 1:50 – 2:00 — Final demo and takeaways (slides 14–16)

Switch to `main` (the complete version) and run the full demo:

```bash
git checkout main

# CLI demo, both modes
uv run python -m support_bot.main --mode workflow
uv run python -m support_bot.main --mode agent

# API demo
uv run uvicorn support_bot.api:app --reload &
curl -X POST http://localhost:8000/tickets \
  -H 'content-type: application/json' \
  -d '{"message":"I was charged twice and I am considering legal action.","mode":"agent"}'

# Eval comparison
uv run python -m support_bot.evals

# Tests
uv run pytest
```

**Takeaway:**

> Not every AI system that uses tools is an agent. **Start with a workflow when the path is predictable. Use an agent when the system must dynamically decide what to do next based on observations.**

**Stretch goals (homework):**

1. Plug a real LLM into `.env` — set `LLM_MODE=openrouter` and your `LLM_API_KEY`. Watch the eval table change.
2. Add a fifth tool: `create_return_label(order_id, reason)` (it can be a stub that writes to a JSON file). Update the agent prompt to use it.
3. Replace the keyword KB search with a vector store (FAISS / Chroma). Compare.
4. Add structured tracing — try LangSmith or OpenTelemetry. See where the agent spends tokens.
5. Add an HTTP retry policy for the real LLM, including a circuit breaker.
