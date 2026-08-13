"""Sources package — pluggable ingest adapters."""

from __future__ import annotations

from oriz_brain.sources.base import Observation, SourceAdapter
from oriz_brain.sources.i2i import I2iAdapter
from oriz_brain.sources.mmi import MmiAdapter

__all__ = ["Observation", "SourceAdapter", "I2iAdapter", "MmiAdapter", "all_adapters"]


def all_adapters() -> list[SourceAdapter]:
    return [I2iAdapter(), MmiAdapter()]
