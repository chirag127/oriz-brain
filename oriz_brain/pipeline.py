"""Brain pipeline: ingest -> reason -> decide -> log -> notify."""

from __future__ import annotations

import structlog

from oriz_brain.decision_log import Decision, log_decision
from oriz_brain.llm import LLMClient
from oriz_brain.notify.base import Notifier
from oriz_brain.notify.console import ConsoleNotifier
from oriz_brain.sources.base import Observation, SourceAdapter

log = structlog.get_logger(__name__)

_REASON_SYSTEM = """\
You are ChiragOS, a personal ambient-brain for Chirag (software engineer, Indian market investor).
Given a data observation, decide if it MATTERS enough to act on right now.

Respond ONLY with valid JSON (no markdown):
{
  "verdict": "matters" | "skip",
  "reasoning": "<one sentence>",
  "action": "<concrete next step, or 'none'>"
}

Criteria for 'matters':
- P2P/portfolio: active_loans < 100 OR avg_rate < 9 OR large unexpected change
- MMI: zone is 'Extreme Fear' OR 'Extreme Greed' (act on extremes)
- Any source returning error/unavailable data
When in doubt, 'skip'.
"""


def reason(obs: Observation, llm: LLMClient) -> Decision:
    prompt = f"Source: {obs.source}\nSummary: {obs.summary}\nData: {obs.data}"
    raw = llm.complete(_REASON_SYSTEM, prompt)

    # parse JSON; degrade gracefully on failure
    import json  # noqa: PLC0415
    import re    # noqa: PLC0415
    raw_stripped = re.sub(r"^```[a-z]*\n?", "", raw)
    raw_stripped = re.sub(r"\n?```$", "", raw_stripped.strip())
    try:
        parsed = json.loads(raw_stripped)
        verdict = parsed.get("verdict", "skip")
        reasoning = parsed.get("reasoning", raw[:200])
        action = parsed.get("action", "none")
    except (json.JSONDecodeError, AttributeError):
        verdict = "skip"
        reasoning = raw[:200]
        action = "none"

    return Decision(
        observation=obs.summary,
        reasoning=reasoning,
        verdict=verdict,
        action=action,
        source=obs.source,
    )


def run_cycle(
    adapters: list[SourceAdapter],
    llm: LLMClient | None = None,
    notifier: Notifier | None = None,
) -> list[Decision]:
    llm = llm or LLMClient()
    notifier = notifier or ConsoleNotifier()
    decisions: list[Decision] = []

    for adapter in adapters:
        try:
            obs = adapter.fetch()
            log.info("ingest.ok", source=adapter.name, summary=obs.summary[:80])
        except Exception as exc:  # noqa: BLE001
            log.warning("ingest.failed", source=adapter.name, error=str(exc)[:80])
            obs = Observation(source=adapter.name, summary=f"ERROR: {exc}", data={}, tags=["error"])

        decision = reason(obs, llm)
        log_decision(decision)
        decisions.append(decision)

        if decision.verdict == "matters":
            notifier.send(decision)

    return decisions
