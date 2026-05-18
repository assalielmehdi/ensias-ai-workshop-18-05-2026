"""CLI entrypoint: run sample tickets through the workflow or the agent.

Usage:
    uv run python -m support_bot.main --mode workflow
    uv run python -m support_bot.main --mode agent
    uv run python -m support_bot.main --mode agent --ticket T-003
    uv run python -m support_bot.main --mode workflow --message "..."

This file is intentionally simple — its job is to show students that the
graphs are plain Python you can call from anywhere.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agent_graph import run_agent
from .config import settings
from .models import TicketRequest, TicketResponse
from .workflow_graph import run_workflow

console = Console()
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_sample_tickets() -> list[dict[str, Any]]:
    with (DATA_DIR / "tickets.json").open() as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a support ticket through the bot.")
    p.add_argument("--mode", choices=["workflow", "agent"], default="workflow")
    p.add_argument(
        "--ticket",
        help="Sample ticket id (e.g. T-001). If omitted, all samples are run.",
    )
    p.add_argument("--message", help="Inline ticket message instead of a sample.")
    p.add_argument("--order-id", help="Optional order id for an inline message.")
    p.add_argument("--customer-id", help="Optional customer id for an inline message.")
    return p.parse_args()


def render(req: TicketRequest, resp: TicketResponse) -> None:
    console.print(Panel.fit(req.message, title="Customer", border_style="cyan"))
    table = Table(show_header=False, box=None)
    table.add_row("[bold]Category[/]", resp.category.value)
    table.add_row("[bold]Urgency[/]", resp.urgency.value)
    table.add_row("[bold]Needs human[/]", str(resp.needs_human))
    table.add_row("[bold]Tools used[/]", ", ".join(resp.tools_used) or "-")
    table.add_row("[bold]Reasoning[/]", resp.reasoning_summary)
    console.print(table)
    console.print(Panel.fit(resp.customer_response, title="Bot reply", border_style="green"))


def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    args = parse_args()
    runner = run_workflow if args.mode == "workflow" else run_agent
    console.rule(f"[bold]Mode: {args.mode}  |  LLM: {settings.llm_mode}")

    if args.message:
        req = TicketRequest(
            message=args.message, order_id=args.order_id, customer_id=args.customer_id
        )
        render(req, runner(req))
        return

    samples = load_sample_tickets()
    if args.ticket:
        samples = [s for s in samples if s["id"] == args.ticket]
        if not samples:
            console.print(f"[red]No sample ticket with id {args.ticket}[/]")
            return
    for s in samples:
        console.rule(f"[bold blue]{s['id']} — {s['label']}")
        req = TicketRequest(
            message=s["message"], customer_id=s.get("customer_id"), order_id=s.get("order_id")
        )
        render(req, runner(req))


if __name__ == "__main__":
    main()
