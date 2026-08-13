"""MMI market-sentiment adapter.

Priority:
1. oriz-mmi committed state (data/*.json) if present.
2. Keyless Tickertape endpoint api.tickertape.in/mmi/now.
3. Degrade to "unavailable" observation (never raise).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import structlog

from oriz_brain.sources.base import Observation

log = structlog.get_logger(__name__)

_DEFAULT_MMI_REPO = Path(__file__).parent.parent.parent.parent / "oriz-mmi"
_TICKERTAPE_URL = "https://api.tickertape.in/mmi/now"
_TIMEOUT = 10.0

# Zone thresholds (matches oriz-mmi logic)
_ZONES = [(25, "Extreme Fear"), (45, "Fear"), (55, "Neutral"), (75, "Greed"), (100, "Extreme Greed")]


def _zone(value: float) -> str:
    for threshold, label in _ZONES:
        if value <= threshold:
            return label
    return "Extreme Greed"


class MmiAdapter:
    name = "mmi"

    def __init__(self, mmi_repo: Path | None = None) -> None:
        env_override = os.environ.get("MMI_REPO_DIR")
        self._repo = Path(env_override) if env_override else (mmi_repo or _DEFAULT_MMI_REPO)

    def fetch(self) -> Observation:
        value = self._from_committed() or self._from_api()
        if value is None:
            return Observation(
                source="mmi",
                summary="MMI: unavailable",
                data={},
                tags=["market", "sentiment"],
            )

        zone = _zone(value)
        summary = f"Market Mood Index: {value:.1f} ({zone})"
        return Observation(
            source="mmi",
            summary=summary,
            data={"mmi": value, "zone": zone},
            tags=["market", "sentiment", zone.lower().replace(" ", "_")],
        )

    def _from_committed(self) -> float | None:
        # oriz-mmi stores latest state in data/ dir
        for candidate in [
            self._repo / "data" / "latest.json",
            self._repo / "tests" / "fixtures" / "mmi_now.json",
        ]:
            if candidate.exists():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                    # support both {indicator: x} and {data: {indicator: x}} shapes
                    if "data" in raw:
                        return float(raw["data"].get("indicator") or raw["data"].get("currentValue", 0))
                    return float(raw.get("indicator", raw.get("currentValue", 0)))
                except Exception:  # noqa: BLE001
                    pass
        return None

    def _from_api(self) -> float | None:
        try:
            resp = httpx.get(_TICKERTAPE_URL, timeout=_TIMEOUT, headers={"User-Agent": "oriz-brain/0.1"})
            resp.raise_for_status()
            body = resp.json()
            # shape: {success, data: {indicator, ...}}
            return float(body["data"]["indicator"])
        except Exception as exc:  # noqa: BLE001
            log.warning("mmi.api_failed", error=str(exc)[:80])
            return None
