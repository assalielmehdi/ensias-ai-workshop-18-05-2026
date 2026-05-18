"""STARTER STUB — to be expanded in step-01 and step-03.

The CLI entrypoint. In the final version it loads sample tickets and runs them
through either the workflow or the agent. In this starter step it just prints
a friendly reminder.
"""

from __future__ import annotations

from rich.console import Console

console = Console()


def main() -> None:
    console.print(
        "[yellow]The CLI is not wired up yet.[/]\n"
        "Switch to [bold]step-01-workflow-chatbot[/] (workflow mode) "
        "or [bold]step-03-agent-loop[/] (agent mode) to try it."
    )


if __name__ == "__main__":
    main()
