"""Base protocol for all source adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Observation:
    source: str
    summary: str                      # human-readable 1-line
    data: dict = field(default_factory=dict)  # raw structured payload
    tags: list[str] = field(default_factory=list)


class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> Observation:
        """Fetch latest observation. Raise on hard failure; return degraded on soft failure."""
        ...
