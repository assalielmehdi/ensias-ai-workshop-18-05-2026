"""Show where the fixed workflow falls short.

Run with: `uv run python -m support_bot.workflow_demo`

Each sample ticket is annotated with the *expected* behaviour and a short note
on what the workflow can't do about it. This is the bridge into step-03,
where we rebuild the bot as a true agent loop.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.table import Table

from .config import settings
from .models import TicketRequest
from .workflow_graph import run_workflow

console = Console()


CASES = [
    {
        "id": "T-001",
        "label": "happy_path_refund",
        "message": "Hi, I ordered headphones last week. They arrived broken. I want a refund. Order ID: ORD-1007.",
        "order_id": "ORD-1007",
        "note": "Workflow handles this fine — the order ID + KB are enough.",
    },
    {
        "id": "T-002",
        "label": "missing_information",
        "message": "My package never arrived and I need this fixed ASAP.",
        "order_id": None,
        "note": "Workflow drafts a 'please send your order ID' reply, but has no way to react when the customer answers. An agent could ask, then call check_order_status.",
    },
    {
        "id": "T-003",
        "label": "multi_intent",
        "message": "I was charged twice, and the item also arrived damaged.",
        "order_id": "ORD-1003",
        "note": "Workflow classifies as ONE category. Half the problem (billing OR damage) goes unaddressed.",
    },
    {
        "id": "T-004",
        "label": "policy_edge_case",
        "message": "I bought this as a gift, it arrived late, and now the return window may be over. Can you help?",
        "order_id": "ORD-1012",
        "note": "Real answer needs check_refund_policy('gift', X). Workflow doesn't decide to call it dynamically.",
    },
    {
        "id": "T-005",
        "label": "high_risk_escalation",
        "message": "I'm furious. I was charged twice and I'm considering legal action.",
        "order_id": None,
        "note": "Workflow safety_check catches this via keyword rule. An agent would call escalate_to_human directly on turn 1.",
    },
]


def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    table = Table(title=f"Workflow output  |  LLM={settings.llm_mode}")
    table.add_column("ID")
    table.add_column("Category")
    table.add_column("Needs\nhuman", justify="center")
    table.add_column("Tools used")
    table.add_column("Limitation", overflow="fold")

    for case in CASES:
        req = TicketRequest(message=case["message"], order_id=case["order_id"])
        out = run_workflow(req)
        table.add_row(
            case["id"],
            out.category.value,
            "✓" if out.needs_human else "—",
            ", ".join(out.tools_used) or "-",
            case["note"],
        )
    console.print(table)
    console.print(
        "\n[bold yellow]Takeaway:[/] the workflow does fine on predictable cases, "
        "but cannot react to tool outputs or handle multi-intent tickets. "
        "Move on to [bold]step-03-agent-loop[/]."
    )


if __name__ == "__main__":
    main()
