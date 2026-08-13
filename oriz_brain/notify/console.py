"""Console/stdout notifier — always available, no deps."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from oriz_brain.decision_log import Decision

_console = Console()


class ConsoleNotifier:
    def send(self, decision: Decision) -> None:
        body = (
            f"[bold]Source:[/bold] {decision.source}\n"
            f"[bold]Observation:[/bold] {decision.observation}\n"
            f"[bold]Reasoning:[/bold] {decision.reasoning}\n"
            f"[bold]Action:[/bold] {decision.action}"
        )
        _console.print(Panel(body, title=f"[green]MATTERS[/green] — {decision.ts}", expand=False))
