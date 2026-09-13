"""Telemetry: the instrument-mediated read surface (No God View boundary).

Presentation and interaction layers read *only* this store. Values arrive from
transducer devices in the INSTRUMENTS phase, noise included; provenance and
age travel with every item.

Age is a reading, not an implementation detail (ata-42-data.md §4). A carried
transducer publishes only in ticks where its terminal answered the bus
controller, so the store keeps the last item that got through and that item
ages. A **stale** item is still readable and still the last honest reading —
it is simply no longer a statement about now, and every consumer is required
to say so rather than hide it.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["STALE_AFTER_TICKS", "TelemetryItem", "TelemetryStore"]

#: Ticks an item may age before it reads stale (10 ticks = 1.0 s at DT_S).
#: One constant for the sim, the panel, and the printed line — a reading that
#: the panel dims must be the reading a monitor stops trusting.
STALE_AFTER_TICKS = 10


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

    def fresh(self, telemetry_id: str, tick: int) -> TelemetryItem | None:
        """The item only while it still describes *now*; None once it ages out.

        Consumers that assert a present-tense fact (a caution lamp) read this;
        consumers that display a value with its age read ``read``. Missing and
        stale deliberately collapse to the same answer here — no sensor and a
        sensor that stopped reporting are the same amount of knowledge.
        """
        item = self._items.get(telemetry_id)
        if item is None or tick - item.tick > STALE_AFTER_TICKS:
            return None
        return item

    def ids(self) -> list[str]:
        return sorted(self._items)
