"""Tiny eval harness: run the same tickets through both versions of the bot.

The point isn't to "score" the LLM — it's to make the comparison visible.
After running it, students should be able to see *which* tickets the workflow
gets wrong and *how* the agent does better (or sometimes worse).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agent_graph import run_agent
from .config import settings
from .models import TicketRequest, TicketResponse
from .workflow_graph import run_workflow

console = Console()
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass
class EvalCase:
    id: str
    label: str
    message: str
    customer_id: str | None
    order_id: str | None
    # Expectations (rough; used for the "✓ / ✗" column).
    expected_category: str
    expected_needs_human: bool


CASES: list[EvalCase] = [
    EvalCase(
        id="T-001",
        label="happy_path_refund",
        message="Hi, I ordered headphones last week. They arrived broken. I want a refund. Order ID: ORD-1007.",
        customer_id="CUST-509",
        order_id="ORD-1007",
        expected_category="refund_request",
        expected_needs_human=True,
    ),
    EvalCase(
        id="T-002",
        label="missing_information",
        message="My package never arrived and I need this fixed ASAP.",
        customer_id=None,
        order_id=None,
        expected_category="delivery_issue",
        expected_needs_human=False,
    ),
    EvalCase(
        id="T-003",
        label="multi_intent",
        message="I was charged twice, and the item also arrived damaged.",
        customer_id="CUST-502",
        order_id="ORD-1003",
        expected_category="billing_issue",
        expected_needs_human=True,
    ),
    EvalCase(
        id="T-004",
        label="policy_edge_case",
        message="I bought this as a gift, it arrived late, and now the return window may be over. Can you help?",
        customer_id="CUST-515",
        order_id="ORD-1012",
        expected_category="refund_request",
        expected_needs_human=False,
    ),
    EvalCase(
        id="T-005",
        label="high_risk_escalation",
        message="I'm furious. I was charged twice and I'm considering legal action.",
        customer_id=None,
        order_id=None,
        expected_category="escalation_required",
        expected_needs_human=True,
    ),
]


def _score(resp: TicketResponse, case: EvalCase) -> tuple[str, str]:
    cat_ok = "✓" if resp.category.value == case.expected_category else "✗"
    esc_ok = "✓" if resp.needs_human == case.expected_needs_human else "✗"
    return cat_ok, esc_ok


def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    table = Table(title=f"Workflow vs Agent  |  LLM={settings.llm_mode}")
    table.add_column("ID")
    table.add_column("Label")
    table.add_column("W cat")
    table.add_column("W esc")
    table.add_column("W tools")
    table.add_column("A cat")
    table.add_column("A esc")
    table.add_column("A tools")

    rows = []
    for case in CASES:
        req = TicketRequest(
            message=case.message, customer_id=case.customer_id, order_id=case.order_id
        )
        wf = run_workflow(req)
        ag = run_agent(req)
        w_cat, w_esc = _score(wf, case)
        a_cat, a_esc = _score(ag, case)
        table.add_row(
            case.id,
            case.label,
            f"{w_cat} {wf.category.value}",
            f"{w_esc} {wf.needs_human}",
            ", ".join(wf.tools_used) or "-",
            f"{a_cat} {ag.category.value}",
            f"{a_esc} {ag.needs_human}",
            ", ".join(ag.tools_used) or "-",
        )
        rows.append(
            {
                "case": asdict(case),
                "workflow": wf.model_dump(mode="json"),
                "agent": ag.model_dump(mode="json"),
            }
        )

    console.print(table)
    out = Path("eval_results.json")
    out.write_text(json.dumps(rows, indent=2, default=str))
    console.print(f"[dim]Full results written to {out}[/]")


if __name__ == "__main__":
    main()
