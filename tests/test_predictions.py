"""Tests for prediction tracker."""

from __future__ import annotations

from pathlib import Path

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_pred_dir(tmp_path: Path, monkeypatch) -> Path:
    pred_dir = tmp_path / "predictions"
    import oriz_brain.predictions as pm
    monkeypatch.setattr(pm, "PRED_DIR", pred_dir)
    return pred_dir


# ── save / load ───────────────────────────────────────────────────────────────

def test_save_and_load(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, load_prediction, save_prediction

    pred = Prediction(
        statement="Nifty will cross 26000 by Sep 2026",
        made_on="2026-08-13",
        resolve_by="2026-09-30",
        confidence=75,
    )
    save_prediction(pred)
    loaded = load_prediction(pred.id)

    assert loaded.statement == pred.statement
    assert loaded.confidence == 75
    assert loaded.status == "open"
    assert loaded.outcome is None


def test_id_format(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, save_prediction

    pred = Prediction(
        statement="Test",
        made_on="2026-08-13",
        resolve_by="2026-09-01",
        confidence=50,
    )
    save_prediction(pred)
    assert pred.id.startswith("20260813-")
    assert pred.id.endswith("0001")


def test_sequential_ids(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, save_prediction

    p1 = Prediction(statement="A", made_on="2026-08-13", resolve_by="2026-09-01", confidence=60)
    p2 = Prediction(statement="B", made_on="2026-08-13", resolve_by="2026-09-01", confidence=70)
    save_prediction(p1)
    save_prediction(p2)
    assert p1.id == "20260813-0001"
    assert p2.id == "20260813-0002"


# ── resolve ───────────────────────────────────────────────────────────────────

def test_resolve_correct(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, resolve_prediction, save_prediction

    pred = Prediction(statement="S", made_on="2026-08-13", resolve_by="2026-09-01", confidence=80)
    save_prediction(pred)
    resolved = resolve_prediction(pred.id, outcome=True)

    assert resolved.status == "resolved"
    assert resolved.outcome is True
    assert resolved.resolved_on != ""


def test_resolve_wrong(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, resolve_prediction, save_prediction

    pred = Prediction(statement="S", made_on="2026-08-13", resolve_by="2026-09-01", confidence=80)
    save_prediction(pred)
    resolved = resolve_prediction(pred.id, outcome=False)

    assert resolved.outcome is False


def test_resolve_missing_raises(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import resolve_prediction

    with pytest.raises(FileNotFoundError):
        resolve_prediction("20260101-9999", outcome=True)


# ── calibration ───────────────────────────────────────────────────────────────

def _resolved(statement: str, confidence: int, outcome: bool):
    from oriz_brain.predictions import Prediction
    return Prediction(
        statement=statement,
        made_on="2026-08-01",
        resolve_by="2026-09-01",
        confidence=confidence,
        status="resolved",
        outcome=outcome,
        resolved_on="2026-09-01",
        id=f"20260801-{hash(statement) % 9999:04d}",
    )


def test_calibration_perfect():
    from oriz_brain.predictions import compute_calibration

    preds = [_resolved("A", 90, True), _resolved("B", 80, True)]
    stats = compute_calibration(preds)

    assert stats.accuracy_pct == 100.0
    assert stats.brier_score < 0.1


def test_calibration_all_wrong():
    from oriz_brain.predictions import compute_calibration

    preds = [_resolved("A", 80, False), _resolved("B", 90, False)]
    stats = compute_calibration(preds)

    assert stats.accuracy_pct == 0.0
    assert stats.correct == 0
    assert stats.brier_score > 0.5


def test_calibration_mixed():
    from oriz_brain.predictions import compute_calibration

    preds = [
        _resolved("A", 90, True),
        _resolved("B", 70, True),
        _resolved("C", 80, False),
        _resolved("D", 60, False),
    ]
    stats = compute_calibration(preds)

    assert stats.resolved == 4
    assert stats.correct == 2
    assert stats.accuracy_pct == 50.0
    # overconfidence: avg_conf_wrong(70) - avg_conf_correct(80) = -10 (underconfident on wrong)
    assert stats.avg_confidence_correct == 80.0
    assert stats.avg_confidence_wrong == 70.0
    assert stats.overconfidence == -10.0
    # brier: ((0.9-1)^2 + (0.7-1)^2 + (0.8-0)^2 + (0.6-0)^2) / 4
    expected_brier = ((0.01 + 0.09 + 0.64 + 0.36) / 4)
    assert abs(stats.brier_score - round(expected_brier, 4)) < 0.001


def test_calibration_no_predictions():
    from oriz_brain.predictions import compute_calibration

    stats = compute_calibration([])
    assert stats.total == 0
    assert stats.brier_score == 0.0


def test_calibration_open_only():
    from oriz_brain.predictions import Prediction, compute_calibration

    open_pred = Prediction(
        statement="Still open", made_on="2026-08-01", resolve_by="2026-12-01",
        confidence=70, status="open", id="20260801-0001"
    )
    stats = compute_calibration([open_pred])
    assert stats.total == 1
    assert stats.resolved == 0


def test_load_all_predictions(tmp_path, monkeypatch):
    _make_pred_dir(tmp_path, monkeypatch)
    from oriz_brain.predictions import Prediction, load_all_predictions, save_prediction

    for i, stmt in enumerate(["Alpha", "Beta", "Gamma"]):
        p = Prediction(statement=stmt, made_on="2026-08-13", resolve_by="2026-10-01", confidence=65+i)
        save_prediction(p)

    all_preds = load_all_predictions()
    assert len(all_preds) == 3
    statements = {p.statement for p in all_preds}
    assert {"Alpha", "Beta", "Gamma"} == statements
