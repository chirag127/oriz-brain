"""Tests for source adapters against synthetic fixture data."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


# ── i2i adapter ───────────────────────────────────────────────────────────────

def test_i2i_reads_fixture():
    from oriz_brain.sources.i2i import I2iAdapter

    adapter = I2iAdapter(data_dir=FIXTURES)
    obs = adapter.fetch()

    assert obs.source == "i2i"
    assert obs.data["total_invested"] == 604500
    assert obs.data["active_loans"] == 130
    assert obs.data["closed_loans"] == 21
    assert "p2p" in obs.tags
    assert "604500" in obs.summary or "604,500" in obs.summary


def test_i2i_missing_files_returns_empty_gracefully():
    from oriz_brain.sources.i2i import I2iAdapter

    adapter = I2iAdapter(data_dir=Path("/nonexistent/path"))
    obs = adapter.fetch()

    # Should not raise; returns zeros
    assert obs.source == "i2i"
    assert obs.data["total_invested"] == 0


# ── MMI adapter ───────────────────────────────────────────────────────────────

def test_mmi_reads_fixture(tmp_path):
    from oriz_brain.sources.mmi import MmiAdapter

    # put fixture in a path the adapter will find
    import shutil
    shutil.copy(FIXTURES / "mmi_now.json", tmp_path / "latest.json")

    adapter = MmiAdapter(mmi_repo=tmp_path.parent)
    # override: monkeypatch _from_committed to read tmp_path/latest.json directly
    import json

    def _committed(self=adapter):
        raw = json.loads((tmp_path / "latest.json").read_text())
        if "data" in raw:
            return float(raw["data"].get("indicator", 0))
        return float(raw.get("indicator", 0))

    adapter._from_committed = _committed  # type: ignore[method-assign]
    obs = adapter.fetch()

    assert obs.source == "mmi"
    assert abs(obs.data["mmi"] - 73.72) < 0.1
    assert obs.data["zone"] == "Greed"
    assert "Greed" in obs.summary


def test_mmi_zone_extreme_fear():
    from oriz_brain.sources.mmi import _zone

    assert _zone(10.0) == "Extreme Fear"


def test_mmi_zone_extreme_greed():
    from oriz_brain.sources.mmi import _zone

    assert _zone(90.0) == "Extreme Greed"


def test_mmi_unavailable_on_no_data(monkeypatch):
    from oriz_brain.sources.mmi import MmiAdapter

    adapter = MmiAdapter(mmi_repo=Path("/nonexistent"))
    monkeypatch.setattr(adapter, "_from_api", lambda: None)

    obs = adapter.fetch()
    assert obs.source == "mmi"
    assert "unavailable" in obs.summary


# ── Decision log ──────────────────────────────────────────────────────────────

def test_decision_log_roundtrip(tmp_path, monkeypatch):
    import oriz_brain.decision_log as dl_mod
    monkeypatch.setattr(dl_mod, "VAULT", tmp_path / "vault")

    from oriz_brain.decision_log import Decision, log_decision, recent_decisions

    d = Decision(
        observation="P2P: 604500 invested",
        reasoning="Normal range, no action needed",
        verdict="skip",
        action="none",
        source="i2i",
    )
    path = log_decision(d)
    assert path.exists()

    lines = recent_decisions(50)
    text = "\n".join(lines)
    assert "P2P: 604500 invested" in text
    assert "skip" in text


def test_decision_log_matters_entry(tmp_path, monkeypatch):
    import oriz_brain.decision_log as dl_mod
    monkeypatch.setattr(dl_mod, "VAULT", tmp_path / "vault")

    from oriz_brain.decision_log import Decision, log_decision

    d = Decision(
        observation="MMI: 92.0 (Extreme Greed)",
        reasoning="Extreme greed — rebalance risk",
        verdict="matters",
        action="Review portfolio allocation",
        source="mmi",
    )
    path = log_decision(d)
    content = path.read_text(encoding="utf-8")
    assert "matters" in content
    assert "Review portfolio allocation" in content


# ── Pipeline ──────────────────────────────────────────────────────────────────

def test_pipeline_run_cycle_smoke(monkeypatch, tmp_path):
    """Smoke-test full cycle with synthetic adapters and stub LLM."""
    import oriz_brain.decision_log as dl_mod
    monkeypatch.setattr(dl_mod, "VAULT", tmp_path / "vault")

    from oriz_brain.sources.base import Observation
    from oriz_brain.llm import LLMClient
    from oriz_brain.pipeline import run_cycle

    class FakeAdapter:
        name = "fake"
        def fetch(self) -> Observation:
            return Observation(source="fake", summary="Test obs", data={"x": 1}, tags=["test"])

    class StubLLM(LLMClient):
        def complete(self, system: str, user: str) -> str:
            return '{"verdict": "skip", "reasoning": "test", "action": "none"}'

    class SilentNotifier:
        sent: list = []
        def send(self, d):
            self.sent.append(d)

    notifier = SilentNotifier()
    decisions = run_cycle([FakeAdapter()], llm=StubLLM(), notifier=notifier)

    assert len(decisions) == 1
    assert decisions[0].verdict == "skip"
    assert decisions[0].source == "fake"


def test_pipeline_notifies_on_matters(monkeypatch, tmp_path):
    import oriz_brain.decision_log as dl_mod
    monkeypatch.setattr(dl_mod, "VAULT", tmp_path / "vault")

    from oriz_brain.sources.base import Observation
    from oriz_brain.llm import LLMClient
    from oriz_brain.pipeline import run_cycle

    class FakeAdapter:
        name = "mmi"
        def fetch(self) -> Observation:
            return Observation(source="mmi", summary="MMI: 91 (Extreme Greed)", data={"mmi": 91}, tags=[])

    class StubLLM(LLMClient):
        def complete(self, system: str, user: str) -> str:
            return '{"verdict": "matters", "reasoning": "extreme greed", "action": "reduce equity"}'

    notified = []

    class CapturingNotifier:
        def send(self, d):
            notified.append(d)

    run_cycle([FakeAdapter()], llm=StubLLM(), notifier=CapturingNotifier())
    assert len(notified) == 1
    assert notified[0].action == "reduce equity"


def test_pipeline_handles_adapter_exception(monkeypatch, tmp_path):
    import oriz_brain.decision_log as dl_mod
    monkeypatch.setattr(dl_mod, "VAULT", tmp_path / "vault")

    from oriz_brain.llm import LLMClient
    from oriz_brain.pipeline import run_cycle

    class BrokenAdapter:
        name = "broken"
        def fetch(self):
            raise RuntimeError("network down")

    class StubLLM(LLMClient):
        def complete(self, system: str, user: str) -> str:
            return '{"verdict": "skip", "reasoning": "error", "action": "none"}'

    decisions = run_cycle([BrokenAdapter()], llm=StubLLM())
    assert len(decisions) == 1
    assert "ERROR" in decisions[0].observation
