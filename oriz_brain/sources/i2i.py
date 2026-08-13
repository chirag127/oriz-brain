"""i2i Funding / P2P adapter — reads committed JSON from i2i-portfolio-data repo."""

from __future__ import annotations

import json
import os
from pathlib import Path

from oriz_brain.sources.base import Observation

# Default: sibling submodule in the same repos/own/ tree; override via env.
_DEFAULT_DATA = Path(__file__).parent.parent.parent.parent / "i2i-portfolio-data" / "raw" / "api"


class I2iAdapter:
    name = "i2i"

    def __init__(self, data_dir: Path | None = None) -> None:
        env_override = os.environ.get("I2I_DATA_DIR")
        self._dir = Path(env_override) if env_override else (data_dir or _DEFAULT_DATA)

    def fetch(self) -> Observation:
        escrow_path = self._dir / "escrow-overview.json"
        emi_path = self._dir / "emi-status-overview.json"

        escrow = _load(escrow_path)
        emi = _load(emi_path)

        total_invested = emi.get("body", {}).get("totalInvestment", 0)
        active_loans = emi.get("body", {}).get("activeLoansCount", 0)
        closed_loans = emi.get("body", {}).get("closedLoansCount", 0)
        avg_rate = emi.get("body", {}).get("avgIntRate", 0)

        escrow_body = escrow.get("body", {})
        total_credit = escrow_body.get("totalCredit", 0)
        amount_invested = escrow_body.get("totalAmountInvested", 0)

        summary = (
            f"i2i P2P: Rs.{total_invested:,.0f} invested, "
            f"{active_loans} active / {closed_loans} closed loans, "
            f"avg rate {avg_rate}%, escrow credit Rs.{total_credit:,.0f}"
        )

        return Observation(
            source="i2i",
            summary=summary,
            data={
                "total_invested": total_invested,
                "active_loans": active_loans,
                "closed_loans": closed_loans,
                "avg_rate": avg_rate,
                "escrow_credit": total_credit,
                "escrow_amount_invested": amount_invested,
            },
            tags=["p2p", "finance", "portfolio"],
        )


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
