"""Data bus network: 1553-flavored command/response, quasi-static per tick
(spec: docs/design/systems/ata-42-data.md §3).

A 1 Mbps bus completes a status transaction in ~100 µs — four orders below
the 100 ms tick — so a poll and its reply land in the tick that schedules
them. The bus owns the *transaction ledger* (the medium's accounting); the
ship layer drives the BC's cyclic schedule and supplies the physical truth
(RT powered or not). Causality is the conservation law: a reply is counted
only for a poll issued in the same tick, and received never exceeds
transmitted.
"""

from __future__ import annotations

__all__ = ["FAIL_AFTER_POLLS", "DataBus", "RtHealth"]

#: Consecutive timeouts before the BC declares an RT FAILED (300 ms at tick).
FAIL_AFTER_POLLS = 3


class RtHealth:
    """The BC's view of one remote terminal: counters and declaration state."""

    __slots__ = ("address", "answered_last", "consec_timeouts", "error_total", "failed")

    def __init__(self, address: int) -> None:
        self.address = address
        self.answered_last = False  # answered the most recent poll
        self.consec_timeouts = 0
        self.error_total = 0  # monotone; the analyzer's evidence
        self.failed = False  # declared after FAIL_AFTER_POLLS consecutive timeouts


class DataBus:
    """One data bus instance: RT registry (insertion order = blueprint order)."""

    def __init__(self, bus_id: str) -> None:
        self.id = bus_id
        self._rts: dict[int, RtHealth] = {}
        self.tx_total = 0  # polls transmitted
        self.rx_total = 0  # replies received; invariant: rx_total <= tx_total

    def register_rt(self, address: int) -> None:
        if address in self._rts:
            raise ValueError(f"{self.id}: duplicate RT address {address}")
        self._rts[address] = RtHealth(address)

    def rt_addresses(self) -> list[int]:
        """Registered RT addresses in registration (blueprint) order."""
        return list(self._rts)

    def rt(self, address: int) -> RtHealth:
        return self._rts[address]

    def poll(self, address: int, answered: bool) -> None:
        """Record one status transaction this tick.

        ``answered`` is the physical truth the ship layer supplies (the RT was
        powered and its transceiver healthy). The ledger counts a reply only
        against a poll issued now — causality (spec §3).
        """
        rt = self._rts[address]
        self.tx_total += 1
        if answered:
            self.rx_total += 1
            rt.answered_last = True
            rt.consec_timeouts = 0
            rt.failed = False
        else:
            rt.answered_last = False
            rt.consec_timeouts += 1
            rt.error_total += 1
            if rt.consec_timeouts >= FAIL_AFTER_POLLS:
                rt.failed = True

    def health_frac(self) -> float:
        """Fraction of registered RTs not declared FAILED (1.0 when none)."""
        if not self._rts:
            return 1.0
        healthy = sum(1 for rt in self._rts.values() if not rt.failed)
        return healthy / len(self._rts)

    @property
    def degraded(self) -> bool:
        return any(rt.failed for rt in self._rts.values())
