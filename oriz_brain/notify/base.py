"""Notifier protocol."""

from __future__ import annotations

from typing import Protocol

from oriz_brain.decision_log import Decision


class Notifier(Protocol):
    def send(self, decision: Decision) -> None:
        """Send a notification for a decision that matters."""
        ...
