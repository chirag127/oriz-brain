"""Prediction tracker — append-only markdown in vault/predictions/.

Each prediction is a markdown file named <id>.md.
ID = YYYYMMDD-NNNN (date + 4-digit sequence within that day).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, date
from pathlib import Path
from typing import Literal

PRED_DIR = Path(__file__).parent.parent / "vault" / "predictions"

Status = Literal["open", "resolved"]


@dataclass
class Prediction:
    statement: str
    made_on: str        # ISO date string YYYY-MM-DD
    resolve_by: str     # ISO date string YYYY-MM-DD
    confidence: int     # 0-100
    status: Status = "open"
    outcome: bool | None = None   # True=correct, False=wrong, None=open
    resolved_on: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        # ID assigned at save time if not provided; leaving blank is fine until save_prediction sets it
        pass

    def to_markdown(self) -> str:
        lines = [
            f"# {self.id}",
            "",
            f"**Statement:** {self.statement}",
            f"**Made on:** {self.made_on}",
            f"**Resolve by:** {self.resolve_by}",
            f"**Confidence:** {self.confidence}%",
            f"**Status:** {self.status}",
        ]
        if self.outcome is not None:
            lines.append(f"**Outcome:** {'correct' if self.outcome else 'wrong'}")
        if self.resolved_on:
            lines.append(f"**Resolved on:** {self.resolved_on}")
        lines.append("")
        return "\n".join(lines)


def _next_id(date_str: str) -> str:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    date_prefix = date_str.replace("-", "")
    existing = sorted(PRED_DIR.glob(f"{date_prefix}-*.md"))
    seq = len(existing) + 1
    return f"{date_prefix}-{seq:04d}"


def save_prediction(pred: Prediction) -> Path:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    if not pred.id:
        pred.id = _next_id(pred.made_on)
    path = PRED_DIR / f"{pred.id}.md"
    path.write_text(pred.to_markdown(), encoding="utf-8")
    return path


def load_prediction(pred_id: str) -> Prediction:
    path = PRED_DIR / f"{pred_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prediction {pred_id} not found")
    return _parse(path.read_text(encoding="utf-8"), pred_id)


def load_all_predictions() -> list[Prediction]:
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    preds = []
    for p in sorted(PRED_DIR.glob("*.md")):
        try:
            preds.append(_parse(p.read_text(encoding="utf-8"), p.stem))
        except Exception:  # noqa: BLE001
            pass
    return preds


def resolve_prediction(pred_id: str, outcome: bool) -> Prediction:
    pred = load_prediction(pred_id)
    pred.status = "resolved"
    pred.outcome = outcome
    pred.resolved_on = datetime.now(UTC).date().isoformat()
    save_prediction(pred)
    return pred


def _get(text: str, key: str) -> str:
    m = re.search(rf"\*\*{key}:\*\*\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _parse(text: str, pred_id: str) -> Prediction:
    statement = _get(text, "Statement")
    made_on = _get(text, "Made on")
    resolve_by = _get(text, "Resolve by")
    conf_str = _get(text, "Confidence").rstrip("%")
    confidence = int(conf_str) if conf_str.isdigit() else 50
    status_str = _get(text, "Status")
    status: Status = "resolved" if status_str == "resolved" else "open"
    outcome_str = _get(text, "Outcome")
    outcome: bool | None = None
    if outcome_str == "correct":
        outcome = True
    elif outcome_str == "wrong":
        outcome = False
    resolved_on = _get(text, "Resolved on")
    return Prediction(
        id=pred_id,
        statement=statement,
        made_on=made_on,
        resolve_by=resolve_by,
        confidence=confidence,
        status=status,
        outcome=outcome,
        resolved_on=resolved_on,
    )


# ── Calibration / scoring ─────────────────────────────────────────────────────

@dataclass
class CalibrationStats:
    total: int
    resolved: int
    correct: int
    accuracy_pct: float
    avg_confidence_correct: float
    avg_confidence_wrong: float
    overconfidence: float   # avg_conf_wrong - avg_conf_correct (positive = overconfident on wrong)
    brier_score: float      # lower is better; 0=perfect, 1=worst
    optimism_bias: float    # avg_confidence - accuracy (positive = overconfident overall)


def compute_calibration(predictions: list[Prediction]) -> CalibrationStats:
    resolved = [p for p in predictions if p.status == "resolved" and p.outcome is not None]
    correct = [p for p in resolved if p.outcome is True]
    wrong = [p for p in resolved if p.outcome is False]

    accuracy = (len(correct) / len(resolved) * 100) if resolved else 0.0
    avg_conf_correct = (sum(p.confidence for p in correct) / len(correct)) if correct else 0.0
    avg_conf_wrong = (sum(p.confidence for p in wrong) / len(wrong)) if wrong else 0.0
    overconfidence = avg_conf_wrong - avg_conf_correct

    # Brier score: mean((confidence/100 - outcome)^2)
    brier = (
        sum(((p.confidence / 100) - (1.0 if p.outcome else 0.0)) ** 2 for p in resolved)
        / len(resolved)
        if resolved
        else 0.0
    )

    avg_conf_all = (sum(p.confidence for p in resolved) / len(resolved)) if resolved else 0.0
    optimism_bias = avg_conf_all - accuracy

    return CalibrationStats(
        total=len(predictions),
        resolved=len(resolved),
        correct=len(correct),
        accuracy_pct=round(accuracy, 1),
        avg_confidence_correct=round(avg_conf_correct, 1),
        avg_confidence_wrong=round(avg_conf_wrong, 1),
        overconfidence=round(overconfidence, 1),
        brier_score=round(brier, 4),
        optimism_bias=round(optimism_bias, 1),
    )
