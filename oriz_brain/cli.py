"""CLI — brain run | brain log | brain sources | brain predict | brain resolve | brain score."""

from __future__ import annotations

from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="ChiragOS ambient brain", no_args_is_help=True)
_console = Console()


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip notify; still logs decisions"),
) -> None:
    """One ambient cycle: ingest all sources -> reason -> log -> notify."""
    from oriz_brain.notify.console import ConsoleNotifier
    from oriz_brain.notify.telegram import TelegramNotifier
    from oriz_brain.pipeline import run_cycle
    from oriz_brain.sources import all_adapters

    notifier = ConsoleNotifier() if dry_run else TelegramNotifier()
    decisions = run_cycle(all_adapters(), notifier=notifier)

    table = Table(title="Cycle results", show_header=True)
    table.add_column("Source")
    table.add_column("Verdict")
    table.add_column("Action")
    for d in decisions:
        color = "green" if d.verdict == "matters" else "dim"
        table.add_row(d.source, f"[{color}]{d.verdict}[/{color}]", d.action)
    _console.print(table)


@app.command(name="log")
def log_cmd(n: int = typer.Option(20, "--n", help="Lines to show")) -> None:
    """Show recent decision log."""
    from oriz_brain.decision_log import recent_decisions

    lines = recent_decisions(n)
    _console.print("\n".join(lines) if lines else "[dim]No decisions logged yet.[/dim]")


@app.command()
def sources() -> None:
    """List available source adapters."""
    from oriz_brain.sources import all_adapters

    table = Table(title="Source adapters", show_header=True)
    table.add_column("Name")
    table.add_column("Description")
    descriptions = {
        "i2i": "i2i Funding P2P — reads committed JSON from i2i-portfolio-data/raw/api/",
        "mmi": "Market Mood Index — oriz-mmi committed state or keyless Tickertape API",
    }
    for adapter in all_adapters():
        table.add_row(adapter.name, descriptions.get(adapter.name, ""))
    _console.print(table)


@app.command()
def predict(
    statement: str = typer.Argument(..., help="Prediction statement"),
    by: str = typer.Option(..., "--by", help="Resolve-by date YYYY-MM-DD"),
    confidence: int = typer.Option(70, "--confidence", min=0, max=100, help="Confidence 0-100"),
) -> None:
    """Record a new prediction."""
    from oriz_brain.predictions import Prediction, save_prediction

    made_on = datetime.now(UTC).date().isoformat()
    pred = Prediction(statement=statement, made_on=made_on, resolve_by=by, confidence=confidence)
    path = save_prediction(pred)
    _console.print(f"[green]Prediction saved:[/green] {pred.id} -> {path}")
    _console.print(f"  Statement : {pred.statement}")
    _console.print(f"  Resolve by: {pred.resolve_by}  Confidence: {pred.confidence}%")


@app.command()
def resolve(
    pred_id: str = typer.Argument(..., help="Prediction ID (e.g. 20260813-0001)"),
    outcome: str = typer.Option(..., "--outcome", help="true or false"),
) -> None:
    """Mark a prediction resolved with its actual outcome."""
    from oriz_brain.predictions import resolve_prediction

    outcome_bool = outcome.lower() in ("true", "1", "yes", "correct")
    pred = resolve_prediction(pred_id, outcome_bool)
    color = "green" if pred.outcome else "red"
    _console.print(
        f"[{color}]Resolved {pred.id}:[/{color}] "
        f"{'correct' if pred.outcome else 'wrong'}  (was {pred.confidence}% confident)"
    )


@app.command()
def score() -> None:
    """Calibration stats over all resolved predictions."""
    from oriz_brain.predictions import CalibrationStats, compute_calibration, load_all_predictions

    preds = load_all_predictions()
    stats = compute_calibration(preds)

    summary = Table(title="Prediction calibration", show_header=True)
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")

    def _row(label: str, value: str, style: str = "") -> None:
        summary.add_row(f"[{style}]{label}[/{style}]" if style else label, value)

    _row("Total predictions", str(stats.total))
    _row("Resolved", str(stats.resolved))
    _row("Correct", str(stats.correct))
    _row("Accuracy", f"{stats.accuracy_pct}%", "bold")
    _row("Avg confidence (correct)", f"{stats.avg_confidence_correct}%")
    _row("Avg confidence (wrong)", f"{stats.avg_confidence_wrong}%")
    overconf_style = "red" if stats.overconfidence > 10 else "green"
    _row("Overconfidence (wrong - correct conf)", f"{stats.overconfidence:+.1f}%", overconf_style)
    bias_style = "red" if abs(stats.optimism_bias) > 10 else "green"
    _row("Optimism bias (avg conf - accuracy)", f"{stats.optimism_bias:+.1f}%", bias_style)
    brier_style = "green" if stats.brier_score < 0.2 else "red"
    _row("Brier score (0=perfect, 1=worst)", f"{stats.brier_score:.4f}", brier_style)

    _console.print(summary)

    if stats.resolved == 0:
        _console.print("[dim]No resolved predictions yet. Use `brain resolve <id> --outcome true|false`.[/dim]")
