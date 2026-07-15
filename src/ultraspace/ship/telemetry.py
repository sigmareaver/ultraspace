"""Telemetry: the instrument-mediated read surface (No God View boundary).

Presentation and interaction layers read *only* this store. Values arrive from
transducer devices in the INSTRUMENTS phase, noise included; provenance and
age travel with every item.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TelemetryItem", "TelemetryStore"]


@dataclass(frozen=True, slots=True)
class TelemetryItem:
    telemetry_id: str
    value: float
    unit: str  # "V" | "A" | "frac" at M1
    source: str  # e.g. "mt.bus.e.v (24-150-001)"
    tick: int  # when sampled


class TelemetryStore:
    """Latest-value store keyed by telemetry id (transducer device id)."""

    def __init__(self) -> None:
        self._items: dict[str, TelemetryItem] = {}

    def publish(self, item: TelemetryItem) -> None:
        self._items[item.telemetry_id] = item

    def read(self, telemetry_id: str) -> TelemetryItem | None:
        """None means no report yet (cold instruments, not an error)."""
        return self._items.get(telemetry_id)

    def ids(self) -> list[str]:
        return sorted(self._items)
