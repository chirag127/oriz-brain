"""Decision log — append-only markdown files in vault/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

VAULT = Path(__file__).parent.parent / "vault"
_DATE_PAT = re.compile(r"^## \d{4}-\d{2}-\d{2}")


@dataclass
class Decision:
    observation: str
    reasoning: str
    verdict: str  # "matters" | "skip"
    action: str
    source: str = ""
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = datetime.now(UTC).isoformat(timespec="seconds")

    def to_markdown(self) -> str:
        return (
            f"### {self.ts}  [{self.source}]\n"
            f"**Observation:** {self.observation}\n\n"
            f"**Reasoning:** {self.reasoning}\n\n"
            f"**Verdict:** {self.verdict}\n\n"
            f"**Action:** {self.action}\n\n"
            "---\n"
        )


def log_decision(decision: Decision) -> Path:
    VAULT.mkdir(parents=True, exist_ok=True)
    date_str = decision.ts[:10]
    path = VAULT / f"{date_str}.md"
    header = f"## {date_str}\n\n"
    if not path.exists():
        path.write_text(header, encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(decision.to_markdown())
    return path


def recent_decisions(n: int = 20) -> list[str]:
    VAULT.mkdir(parents=True, exist_ok=True)
    files = sorted(VAULT.glob("*.md"), reverse=True)
    lines: list[str] = []
    for f in files:
        lines.extend(f.read_text(encoding="utf-8").splitlines())
        if len(lines) >= n * 10:
            break
    return lines[:n * 10]
